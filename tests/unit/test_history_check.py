"""Tests for scripts/history_check.py.

Every sample of private data is built at run time from parts, so that this file's own
text never holds one and the history check stays clean on this repository.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import history_check  # noqa: E402

AT = "@"
PERSONAL = "dana" + AT + "example.com"
ALLOWED = [
    "339821316+heveliusai-dev" + AT + "users.noreply.github.com",
    "chrisz-glitch" + AT + "users.noreply.github.com",
    "41898282+github-actions[bot]" + AT + "users.noreply.github.com",
    "noreply" + AT + "github.com",
    "noreply" + AT + "anthropic.com",
]
SAMPLES = {
    "Windows user path": ("C:" + "\\" + "Users" + "\\" + "dana\\Desktop", "local user path"),
    "Windows user path, doubled backslashes": ("C:" + "\\\\" + "Users" + "\\\\" + "dana", "local user path"),
    "Windows user path, forward slashes": ("c:" + "/" + "users/dana", "local user path"),
    "Git Bash user path": ("/c/" + "Users/dana/x", "local user path"),
    "Linux home path": ("/home/" + "dana/project", "local user path"),
    "GitHub token": ("gh" + "p_" + "A1" * 18, "GitHub token"),
    "GitHub fine-grained token": ("github_" + "pat_" + "B2" * 20, "GitHub token"),
    "Anthropic key": ("sk-" + "ant-" + "c3" * 12, "Anthropic key"),
    "AWS key": ("AK" + "IA" + "ABCDEFGHIJKLMNOP", "AWS key"),
    "private key": ("-----BEGIN " + "OPENSSH PRIVATE KEY-----", "private key"),
}


def test_allowed_addresses_are_not_findings() -> None:
    for address in ALLOWED:
        assert history_check.kinds_in(f"Author <{address}>") == []


def test_a_personal_email_address_is_a_finding() -> None:
    assert history_check.kinds_in(f"written by {PERSONAL}") == ["email address"]


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_each_kind_of_private_data_is_a_finding(name: str) -> None:
    text, kind = SAMPLES[name]
    assert history_check.kinds_in(f"see {text} here") == [kind]


def test_ordinary_code_is_not_a_finding() -> None:
    text = "\n".join(
        [
            "@dataclass(frozen=True)",
            "- uses: actions/checkout" + AT + "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5.1.0",
            "pytest==9.2.0",
            "see the folder Users/ and /home/ in the docs",
        ]
    )
    assert history_check.kinds_in(text) == []


def test_each_kind_is_listed_once_in_a_fixed_order() -> None:
    token = SAMPLES["GitHub token"][0]
    text = f"{token} {PERSONAL} {PERSONAL} {token}"
    assert history_check.kinds_in(text) == ["email address", "GitHub token"]


def test_only_added_lines_are_read_and_grouped_by_file() -> None:
    patch = "\n".join(
        [
            "diff --git a/a.txt b/a.txt",
            "--- a/a.txt",
            "+++ b/a.txt",
            "@@ -1 +1,2 @@",
            "-removed line",
            "+added one",
            "++ added line that starts with two plus signs",
            "diff --git a/gone.txt b/gone.txt",
            "--- a/gone.txt",
            "+++ /dev/null",
        ]
    )
    assert history_check.added_lines_by_file(patch) == {
        "a.txt": ["added one", "+ added line that starts with two plus signs"]
    }


def test_lines_before_any_file_header_are_still_read() -> None:
    findings = history_check.scan_patch("abc1234", "+" + PERSONAL)
    assert [f.line() for f in findings] == ["abc1234: email address in file (unknown file)"]


# A real repository in a temporary folder, with no global or system git settings.


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.chdir(tmp_path)
    run_git("init", "-q")
    return tmp_path


def run_git(*args: str, email: str = ALLOWED[0]) -> None:
    subprocess.run(
        ["git", "-c", "user.name=tester", "-c", f"user.email={email}", "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
    )


def commit_file(name: str, text: str, email: str = ALLOWED[0]) -> None:
    Path(name).write_text(text, encoding="utf-8")
    run_git("add", name)
    run_git("commit", "-q", "-m", f"add {name}", email=email)


def test_a_clean_history_exits_0(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n")
    commit_file("notes.txt", "More plain words.\n")
    assert history_check.main([]) == 0
    assert capsys.readouterr().out.strip() == "history check: 2 commits scanned, clean"


def test_a_personal_author_address_exits_1_without_printing_it(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n", email=PERSONAL)
    assert history_check.main([]) == 1
    out = capsys.readouterr().out
    assert "email address in commit details" in out
    assert "history check: 1 finding(s) in 1 commits" in out
    assert PERSONAL not in out


def test_a_token_in_a_file_exits_1_without_printing_it(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    token = SAMPLES["GitHub token"][0]
    commit_file("README.md", "A plain file.\n")
    commit_file("secret.txt", f"token = {token}\n")
    assert history_check.main(["HEAD"]) == 1
    out = capsys.readouterr().out
    assert "GitHub token in file secret.txt" in out
    assert token not in out


def test_staged_changes_are_scanned_with_the_staged_flag(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n")
    Path("notes.txt").write_text(SAMPLES["Windows user path"][0] + "\n", encoding="utf-8")
    run_git("add", "notes.txt")
    assert history_check.main(["--staged"]) == 1
    assert "staged: local user path in file notes.txt" in capsys.readouterr().out
    Path("notes.txt").write_text("plain\n", encoding="utf-8")
    run_git("add", "notes.txt")
    assert history_check.main(["--staged"]) == 0
    assert capsys.readouterr().out.strip() == "history check: the staged changes scanned, clean"


def test_nothing_to_scan_exits_2(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n")
    assert history_check.main(["HEAD..HEAD"]) == 2
    assert "no commit to scan" in capsys.readouterr().err


def test_a_git_failure_exits_2(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert history_check.main([]) == 2
    assert "git rev-list failed" in capsys.readouterr().err


def test_arguments_come_from_the_command_line_by_default(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    commit_file("README.md", "A plain file.\n")
    monkeypatch.setattr(sys, "argv", ["history_check.py", "HEAD"])
    assert history_check.main() == 0
    assert "1 commits scanned, clean" in capsys.readouterr().out
