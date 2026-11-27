"""The owner's optional rule (design §1, §3 step 6): the allowed patterns and the required checks.

A pull request is an exception when its pattern is not allowed, or a required check did not end in `success` on the
merged version; a direct push only when "No pull request" is not allowed (required checks do not apply to it). Each
reason is one plain sentence, the pattern first.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from asrecorded.errors import Stop
from asrecorded.wording import mask

PATTERNS = (
    "Two people",
    "Agent and person",
    "AI reviewer only",
    "Automatic, no approval",
    "One account",
    "No pull request",
)
KEYS = ("allowed_patterns", "required_checks")
STOP = "No record was written."


@dataclass(frozen=True)
class Rule:
    allowed: tuple[str, ...]
    required: tuple[str, ...]


def load_rule(path: Path | None) -> Rule | None:
    if path is None:
        return None
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Stop(f"Cannot find the rule file {path}. {STOP}") from None
    except UnicodeDecodeError:
        raise Stop(f"The rule file {path} is not plain text (UTF-8). {STOP}") from None
    except OSError as error:
        raise Stop(f"Cannot read the rule file {path}: {error.strerror or error}. {STOP}") from None
    except tomllib.TOMLDecodeError as error:
        raise Stop(f"The rule file {path} is not valid TOML: {error}. {STOP}") from None
    for key in raw:
        if key not in KEYS:
            raise Stop(f'The rule file holds "{key}", which it does not use: only {KEYS[0]} and {KEYS[1]}. {STOP}')
    allowed, required = _words(raw, KEYS[0]), _words(raw, KEYS[1])
    for name in allowed:
        if name not in PATTERNS:
            raise Stop(f'"{name}" is not one of the six patterns: {", ".join(PATTERNS)}. {STOP}')
    return Rule(allowed, required)


def _words(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise Stop(f'"{key}" in the rule file must be a list of words in quotes. {STOP}')
    return tuple(value)


def reasons(rule: Rule, pattern: str, results: tuple[tuple[str, str], ...] | None) -> list[str]:
    """Why a change is an exception; empty when it is not. `results` is None for a direct push."""
    found = []
    if pattern not in rule.allowed:
        found.append(f'the pattern "{pattern}" is not allowed by the rule.')
    if results is not None:
        for name in rule.required:
            shown = [state for check, state in results if check == name]
            if not shown:
                found.append(f'the required check "{mask(name)}" did not run on the merged version.')
            elif any(state != "success" for state in shown):
                found.append(
                    f'the required check "{mask(name)}" did not end in success on the merged version '
                    f"(it shows: {', '.join(shown)})."
                )
    return found


def _joined(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def sentence(rule: Rule) -> str:
    allowed = list(rule.allowed)
    if not allowed:
        text = "The rule allows no pattern"
    else:
        text = f"The rule allows the pattern{'s' if len(allowed) > 1 else ''} {_joined(allowed)}"
    if rule.required:
        names = [mask(name) for name in rule.required]
        text += f", and requires the check{'s' if len(names) > 1 else ''} {_joined(names)}"
    return text + "."
