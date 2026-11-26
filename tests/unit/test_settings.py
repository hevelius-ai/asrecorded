"""Reading the settings file (design §1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from asrecorded.errors import Stop
from asrecorded.settings import folder_name, load

GOOD = 'repositories = ["acme/shop", "acme/joined"]\nstart = "2026-11-01T00:00:00Z"\nend = "2026-12-01T00:00:00Z"\n'


def settings_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_defaults_are_read_from_the_settings_folder(tmp_path: Path) -> None:
    settings = load(settings_file(tmp_path, GOOD))
    assert settings.repositories == ("acme/shop", "acme/joined")
    assert settings.start.isoformat() == "2026-11-01T00:00:00+00:00"
    assert settings.end.isoformat() == "2026-12-01T00:00:00+00:00"
    assert settings.agent_accounts == ()
    assert settings.disclosures == ()
    assert settings.data == tmp_path / "data"
    assert settings.output == tmp_path / "record"
    assert settings.rule is None


def test_every_key_is_read(tmp_path: Path) -> None:
    text = GOOD + (
        'agent_accounts = ["builder-bot"]\ndisclosures = ["One person directs the agent."]\n'
        'data = "saved"\noutput = "out"\nrule = "rule.toml"\n'
    )
    settings = load(settings_file(tmp_path, text))
    assert settings.agent_accounts == ("builder-bot",)
    assert settings.disclosures == ("One person directs the agent.",)
    assert settings.data == tmp_path / "saved"
    assert settings.output == tmp_path / "out"
    assert settings.rule == tmp_path / "rule.toml"


def test_a_missing_settings_file_is_named(tmp_path: Path) -> None:
    path = tmp_path / "nowhere.toml"
    with pytest.raises(Stop) as stop:
        load(path)
    assert stop.value.message == f"Cannot find the settings file {path}."


def test_a_settings_file_that_is_not_toml_is_refused(tmp_path: Path) -> None:
    path = settings_file(tmp_path, "repositories = [")
    with pytest.raises(Stop) as stop:
        load(path)
    assert stop.value.message.startswith(f"The settings file {path} is not valid TOML: ")


REPOSITORIES = 'The settings need "repositories": a list of GitHub repositories written as owner/name.'
START = 'The settings need "start" as a UTC time ending in Z, such as 2026-11-01T00:00:00Z.'
END = 'The settings need "end" as a UTC time ending in Z, such as 2026-11-01T00:00:00Z.'
TIMES = 'start = "2026-11-01T00:00:00Z"\nend = "2026-12-01T00:00:00Z"\n'


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (TIMES, REPOSITORIES),
        ('repositories = "acme/shop"\n' + TIMES, REPOSITORIES),
        ("repositories = []\n" + TIMES, REPOSITORIES),
        ("repositories = [1]\n" + TIMES, REPOSITORIES),
        ('repositories = ["shop"]\n' + TIMES, '"shop" in "repositories" is not written as owner/name.'),
        ('repositories = ["/shop"]\n' + TIMES, '"/shop" in "repositories" is not written as owner/name.'),
        ('repositories = ["acme/"]\n' + TIMES, '"acme/" in "repositories" is not written as owner/name.'),
        ('repositories = ["a/b/c"]\n' + TIMES, '"a/b/c" in "repositories" is not written as owner/name.'),
        ('repositories = ["acme/shop"]\nend = "2026-12-01T00:00:00Z"\n', START),
        ('repositories = ["acme/shop"]\nstart = "2026-11-01T00:00:00"\nend = "2026-12-01T00:00:00Z"\n', START),
        ('repositories = ["acme/shop"]\nstart = "yesterdayZ"\nend = "2026-12-01T00:00:00Z"\n', START),
        ('repositories = ["acme/shop"]\nstart = 2026-11-01T00:00:00Z\nend = "2026-12-01T00:00:00Z"\n', START),
        ('repositories = ["acme/shop"]\nstart = "2026-11-01T00:00:00Z"\n', END),
        (
            'repositories = ["acme/shop"]\nstart = "2026-12-01T00:00:00Z"\nend = "2026-12-01T00:00:00Z"\n',
            'The settings\' "start" must be before "end".',
        ),
        (
            GOOD + 'agent_accounts = "builder-bot"\n',
            '"agent_accounts" in the settings must be a list of words in quotes.',
        ),
        (GOOD + "disclosures = [1]\n", '"disclosures" in the settings must be a list of words in quotes.'),
        (GOOD + "data = 1\n", '"data" in the settings must be a path in quotes.'),
        (GOOD + 'output = ""\n', '"output" in the settings must be a path in quotes.'),
        (GOOD + "rule = []\n", '"rule" in the settings must be a path in quotes.'),
    ],
)
def test_wrong_settings_are_refused_in_plain_words(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(Stop) as stop:
        load(settings_file(tmp_path, text))
    assert stop.value.message == message


def test_a_repository_folder_name_joins_owner_and_name() -> None:
    assert folder_name("acme/shop") == "acme__shop"
