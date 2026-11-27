"""The fixed list of coding agents (docs/spike-S0.md row 5; design §3 step 3; decision S0-3).

An account is recognised by its id, never by its login: a login is text another account can resemble (GitHub shows
`Copilot` for two accounts with different ids). A commit marker is read from a `Co-Authored-By` line or a commit's
author name, which anyone can write, so it only ever adds an AI marker, never a login. The name printed is always the
list's own entry, never text from a commit: a Claude `Co-Authored-By` line names a model, not the tool.
Account ids were read with `gh api --method GET users/<login>` on 27 Nov 2026.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

ANTHROPIC = "noreply@anthropic.com"
TRAILER = re.compile(r"^co-authored-by:\s*(.*?)\s*<([^>]*)>\s*$", re.IGNORECASE | re.MULTILINE)

Match = Callable[[str, str], bool]  # (name, address), both as written in the commit


def _never(name: str, address: str) -> bool:
    return False


@dataclass(frozen=True)
class Agent:
    name: str
    account_ids: frozenset[int] = frozenset()
    trailer: Match = _never
    author: Match = _never


def _claude(name: str, address: str) -> bool:
    return address.lower() == ANTHROPIC and name.lower().startswith("claude")


FIXED = (
    Agent(
        "Claude (Anthropic)",
        frozenset({209825114}),  # claude[bot]
        trailer=lambda name, address: address.lower() == ANTHROPIC,
        author=_claude,
    ),
    Agent("GitHub Copilot", frozenset({198982749})),  # copilot-swe-agent[bot], shown as Copilot
    Agent("Gemini Code Assist (Google)", frozenset({176961590})),  # gemini-code-assist[bot]
    Agent(
        "CodeRabbit",
        frozenset({136622811}),  # coderabbitai[bot]
        trailer=lambda name, address: name.lower() == "coderabbitai[bot]",
    ),
    Agent("Amp", frozenset({211718141}), trailer=lambda name, address: name.lower() == "amp"),  # amp-for-github[bot]
    Agent("Cursor", frozenset({206951365})),  # cursor[bot]
    Agent("Jules (Google)", frozenset({161369871})),  # google-labs-jules[bot]
    Agent("Aider", author=lambda name, address: name.endswith("(aider)")),
)


def account_agent(account: dict[str, Any]) -> str | None:
    """The list's name for an account on the fixed list, known by its id; None for any other account."""
    for agent in FIXED:
        if account["id"] in agent.account_ids:
            return agent.name
    return None


def commit_markers(commits: list[dict[str, Any]]) -> list[str]:
    """The list's names of the tools the commits name, each once, in the list's order."""
    trailers: list[tuple[str, str]] = []
    authors: list[tuple[str, str]] = []
    for c in commits:
        trailers += TRAILER.findall(c["commit"]["message"])
        author = c["commit"]["author"] or {}
        authors.append((author.get("name") or "", author.get("email") or ""))
    return [
        agent.name
        for agent in FIXED
        if any(agent.trailer(n, a) for n, a in trailers) or any(agent.author(n, a) for n, a in authors)
    ]
