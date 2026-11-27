"""Checks on the merged version (design §3 step 5, decision S0-5), from saved data only.

Read on a pull request's last commit, as collect saved them: every check run (`filter=all`) and every commit status.
For each name, only what had started (a run) or been posted (a status) before the merge counts, and a result counts
only when it was in before the merge. Results are written as GitHub gives them; no name is treated differently.
GitHub's times step by one second, so two entries of one name can share a second (elastic/elasticsearch #167931,
27 Nov 2026); GitHub's id, which grows as entries are made, then gives their order.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from asrecorded.changes import DIRECT, RepositoryList
from asrecorded.errors import reading_saved
from asrecorded.times import parse
from asrecorded.wording import mask

NONE_RAN = "no checks ran on the merged version"
NOT_FINISHED = "not finished at the merge"
DIRECT_PUSH = "checks not read for a direct push"


Results = tuple[tuple[str, str], ...]  # (name as GitHub gives it, result), sorted by name; None for a direct push


def describe_results(result: RepositoryList, folder: Path) -> dict[str, Results | None]:
    """Each change's checks on the merged version, by its id: what the rule reads."""
    with reading_saved(result.repository, folder):
        return {
            change.change: None if change.how == DIRECT else _results(folder / "pr" / change.change.removeprefix("#"))
            for change in result.changes
        }


def cell(results: Results | None) -> str:
    """The `checks` cell; a name is printed with any banned word or address replaced (S4-W1 C)."""
    if results is None:
        return DIRECT_PUSH
    if not results:
        return NONE_RAN
    return "; ".join(f"{mask(name)}: {state}" for name, state in results)


def describe_checks(result: RepositoryList, folder: Path) -> dict[str, str]:
    """Each change's `checks` cell, by its id."""
    return {change: cell(results) for change, results in describe_results(result, folder).items()}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _runs(runs: list[dict[str, Any]], merged: datetime) -> list[tuple[str, str]]:
    """For each name, the run that started last before the merge, and its result as things stood at the merge."""
    last: dict[str, dict[str, Any]] = {}
    for run in sorted(runs, key=lambda r: (parse(r["started_at"]), r["id"])):
        if parse(run["started_at"]) < merged:
            last[run["name"]] = run
    shown = []
    for name, run in last.items():
        done = run["status"] == "completed" and run["conclusion"] and parse(run["completed_at"]) < merged
        shown.append((name, run["conclusion"] if done else NOT_FINISHED))
    return shown


def _statuses(statuses: list[dict[str, Any]], merged: datetime) -> list[tuple[str, str]]:
    """For each context, the entry posted last before the merge; `pending` is a result not yet in."""
    last: dict[str, str] = {}
    for entry in sorted(statuses, key=lambda s: (parse(s["created_at"]), s["id"])):
        if parse(entry["created_at"]) < merged:
            last[entry["context"]] = NOT_FINISHED if entry["state"] == "pending" else entry["state"]
    return list(last.items())


def _results(base: Path) -> Results:
    merged = parse(_read(base / "pull.json")["merged_at"])
    shown = _runs(_read(base / "check_runs.json"), merged) + _statuses(_read(base / "statuses.json"), merged)
    return tuple(sorted(shown, key=lambda s: (s[0].casefold(), s[0])))
