"""Writing changes.csv and the screen summary (design §1, §3 step 7)."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from asrecorded.changes import Change, RepositoryList
from asrecorded.errors import Stop
from asrecorded.output import changes_csv, write, write_files
from asrecorded.settings import load
from asrecorded.times import parse
from asrecorded.who import Who

HEADER = (
    "repository,change,how,when,builder,let_in_by,approvals,ai_shown,ai_trace,pattern,declared_agent_operated,checks\n"
)
ONE = Who("dana", "dana", "", "not shown", "", "One account", "")
FILES = {"changes.csv": b"rows\n", "record.json": b"{}\n", "record.md": b"# Record\n"}


def test_rows_are_sorted_by_repository_order_then_time_then_id(tmp_path: Path) -> None:
    joined = RepositoryList(
        "acme/joined",
        [Change("acme/joined", "#2", "pull request", parse("2026-11-08T10:00:00Z"))],
        [],
        [],
    )
    shop = RepositoryList(
        "acme/shop",
        [
            Change("acme/shop", "b000000", "pushed directly", parse("2026-11-09T10:00:00Z")),
            Change("acme/shop", "a000000", "pushed directly", parse("2026-11-09T10:00:00Z")),
            Change("acme/shop", "#11", "pull request", parse("2026-11-02T10:00:00Z")),
        ],
        [],
        [],
    )
    pushed = Who("no pull request: not shown", "pushed by lee", "", "not shown", "", "No pull request", "")
    details = {
        ("acme/shop", "#11"): Who("dana", "dana", "lee (on the merged version)", "not shown", "", "Two people", ""),
        ("acme/shop", "a000000"): pushed,
        ("acme/shop", "b000000"): pushed,
        ("acme/joined", "#2"): Who("bot", "bot", "", "yes", "declared agent-operated account", "One account", "yes"),
    }
    direct = "checks not read for a direct push"
    checks = {
        ("acme/shop", "#11"): "AsBuild: success; ci: failure",
        ("acme/shop", "a000000"): direct,
        ("acme/shop", "b000000"): direct,
        ("acme/joined", "#2"): "no checks ran on the merged version",
    }
    text = changes_csv([shop, joined], details, checks)
    assert text.encode() == HEADER.encode() + (
        b"acme/shop,#11,pull request,2026-11-02T10:00:00Z,dana,dana,lee (on the merged version),not shown,,"
        b"Two people,,AsBuild: success; ci: failure\n"
        b"acme/shop,a000000,pushed directly,2026-11-09T10:00:00Z,no pull request: not shown,pushed by lee,,"
        b"not shown,,No pull request,,checks not read for a direct push\n"
        b"acme/shop,b000000,pushed directly,2026-11-09T10:00:00Z,no pull request: not shown,pushed by lee,,"
        b"not shown,,No pull request,,checks not read for a direct push\n"
        b"acme/joined,#2,pull request,2026-11-08T10:00:00Z,bot,bot,,yes,declared agent-operated account,"
        b"One account,yes,no checks ran on the merged version\n"
    )


def settings_in(tmp_path: Path) -> object:
    path = tmp_path / "settings.toml"
    path.write_text(
        'repositories = ["acme/shop"]\nstart = "2026-11-01T00:00:00Z"\nend = "2026-12-01T00:00:00Z"\n',
        encoding="utf-8",
    )
    return load(path)


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_write_reads_the_data_folder_only_and_says_what_it_wrote(tmp_path: Path) -> None:
    folder = tmp_path / "data" / "acme__shop"
    save(folder / "repo.json", {"default_branch": "main", "created_at": "2026-10-01T00:00:00Z"})
    save(folder / "pulls.json", [])
    save(
        folder / "activity.json",
        [{"activity_type": "branch_creation", "before": "0", "after": "c", "timestamp": "2026-10-01T00:00:00Z"}],
    )
    save(folder / "main_commits.json", [])
    lines = write(settings_in(tmp_path))  # type: ignore[arg-type]
    output = tmp_path / "record"
    assert lines == [
        "acme/shop: 0 changes (0 pull requests, 0 commits pushed directly)",
        "acme/shop: One account 0 (0 declared agent-operated)",
        f"Wrote record.md, changes.csv and record.json in {output}: 0 changes from 1 repository.",
    ]
    assert (output / "changes.csv").read_text(encoding="utf-8") == HEADER
    assert sorted(x.name for x in output.iterdir()) == ["changes.csv", "record.json", "record.md"]
    record = (output / "record.md").read_text(encoding="utf-8")
    assert "- Changes: 0 (0 through a pull request, 0 pushed directly)" in record
    assert "## What was not covered\n\n- Nothing.\n" in record


def test_a_failed_write_removes_the_record_it_would_replace(tmp_path: Path) -> None:
    old = tmp_path / "record" / "record.md"
    old.parent.mkdir()
    old.write_text("an earlier record", encoding="utf-8")
    with pytest.raises(Stop) as stop:
        write(settings_in(tmp_path))  # type: ignore[arg-type]
    assert stop.value.message == (
        "The data folder has no saved repo.json for acme/shop. Run collect first. No record was written."
    )
    assert not old.exists()


def test_a_failed_write_with_no_earlier_record_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(Stop):
        write(settings_in(tmp_path))  # type: ignore[arg-type]
    assert not (tmp_path / "record").exists()


def test_a_write_that_fails_keeps_the_earlier_changes_file_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    earlier = tmp_path / "record" / "changes.csv"
    earlier.parent.mkdir()
    earlier.write_text("the earlier list\n", encoding="utf-8")

    def refuse(source: object, target: object) -> None:
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr("asrecorded.output.os.replace", refuse)
    with pytest.raises(Stop) as stop:
        write_files(tmp_path / "record", FILES)
    assert stop.value.message == (
        f"Cannot write {earlier}: Access is denied. Close any program that has it open, then run write again. "
        "No record was written."
    )
    assert earlier.read_text(encoding="utf-8") == "the earlier list\n"
    assert sorted(x.name for x in earlier.parent.iterdir()) == ["changes.csv"]


def test_an_output_that_names_a_file_gives_one_plain_sentence(tmp_path: Path) -> None:
    taken = tmp_path / "record"
    taken.write_text("a file, not a folder", encoding="utf-8")
    with pytest.raises(Stop) as stop:
        write_files(taken, FILES)
    assert stop.value.message.startswith(f"Cannot write {taken / 'changes.csv'}: ")
    assert stop.value.message.endswith("No record was written.")
    assert taken.read_text(encoding="utf-8") == "a file, not a folder"


def test_write_with_an_output_that_names_a_file_gives_one_plain_sentence(tmp_path: Path) -> None:
    folder = tmp_path / "data" / "acme__shop"
    save(folder / "repo.json", {"default_branch": "main", "created_at": "2026-10-01T00:00:00Z"})
    save(folder / "pulls.json", [])
    save(
        folder / "activity.json",
        [{"activity_type": "branch_creation", "before": "0", "after": "c", "timestamp": "2026-10-01T00:00:00Z"}],
    )
    save(folder / "main_commits.json", [])
    taken = tmp_path / "record"
    taken.write_text("a file, not a folder", encoding="utf-8")
    with pytest.raises(Stop) as stop:  # on Linux, removing record/record.md raises NotADirectoryError
        write(settings_in(tmp_path))  # type: ignore[arg-type]
    assert stop.value.message.startswith(f"Cannot write {taken / 'changes.csv'}: ")
    assert taken.read_text(encoding="utf-8") == "a file, not a folder"


BANNED = re.compile(r"\b(approved|compliant|certified|secure|safe|audited|passed)\b|no ai", re.IGNORECASE)


def test_logins_come_only_from_authenticated_actions_and_the_wording_rules_hold(tmp_path: Path) -> None:
    """Design section 5: no login appears that is not an opener, merger, reviewer, auto-merge enabler or pusher in
    the saved data. The commit fields hold `claude`, whom GitHub links to an author name; it is never printed."""
    folder = tmp_path / "data" / "acme__shop"
    root, head, merge = "1" * 40, "2" * 40, "3" * 40
    dana = {"login": "dana", "id": 1001, "type": "User"}
    lee = {"login": "lee", "id": 1002, "type": "User"}
    claude = {"login": "claude", "id": 81847, "type": "User"}
    merged = "2026-11-05T10:00:00Z"
    save(folder / "repo.json", {"default_branch": "main", "created_at": "2026-10-01T00:00:00Z"})
    save(
        folder / "pulls.json", [{"number": 5, "merged_at": merged, "merge_commit_sha": merge, "base": {"ref": "main"}}]
    )
    save(
        folder / "activity.json",
        [
            {"activity_type": "branch_creation", "before": "0", "after": root, "timestamp": "2026-10-01T00:00:00Z"},
            {"activity_type": "pr_merge", "before": root, "after": merge, "timestamp": merged, "actor": dana},
        ],
    )
    save(folder / "main_commits.json", [])
    piece = {
        "sha": head,
        "parents": [{"sha": root}],
        "commit": {
            "message": "work\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n",
            "author": {"name": "Claude", "email": "noreply@anthropic.com"},
        },
        "author": claude,
        "committer": claude,
    }
    save(folder / "pr" / "5" / "commits.json", [piece])
    pull = {"number": 5, "commits": 1, "merged_at": merged, "head": {"sha": head}, "user": dana, "merged_by": dana}
    save(folder / "pr" / "5" / "pull.json", pull)
    approval = {"id": 9, "user": lee, "state": "APPROVED", "commit_id": head, "submitted_at": "2026-11-05T09:00:00Z"}
    save(folder / "pr" / "5" / "reviews.json", [approval])
    save(folder / "pr" / "5" / "timeline.json", [{"event": "merged", "actor": dana, "created_at": merged}])
    save(folder / "pr" / "5" / "check_runs.json", [])
    save(folder / "pr" / "5" / "statuses.json", [])
    lines = write(settings_in(tmp_path))  # type: ignore[arg-type]
    path = tmp_path / "record" / "changes.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [(r["builder"], r["let_in_by"], r["approvals"], r["ai_trace"]) for r in rows] == [
        ("dana", "dana", "lee (on the merged version)", "commit marker: Claude (Anthropic)")
    ]
    logins = {r["builder"] for r in rows} | {r["let_in_by"] for r in rows}
    logins |= {a.split(" (on ")[0] for r in rows for a in r["approvals"].split("; ") if a}
    assert logins <= {"dana", "lee"}
    text = "\n".join(lines) + "".join(
        (tmp_path / "record" / name).read_text(encoding="utf-8") for name in ("changes.csv", "record.json", "record.md")
    )
    assert "@" not in text
    assert not BANNED.search(text)
    assert "claude " not in text.lower().replace("claude (anthropic)", "")


def test_the_three_files_are_renamed_only_when_all_are_written_and_record_md_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    renamed: list[str] = []
    real = os.replace

    def watch(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        if not renamed:  # before the first rename, all three are written in full
            listed = sorted(x.name for x in Path(source).parent.iterdir())
            assert listed == ["changes.csv.tmp", "record.json.tmp", "record.md.tmp"]
        renamed.append(Path(target).name)
        real(source, target)

    monkeypatch.setattr("asrecorded.output.os.replace", watch)
    write_files(tmp_path / "record", FILES)
    assert renamed == ["changes.csv", "record.json", "record.md"]
    assert (tmp_path / "record" / "record.md").read_bytes() == b"# Record\n"
    assert sorted(x.name for x in (tmp_path / "record").iterdir()) == ["changes.csv", "record.json", "record.md"]


def test_a_write_whose_record_md_cannot_be_renamed_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    real = os.replace

    def refuse_md(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        if Path(target).name == "record.md":
            raise PermissionError(13, "Access is denied")
        real(source, target)

    monkeypatch.setattr("asrecorded.output.os.replace", refuse_md)
    with pytest.raises(Stop) as stop:
        write_files(tmp_path / "record", FILES)
    assert stop.value.message.startswith(f"Cannot write {tmp_path / 'record' / 'record.md'}: Access is denied.")
    assert sorted(x.name for x in (tmp_path / "record").iterdir()) == ["changes.csv", "record.json"]


def test_a_direct_push_is_listed_with_its_checks_named_as_not_read(tmp_path: Path) -> None:
    folder = tmp_path / "data" / "acme__shop"
    root, pushed = "1" * 40, "a1b2c3d" + "4" * 33
    lee = {"login": "lee", "id": 1002, "type": "User"}
    save(folder / "repo.json", {"default_branch": "main", "created_at": "2026-10-01T00:00:00Z"})
    save(folder / "pulls.json", [])
    save(
        folder / "activity.json",
        [
            {
                "activity_type": "branch_creation",
                "before": "0" * 40,
                "after": root,
                "timestamp": "2026-10-01T00:00:00Z",
            },
            {
                "activity_type": "push",
                "before": root,
                "after": pushed,
                "timestamp": "2026-11-09T10:00:00Z",
                "actor": lee,
            },
        ],
    )
    save(folder / "main_commits.json", [])
    piece = {"sha": pushed, "parents": [{"sha": root}], "commit": {"message": "work", "author": {"name": "lee"}}}
    save(folder / "push" / f"{root}...{pushed}.json", [piece])
    write(settings_in(tmp_path))  # type: ignore[arg-type]
    record = (tmp_path / "record" / "record.md").read_text(encoding="utf-8")
    assert "- acme/shop: not covered: checks were not read for 1 commit pushed directly" in record
    assert f"[a1b2c3d](https://github.com/acme/shop/commit/{pushed})" in record
    assert "| no pull request: not shown | pushed by lee |" in record


def test_a_record_md_that_cannot_be_removed_stops_before_anything_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "record"
    output.mkdir()
    for name in ("changes.csv", "record.json", "record.md"):
        (output / name).write_bytes(b"earlier " + name.encode())
    real = Path.unlink

    def locked(self: Path, missing_ok: bool = False) -> None:
        if self.name == "record.md":
            raise PermissionError(13, "Access is denied")
        real(self, missing_ok)

    monkeypatch.setattr(Path, "unlink", locked)
    with pytest.raises(Stop) as stop:
        write_files(output, FILES)
    assert stop.value.message == (
        f"Cannot replace {output / 'record.md'}: Access is denied. Close any program that has it open, then run "
        "write again. The earlier record was kept whole. No record was written."
    )
    for name in ("changes.csv", "record.json", "record.md"):
        assert (output / name).read_bytes() == b"earlier " + name.encode()
    assert sorted(x.name for x in output.iterdir()) == ["changes.csv", "record.json", "record.md"]


def test_a_failed_write_whose_record_md_cannot_be_removed_gives_one_plain_sentence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = tmp_path / "record" / "record.md"
    old.parent.mkdir()
    old.write_text("an earlier record", encoding="utf-8")
    real = Path.unlink

    def locked(self: Path, missing_ok: bool = False) -> None:
        if self.name == "record.md":
            raise PermissionError(13, "Access is denied")
        real(self, missing_ok)

    monkeypatch.setattr(Path, "unlink", locked)
    with pytest.raises(Stop) as stop:
        write(settings_in(tmp_path))  # type: ignore[arg-type]
    assert stop.value.message == (
        "The data folder has no saved repo.json for acme/shop. Run collect first. No record was written."
    )


def one_pull_request(tmp_path: Path, merger: str, approver: str = "lee") -> None:
    """Data for acme/shop: pull request #5, opened by dana, merged by `merger`, approved by `approver`."""
    folder = tmp_path / "data" / "acme__shop"
    root, head, merge = "1" * 40, "2" * 40, "3" * 40
    dana = {"login": "dana", "id": 1001, "type": "User"}
    merged = "2026-11-05T10:00:00Z"
    save(folder / "repo.json", {"default_branch": "main", "created_at": "2026-10-01T00:00:00Z"})
    pulls = [{"number": 5, "merged_at": merged, "merge_commit_sha": merge, "base": {"ref": "main"}}]
    save(folder / "pulls.json", pulls)
    save(
        folder / "activity.json",
        [
            {"activity_type": "branch_creation", "before": "0", "after": root, "timestamp": "2026-10-01T00:00:00Z"},
            {"activity_type": "pr_merge", "before": root, "after": merge, "timestamp": merged, "actor": dana},
        ],
    )
    save(folder / "main_commits.json", [])
    piece = {"sha": head, "parents": [{"sha": root}], "commit": {"message": "work", "author": {"name": "dana"}}}
    save(folder / "pr" / "5" / "commits.json", [piece])
    by = {"login": merger, "id": 1003, "type": "User"}
    pull = {"number": 5, "commits": 1, "merged_at": merged, "head": {"sha": head}, "user": dana, "merged_by": by}
    save(folder / "pr" / "5" / "pull.json", pull)
    review = {
        "id": 9,
        "user": {"login": approver, "id": 1004, "type": "User"},
        "state": "APPROVED",
        "commit_id": head,
        "submitted_at": "2026-11-05T09:00:00Z",
    }
    save(folder / "pr" / "5" / "reviews.json", [review])
    save(folder / "pr" / "5" / "timeline.json", [{"event": "merged", "actor": by, "created_at": merged}])
    save(folder / "pr" / "5" / "check_runs.json", [])
    save(folder / "pr" / "5" / "statuses.json", [])


@pytest.mark.parametrize(
    ("merger", "approver", "message"),
    [
        (
            "secure-lee",
            "lee",
            'acme/shop #5: the login "secure-lee" holds the word "secure", which a record never uses. '
            "No record was written.",
        ),
        (
            "lee",
            "approved",
            'acme/shop #5: the login "approved" holds the word "approved", which a record never uses. '
            "No record was written.",
        ),
    ],
)
def test_a_login_the_record_would_print_with_a_banned_word_stops_the_write(
    tmp_path: Path, merger: str, approver: str, message: str
) -> None:
    """Decision S4-W2 (the owner's choice PR14-1 C): such a record is refused, never written with the word."""
    one_pull_request(tmp_path, merger, approver)
    old = tmp_path / "record" / "record.md"
    old.parent.mkdir()
    old.write_text("an earlier record", encoding="utf-8")
    with pytest.raises(Stop) as stop:
        write(settings_in(tmp_path))  # type: ignore[arg-type]
    assert stop.value.message == message
    assert not old.exists()
    assert sorted(x.name for x in old.parent.iterdir()) == []


def test_a_login_that_rewrote_history_with_a_banned_word_stops_the_write(tmp_path: Path) -> None:
    one_pull_request(tmp_path, "lee")
    folder = tmp_path / "data" / "acme__shop"
    activity = json.loads((folder / "activity.json").read_text(encoding="utf-8"))
    merge, again = "3" * 40, "4" * 40
    ops = {"login": "safe-ops", "id": 1009, "type": "User"}
    activity.append(
        {
            "activity_type": "force_push",
            "before": merge,
            "after": again,
            "timestamp": "2026-11-06T10:00:00Z",
            "actor": ops,
        }
    )
    save(folder / "activity.json", activity)
    save(folder / "push" / f"{merge}...{again}.json", [{"sha": again, "parents": [{"sha": merge}]}])
    with pytest.raises(Stop) as stop:
        write(settings_in(tmp_path))  # type: ignore[arg-type]
    assert stop.value.message == (
        'acme/shop: the login "safe-ops" holds the word "safe", which a record never uses. No record was written.'
    )


def test_logins_with_no_banned_word_are_written(tmp_path: Path) -> None:
    one_pull_request(tmp_path, "lee", "safely-reviewed")
    folder = tmp_path / "data" / "acme__shop"
    # auto-merge switched on by an account GitHub does not show, and a history rewrite by a login with no banned word
    timeline = json.loads((folder / "pr" / "5" / "timeline.json").read_text(encoding="utf-8"))
    save(folder / "pr" / "5" / "timeline.json", [{"event": "auto_merge_enabled", "actor": None}, *timeline])
    activity = json.loads((folder / "activity.json").read_text(encoding="utf-8"))
    merge, again = "3" * 40, "4" * 40
    lee = {"login": "lee", "id": 1002, "type": "User"}
    activity.append(
        {
            "activity_type": "force_push",
            "before": merge,
            "after": again,
            "timestamp": "2026-11-06T10:00:00Z",
            "actor": lee,
        }
    )
    save(folder / "activity.json", activity)
    save(folder / "push" / f"{merge}...{again}.json", [{"sha": again, "parents": [{"sha": merge}]}])
    write(settings_in(tmp_path))  # type: ignore[arg-type]
    record = (tmp_path / "record" / "record.md").read_text(encoding="utf-8")
    assert "safely-reviewed (on the merged version)" in record
    assert "auto-merge switched on (account not shown)" in record
    assert "- acme/shop: history rewritten on 2026-11-06 at 10:00 UTC by lee, 1 commit brought in" in record
