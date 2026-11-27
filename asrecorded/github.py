"""Every read of GitHub (design §2): `gh api --method GET --paginate --slurp <path>`, and nothing else.

`ASRECORDED_GH` may name a stand-in for `gh` as a JSON list (design §4): the one seam added for tests.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from asrecorded.errors import Stop

SHAPE = "GitHub's reply had an unexpected shape"


class Refused(Exception):
    """GitHub did not answer `path`; `message` is GitHub's own words where it gave some."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


def program() -> list[str]:
    raw = os.environ.get("ASRECORDED_GH")
    if raw is None:
        return ["gh"]
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = None
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise Stop('ASRECORDED_GH must be a JSON list naming a program and its arguments, such as ["gh"].')
    return value


def pages(path: str) -> list[Any]:
    """Every page GitHub gives for `path`, as `--slurp` lists them."""
    if path.startswith("-"):  # it would pass as a flag to gh, such as -XPOST (PR #14 review, H1)
        raise Stop(
            f"Refused to ask GitHub for {path!r}: a path never starts with '-', so it cannot pass as a flag to gh."
        )
    command = [*program(), "api", "--method", "GET", "--paginate", "--slurp", path]
    try:
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except FileNotFoundError:
        raise Stop(
            "The gh command was not found. Install GitHub's gh, sign in with gh auth login, then run this again."
        ) from None
    if done.returncode != 0:
        raise Refused(path, _message(done.stdout, done.stderr))
    try:
        reply = json.loads(done.stdout)
    except json.JSONDecodeError:
        reply = None
    if not isinstance(reply, list):
        raise Refused(path, "GitHub's reply could not be read")
    return reply


def _message(stdout: str, stderr: str) -> str:
    try:
        reply = json.loads(stdout)
    except json.JSONDecodeError:
        reply = None
    if isinstance(reply, list) and reply:
        reply = reply[0]
    if isinstance(reply, dict) and isinstance(reply.get("message"), str):
        return str(reply["message"])
    return stderr.strip() or "no reply"


def get_object(path: str) -> dict[str, Any]:
    """One object, such as a repository or a pull request."""
    replied = pages(path)
    if len(replied) != 1 or not isinstance(replied[0], dict):
        raise Refused(path, SHAPE)
    return replied[0]


def get_list(path: str) -> list[Any]:
    """A list, its pages joined."""
    joined: list[Any] = []
    for page in pages(path):
        if not isinstance(page, list):
            raise Refused(path, SHAPE)
        joined.extend(page)
    return joined


def get_check_runs(path: str) -> list[Any]:
    """The check runs of a commit: each page's `check_runs`, joined."""
    return _named_lists(path, "check_runs")


def get_compare(path: str) -> list[Any]:
    """The commits of a compare: each page's `commits`, joined."""
    return _named_lists(path, "commits")


def _named_lists(path: str, key: str) -> list[Any]:
    joined: list[Any] = []
    for page in pages(path):
        items = page.get(key) if isinstance(page, dict) else None
        if not isinstance(items, list):
            raise Refused(path, SHAPE)
        joined.extend(items)
    return joined
