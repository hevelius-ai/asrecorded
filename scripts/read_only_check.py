"""Read-only check: every call this package makes to GitHub is a read (S4, design §2, decision A4).

Reads each Python file of a package folder, never runs it. It is an allow-list for code written plainly: a later
change that adds another way out in the usual forms (another import, another process call, another list of words for
gh, a write flag, a call outside github.py) is a finding and must be looked at in review.
- Imports: only the modules in ALLOWED (and the package itself). Anything else, a network module or any other, is
  a finding; so is an import of a name given at run time (`exec`, `eval`, `compile`, `__import__`, `sys.modules`).
- `os`: only `os.environ` and `os.replace`.
- Processes: only `github.py` may import `subprocess`, as `import subprocess`, and use it in one way only:
  `subprocess.run(command, ...)`, where `command` is set once, in the same function, to
  `[*program(), "api", "--method", "GET", "--paginate", "--slurp", path]` and never changed. Any other use of
  `subprocess`, in any file, is a finding.

Limit (stated, decision S4-RO, the owner's choice PR14-2 B): it reads code as written and does not follow where a
name leads, so code written on purpose to hide a call passes it: a module reached through another module or a new
name (`shutil.os.system`, `github.subprocess.run`, `import os as o`, `x = os`), `getattr`, `vars`, `__builtins__`,
`from sys import modules`, `global`, or an edit to `program()`. The second net is at run time: every check of the
tool runs gh through a stand-in that answers read requests only, and `github.pages` refuses a path that starts with
"-". tests/unit/test_read_only_check.py holds these forms as known limits.

Use: python scripts/read_only_check.py <package folder>
Exit codes: 0 every call is a read; 1 something else was found; 2 the check could not run.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Sequence
from pathlib import Path

ALLOWED = {
    "__future__",
    "collections",
    "contextlib",
    "csv",
    "dataclasses",
    "datetime",
    "hashlib",
    "heapq",
    "io",
    "json",
    "os",
    "pathlib",
    "re",
    "shutil",
    "subprocess",
    "sys",
    "tomllib",
    "typing",
}
OS_ALLOWED = {"environ", "replace"}
RUN_TIME = {"exec", "eval", "compile", "__import__"}
READ = ["api", "--method", "GET", "--paginate", "--slurp"]
KEYWORDS = {"capture_output", "text", "encoding", "errors", "check"}
HOME = "github.py"


def _parents(tree: ast.AST) -> dict[int, ast.AST]:
    return {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def _function(node: ast.AST, parents: dict[int, ast.AST]) -> ast.AST | None:
    current = parents.get(id(node))
    while current is not None and not isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
        current = parents.get(id(current))
    return current


def _the_read(command: ast.expr) -> bool:
    """`[*program(), "api", "--method", "GET", "--paginate", "--slurp", path]`, exactly."""
    if not isinstance(command, ast.List) or len(command.elts) != len(READ) + 2:
        return False
    first, *words, last = command.elts
    starts = (
        isinstance(first, ast.Starred)
        and isinstance(first.value, ast.Call)
        and isinstance(first.value.func, ast.Name)
        and first.value.func.id == "program"
        and not first.value.args
    )
    plain = [w.value if isinstance(w, ast.Constant) else None for w in words]
    return starts and plain == READ and isinstance(last, ast.Name)


def _run_is_the_read(call: ast.Call, scope: ast.AST | None) -> bool:
    """`subprocess.run(command, ...)` with `command` set once, to the read, and used nowhere else in the function."""
    unknown_keyword = any(k.arg not in KEYWORDS for k in call.keywords)
    if scope is None or unknown_keyword or len(call.args) != 1 or not isinstance(call.args[0], ast.Name):
        return False
    name = call.args[0].id
    uses = [n for n in ast.walk(scope) if isinstance(n, ast.Name) and n.id == name]
    sets = [
        n
        for n in ast.walk(scope)
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
        if n.targets[0].id == name
    ]
    return len(sets) == 1 and len(uses) == 2 and _the_read(sets[0].value)  # set once, read once: nothing else


def _file(path: Path, name: str) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return [f"{name}:1: cannot be read as Python, so it cannot be checked"]
    parents = _parents(tree)
    found: list[str] = []

    def add(node: ast.AST, why: str) -> None:
        found.append(f"{name}:{getattr(node, 'lineno', 1)}: {why}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in ALLOWED and top != "asrecorded":
                    add(node, f"imports {alias.name}, which this check does not allow")
                elif top == "subprocess" and (name != HOME or alias.name != "subprocess" or alias.asname):
                    add(node, "imports subprocess: only github.py may, as `import subprocess`")
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if node.level == 0 and top not in ALLOWED and top != "asrecorded":
                add(node, f"imports from {node.module}, which this check does not allow")
            elif top == "subprocess":
                add(node, "imports from subprocess: only github.py may use it, as `import subprocess`")
            elif top == "os" and any(a.name not in OS_ALLOWED for a in node.names):
                add(node, f"imports from os something other than {', '.join(sorted(OS_ALLOWED))}")
        elif isinstance(node, ast.Name) and node.id in RUN_TIME:
            add(node, f"uses {node.id}, so what it runs cannot be checked")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "os" and node.attr not in OS_ALLOWED:
                add(node, f"uses os.{node.attr}: only os.environ and os.replace are allowed")
            elif node.value.id == "sys" and node.attr == "modules":
                add(node, "uses sys.modules, so what it runs cannot be checked")
            elif node.value.id == "subprocess":
                call = parents.get(id(node))
                if not (
                    name == HOME
                    and node.attr == "run"
                    and isinstance(call, ast.Call)
                    and call.func is node
                    and _run_is_the_read(call, _function(call, parents))
                ):
                    add(node, f"uses subprocess.{node.attr} other than as the one read, gh api --method GET")
        if isinstance(node, ast.Name) and node.id == "subprocess":
            holder = parents.get(id(node))
            if not (isinstance(holder, ast.Attribute) and holder.value is node):
                add(node, "uses subprocess other than as subprocess.run(...)")
    return sorted(set(found), key=lambda line: (int(line.split(":")[1]), line))


def check(folder: Path) -> tuple[list[str], int]:
    """What in the package is not a read of GitHub, and how many files were read."""
    files = sorted(p for p in folder.rglob("*.py") if "__pycache__" not in p.parts)
    found = [line for path in files for line in _file(path, path.relative_to(folder).as_posix())]
    return found, len(files)


def main(argv: Sequence[str]) -> int:
    if len(argv) != 1:
        print("Use: python scripts/read_only_check.py <package folder>", file=sys.stderr)
        return 2
    folder = Path(argv[0])
    if not folder.is_dir():
        print(f"{folder} is not a folder.", file=sys.stderr)
        return 2
    found, files = check(folder)
    if not found:
        print(f"Every call to GitHub in {folder} is gh api --method GET ({files} files read).")
        return 0
    for line in found:
        print(line)
    if len(found) == 1:
        print("1 call or import that is not a read of GitHub. Fix it before merging.")
    else:
        print(f"{len(found)} calls or imports that are not reads of GitHub. Fix them before merging.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
