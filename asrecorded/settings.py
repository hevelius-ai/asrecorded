"""Reading the settings file (design §1): TOML, read with the standard library."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from asrecorded import times
from asrecorded.errors import Stop
from asrecorded.wording import found


@dataclass(frozen=True)
class Settings:
    repositories: tuple[str, ...]
    start: datetime
    end: datetime
    agent_accounts: tuple[str, ...]
    disclosures: tuple[str, ...]
    data: Path
    output: Path
    rule: Path | None


def folder_name(repository: str) -> str:
    """The data folder's sub-folder for one repository: acme/shop is acme__shop."""
    return repository.replace("/", "__")


def load(path: Path) -> Settings:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Stop(f"Cannot find the settings file {path}.") from None
    except tomllib.TOMLDecodeError as error:
        raise Stop(f"The settings file {path} is not valid TOML: {error}.") from None
    except OSError:
        raise Stop(f"Cannot read the settings file {path}.") from None
    repositories = raw.get("repositories")
    if not isinstance(repositories, list) or not repositories or not all(isinstance(r, str) for r in repositories):
        raise Stop('The settings need "repositories": a list of GitHub repositories written as owner/name.')
    for name in repositories:
        owner, _, rest = name.partition("/")
        if not owner or not rest or "/" in rest:
            raise Stop(f'"{name}" in "repositories" is not written as owner/name.')
        if repositories.count(name) > 1:
            raise Stop(f'"{name}" is listed twice in "repositories".')
    start, end = _time(raw, "start"), _time(raw, "end")
    if start >= end:
        raise Stop('The settings\' "start" must be before "end".')
    folder = path.parent
    return Settings(
        repositories=tuple(repositories),
        start=start,
        end=end,
        agent_accounts=_words(raw, "agent_accounts"),
        disclosures=_disclosures(raw),
        data=folder / _path(raw, "data", "data"),
        output=folder / _path(raw, "output", "record"),
        rule=folder / _path(raw, "rule", "") if "rule" in raw else None,
    )


def _time(raw: dict[str, Any], key: str) -> datetime:
    try:
        return times.parse(raw.get(key))
    except ValueError:
        raise Stop(
            f'The settings need "{key}" as a UTC time in quotes, ending in Z, such as "2026-11-01T00:00:00Z".'
        ) from None


def _words(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise Stop(f'"{key}" in the settings must be a list of words in quotes.')
    return tuple(value)


def _path(raw: dict[str, Any], key: str, default: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str) or not value:
        raise Stop(f'"{key}" in the settings must be a path in quotes.')
    return value


def _disclosures(raw: dict[str, Any]) -> tuple[str, ...]:
    """Disclosures are printed in the record as written (design section 1), so none may break the wording rules."""
    texts = _words(raw, "disclosures")
    for number, text in enumerate(texts, start=1):
        problems = found(text)
        if problems and problems[0] == "an email address":
            raise Stop(
                f"Disclosure {number} in the settings holds an email address, which a record never shows. "
                "Change it, then run this again."
            )
        if problems:
            raise Stop(
                f"Disclosure {number} in the settings holds {problems[0]}, which a record never uses. "
                "Change it, then run this again."
            )
    return texts
