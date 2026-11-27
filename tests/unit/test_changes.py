"""The list of changes, built from saved data only (design §3 step 1)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from asrecorded.changes import Change, RepositoryList, Rewrite, list_changes, summary_lines
from asrecorded.errors import Stop
from asrecorded.times import iso, parse

START, END = parse("2026-11-01T00:00:00Z"), parse("2026-12-01T00:00:00Z")
ZERO = "0" * 40
OUTSIDE = "2026-10-01T00:00:00Z"


def h(n: int) -> str:
    return f"{n:07x}" + "0" * 33


def commit(n: int, parents: list[int], date: str = "2026-11-05T10:00:00Z") -> dict[str, Any]:
    return {"sha": h(n), "parents": [{"sha": h(p)} for p in parents], "commit": {"committer": {"date": date}}}


def entry(kind: str, before: str, after: str, when: str, actor: str = "lee") -> dict[str, Any]:
    return {"activity_type": kind, "before": before, "after": after, "timestamp": when, "actor": {"login": actor}}


def pull(n: int, merged_at: str | None, merge: int, base: str = "main") -> dict[str, Any]:
    return {"number": n, "merged_at": merged_at, "merge_commit_sha": h(merge), "base": {"ref": base}}


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def repository(
    tmp_path: Path,
    *,
    pulls: list[dict[str, Any]],
    activity: list[dict[str, Any]],
    main: list[dict[str, Any]],
    details: dict[int, tuple[int, list[dict[str, Any]]]] | None = None,
    pushes: dict[int, list[dict[str, Any]]] | None = None,
    push_files: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
    created: str = OUTSIDE,
) -> Path:
    folder = tmp_path / "acme__shop"
    save(folder / "repo.json", {"default_branch": "main", "created_at": created})
    save(folder / "pulls.json", pulls)
    save(folder / "activity.json", activity)
    save(folder / "main_commits.json", main)
    for n, (count, commits) in (details or {}).items():
        save(folder / "pr" / str(n) / "pull.json", {"number": n, "commits": count})
        save(folder / "pr" / str(n) / "commits.json", commits)
    for e in activity:  # one saved reply per push, named by its `before` and `after`
        for n, commits in (pushes or {}).items():
            if e["after"] == h(n):
                save(folder / "push" / f"{e['before']}...{e['after']}.json", commits)
    for (before, after), commits in (push_files or {}).items():
        save(folder / "push" / f"{before}...{after}.json", commits)
    return folder


def shown(result: RepositoryList) -> list[tuple[str, str, str]]:
    return [(c.change, c.how, iso(c.when)) for c in result.changes]


def test_pull_requests_and_direct_pushes_of_the_period(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[
            pull(17, "2026-12-01T00:00:00Z", 403),
            pull(20, "2026-11-10T10:00:00Z", 503, base="release"),
            pull(19, None, 603),
            pull(11, "2026-11-02T10:00:00Z", 103),
            pull(12, "2026-11-01T00:00:00Z", 203),
        ],
        activity=[
            entry("pr_merge", h(301), h(403), "2026-12-01T00:00:00Z"),
            entry("push", h(103), h(301), "2026-11-09T10:00:00Z"),
            entry("pr_merge", h(203), h(103), "2026-11-02T10:00:00Z"),
            entry("pr_merge", h(1), h(203), "2026-11-01T00:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[
            commit(403, [301], "2026-12-01T00:00:00Z"),
            commit(301, [103], "2026-11-09T10:00:00Z"),
            commit(103, [203, 102], "2026-11-02T10:00:00Z"),
            commit(102, [101]),
            commit(101, [203]),
            commit(203, [1], "2026-11-01T00:00:00Z"),
            commit(1, [], OUTSIDE),
        ],
        details={11: (2, [commit(101, [203]), commit(102, [101])]), 12: (1, [commit(201, [1])])},
        pushes={301: [commit(301, [103])]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [
        ("#12", "pull request", "2026-11-01T00:00:00Z"),
        ("#11", "pull request", "2026-11-02T10:00:00Z"),
        (h(301)[:7], "pushed directly", "2026-11-09T10:00:00Z"),
    ]
    assert result.rewrites == []
    assert result.not_covered == []
    assert summary_lines(result) == ["acme/shop: 3 changes (2 pull requests, 1 commit pushed directly)"]


def test_a_merge_push_leaves_out_the_branch_and_keeps_the_main_line(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(5, "2026-11-05T10:00:00Z", 103)],
        activity=[
            entry("push", h(1), h(103), "2026-11-05T10:00:00Z", actor="merge-bot"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(103, [201, 102]), commit(201, [1]), commit(102, [101]), commit(101, [1]), commit(1, [], OUTSIDE)],
        details={5: (251, [commit(101, [1])])},
        pushes={103: [commit(201, [1]), commit(101, [1]), commit(102, [101]), commit(103, [201, 102])]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [
        ("#5", "pull request", "2026-11-05T10:00:00Z"),
        (h(201)[:7], "pushed directly", "2026-11-05T10:00:00Z"),
    ]
    assert result.not_covered == ["acme/shop: not covered: #5 has 251 commits, and GitHub lists only 250 of them"]


def test_a_rewrite_is_listed_on_its_own(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(1, "2026-11-05T10:00:00Z", 103)],
        activity=[
            entry("force_push", h(103), h(303), "2026-11-20T09:00:00Z"),
            entry("pr_merge", h(1), h(103), "2026-11-05T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(303, [302]), commit(302, [301]), commit(301, [1]), commit(1, [], OUTSIDE)],
        details={1: (2, [])},
        pushes={303: [commit(301, [1]), commit(302, [301]), commit(303, [302])]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [("#1", "pull request", "2026-11-05T10:00:00Z")]
    assert result.rewrites == [Rewrite("acme/shop", parse("2026-11-20T09:00:00Z"), "lee", 3)]
    assert summary_lines(result) == [
        "acme/shop: 1 change (1 pull request, 0 commits pushed directly)",
        "acme/shop: history rewritten on 2026-11-20 at 09:00 UTC by lee, 3 commits brought in",
    ]


def test_a_first_push_lists_its_commits_once(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[
            entry("push", h(2), h(3), "2026-11-04T10:00:00Z"),
            entry("branch_creation", ZERO, h(2), "2026-11-03T10:00:00Z"),
        ],
        main=[commit(3, [2]), commit(2, [1]), commit(1, [])],
        pushes={2: [commit(1, []), commit(2, [1])], 3: [commit(2, [1]), commit(3, [2])]},
        created="2026-11-03T10:00:00Z",
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [
        (h(1)[:7], "pushed directly", "2026-11-03T10:00:00Z"),
        (h(2)[:7], "pushed directly", "2026-11-03T10:00:00Z"),
        (h(3)[:7], "pushed directly", "2026-11-04T10:00:00Z"),
    ]
    assert result.not_covered == []


def test_a_main_line_commit_no_entry_explains_is_not_covered(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(7, "2026-11-06T10:00:00Z", 103)],
        activity=[
            entry("pr_merge", h(99), h(103), "2026-11-06T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(103, [5]), commit(5, [1]), commit(1, [], OUTSIDE)],
        details={7: (1, [])},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [("#7", "pull request", "2026-11-06T10:00:00Z")]
    assert result.not_covered == [
        f"acme/shop: not covered: commit {h(5)[:7]} on the main line, dated 2026-11-05 at 10:00 UTC, "
        "is not explained by the activity history"
    ]


def test_an_activity_history_that_starts_late_is_not_covered(tmp_path: Path) -> None:
    folder = repository(tmp_path, pulls=[], activity=[entry("pr_merge", h(1), h(2), "2026-11-10T10:00:00Z")], main=[])
    assert list_changes("acme/shop", folder, START, END).not_covered == [
        "acme/shop: not covered: the activity history reaches back only to 2026-11-10 at 10:00 UTC, "
        "after the period's start"
    ]


def test_a_repository_created_in_the_period_is_covered_from_its_start(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[entry("pr_merge", h(1), h(2), "2026-11-10T10:00:00Z")],
        main=[],
        created="2026-11-10T09:00:00Z",
    )
    assert list_changes("acme/shop", folder, START, END).not_covered == []


def test_an_empty_activity_history_is_not_covered(tmp_path: Path) -> None:
    folder = repository(tmp_path, pulls=[], activity=[], main=[])
    assert list_changes("acme/shop", folder, START, END).not_covered == [
        "acme/shop: not covered: GitHub's activity history holds no entry for the default branch"
    ]


@pytest.mark.parametrize("name", ["repo.json", "pulls.json", "activity.json", "main_commits.json"])
def test_a_data_folder_without_a_required_file_is_refused(tmp_path: Path, name: str) -> None:
    folder = repository(tmp_path, pulls=[], activity=[], main=[])
    (folder / name).unlink()
    with pytest.raises(Stop) as stop:
        list_changes("acme/shop", folder, START, END)
    assert stop.value.message == (
        f"The data folder has no saved {name} for acme/shop. Run collect first. No record was written."
    )


def test_a_missing_detail_file_is_named(tmp_path: Path) -> None:
    folder = repository(tmp_path, pulls=[pull(11, "2026-11-02T10:00:00Z", 103)], activity=[], main=[])
    with pytest.raises(Stop) as stop:
        list_changes("acme/shop", folder, START, END)
    assert stop.value.message == (
        "The saved data for acme/shop is missing pr/11/pull.json. Run collect again. No record was written."
    )


def test_saved_data_of_an_unexpected_shape_is_refused(tmp_path: Path) -> None:
    folder = repository(tmp_path, pulls=[{"number": 11, "merged_at": "yesterday"}], activity=[], main=[])
    with pytest.raises(Stop) as stop:
        list_changes("acme/shop", folder, START, END)
    assert (
        stop.value.message
        == "The saved data for acme/shop could not be read. Run collect again. No record was written."
    )


@pytest.mark.parametrize("loop", [[commit(1, [1])], [commit(3, [2, 1]), commit(2, [1]), commit(1, [3])]])
def test_saved_commits_that_loop_back_on_themselves_are_refused(tmp_path: Path, loop: list[dict[str, Any]]) -> None:
    folder = repository(tmp_path, pulls=[], activity=[entry("branch_creation", ZERO, h(1), OUTSIDE)], main=loop)
    with pytest.raises(Stop) as stop:
        list_changes("acme/shop", folder, START, END)
    assert (
        stop.value.message
        == "The saved data for acme/shop could not be read. Run collect again. No record was written."
    )


def test_a_parent_that_is_also_a_grandparent_is_walked_once(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[
            entry("push", h(1), h(3), "2026-11-12T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(3, [1, 2]), commit(2, [1]), commit(1, [], OUTSIDE)],
        pushes={3: [commit(2, [1]), commit(3, [1, 2])]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [
        (h(2)[:7], "pushed directly", "2026-11-12T10:00:00Z"),
        (h(3)[:7], "pushed directly", "2026-11-12T10:00:00Z"),
    ]
    assert result.not_covered == []


def test_one_of_each_is_counted_in_the_singular() -> None:
    when = datetime.fromisoformat("2026-11-20T09:00:00Z")
    result = RepositoryList(
        "acme/shop",
        [Change("acme/shop", "a1b2c3d", "pushed directly", when)],
        [Rewrite("acme/shop", when, "lee", 1)],
        ["acme/shop: not covered: example"],
    )
    assert summary_lines(result) == [
        "acme/shop: 1 change (0 pull requests, 1 commit pushed directly)",
        "acme/shop: history rewritten on 2026-11-20 at 09:00 UTC by lee, 1 commit brought in",
        "acme/shop: not covered: example",
    ]


def test_a_merge_queue_merge_is_explained_by_the_activity_history(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(8, "2026-11-07T10:00:00Z", 103)],
        activity=[
            entry("merge_queue_merge", h(1), h(103), "2026-11-07T10:00:00Z", actor="merge-queue"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(103, [1, 102]), commit(102, [1]), commit(1, [], OUTSIDE)],
        details={8: (1, [commit(102, [1])])},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [("#8", "pull request", "2026-11-07T10:00:00Z")]
    assert result.not_covered == []


def test_a_pull_request_saved_twice_is_listed_once(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(11, "2026-11-02T10:00:00Z", 103), pull(11, "2026-11-02T10:00:00Z", 103)],
        activity=[
            entry("pr_merge", h(1), h(103), "2026-11-02T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(103, [1]), commit(1, [], OUTSIDE)],
        details={11: (1, [])},
    )
    assert shown(list_changes("acme/shop", folder, START, END)) == [("#11", "pull request", "2026-11-02T10:00:00Z")]


def test_a_commit_pushed_after_the_period_is_not_called_not_covered(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[
            entry("push", h(2), h(3), "2026-12-01T00:00:00Z"),
            entry("push", h(1), h(2), "2026-11-10T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(3, [2], "2026-11-30T10:00:00Z"), commit(2, [1], "2026-11-10T10:00:00Z"), commit(1, [], OUTSIDE)],
        pushes={2: [commit(2, [1])]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [(h(2)[:7], "pushed directly", "2026-11-10T10:00:00Z")]
    assert result.not_covered == []


def test_a_push_after_the_period_that_brought_two_commits_explains_both(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[
            entry("push", h(2), h(4), "2026-12-01T05:00:00Z"),
            entry("push", h(1), h(2), "2026-11-10T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[
            commit(4, [3], "2026-11-30T23:55:00Z"),
            commit(3, [2], "2026-11-30T23:50:00Z"),
            commit(2, [1], "2026-11-10T10:00:00Z"),
            commit(1, [], OUTSIDE),
        ],
        pushes={2: [commit(2, [1])]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [(h(2)[:7], "pushed directly", "2026-11-10T10:00:00Z")]
    assert result.not_covered == []


def test_a_git_pull_merge_pushed_after_the_period_explains_its_local_commit(tmp_path: Path) -> None:
    # `git pull` merges the branch into the local commit: the local commit is the merge's first parent, the pushed
    # branch's `before` its second, so `before` is not on the merge's first-parent line.
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[
            entry("push", h(2), h(4), "2026-12-01T00:05:00Z"),
            entry("push", h(1), h(2), "2026-11-10T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[
            commit(4, [3, 2], "2026-12-01T00:04:00Z"),
            commit(3, [1], "2026-11-30T23:50:00Z"),
            commit(2, [1], "2026-11-10T10:00:00Z"),
            commit(1, [], OUTSIDE),
        ],
        pushes={2: [commit(2, [1])]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [(h(2)[:7], "pushed directly", "2026-11-10T10:00:00Z")]
    assert result.not_covered == []


def test_a_branch_first_pushed_after_the_period_explains_what_it_brought(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[entry("branch_creation", ZERO, h(3), "2026-12-01T00:05:00Z")],
        main=[
            commit(3, [2, 1], "2026-11-30T23:55:00Z"),
            commit(2, [], "2026-11-30T23:50:00Z"),
            commit(1, [9], "2026-11-30T23:40:00Z"),  # its parent was not saved: the walk stops there
        ],
        created="2026-11-30T23:00:00Z",
    )
    assert list_changes("acme/shop", folder, START, END).not_covered == []


def test_a_merge_pushed_after_the_period_explains_only_what_its_before_did_not_hold(tmp_path: Path) -> None:
    # The late push brought 4, 3 and 6. Commit 2 was already on `main` at its `before`, and no entry brought it in.
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[
            entry("push", h(2), h(4), "2026-12-01T00:05:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[
            commit(4, [2, 3], "2026-12-01T00:04:00Z"),
            commit(3, [6], "2026-11-30T23:50:00Z"),
            commit(6, [1], "2026-11-29T10:00:00Z"),
            commit(2, [1], "2026-11-10T10:00:00Z"),
            commit(1, [], OUTSIDE),
        ],
    )
    assert list_changes("acme/shop", folder, START, END).not_covered == [
        f"acme/shop: not covered: commit {h(2)[:7]} on the main line, dated 2026-11-10 at 10:00 UTC, "
        "is not explained by the activity history"
    ]


def test_a_push_undone_by_a_force_push_back_counts_what_each_brought(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[
            entry("force_push", h(3), h(2), "2026-11-20T09:00:00Z"),
            entry("push", h(2), h(3), "2026-11-10T10:00:00Z"),
            entry("push", h(1), h(2), "2026-11-05T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(2, [1]), commit(1, [], OUTSIDE)],
        push_files={(h(1), h(2)): [commit(2, [1])], (h(2), h(3)): [commit(3, [2])], (h(3), h(2)): []},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [
        (h(2)[:7], "pushed directly", "2026-11-05T10:00:00Z"),
        (h(3)[:7], "pushed directly", "2026-11-10T10:00:00Z"),
    ]
    assert summary_lines(result)[1] == (
        "acme/shop: history rewritten on 2026-11-20 at 09:00 UTC by lee, 0 commits brought in"
    )


def test_a_fast_forward_merge_push_lists_only_the_pull_request(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(9, "2026-11-08T10:00:00Z", 3)],
        activity=[
            entry("push", h(1), h(3), "2026-11-08T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(3, [2]), commit(2, [1]), commit(1, [], OUTSIDE)],
        details={9: (2, [commit(2, [1]), commit(3, [2])])},
        pushes={3: [commit(2, [1]), commit(3, [2])]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [("#9", "pull request", "2026-11-08T10:00:00Z")]
    assert result.not_covered == []


def test_a_rebase_merge_brings_in_its_whole_range(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(4, "2026-11-04T10:00:00Z", 13)],
        activity=[
            entry("branch_creation", ZERO, h(13), "2026-11-06T10:00:00Z"),
            entry("pr_merge", h(1), h(13), "2026-11-04T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(13, [12]), commit(12, [11]), commit(11, [1]), commit(1, [], OUTSIDE)],
        details={4: (3, [])},
        pushes={13: [commit(11, [1]), commit(12, [11]), commit(13, [12])]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [("#4", "pull request", "2026-11-04T10:00:00Z")]
    assert result.not_covered == []


def test_a_push_at_the_period_start_is_listed_and_250_commits_are_all_listed(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(6, "2026-11-02T10:00:00Z", 103)],
        activity=[
            entry("pr_merge", h(2), h(103), "2026-11-02T10:00:00Z"),
            entry("push", h(1), h(2), "2026-11-01T00:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(103, [2]), commit(2, [1], "2026-11-01T00:00:00Z"), commit(1, [], OUTSIDE)],
        details={6: (250, [])},
        pushes={2: [commit(2, [1], "2026-11-01T00:00:00Z")]},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [
        (h(2)[:7], "pushed directly", "2026-11-01T00:00:00Z"),
        ("#6", "pull request", "2026-11-02T10:00:00Z"),
    ]
    assert result.not_covered == []


def test_a_main_line_commit_above_the_last_entry_is_not_covered(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(11, "2026-11-02T10:00:00Z", 103)],
        activity=[
            entry("pr_merge", h(1), h(103), "2026-11-02T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[
            commit(5, [103], "2026-11-10T10:00:00Z"),
            commit(103, [1, 102]),
            commit(102, [1]),
            commit(1, [], OUTSIDE),
        ],
        details={11: (1, [commit(102, [1])])},
    )
    assert list_changes("acme/shop", folder, START, END).not_covered == [
        f"acme/shop: not covered: commit {h(5)[:7]} on the main line, dated 2026-11-10 at 10:00 UTC, "
        "is not explained by the activity history"
    ]


def test_a_rewrite_after_the_period_end_is_named_in_place_of_the_cross_check(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[pull(11, "2026-11-02T10:00:00Z", 103)],
        activity=[
            entry("force_push", h(103), h(303), "2026-12-02T09:00:00Z"),
            entry("pr_merge", h(1), h(103), "2026-11-02T10:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[
            commit(303, [302], "2026-11-15T10:00:00Z"),
            commit(302, [1], "2026-11-15T10:00:00Z"),
            commit(1, [], OUTSIDE),
        ],
        details={11: (1, [])},
    )
    result = list_changes("acme/shop", folder, START, END)
    assert shown(result) == [("#11", "pull request", "2026-11-02T10:00:00Z")]
    assert result.rewrites == []
    assert result.not_covered == [
        "acme/shop: not covered: history was rewritten after the period's end, on 2026-12-02 at 09:00 UTC, "
        "so the main line was not cross-checked"
    ]


def test_a_rewrite_stamped_at_the_period_end_is_named(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[
            entry("force_push", h(2), h(3), "2026-12-01T00:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(3, [1], "2026-11-15T10:00:00Z"), commit(1, [], OUTSIDE)],
    )
    result = list_changes("acme/shop", folder, START, END)
    assert result.rewrites == []
    assert result.not_covered == [
        "acme/shop: not covered: history was rewritten after the period's end, on 2026-12-01 at 00:00 UTC, "
        "so the main line was not cross-checked"
    ]


def test_the_first_of_several_rewrites_after_the_period_end_is_named(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[
            entry("force_push", h(4), h(5), "2026-12-03T09:00:00Z"),
            entry("force_push", h(2), h(4), "2026-12-04T09:00:00Z"),
            entry("force_push", h(1), h(2), "2026-12-02T09:00:00Z"),
            entry("branch_creation", ZERO, h(1), OUTSIDE),
        ],
        main=[commit(5, [1], "2026-11-15T10:00:00Z"), commit(1, [], OUTSIDE)],
    )
    assert list_changes("acme/shop", folder, START, END).not_covered == [
        "acme/shop: not covered: history was rewritten after the period's end, on 2026-12-02 at 09:00 UTC, "
        "so the main line was not cross-checked"
    ]


def test_the_cross_check_counts_the_period_start_in_and_the_end_out(tmp_path: Path) -> None:
    folder = repository(
        tmp_path,
        pulls=[],
        activity=[entry("branch_creation", ZERO, h(1), OUTSIDE)],
        main=[
            commit(7, [6], "2026-12-01T00:00:00Z"),
            commit(6, [1], "2026-11-01T00:00:00Z"),
            commit(1, [], OUTSIDE),
        ],
    )
    assert list_changes("acme/shop", folder, START, END).not_covered == [
        f"acme/shop: not covered: commit {h(6)[:7]} on the main line, dated 2026-11-01 at 00:00 UTC, "
        "is not explained by the activity history"
    ]


def test_an_activity_history_that_starts_at_the_period_start_is_covered(tmp_path: Path) -> None:
    folder = repository(tmp_path, pulls=[], activity=[entry("pr_merge", h(1), h(2), "2026-11-01T00:00:00Z")], main=[])
    assert list_changes("acme/shop", folder, START, END).not_covered == []
