"""Read-only check: every call this package makes to GitHub is a read (S4, design §2, decision A4).

Reads each Python file of a package folder, never runs it, and reports:
- any import of a network module (the package talks to GitHub only through the `gh` command);
- any import of a module by a name given at run time (it cannot be checked);
- any process call (subprocess, os.system and the like) whose command is not a list holding "api", "--method",
  "GET" in that order, or that also holds a way to write ("-X", another "--method", "-f", "-F", "--field",
  "--raw-field", "--input").

Use: python scripts/read_only_check.py <package folder>
Exit codes: 0 every call is a read; 1 something else was found; 2 the check could not run.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Sequence
from pathlib import Path

NETWORK = {
    "aiohttp",
    "ftplib",
    "http",
    "httpx",
    "imaplib",
    "nntplib",
    "poplib",
    "requests",
    "smtplib",
    "socket",
    "ssl",
    "telnetlib",
    "urllib",
    "urllib3",
    "websocket",
    "websockets",
    "xmlrpc",
}
PROCESS: tuple[str, ...] = ("subprocess.", "os.system", "os.popen", "os.exec", "os.spawn", "os.posix_spawn")
PROCESS += ("os.startfile", "pty.spawn", "asyncio.create_subprocess_")
DYNAMIC = ("importlib.import_module", "__import__")
READ = ["api", "--method", "GET"]
WRITES = {"-X", "-f", "-F", "--field", "--raw-field", "--input"}


def _names(tree: ast.Module) -> dict[str, str]:
    """Each local name an import gives, with the qualified name it stands for."""
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                names[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return names


def _qualified(func: ast.expr, names: dict[str, str]) -> str:
    if isinstance(func, ast.Name):
        return names.get(func.id, func.id)
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{names.get(func.value.id, func.value.id)}.{func.attr}"
    return ""


def _strings(node: ast.expr) -> list[str] | None:
    """The words of a command written as a list (other items, such as `*program()`, are skipped)."""
    if not isinstance(node, ast.List):
        return None
    return [item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]


def _command(call: ast.Call, scope: ast.AST) -> list[str] | None:
    """The command a process call runs, when it is a list, or a name given a list in the same function."""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Name):
        for node in ast.walk(scope):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == first.id for t in node.targets):
                return _strings(node.value)
        return None
    return _strings(first)


def _is_read(words: list[str]) -> bool:
    has_read = any(words[i : i + 3] == READ for i in range(len(words)))
    methods = [words[i + 1] for i, w in enumerate(words[:-1]) if w == "--method"]
    other = any(w.startswith("--method=") and w != "--method=GET" for w in words)
    return has_read and all(m == "GET" for m in methods) and not other and not WRITES.intersection(words)


def _file(path: Path, name: str) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return [f"{name}:1: cannot be read as Python, so it cannot be checked"]
    names = _names(tree)
    found: list[str] = []
    scopes: list[ast.AST] = [
        tree,
        *(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)),
    ]
    seen: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for module in modules:
                if module.split(".")[0] in NETWORK:
                    found.append(f"{name}:{node.lineno}: imports {module}, a network module")
    for scope in reversed(scopes):  # the innermost function first, so a name is looked up where it is set
        for node in ast.walk(scope):
            if not isinstance(node, ast.Call) or id(node) in seen:
                continue
            seen.add(id(node))
            called = _qualified(node.func, names)
            if called in DYNAMIC:
                found.append(
                    f"{name}:{node.lineno}: imports a module by a name given at run time, so it cannot be checked"
                )
            elif called.startswith(PROCESS):
                words = _command(node, scope)
                if words is None or not _is_read(words):
                    found.append(f"{name}:{node.lineno}: runs a process that is not gh api --method GET ({called})")
    return sorted(found, key=lambda line: int(line.split(":")[1]))


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
