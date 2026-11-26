"""History check: no private data in any commit of this repository.

Reads every object reachable from a revision (default HEAD): each commit object whole
(author, committer, message), each file version whole (text, binary or UTF-16), and each
file and folder name. With --staged it reads the staged file versions instead, for use
before a commit. It reports the object, the place and the kind of each finding, never
the matched text itself.

Exit codes: 0 clean; 1 findings; 2 nothing was scanned, the clone is shallow, or git failed.
Not read: annotated tags, notes and other refs outside the revision's history.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
ALLOWED_EMAIL = re.compile(
    r"^(?:\d+\+)?[A-Za-z0-9-]+(?:\[bot\])?@users\.noreply\.github\.com$"
    r"|^noreply@github\.com$"
    r"|^noreply@anthropic\.com$"
    r"|^git@github\.com$",  # the SSH clone form, git at github.com:owner/name
    re.IGNORECASE,
)
# Path patterns are written with [/] so that this file's own text does not match them.
BEFORE_PATH = r"(?:^|(?<=[\s\"'=(\[,;:<>`]))"
PATTERNS: dict[str, re.Pattern[str]] = {
    "local user path": re.compile(
        r"[A-Za-z](?::|%3A)(?:\\\\|\\|[/])+Users(?:\\\\|\\|[/])"  # Windows, with either slash, and file addresses
        r"|[/][a-z][/]Users[/]"  # Git Bash
        rf"|{BEFORE_PATH}[/]Users[/][A-Za-z0-9._-]+"  # macOS
        rf"|{BEFORE_PATH}[/]home[/](?!runner\b)[A-Za-z0-9._-]+",  # Linux, except the CI runner's own folder
        re.IGNORECASE | re.MULTILINE,
    ),
    "GitHub token": re.compile(r"gh[opsur]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"),
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "AWS key": re.compile(r"AKIA[0-9A-Z]{16}(?![0-9A-Z])"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),
}
HINT = "To find the commit that added a file version: git log --all --find-object=<object id>"


@dataclass(frozen=True)
class Finding:
    label: str
    place: str
    kind: str

    def line(self) -> str:
        return f"{self.label}: {self.kind} in {self.place}"


def kinds_in(text: str) -> list[str]:
    """The kinds of private data found in one piece of text, each kind once, in a fixed order."""
    found: list[str] = []
    if any(not ALLOWED_EMAIL.match(m) for m in EMAIL.findall(text)):
        found.append("email address")
    found.extend(kind for kind, pattern in PATTERNS.items() if pattern.search(text))
    return found


def decode(data: bytes) -> str:
    """Text from any file version: UTF-16 when it starts with a byte order mark, else UTF-8;
    NUL bytes are dropped, so UTF-16 text without a mark and text inside binary files are read too."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace").replace("\x00", "")


def run(args: Sequence[str], stdin: bytes | None = None) -> bytes:
    """Run git with core.quotepath off, so that file names come back as written."""
    result = subprocess.run(["git", "-c", "core.quotepath=off", *args], input=stdin, capture_output=True)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {args[0]} failed: {message}")
    return result.stdout


def read_objects(ids: list[str]) -> Iterator[tuple[str, str, bytes]]:
    """(id, type, content) for each object id, read in one git cat-file call."""
    out = run(["cat-file", "--batch"], ("\n".join(ids) + "\n").encode("ascii"))
    at = 0
    for _ in ids:
        end = out.index(b"\n", at)
        oid, kind, size = out[at:end].decode("ascii").split()
        start = end + 1
        yield oid, kind, out[start : start + int(size)]
        at = start + int(size) + 1


def scan_names(label: str, paths: list[str]) -> list[Finding]:
    """Findings in file and folder names; the names themselves are never printed."""
    return [Finding(label, "a file name", kind) for kind in kinds_in("\n".join(paths))]


def scan_content(label: str, path: str, content: bytes) -> list[Finding]:
    shown = "a file whose name is withheld" if kinds_in(path) else f"file {path}"
    return [Finding(label, shown, kind) for kind in kinds_in(decode(content))]


def scan_history(revision: str) -> tuple[list[Finding], int]:
    if run(["rev-parse", "--is-shallow-repository"]).strip() == b"true":
        raise RuntimeError("this is a shallow clone, so part of the history is missing: fetch the full history")
    names: dict[str, str] = {}
    for line in run(["rev-list", "--objects", revision]).decode("utf-8").splitlines():
        oid, _, name = line.partition(" ")
        names.setdefault(oid, name)
    findings: list[Finding] = []
    commits = 0
    for oid, kind, content in read_objects(list(names)):
        if kind == "commit":
            commits += 1
            findings += [Finding(oid[:7], "commit details", k) for k in kinds_in(decode(content))]
        elif kind == "blob":
            findings += scan_content(oid[:7], names[oid], content)
    every_path = run(["log", "--format=", "--name-only", "-z", "--no-renames", "--diff-merges=first-parent", revision])
    paths = {p.strip("\n") for p in every_path.decode("utf-8").split("\0")}
    findings += scan_names("names", sorted(p for p in paths if p))
    return findings, commits


def scan_staged() -> tuple[list[Finding], int]:
    listed = run(["diff", "--cached", "--name-only", "-z", "--diff-filter=d"])
    files = [name for name in listed.decode("utf-8").split("\0") if name]
    findings = scan_names("staged", files)
    for name in files:
        findings += scan_content("staged", name, run(["cat-file", "blob", f":{name}"]))
    return findings, len(files)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args == ["--staged"]:
            findings, count = scan_staged()
            scanned, nothing = f"{count} staged file(s)", "nothing is staged"
        else:
            findings, count = scan_history(args[0] if args else "HEAD")
            scanned, nothing = f"{count} commits", "no commit to scan"
    except RuntimeError as error:
        print(f"history check: {error}", file=sys.stderr)
        return 2
    if count == 0:
        print(f"history check: {nothing}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.line())
    if findings:
        print(f"history check: {len(findings)} finding(s) in {scanned}")
        print(HINT)
        return 1
    print(f"history check: {scanned} scanned, clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
