"""Who built each change, who let it in, approvals, AI shown and the pattern (design §3 steps 2 to 4), from saved data.

Logins come only from actions GitHub authenticates (A10, S0-3): opening the pull request, merging it, approving it,
switching auto-merge on, adding it to a merge queue, and pushing (the activity history's account). A commit's author
and committer fields are read only as AI markers, by the fixed list (`agents`), and no login is ever taken from them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from asrecorded.agents import account_agent, commit_markers
from asrecorded.changes import DIRECT, Change, RepositoryList
from asrecorded.errors import reading_saved
from asrecorded.times import parse

AUTO_ON = ("auto_merge_enabled", "auto_squash_enabled", "auto_rebase_enabled")
ONE_ACCOUNT = "One account"


@dataclass(frozen=True)
class Who:
    builder: str
    let_in_by: str
    approvals: str
    ai_shown: str
    ai_trace: str
    pattern: str
    declared_agent_operated: str


def describe(result: RepositoryList, folder: Path, declared: frozenset[str]) -> tuple[dict[str, Who], list[str]]:
    """Each change's `Who`, by its id, and the "not covered" lines (a merge queue, by the owner's cut)."""
    with reading_saved(result.repository, folder):
        return _describe(result, folder, frozenset(login.lower() for login in declared))  # logins ignore case


def pattern_line(repository: str, details: dict[str, Who]) -> str:
    one = [w for w in details.values() if w.pattern == ONE_ACCOUNT]
    declared = sum(1 for w in one if w.declared_agent_operated)
    return f"{repository}: {ONE_ACCOUNT} {len(one)} ({declared} declared agent-operated)"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _describe(result: RepositoryList, folder: Path, declared: frozenset[str]) -> tuple[dict[str, Who], list[str]]:
    details: dict[str, Who] = {}
    not_covered: list[str] = []
    for change in result.changes:
        if change.how == DIRECT:
            details[change.change] = _pushed(change, declared)
        else:
            who, queued = _pull_request(folder / "pr" / change.change.removeprefix("#"), declared)
            details[change.change] = who
            if queued:
                not_covered.append(
                    f"{result.repository}: not covered: {change.change} was let in by a merge queue, "
                    "which this record does not follow"
                )
    return details, not_covered


def _ai(account: dict[str, Any], commits: list[dict[str, Any]], declared: frozenset[str]) -> tuple[str, str]:
    """`ai_shown` and `ai_trace`: the account's kind first, then each tool a commit names."""
    kinds = []
    agent = account_agent(account)
    if agent:
        kinds.append(f"coding agent account: {agent}")
    elif account["login"].lower() in declared:
        kinds.append("declared agent-operated account")
    kinds += [f"commit marker: {name}" for name in commit_markers(commits)]
    return ("yes", "; ".join(kinds)) if kinds else ("not shown", "")


def _pushed(change: Change, declared: frozenset[str]) -> Who:
    actor = cast(dict[str, Any], change.actor)  # every direct push carries its pusher and commit (changes.py)
    shown, trace = _ai(actor, [cast(dict[str, Any], change.commit)], declared)
    return Who("no pull request: not shown", f"pushed by {actor['login']}", "", shown, trace, "No pull request", "")


def _until_merged(timeline: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Who switched auto-merge on, and who added it to a merge queue, as things stood at the `merged` entry (the
    whole timeline when it holds none). None: off; an empty dict: on, by an account GitHub does not show.
    GitHub's own queue bot writes `removed_from_merge_queue` as it merges the change (microsoft/vscode #350667,
    27 Nov 2026), so only a person taking it out of the queue ends the queue."""
    auto: dict[str, Any] | None = None
    queued: dict[str, Any] | None = None
    for entry in timeline:
        kind = entry.get("event")
        if kind == "merged":
            break
        if kind in AUTO_ON:
            auto = entry["actor"] or {}
        elif kind == "auto_merge_disabled":
            auto = None
        elif kind == "added_to_merge_queue":
            queued = entry["actor"] or {}
        elif kind == "removed_from_merge_queue" and (entry["actor"] or {}).get("type") == "User":
            queued = None
    return auto, queued


def _by(words: str, account: dict[str, Any]) -> str:
    return f"{words} by {account['login']}" if account else f"{words} (account not shown)"


def _approvals(reviews: list[dict[str, Any]], merged_at: str, head: str) -> list[tuple[dict[str, Any], str]]:
    """Each approver once, by their last approval given before the merge, in time order (S0-6)."""
    last: dict[str, tuple[dict[str, Any], str]] = {}
    given = [r for r in reviews if r.get("submitted_at")]  # a draft review has no time yet
    for review in sorted(given, key=lambda r: parse(r["submitted_at"])):
        if review["state"] == "APPROVED" and review["user"] and parse(review["submitted_at"]) < parse(merged_at):
            version = "on the merged version" if review["commit_id"] == head else "on an earlier version"
            last.pop(review["user"]["login"], None)  # keep the order of each approver's last approval
            last[review["user"]["login"]] = (review["user"], version)
    return list(last.values())


def _pull_request(base: Path, declared: frozenset[str]) -> tuple[Who, bool]:
    pull = _read(base / "pull.json")
    reviews = _read(base / "reviews.json")
    timeline = _read(base / "timeline.json")
    commits = _read(base / "commits.json")
    opener, merger = pull["user"], pull["merged_by"]
    auto, queued = _until_merged(timeline)
    approvals = _approvals(reviews, pull["merged_at"], pull["head"]["sha"])
    shown, trace = _ai(opener, commits, declared)

    def person(account: dict[str, Any]) -> bool:
        return bool(account["type"] == "User" and account["login"].lower() not in declared)

    def agent(account: dict[str, Any]) -> bool:
        return bool(account["login"].lower() in declared or account["type"] == "Bot")

    other = merger["login"] != opener["login"]
    by_hand = auto is None and queued is None
    mark = ""
    if any(person(a) and a["login"] != opener["login"] for a, _ in approvals) or (by_hand and person(merger) and other):
        pattern = "Agent and person" if shown == "yes" or agent(opener) else "Two people"
    elif approvals and all(agent(a) for a, _ in approvals):
        pattern = "AI reviewer only"
    elif not approvals and (not by_hand or (agent(merger) and other) or merger["type"] == "Bot"):
        pattern = "Automatic, no approval"
    else:
        pattern = ONE_ACCOUNT
        mark = "yes" if opener["login"].lower() in declared else ""
    if queued is not None:
        let_in = f"merge queue: added by {queued['login']}" if queued else "merge queue (account not shown)"
    elif auto is not None:
        let_in = _by("auto-merge switched on", auto)
    else:
        let_in = merger["login"]
    listed = "; ".join(f"{a['login']} ({version})" for a, version in approvals)
    return Who(opener["login"], let_in, listed, shown, trace, pattern, mark), queued is not None
