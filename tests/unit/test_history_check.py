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
NEAR_MISSES = [
    "noreply" + AT + "github.com.example.org",
    "dana" + AT + "github.com",
    "dana" + AT + "anthropic.com",
    "1+dana" + AT + "users.noreply.github.com.example.org",
]
WINDOWS_PATH = "C:" + "\\" + "Users" + "\\" + "dana\\Desktop"
TOKEN = "gh" + "p_" + "A1" * 18
SAMPLES = {
    "Windows user path": (WINDOWS_PATH, "local user path"),
    "Windows user path, doubled backslashes": ("C:" + "\\\\" + "Users" + "\\\\" + "dana", "local user path"),
    "Windows user path, forward slashes": ("c:" + "/" + "users/dana", "local user path"),
    "Windows user path in a file address": ("file:///c" + "%3A/" + "Users/dana/x", "local user path"),
    "Git Bash user path": ("/c/" + "Users/dana/x", "local user path"),
    "macOS user path": ("/" + "Users/dana/project", "local user path"),
    "Linux home path": ("/home/" + "dana/project", "local user path"),
    "Linux home path without a slash after it": ("HOME=/home/" + "dana", "local user path"),
    "Linux home path with a dot in the name": ("/home/" + "dana.smith/project", "local user path"),
    "GitHub token": (TOKEN, "GitHub token"),
    "GitHub OAuth token": ("gh" + "o_" + "A1" * 18, "GitHub token"),
    "GitHub app token": ("gh" + "s_" + "A1" * 18, "GitHub token"),
    "GitHub user-to-server token": ("gh" + "u_" + "A1" * 18, "GitHub token"),
    "GitHub refresh token": ("gh" + "r_" + "A1" * 18, "GitHub token"),
    "GitHub token after a JSON line break": ('"\\n' + TOKEN + '"', "GitHub token"),
    "GitHub token after an underscore": ("KEY_" + TOKEN, "GitHub token"),
    "GitHub fine-grained token": ("github_" + "pat_" + "B2" * 20, "GitHub token"),
    "Anthropic key": ("sk-" + "ant-" + "c3" * 12, "Anthropic key"),
    "AWS key": ("AK" + "IA" + "ABCDEFGHIJKLMNOP", "AWS key"),
    "OpenSSH private key": ("-----BEGIN " + "OPENSSH PRIVATE KEY-----", "private key"),
    "RSA private key": ("-----BEGIN " + "RSA PRIVATE KEY-----", "private key"),
    "PGP private key": ("-----BEGIN " + "PGP PRIVATE KEY BLOCK-----", "private key"),
}


def test_allowed_addresses_are_not_findings() -> None:
    for address in ALLOWED:
        assert history_check.kinds_in(f"Author <{address}>") == []


@pytest.mark.parametrize("address", NEAR_MISSES)
def test_addresses_that_only_look_allowed_are_findings(address: str) -> None:
    assert history_check.kinds_in(f"Author <{address}>") == ["email address"]


def test_a_personal_email_address_is_a_finding() -> None:
    assert history_check.kinds_in(f"written by {PERSONAL}") == ["email address"]


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_each_kind_of_private_data_is_a_finding(name: str) -> None:
    text, kind = SAMPLES[name]
    assert history_check.kinds_in(f"see {text} here") == [kind]


def test_ordinary_code_and_text_are_not_findings() -> None:
    text = "\n".join(
        [
            "@dataclass(frozen=True)",
            "- uses: actions/checkout" + AT + "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5.1.0",
            "pytest==9.2.0",
            "git clone git" + AT + "github.com:hevelius-ai/asrecorded.git",
            "working folder /home/" + "runner/work/asrecorded",
            "https://example.org/home/" + "about/team",
            "see the folder Users/ and /home/ in the docs",
        ]
    )
    assert history_check.kinds_in(text) == []


def test_each_kind_is_listed_once_in_a_fixed_order() -> None:
    text = f"{TOKEN} {PERSONAL} {PERSONAL} {TOKEN}"
    assert history_check.kinds_in(text) == ["email address", "GitHub token"]


def test_utf16_text_is_read_with_or_without_a_byte_order_mark() -> None:
    assert history_check.decode(("﻿" + WINDOWS_PATH).encode("utf-16-le")) == WINDOWS_PATH
    assert history_check.decode(WINDOWS_PATH.encode("utf-16-le")) == WINDOWS_PATH
    assert history_check.decode(b"plain text") == "plain text"


# A real repository in a temporary folder, with no global or system git settings.


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    folder = tmp_path / "repo"
    folder.mkdir()
    monkeypatch.chdir(folder)
    run_git("init", "-q", "-b", "main")
    return folder


def run_git(*args: str, email: str = ALLOWED[0], committer: str | None = None) -> None:
    env = dict(os.environ)
    if committer is not None:
        env["GIT_COMMITTER_EMAIL"] = committer
    subprocess.run(
        ["git", "-c", "user.name=tester", "-c", f"user.email={email}", "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        env=env,
    )


def commit_bytes(name: str, data: bytes, message: str = "", email: str = ALLOWED[0]) -> None:
    Path(name).write_bytes(data)
    run_git("add", name)
    run_git("commit", "-q", "-m", message or f"add {name}", email=email)


def commit_file(name: str, text: str, message: str = "", email: str = ALLOWED[0]) -> None:
    commit_bytes(name, text.encode("utf-8"), message, email)


def scan(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = history_check.main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_a_clean_history_exits_0(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n")
    commit_file("notes.txt", "More plain words.\n")
    assert scan(capsys) == (0, "history check: 2 commits scanned, clean\n", "")


def test_a_personal_author_address_exits_1_without_printing_it(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n", email=PERSONAL)
    code, out, _ = scan(capsys)
    assert code == 1
    assert "email address in commit details" in out
    assert "history check: 1 finding(s) in 1 commits" in out
    assert PERSONAL not in out


def test_a_personal_committer_address_is_a_finding(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    Path("README.md").write_text("A plain file.\n", encoding="utf-8")
    run_git("add", "README.md")
    run_git("commit", "-q", "-m", "add README.md", committer=PERSONAL)
    code, out, _ = scan(capsys)
    assert (code, "email address in commit details" in out) == (1, True)


def test_an_address_in_the_commit_message_is_a_finding(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n", message=f"Thanks to {PERSONAL}")
    code, out, _ = scan(capsys)
    assert (code, "email address in commit details" in out) == (1, True)


def test_a_token_in_a_file_exits_1_without_printing_it(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n")
    commit_file("secret.txt", f"token = {TOKEN}\n")
    code, out, _ = scan(capsys, "HEAD")
    assert code == 1
    assert "GitHub token in file secret.txt" in out
    assert TOKEN not in out


def test_a_token_added_and_later_removed_is_still_a_finding(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("secret.txt", f"token = {TOKEN}\n")
    commit_file("secret.txt", "nothing here now\n")
    code, out, _ = scan(capsys)
    assert (code, "GitHub token in file secret.txt" in out) == (1, True)


def test_a_utf16_file_with_a_byte_order_mark_is_read(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_bytes("log.txt", ("﻿saved to " + WINDOWS_PATH + "\r\n").encode("utf-16-le"))
    code, out, _ = scan(capsys)
    assert (code, "local user path in file log.txt" in out) == (1, True)


def test_a_file_git_treats_as_binary_is_read(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file(".gitattributes", "*.lock -diff\n")
    commit_file("deps.lock", f"token = {TOKEN}\n")
    commit_bytes("blob.bin", b"\x00\x01" + TOKEN.encode("ascii"))
    code, out, _ = scan(capsys)
    assert code == 1
    assert "GitHub token in file deps.lock" in out
    assert "GitHub token in file blob.bin" in out


def test_text_after_a_lone_carriage_return_is_read(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("progress.log", "10%\rsaved to " + WINDOWS_PATH + "\r" + "\f" + TOKEN + " done\n")
    code, out, _ = scan(capsys)
    assert code == 1
    assert "local user path in file progress.log" in out
    assert "GitHub token in file progress.log" in out


def test_an_address_in_a_file_name_is_a_finding_without_printing_it(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit_file(f"notes-{PERSONAL}.txt", "plain\n")
    code, out, _ = scan(capsys)
    assert code == 1
    assert "email address in a file name" in out
    assert PERSONAL not in out


def test_a_token_added_by_a_merge_commit_is_a_finding(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n")
    run_git("switch", "-q", "-c", "side")
    commit_file("side.txt", "side work\n")
    run_git("switch", "-q", "main")
    commit_file("main.txt", "main work\n")
    run_git("merge", "-q", "--no-ff", "--no-commit", "side")
    Path("merged.txt").write_text(f"token = {TOKEN}\n", encoding="utf-8")
    run_git("add", "merged.txt")
    run_git("commit", "-q", "-m", "merge side")
    code, out, _ = scan(capsys)
    assert (code, "GitHub token in file merged.txt" in out) == (1, True)


def test_staged_changes_are_scanned_with_the_staged_flag(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n")
    Path("notes.txt").write_text(WINDOWS_PATH + "\n", encoding="utf-8")
    run_git("add", "notes.txt")
    code, out, _ = scan(capsys, "--staged")
    assert (code, "staged: local user path in file notes.txt" in out) == (1, True)
    Path("notes.txt").write_text("plain\n", encoding="utf-8")
    run_git("add", "notes.txt")
    assert scan(capsys, "--staged") == (0, "history check: 1 staged file(s) scanned, clean\n", "")


def test_nothing_staged_exits_2(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n")
    code, _, err = scan(capsys, "--staged")
    assert (code, "nothing is staged" in err) == (2, True)


def test_a_shallow_clone_exits_2(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("secret.txt", f"token = {TOKEN}\n")
    commit_file("secret.txt", "nothing here now\n")
    run_git("clone", "-q", "--depth", "1", repo.as_uri(), str(tmp_path / "shallow"))
    os.chdir(tmp_path / "shallow")
    code, _, err = scan(capsys)
    assert (code, "shallow clone" in err) == (2, True)


def test_nothing_to_scan_exits_2(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_file("README.md", "A plain file.\n")
    code, _, err = scan(capsys, "HEAD..HEAD")
    assert (code, "no commit to scan" in err) == (2, True)


def test_a_git_failure_exits_2(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = scan(capsys)
    assert (code, "git rev-list failed" in err) == (2, True)


def test_arguments_come_from_the_command_line_by_default(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    commit_file("README.md", "A plain file.\n")
    monkeypatch.setattr(sys, "argv", ["history_check.py", "HEAD"])
    assert history_check.main() == 0
    assert capsys.readouterr().out == "history check: 1 commits scanned, clean\n"
