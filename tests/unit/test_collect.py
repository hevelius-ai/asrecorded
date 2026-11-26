"""Collect saves GitHub's raw replies, and swaps the data folder in only when every repository is complete."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from asrecorded import github
from asrecorded.collect import collect
from asrecorded.errors import Stop
from asrecorded.settings import load

ZERO = "0" * 40


def fake_pages(answers: dict[str, Any], calls: list[str]) -> Callable[[str], list[Any]]:
    def pages(path: str) -> list[Any]:
        calls.append(path)
        key = path.split("?", 1)[0]
        if key not in answers:
            raise github.Refused(path, "Not Found")
        answer = answers[key]
        if isinstance(answer, github.Refused):
            raise answer
        return [answer]

    return pages


def entry(kind: str, before: str, after: str, when: str) -> dict[str, Any]:
    return {"activity_type": kind, "before": before, "after": after, "timestamp": when, "actor": {"login": "lee"}}


def shop() -> dict[str, Any]:
    r = "repos/acme/shop"
    return {
        r: {"full_name": "acme/shop", "default_branch": "main", "created_at": "2026-10-01T00:00:00Z"},
        f"{r}/pulls": [
            {"number": 11, "merged_at": "2026-11-02T10:00:00Z", "head": {"sha": "h11"}},
            {"number": 17, "merged_at": "2026-12-01T00:00:00Z", "head": {"sha": "h17"}},
            {"number": 19, "merged_at": None, "head": {"sha": "h19"}},
        ],
        f"{r}/activity": [
            entry("push", "c3", "c4", "2026-12-01T00:00:00Z"),
            entry("force_push", "c2", "c3", "2026-11-20T09:00:00Z"),
            entry("pr_merge", "c1", "m11", "2026-11-02T10:00:00Z"),
            entry("push", "c0", "c1", "2026-11-09T10:00:00Z"),
            entry("branch_creation", ZERO, "c0", "2026-11-01T00:00:00Z"),
        ],
        f"{r}/commits": [{"sha": "c0"}],
        f"{r}/pulls/11": {"number": 11, "merged": True, "commits": 2},
        f"{r}/pulls/11/commits": [{"sha": "w1"}, {"sha": "w2"}],
        f"{r}/pulls/11/reviews": [],
        "repos/acme/shop/issues/11/timeline": [],
        f"{r}/commits/h11/check-runs": {"total_count": 0, "check_runs": []},
        f"{r}/commits/h11/statuses": [],
        f"{r}/compare/c0...c1": {"status": "ahead", "commits": [{"sha": "c1"}]},
        f"{r}/compare/c2...c3": github.Refused(f"{r}/compare/c2...c3", "No common ancestor between c2 and c3."),
    }


def settings_in(tmp_path: Path, repositories: str = '"acme/shop"') -> Any:
    path = tmp_path / "settings.toml"
    path.write_text(
        f'repositories = [{repositories}]\nstart = "2026-11-01T00:00:00Z"\nend = "2026-12-01T00:00:00Z"\n',
        encoding="utf-8",
    )
    return load(path)


def saved(tmp_path: Path, name: str) -> Any:
    return json.loads((tmp_path / "data" / "acme__shop" / name).read_text(encoding="utf-8"))


def test_collect_saves_every_reply_the_period_needs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(github, "pages", fake_pages(shop(), calls))
    lines = collect(settings_in(tmp_path))
    data = tmp_path / "data"
    assert lines == [f"Saved GitHub's replies for 1 repository in {data}."]
    assert (data / ".gitignore").read_text(encoding="utf-8") == "*\n"
    assert saved(tmp_path, "repo.json")["default_branch"] == "main"
    assert [p["number"] for p in saved(tmp_path, "pulls.json")] == [11, 17, 19]
    assert len(saved(tmp_path, "activity.json")) == 5
    assert saved(tmp_path, "main_commits.json") == [{"sha": "c0"}]
    assert saved(tmp_path, "pr/11/commits.json") == [{"sha": "w1"}, {"sha": "w2"}]
    names = sorted(p.name for p in (data / "acme__shop" / "pr" / "11").iterdir())
    assert names == ["check_runs.json", "commits.json", "pull.json", "reviews.json", "statuses.json", "timeline.json"]
    assert not (data / "acme__shop" / "pr" / "17").exists()
    assert saved(tmp_path, "push/c1.json") == [{"sha": "c1"}]
    assert saved(tmp_path, "push/c3.json") == [{"sha": "c0"}]
    assert saved(tmp_path, "push/c0.json") == [{"sha": "c0"}]
    assert sorted(p.name for p in (data / "acme__shop" / "push").iterdir()) == ["c0.json", "c1.json", "c3.json"]
    assert "repos/acme/shop/pulls?state=closed&base=main&per_page=100" in calls
    assert "repos/acme/shop/activity?ref=main&per_page=100" in calls
    assert "repos/acme/shop/commits?sha=main&per_page=100" in calls
    assert "repos/acme/shop/commits/h11/check-runs?filter=all&per_page=100" in calls
    assert "repos/acme/shop/commits?sha=c3&per_page=100" in calls
    assert "repos/acme/shop/compare/c0...c1" in calls
    text = (data / "acme__shop" / "repo.json").read_text(encoding="utf-8")
    assert text == json.dumps(shop()["repos/acme/shop"], sort_keys=True, indent=2) + "\n"
    assert not (tmp_path / "data.collecting").exists()


def test_a_new_collect_replaces_the_data_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = tmp_path / "data" / "acme__gone"
    old.mkdir(parents=True)
    (tmp_path / "data.old").mkdir()
    (tmp_path / "data.collecting").mkdir()
    monkeypatch.setattr(github, "pages", fake_pages(shop(), []))
    collect(settings_in(tmp_path))
    assert sorted(p.name for p in (tmp_path / "data").iterdir()) == [".gitignore", "acme__shop"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data", "settings.toml"]


def test_an_unreadable_repository_stops_and_leaves_the_data_folder_as_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = tmp_path / "data" / "acme__shop" / "repo.json"
    before.parent.mkdir(parents=True)
    before.write_text("earlier", encoding="utf-8")
    monkeypatch.setattr(github, "pages", fake_pages(shop(), []))
    with pytest.raises(Stop) as stop:
        collect(settings_in(tmp_path, '"acme/shop", "acme/secret"'))
    assert stop.value.message == "Cannot read acme/secret with your GitHub sign-in. No record was written."
    assert before.read_text(encoding="utf-8") == "earlier"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data", "settings.toml"]


def test_a_later_refused_read_is_named(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    answers = shop()
    del answers["repos/acme/shop/pulls/11/reviews"]
    monkeypatch.setattr(github, "pages", fake_pages(answers, []))
    with pytest.raises(Stop) as stop:
        collect(settings_in(tmp_path))
    assert stop.value.message == (
        "GitHub did not answer repos/acme/shop/pulls/11/reviews?per_page=100: Not Found. No record was written."
    )
    assert not (tmp_path / "data").exists()


def test_a_compare_refused_for_another_reason_is_named(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    answers = shop()
    answers["repos/acme/shop/compare/c2...c3"] = github.Refused("repos/acme/shop/compare/c2...c3", "Server Error")
    monkeypatch.setattr(github, "pages", fake_pages(answers, []))
    with pytest.raises(Stop) as stop:
        collect(settings_in(tmp_path))
    assert (
        stop.value.message
        == "GitHub did not answer repos/acme/shop/compare/c2...c3: Server Error. No record was written."
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"default_branch": None}, "GitHub's reply for acme/shop names no default branch. No record was written."),
        (
            {"activity": [{"activity_type": "push"}]},
            "GitHub's replies for acme/shop had an unexpected shape. No record was written.",
        ),
    ],
)
def test_replies_of_an_unexpected_shape_stop_collecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, Any], message: str
) -> None:
    answers = shop()
    if "default_branch" in change:
        answers["repos/acme/shop"] = {"full_name": "acme/shop"}
    else:
        answers["repos/acme/shop/activity"] = change["activity"]
    monkeypatch.setattr(github, "pages", fake_pages(answers, []))
    with pytest.raises(Stop) as stop:
        collect(settings_in(tmp_path))
    assert stop.value.message == message
