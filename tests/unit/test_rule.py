"""The owner's optional rule (design §1, §3 step 6): reading it, and each change's exception reasons."""

from __future__ import annotations

from pathlib import Path

import pytest

from asrecorded.errors import Stop
from asrecorded.rule import Rule, load_rule, reasons, sentence

RULE = Rule(("Two people", "Agent and person"), ("ci",))


def write(tmp: Path, text: str) -> Path:
    path = tmp / "rule.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_no_rule_file_means_no_rule(tmp_path: Path) -> None:
    assert load_rule(None) is None


def test_a_rule_file_is_read(tmp_path: Path) -> None:
    path = write(tmp_path, 'allowed_patterns = ["Two people", "Agent and person"]\nrequired_checks = ["ci"]\n')
    assert load_rule(path) == RULE
    assert load_rule(write(tmp_path, 'allowed_patterns = ["One account"]\n')) == Rule(("One account",), ())


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("allowed_patterns = [", "is not valid TOML"),
        ('allowed_patterns = ["Three people"]\n', '"Three people" is not one of the six patterns'),
        ("allowed_patterns = 3\n", '"allowed_patterns" in the rule file must be a list of words in quotes'),
        ("required_checks = [1]\n", '"required_checks" in the rule file must be a list of words in quotes'),
        ('allowed = ["Two people"]\n', 'The rule file holds "allowed", which it does not use'),
    ],
)
def test_a_rule_file_it_cannot_use_is_refused_with_a_plain_sentence(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(Stop) as stop:
        load_rule(write(tmp_path, text))
    assert message in stop.value.message
    assert stop.value.message.endswith("No record was written.")


def test_a_rule_file_that_cannot_be_found_is_refused(tmp_path: Path) -> None:
    with pytest.raises(Stop) as stop:
        load_rule(tmp_path / "missing.toml")
    assert stop.value.message == f"Cannot find the rule file {tmp_path / 'missing.toml'}. No record was written."


def test_a_pattern_not_allowed_is_the_reason() -> None:
    assert reasons(RULE, "One account", (("ci", "success"),)) == [
        'the pattern "One account" is not allowed by the rule.'
    ]


def test_a_required_check_that_did_not_end_in_success_is_a_reason_after_the_pattern() -> None:
    assert reasons(RULE, "Agent and person", (("ci", "failure"),)) == [
        'the required check "ci" did not end in success on the merged version (it shows: failure).'
    ]
    assert reasons(RULE, "AI reviewer only", (("ci", "not finished at the merge"), ("ci", "success"))) == [
        'the pattern "AI reviewer only" is not allowed by the rule.',
        'the required check "ci" did not end in success on the merged version '
        "(it shows: not finished at the merge, success).",
    ]


def test_a_required_check_that_did_not_run_is_a_reason() -> None:
    assert reasons(RULE, "Two people", ()) == ['the required check "ci" did not run on the merged version.']
    assert reasons(RULE, "Two people", (("lint", "success"),)) == [
        'the required check "ci" did not run on the merged version.'
    ]


def test_a_direct_push_is_judged_on_its_pattern_only() -> None:
    assert reasons(RULE, "No pull request", None) == ['the pattern "No pull request" is not allowed by the rule.']
    allowed = Rule(("No pull request",), ("ci",))
    assert reasons(allowed, "No pull request", None) == []


def test_a_change_inside_the_rule_has_no_reason() -> None:
    assert reasons(RULE, "Two people", (("ci", "success"),)) == []


def test_the_rule_in_one_sentence() -> None:
    assert sentence(RULE) == "The rule allows the patterns Two people and Agent and person, and requires the check ci."
    assert sentence(Rule(("Two people",), ())) == "The rule allows the pattern Two people."
    three = Rule(("Two people", "Agent and person", "One account"), ("ci", "lint"))
    assert sentence(three) == (
        "The rule allows the patterns Two people, Agent and person and One account, and requires the checks ci "
        "and lint."
    )
    assert sentence(Rule((), ("all jobs passed",))) == (
        "The rule allows no pattern, and requires the check all jobs [a word this record does not use]."
    )
