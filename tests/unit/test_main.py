"""The three commands, `python -m asrecorded run|collect|write settings.toml` (design §1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from asrecorded import __main__ as cli
from asrecorded import collect, output
from asrecorded.errors import Stop
from asrecorded.settings import Settings

USAGE = "Use: python -m asrecorded run|collect|write settings.toml\n"


def settings_file(tmp_path: Path) -> str:
    path = tmp_path / "settings.toml"
    path.write_text(
        'repositories = ["acme/shop"]\nstart = "2026-11-01T00:00:00Z"\nend = "2026-12-01T00:00:00Z"\n',
        encoding="utf-8",
    )
    return str(path)


@pytest.mark.parametrize("argv", [[], ["run"], ["publish", "settings.toml"], ["run", "a.toml", "b.toml"]])
def test_a_wrong_command_shows_how_to_use_it(capsys: pytest.CaptureFixture[str], argv: list[str]) -> None:
    assert cli.main(argv) == 2
    assert capsys.readouterr().err == USAGE


def fake(monkeypatch: pytest.MonkeyPatch, done: list[str]) -> None:
    def collected(settings: Settings) -> list[str]:
        done.append("collect")
        return ["collected"]

    def written(settings: Settings) -> list[str]:
        done.append("write")
        return ["written"]

    monkeypatch.setattr(collect, "collect", collected)
    monkeypatch.setattr(output, "write", written)


@pytest.mark.parametrize(
    ("command", "steps"), [("run", ["collect", "write"]), ("collect", ["collect"]), ("write", ["write"])]
)
def test_each_command_runs_its_steps_and_prints_their_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], command: str, steps: list[str]
) -> None:
    done: list[str] = []
    fake(monkeypatch, done)
    assert cli.main([command, settings_file(tmp_path)]) == 0
    assert done == steps
    printed = {"collect": "collected\n", "write": "written\n"}
    assert capsys.readouterr().out == "".join(printed[step] for step in steps)


def test_a_stop_prints_one_plain_sentence_and_exits_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refused(settings: Settings) -> list[str]:
        raise Stop("Cannot read acme/secret with your GitHub sign-in. No record was written.")

    monkeypatch.setattr(collect, "collect", refused)
    assert cli.main(["run", settings_file(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Cannot read acme/secret with your GitHub sign-in. No record was written.\n"


def test_the_arguments_come_from_the_command_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    done: list[str] = []
    fake(monkeypatch, done)
    monkeypatch.setattr(sys, "argv", ["asrecorded", "write", settings_file(tmp_path)])
    assert cli.main() == 0
    assert done == ["write"]
