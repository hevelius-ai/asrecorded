"""The wording rules (BRD section 7) and S4-W1 C: banned words and email addresses, found and masked."""

from __future__ import annotations

from asrecorded.wording import ADDRESS, WORD, found, mask

AT = "@"
ADDRESS_TEXT = "ops" + AT + "example.invalid"


def test_a_banned_word_inside_a_name_is_replaced_and_the_rest_kept() -> None:
    assert mask("all required jobs passed") == f"all required jobs {WORD}"
    assert mask("Security APPROVED by bot") == f"Security {WORD} by bot"


def test_the_underscore_and_other_signs_end_a_word() -> None:
    assert mask("checks_passed") == f"checks_{WORD}"
    assert mask("safe-settings") == f"{WORD}-settings"
    assert mask("passedby") == "passedby"
    assert mask("unsafe") == "unsafe"


def test_no_ai_is_banned_as_two_words() -> None:
    assert mask("ran with no AI review") == f"ran with {WORD} review"
    assert mask("no_ai") == f"{WORD}"
    assert mask("nominal AI") == "nominal AI"


def test_an_email_address_is_replaced() -> None:
    assert mask(f"deploy ({ADDRESS_TEXT})") == f"deploy ({ADDRESS})"


def test_found_names_each_kind_once_in_order() -> None:
    text = f"audited and passed, reach {ADDRESS_TEXT}; passed again"
    assert found(text) == ['the word "audited"', 'the word "passed"', "an email address"]
    assert found("Two people let it in") == []
