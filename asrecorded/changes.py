"""The list of changes (design §3 step 1), built from the saved data only.

A change is a merged pull request of the period, or a commit a push of the period brought straight to the default
branch. A commit that is part of a merged pull request is never a direct push: those a `pr_merge` entry (or a
`merge_queue_merge` entry, GitHub's type for a merge queue's merge) brought in,
every merged pull request's `merge_commit_sha`, the commits in its saved `commits.json`, and, for a push whose `after`
is a `merge_commit_sha` (a merge bot, or a person's own merge), the pushed commits off that push's first-parent line.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from asrecorded.collect import push_file
from asrecorded.errors import Stop
from asrecorded.times import clock, count, day, parse

PULL, DIRECT = "pull request", "pushed directly"
MERGES = ("pr_merge", "merge_queue_merge")
PUSHES = ("push", "force_push", "branch_creation")
REQUIRED = ("repo.json", "pulls.json", "activity.json", "main_commits.json")
LISTED = 250  # GitHub lists at most 250 commits for a pull request


@dataclass(frozen=True)
class Change:
    repository: str
    change: str  # "#11" for a pull request, the first 7 characters of the hash for a commit
    how: str
    when: datetime


@dataclass(frozen=True)
class Rewrite:
    repository: str
    when: datetime
    actor: str
    commits: int


@dataclass
class RepositoryList:
    repository: str
    changes: list[Change] = field(default_factory=list)
    rewrites: list[Rewrite] = field(default_factory=list)
    not_covered: list[str] = field(default_factory=list)


def list_changes(repository: str, folder: Path, start: datetime, end: datetime) -> RepositoryList:
    for name in REQUIRED:
        if not (folder / name).is_file():
            raise Stop(
                f"The data folder has no saved {name} for {repository}. Run collect first. No record was written."
            )
    try:
        return _list(repository, folder, start, end)
    except FileNotFoundError as missing:
        name = Path(missing.filename).relative_to(folder).as_posix()
        raise Stop(
            f"The saved data for {repository} is missing {name}. Run collect again. No record was written."
        ) from None
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        raise Stop(
            f"The saved data for {repository} could not be read. Run collect again. No record was written."
        ) from None


def summary_lines(result: RepositoryList) -> list[str]:
    pulls = sum(1 for c in result.changes if c.how == PULL)
    direct = len(result.changes) - pulls
    lines = [
        f"{result.repository}: {count(len(result.changes), 'change')} "
        f"({count(pulls, 'pull request')}, {count(direct, 'commit')} pushed directly)"
    ]
    for rewrite in result.rewrites:
        lines.append(
            f"{result.repository}: history rewritten on {day(rewrite.when)} at {clock(rewrite.when)} UTC "
            f"by {rewrite.actor}, {count(rewrite.commits, 'commit')} brought in"
        )
    return lines + result.not_covered


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parents(commits: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {c["sha"]: [p["sha"] for p in c["parents"]] for c in commits}


def _first_parent_line(tip: str, parents: dict[str, list[str]], stop: str | None) -> tuple[list[str], bool]:
    """The commits from `tip` through each first parent, until `stop` or the end of what is known; and whether
    `stop` was reached."""
    line: list[str] = []
    current: str | None = tip
    while current is not None and current != stop and current in parents and current not in line:
        line.append(current)
        first = parents[current]
        current = first[0] if first else None
    return line, current == stop


def _list(repository: str, folder: Path, start: datetime, end: datetime) -> RepositoryList:
    info = _read(folder / "repo.json")
    pulls = _read(folder / "pulls.json")
    activity = _read(folder / "activity.json")
    main = _read(folder / "main_commits.json")
    result = RepositoryList(repository)

    def inside(text: str) -> bool:
        return start <= parse(text) < end

    merged = [p for p in pulls if p["merged_at"]]
    merge_shas = {p["merge_commit_sha"] for p in merged}
    excluded = set(merge_shas)
    brought: set[str] = set()  # every commit an activity entry explains, for the cross-check
    main_parents = _parents(main)

    numbers: set[int] = set()  # a pull request saved twice (paging while another one closes) is listed once
    for pull in merged:
        if (
            pull["base"]["ref"] == info["default_branch"]
            and inside(pull["merged_at"])
            and pull["number"] not in numbers
        ):
            number = pull["number"]
            numbers.add(number)
            detail = _read(folder / "pr" / str(number) / "pull.json")
            excluded.update(c["sha"] for c in _read(folder / "pr" / str(number) / "commits.json"))
            if detail["commits"] > LISTED:
                result.not_covered.append(
                    f"{repository}: not covered: #{number} has {detail['commits']} commits, "
                    f"and GitHub lists only {LISTED} of them"
                )
            result.changes.append(Change(repository, f"#{number}", PULL, parse(pull["merged_at"])))

    pushes: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for entry in sorted(activity, key=lambda e: parse(e["timestamp"])):
        kind = entry["activity_type"]
        if kind in MERGES:
            line, reached = _first_parent_line(entry["after"], main_parents, entry["before"])
            merged_in = set(line) if reached else {entry["after"]}
            excluded |= merged_in
            brought |= merged_in
        elif kind in PUSHES and inside(entry["timestamp"]):
            commits = _read(folder / "push" / push_file(entry))
            brought.update(c["sha"] for c in commits)
            if kind == "force_push":
                when = parse(entry["timestamp"])
                result.rewrites.append(Rewrite(repository, when, entry["actor"]["login"], len(commits)))
                continue
            if entry["after"] in merge_shas:
                line, _ = _first_parent_line(entry["after"], _parents(commits), entry["before"])
                excluded.update(c["sha"] for c in commits if c["sha"] not in line)
            pushes.append((entry, commits))

    listed = {c.change for c in result.changes}
    for entry, commits in pushes:
        for c in commits:
            sha = c["sha"]
            if sha not in excluded and sha[:7] not in listed:
                listed.add(sha[:7])
                result.changes.append(Change(repository, sha[:7], DIRECT, parse(entry["timestamp"])))
    result.changes.sort(key=lambda c: (c.when, c.change))

    # Cross-check: the main line as it stood at the period's end, from the last entry stamped before it; a commit
    # pushed after the end is not on that part of the line, and its push is not read.
    before_end = [e for e in activity if parse(e["timestamp"]) < end]
    if before_end:
        by_sha = {c["sha"]: c for c in main}
        tip = max(before_end, key=lambda e: parse(e["timestamp"]))["after"]
        line, _ = _first_parent_line(tip, main_parents, None)
        for sha in line:
            dated = parse(by_sha[sha]["commit"]["committer"]["date"])
            if sha not in brought and start <= dated < end:
                result.not_covered.append(
                    f"{repository}: not covered: commit {sha[:7]} on the main line, dated {day(dated)} at "
                    f"{clock(dated)} UTC, is not explained by the activity history"
                )
    if not activity:
        result.not_covered.append(
            f"{repository}: not covered: GitHub's activity history holds no entry for the default branch"
        )
    else:
        oldest = min(parse(e["timestamp"]) for e in activity)
        if oldest > start and parse(info["created_at"]) < start:
            result.not_covered.append(
                f"{repository}: not covered: the activity history reaches back only to {day(oldest)} at "
                f"{clock(oldest)} UTC, after the period's start"
            )
    return result
