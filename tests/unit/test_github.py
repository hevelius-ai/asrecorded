"""Every read of GitHub goes through `gh api --method GET --paginate --slurp` (design §2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from asrecorded import github
from asrecorded.errors import Stop

STAND_IN = """
import json
import sys
from pathlib import Path

here = Path(__file__).parent
(here / "args.json").write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
reply = json.loads((here / "reply.json").read_text(encoding="utf-8"))
sys.stdout.write(reply["stdout"])
sys.stderr.write(reply["stderr"])
sys.exit(reply["code"])
"""


def stand_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str, code: int = 0, stderr: str = "") -> Path:
    script = tmp_path / "gh_stand_in.py"
    script.write_text(STAND_IN, encoding="utf-8")
    (tmp_path / "reply.json").write_text(
        json.dumps({"stdout": stdout, "stderr": stderr, "code": code}), encoding="utf-8"
    )
    monkeypatch.setenv("ASRECORDED_GH", json.dumps([sys.executable, str(script)]))
    return tmp_path / "args.json"


def test_gh_is_run_when_no_stand_in_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASRECORDED_GH", raising=False)
    assert github.program() == ["gh"]


def test_the_stand_in_is_a_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASRECORDED_GH", '["python", "stand_in.py"]')
    assert github.program() == ["python", "stand_in.py"]


@pytest.mark.parametrize("value", ["python stand_in.py", '"python"', "[]", '["python", 1]'])
def test_a_stand_in_that_is_not_a_list_of_words_is_refused(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("ASRECORDED_GH", value)
    with pytest.raises(Stop) as stop:
        github.program()
    assert stop.value.message == (
        'ASRECORDED_GH must be a JSON list naming a program and its arguments, such as ["gh"].'
    )


def test_only_a_get_request_is_made(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = stand_in(tmp_path, monkeypatch, '[{"full_name": "acme/shop"}]')
    assert github.pages("repos/acme/shop") == [{"full_name": "acme/shop"}]
    assert json.loads(args.read_text(encoding="utf-8")) == [
        "api",
        "--method",
        "GET",
        "--paginate",
        "--slurp",
        "repos/acme/shop",
    ]


@pytest.mark.parametrize(
    ("stdout", "stderr", "message"),
    [
        ('[{"message": "Not Found", "status": "404"}]', "gh: Not Found (HTTP 404)", "Not Found"),
        ('{"message": "No common ancestor between a and b."}', "", "No common ancestor between a and b."),
        ("", "gh: could not connect\n", "gh: could not connect"),
        ("[]", "", "no reply"),
    ],
)
def test_a_refused_read_carries_github_s_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str, stderr: str, message: str
) -> None:
    stand_in(tmp_path, monkeypatch, stdout, code=1, stderr=stderr)
    with pytest.raises(github.Refused) as refused:
        github.pages("repos/acme/secret")
    assert refused.value.path == "repos/acme/secret"
    assert refused.value.message == message


@pytest.mark.parametrize("stdout", ["not json", '{"message": "one page, not a list"}'])
def test_a_reply_that_is_not_a_list_of_pages_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    stand_in(tmp_path, monkeypatch, stdout)
    with pytest.raises(github.Refused) as refused:
        github.pages("repos/acme/shop")
    assert refused.value.message == "GitHub's reply could not be read"


def test_a_missing_gh_is_named_in_plain_words(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASRECORDED_GH", '["asrecorded-no-such-program"]')
    with pytest.raises(Stop) as stop:
        github.pages("repos/acme/shop")
    assert stop.value.message == (
        "The gh command was not found. Install GitHub's gh, sign in with gh auth login, then run this again."
    )


def replies(monkeypatch: pytest.MonkeyPatch, pages: list[Any]) -> None:
    monkeypatch.setattr(github, "pages", lambda path: pages)


def test_one_object(monkeypatch: pytest.MonkeyPatch) -> None:
    replies(monkeypatch, [{"number": 11}])
    assert github.get_object("repos/acme/shop/pulls/11") == {"number": 11}


@pytest.mark.parametrize("pages", [[], [[{"number": 11}]]])
def test_one_object_of_another_shape_is_refused(monkeypatch: pytest.MonkeyPatch, pages: list[Any]) -> None:
    replies(monkeypatch, pages)
    with pytest.raises(github.Refused) as refused:
        github.get_object("repos/acme/shop/pulls/11")
    assert refused.value.message == github.SHAPE


def test_list_pages_are_joined(monkeypatch: pytest.MonkeyPatch) -> None:
    replies(monkeypatch, [[1, 2], [3]])
    assert github.get_list("repos/acme/shop/pulls") == [1, 2, 3]


def test_list_pages_of_another_shape_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    replies(monkeypatch, [[1], {"commits": 2}])
    with pytest.raises(github.Refused):
        github.get_list("repos/acme/shop/pulls/11")


def test_check_run_pages_are_joined(monkeypatch: pytest.MonkeyPatch) -> None:
    replies(monkeypatch, [{"total_count": 2, "check_runs": ["a"]}, {"total_count": 2, "check_runs": ["b"]}])
    assert github.get_check_runs("repos/acme/shop/commits/abc/check-runs") == ["a", "b"]


def test_compare_pages_are_joined(monkeypatch: pytest.MonkeyPatch) -> None:
    replies(monkeypatch, [{"status": "ahead", "commits": ["a"]}, {"status": "ahead", "commits": ["b"]}])
    assert github.get_compare("repos/acme/shop/compare/a...b") == ["a", "b"]


@pytest.mark.parametrize("pages", [[["a"]], [{"total_count": 1}], [{"commits": 2}]])
def test_pages_without_the_named_list_are_refused(monkeypatch: pytest.MonkeyPatch, pages: list[Any]) -> None:
    replies(monkeypatch, pages)
    with pytest.raises(github.Refused):
        github.get_compare("repos/acme/shop/compare/a...b")
