"""History check: no private data in any commit of this repository.

Scans every commit reachable from a revision (default HEAD): its author and committer
fields, its message, and every line it adds. With --staged it scans the staged changes
instead, for use before a commit. It reports the commit, the place and the kind of each
finding, never the matched text itself.

Exit codes: 0 clean; 1 findings; 2 nothing was scanned or git failed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
ALLOWED_EMAIL = re.compile(
    r"^(?:\d+\+)?[A-Za-z0-9-]+(?:\[bot\])?@users\.noreply\.github\.com$"
    r"|^noreply@github\.com$"
    r"|^noreply@anthropic\.com$",
    re.IGNORECASE,
)
PATTERNS: dict[str, re.Pattern[str]] = {
    # Written with [/] so that this file's own text does not match its pattern.
    "local user path": re.compile(
        r"[A-Za-z]:(?:\\\\|\\|/)+Users(?:\\\\|\\|/)|[/]c[/]Users[/]|[/]home[/][a-z][a-z0-9_-]*[/]", re.IGNORECASE
    ),
    "GitHub token": re.compile(r"\bgh[opsur]_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}"),
    "Anthropic key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    "AWS key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


@dataclass(frozen=True)
class Finding:
    commit: str
    place: str
    kind: str

    def line(self) -> str:
        return f"{self.commit}: {self.kind} in {self.place}"


def kinds_in(text: str) -> list[str]:
    """The kinds of private data found in one piece of text, each kind once, in a fixed order."""
    found: list[str] = []
    if any(not ALLOWED_EMAIL.match(m) for m in EMAIL.findall(text)):
        found.append("email address")
    found.extend(kind for kind, pattern in PATTERNS.items() if pattern.search(text))
    return found


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def added_lines_by_file(patch: str) -> dict[str, list[str]]:
    """The lines a patch adds, grouped by the file they are added to."""
    files: dict[str, list[str]] = {}
    current = "(unknown file)"
    previous = ""
    for line in patch.splitlines():
        if line.startswith("+++ ") and previous.startswith("--- "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
        elif line.startswith("+"):
            files.setdefault(current, []).append(line[1:])
        previous = line
    return files


def scan_patch(commit: str, patch: str) -> list[Finding]:
    return [
        Finding(commit, f"file {name}", kind)
        for name, lines in added_lines_by_file(patch).items()
        for kind in kinds_in("\n".join(lines))
    ]


def scan_commit(sha: str) -> list[Finding]:
    short = sha[:7]
    meta = git("show", "-s", "--format=%an%n%ae%n%cn%n%ce%n%B", sha)
    findings = [Finding(short, "commit details", kind) for kind in kinds_in(meta)]
    patch = git("show", "--format=", "-p", "--no-color", "--no-ext-diff", "-m", "--first-parent", sha)
    return findings + scan_patch(short, patch)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args == ["--staged"]:
            findings = scan_patch("staged", git("diff", "--cached", "--no-color", "--no-ext-diff"))
            scanned = "the staged changes"
        else:
            revision = args[0] if args else "HEAD"
            commits = git("rev-list", revision).split()
            if not commits:
                print("history check: no commit to scan", file=sys.stderr)
                return 2
            findings = [f for sha in commits for f in scan_commit(sha)]
            scanned = f"{len(commits)} commits"
    except RuntimeError as error:
        print(f"history check: {error}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.line())
    if findings:
        print(f"history check: {len(findings)} finding(s) in {scanned}")
        return 1
    print(f"history check: {scanned} scanned, clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
