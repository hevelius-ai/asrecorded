"""Times are UTC and end in Z, in the settings and in GitHub's replies."""

from __future__ import annotations

from datetime import datetime


def parse(value: object) -> datetime:
    """A UTC time such as 2026-11-01T00:00:00Z; anything else raises ValueError."""
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"not a UTC time ending in Z: {value!r}")
    return datetime.fromisoformat(value)


def iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def day(when: datetime) -> str:
    return when.strftime("%Y-%m-%d")


def clock(when: datetime) -> str:
    return when.strftime("%H:%M")


def count(n: int, one: str, many: str | None = None) -> str:
    """'1 change', '2 changes'; `many` for a word that does not just take an s."""
    return f"{n} {one if n == 1 else many or one + 's'}"
