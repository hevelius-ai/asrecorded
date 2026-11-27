"""Checks on the merged version (design §3 step 5, decision S0-5), from saved data only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from asrecorded.changes import Change, RepositoryList
from asrecorded.checks import describe_checks
from asrecorded.errors import Stop
from asrecorded.times import parse

MERGED = "2026-11-10T10:00:00Z"
NONE = "no checks ran on the merged version"
LATE = "not finished at the merge"


def run(name: str, conclusion: str | None, started: str, completed: str | None, oid: int = 1) -> dict[str, Any]:
    status = "completed" if completed else "in_progress"
    return {
        "id": oid,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "started_at": started,
        "completed_at": completed,
    }


def status(context: str, state: str, created: str, oid: int = 1) -> dict[str, Any]:
    return {"id": oid, "context": context, "state": state, "created_at": created, "updated_at": created}


def cell(tmp: Path, runs: list[dict[str, Any]], statuses: list[dict[str, Any]] | None = None) -> str:
    base = tmp / "pr" / "11"
    base.mkdir(parents=True, exist_ok=True)
    (base / "pull.json").write_text(json.dumps({"number": 11, "merged_at": MERGED}), encoding="utf-8")
    (base / "check_runs.json").write_text(json.dumps(runs), encoding="utf-8")
    (base / "statuses.json").write_text(json.dumps(statuses or []), encoding="utf-8")
    change = Change("acme/shop", "#11", "pull request", parse(MERGED))
    return describe_checks(RepositoryList("acme/shop", [change]), tmp)["#11"]


def test_a_run_that_ended_before_the_merge_shows_its_result_as_github_gives_it(tmp_path: Path) -> None:
    assert cell(tmp_path, [run("ci", "failure", "2026-11-10T09:00:00Z", "2026-11-10T09:10:00Z")]) == "ci: failure"
    assert cell(tmp_path, [run("lint", "neutral", "2026-11-10T09:00:00Z", "2026-11-10T09:10:00Z")]) == "lint: neutral"


def test_a_run_still_going_at_the_merge_is_not_finished(tmp_path: Path) -> None:
    ended_after = run("ci", "success", "2026-11-10T09:55:00Z", "2026-11-10T10:05:00Z")
    assert cell(tmp_path, [ended_after]) == f"ci: {LATE}"
    running = run("ci", None, "2026-11-10T09:55:00Z", None)
    assert cell(tmp_path, [running]) == f"ci: {LATE}"
    ended_at_the_merge = run("ci", "success", "2026-11-10T09:55:00Z", MERGED)
    assert cell(tmp_path, [ended_at_the_merge]) == f"ci: {LATE}"


def test_a_run_started_at_or_after_the_merge_is_not_read(tmp_path: Path) -> None:
    after = run("ci", "success", "2026-11-10T10:01:00Z", "2026-11-10T10:05:00Z")
    at = run("lint", "success", MERGED, "2026-11-10T10:05:00Z")
    assert cell(tmp_path, [after, at]) == NONE


def test_the_last_run_of_a_name_started_before_the_merge_is_shown_whatever_the_order(tmp_path: Path) -> None:
    rerun = run("ci", "success", "2026-11-10T09:30:00Z", "2026-11-10T09:40:00Z", 3)
    first = run("ci", "failure", "2026-11-10T09:00:00Z", "2026-11-10T09:10:00Z", 2)
    after = run("ci", "cancelled", "2026-11-10T10:30:00Z", "2026-11-10T10:31:00Z", 4)
    assert cell(tmp_path, [after, rerun, first]) == "ci: success"  # GitHub lists the newest first
    assert cell(tmp_path, [first, after, rerun]) == "ci: success"


def test_commit_statuses_are_read_the_same_way(tmp_path: Path) -> None:
    statuses = [
        status("deploy", "success", "2026-11-10T10:30:00Z", 5),  # after the merge: not read
        status("deploy", "failure", "2026-11-10T09:20:00Z", 4),
        status("deploy", "pending", "2026-11-10T09:00:00Z", 3),
        status("build", "pending", "2026-11-10T09:50:00Z", 2),
        status("legacy", "error", "2026-11-10T08:00:00Z", 1),
    ]
    assert cell(tmp_path, [], statuses) == f"build: {LATE}; deploy: failure; legacy: error"


def test_a_status_created_at_or_after_the_merge_is_not_read(tmp_path: Path) -> None:
    assert cell(tmp_path, [], [status("deploy", "success", MERGED)]) == NONE


def test_names_are_sorted_ignoring_letter_case_and_none_is_treated_specially(tmp_path: Path) -> None:
    runs = [
        run("zeta", "success", "2026-11-10T09:00:00Z", "2026-11-10T09:01:00Z", 1),
        run("ci", "success", "2026-11-10T09:00:00Z", "2026-11-10T09:01:00Z", 2),
        run("AsBuild", "failure", "2026-11-10T09:00:00Z", "2026-11-10T09:01:00Z", 3),
        run("Build", "success", "2026-11-10T09:00:00Z", "2026-11-10T09:01:00Z", 4),
    ]
    statuses = [status("beta", "success", "2026-11-10T09:00:00Z")]
    expected = "AsBuild: failure; beta: success; Build: success; ci: success; zeta: success"
    assert cell(tmp_path, runs, statuses) == expected


def test_no_checks_at_all_says_so_and_never_passed(tmp_path: Path) -> None:
    assert cell(tmp_path, []) == NONE
    assert "passed" not in NONE


def test_a_direct_push_has_no_checks_read(tmp_path: Path) -> None:
    pushed = Change("acme/shop", "a1b2c3d", "pushed directly", parse(MERGED), {"login": "lee"}, {"sha": "a1b2c3d"})
    assert describe_checks(RepositoryList("acme/shop", [pushed]), tmp_path) == {
        "a1b2c3d": "checks not read for a direct push"
    }


def test_a_missing_saved_file_stops_with_a_plain_sentence(tmp_path: Path) -> None:
    cell(tmp_path, [])
    (tmp_path / "pr" / "11" / "statuses.json").unlink()
    change = Change("acme/shop", "#11", "pull request", parse(MERGED))
    with pytest.raises(Stop) as stop:
        describe_checks(RepositoryList("acme/shop", [change]), tmp_path)
    assert stop.value.message == (
        "The saved data for acme/shop is missing pr/11/statuses.json. Run collect again. No record was written."
    )


def test_saved_checks_of_the_wrong_shape_stop_with_a_plain_sentence(tmp_path: Path) -> None:
    with pytest.raises(Stop) as stop:
        cell(tmp_path, [{"name": "ci"}])
    assert stop.value.message == (
        "The saved data for acme/shop could not be read. Run collect again. No record was written."
    )


def test_entries_of_one_name_in_the_same_second_are_ordered_by_their_github_id(tmp_path: Path) -> None:
    """GitHub's times step by one second and it lists the newest first: elastic/elasticsearch #167931's `CLA` has
    `pending` and then `success` in one second (read 27 Nov 2026). The id gives the order they were posted in."""
    statuses = [
        status("CLA", "success", "2026-11-10T09:35:08Z", 7689),
        status("CLA", "pending", "2026-11-10T09:35:08Z", 6919),
    ]
    assert cell(tmp_path, [], statuses) == "CLA: success"
    rerun = run("ci", "success", "2026-11-10T09:00:00Z", "2026-11-10T09:05:00Z", 2)
    first = run("ci", "failure", "2026-11-10T09:00:00Z", "2026-11-10T09:02:00Z", 1)
    assert cell(tmp_path, [rerun, first]) == "ci: success"
    assert cell(tmp_path, [first, rerun]) == "ci: success"


def test_the_run_started_last_wins_even_when_an_earlier_one_ended_later(tmp_path: Path) -> None:
    slow = run("ci", "failure", "2026-11-10T09:00:00Z", "2026-11-10T09:50:00Z", 1)
    rerun = run("ci", "success", "2026-11-10T09:10:00Z", "2026-11-10T09:20:00Z", 2)
    assert cell(tmp_path, [slow, rerun]) == "ci: success"
    assert cell(tmp_path, [rerun, slow]) == "ci: success"


def test_statuses_are_read_by_time_whatever_the_order_they_are_saved_in(tmp_path: Path) -> None:
    older = status("deploy", "pending", "2026-11-10T09:00:00Z", 1)
    newer = status("deploy", "failure", "2026-11-10T09:20:00Z", 2)
    assert cell(tmp_path, [], [older, newer]) == "deploy: failure"
    assert cell(tmp_path, [], [newer, older]) == "deploy: failure"


def test_asbuild_is_sorted_by_its_name_like_any_other(tmp_path: Path) -> None:
    runs = [
        run("AsBuild", "success", "2026-11-10T09:00:00Z", "2026-11-10T09:01:00Z", 1),
        run("Analyze", "success", "2026-11-10T09:00:00Z", "2026-11-10T09:01:00Z", 2),
        run("aardvark", "failure", "2026-11-10T09:00:00Z", "2026-11-10T09:01:00Z", 3),
    ]
    assert cell(tmp_path, runs) == "aardvark: failure; Analyze: success; AsBuild: success"
