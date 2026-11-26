"""The one kind of failure a user sees: a plain sentence, then a non-zero exit."""

from __future__ import annotations


class Stop(Exception):
    """Stops the command; `message` is shown to the user as it is."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
