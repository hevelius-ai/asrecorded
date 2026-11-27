"""The fixed list of coding agents (S0 row 5, design §3 step 3): accounts by id, commit markers by trailer or name."""

from __future__ import annotations

from typing import Any

from asrecorded.agents import account_agent, commit_markers

ANTHROPIC = "noreply@anthropic.com"


def account(login: str, oid: int, kind: str = "Bot") -> dict[str, Any]:
    return {"login": login, "id": oid, "type": kind}


def piece(
    message: str = "work", name: str = "dana", address: str = "1001+dana@users.noreply.github.com"
) -> dict[str, Any]:
    return {"commit": {"message": message, "author": {"name": name, "email": address}}}


def test_a_coding_agent_account_is_known_by_its_id_and_named_from_the_list() -> None:
    assert account_agent(account("claude[bot]", 209825114)) == "Claude (Anthropic)"
    assert account_agent(account("Copilot", 198982749)) == "GitHub Copilot"
    assert account_agent(account("gemini-code-assist[bot]", 176961590)) == "Gemini Code Assist (Google)"
    assert account_agent(account("coderabbitai[bot]", 136622811)) == "CodeRabbit"
    assert account_agent(account("amp-for-github[bot]", 211718141)) == "Amp"
    assert account_agent(account("cursor[bot]", 206951365)) == "Cursor"
    assert account_agent(account("google-labs-jules[bot]", 161369871)) == "Jules (Google)"


def test_a_login_alone_never_makes_a_coding_agent() -> None:
    assert account_agent(account("claude[bot]", 1)) is None  # the right login under another id
    assert account_agent(account("Copilot", 175728472)) is None  # Copilot's reviewer, a different id
    assert account_agent(account("dana", 1001, "User")) is None


def test_a_claude_co_authored_by_line_is_a_marker_named_from_the_list() -> None:
    message = f"work\n\nCo-Authored-By: Claude Opus 5.5 <{ANTHROPIC}>\n"
    assert commit_markers([piece(message)]) == ["Claude (Anthropic)"]
    lower = f"work\n\nco-authored-by:   Claude Sonnet 5.5   <{ANTHROPIC.upper()}>"
    assert commit_markers([piece(lower)]) == ["Claude (Anthropic)"]


def test_a_claude_author_name_is_a_marker_only_with_anthropics_address() -> None:
    assert commit_markers([piece(name="Claude", address=ANTHROPIC)]) == ["Claude (Anthropic)"]
    assert commit_markers([piece(name="Claude", address="noreply@github.com")]) == []
    assert commit_markers([piece("work\n\nCo-Authored-By: Claude <noreply@github.com>")]) == []


def test_the_other_listed_markers() -> None:
    assert commit_markers(
        [piece("x\n\nCo-authored-by: coderabbitai[bot] <136622811+coderabbitai[bot]@users.noreply.github.com>")]
    ) == ["CodeRabbit"]
    assert commit_markers([piece("x\n\nCo-authored-by: Amp <noreply@github.com>")]) == ["Amp"]
    assert commit_markers([piece(name="dana (aider)")]) == ["Aider"]
    assert commit_markers([piece("x\n\nCo-authored-by: Someone <noreply@github.com>"), piece()]) == []


def test_each_tool_is_named_once_in_the_lists_order() -> None:
    claude = f"x\n\nCo-Authored-By: Claude Opus 5.5 <{ANTHROPIC}>"
    pieces = [
        piece(name="lee (aider)"),
        piece(claude),
        piece(claude),
        piece("x\n\nCo-authored-by: Amp <noreply@github.com>"),
    ]
    assert commit_markers(pieces) == ["Claude (Anthropic)", "Amp", "Aider"]


def test_a_commit_with_no_author_name_or_address_is_read_as_no_marker() -> None:
    assert commit_markers([{"commit": {"message": "work", "author": None}}]) == []
    assert commit_markers([{"commit": {"message": "work", "author": {}}}]) == []


def test_anthropics_address_alone_does_not_make_an_author_name_a_marker() -> None:
    assert commit_markers([piece(name="dana", address=ANTHROPIC)]) == []
