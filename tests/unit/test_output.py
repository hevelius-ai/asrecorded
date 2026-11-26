"""Writing changes.csv and the screen summary (design §1, §3 step 7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from asrecorded.changes import Change, RepositoryList
from asrecorded.errors import Stop
from asrecorded.output import write, write_changes
from asrecorded.settings import load
from asrecorded.times import parse


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
    path = write_changes(tmp_path / "record", [shop, joined])
    assert path == tmp_path / "record" / "changes.csv"
    assert path.read_bytes() == (
        b"repository,change,how,when\n"
        b"acme/shop,#11,pull request,2026-11-02T10:00:00Z\n"
        b"acme/shop,a000000,pushed directly,2026-11-09T10:00:00Z\n"
        b"acme/shop,b000000,pushed directly,2026-11-09T10:00:00Z\n"
        b"acme/joined,#2,pull request,2026-11-08T10:00:00Z\n"
    )
    assert sorted(p.name for p in path.parent.iterdir()) == ["changes.csv"]


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
    path = tmp_path / "record" / "changes.csv"
    assert lines == [
        "acme/shop: 0 changes (0 pull requests, 0 commits pushed directly)",
        f"Wrote {path}: 0 changes from 1 repository.",
    ]
    assert path.read_text(encoding="utf-8") == "repository,change,how,when\n"


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
