"""The one kind of failure a user sees: a plain sentence, then a non-zero exit."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Stop(Exception):
    """Stops the command; `message` is shown to the user as it is."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@contextmanager
def reading_saved(repository: str, folder: Path) -> Iterator[None]:
    """Turns a failure to read a repository's saved data into one plain sentence, the same wherever it is read."""
    try:
        yield
    except FileNotFoundError as missing:
        name = Path(missing.filename).relative_to(folder).as_posix()
        raise Stop(
            f"The saved data for {repository} is missing {name}. Run collect again. No record was written."
        ) from None
    except OSError as error:  # a locked file, or a folder where a file should be
        raise Stop(
            f"Cannot read the saved data for {repository}: {error.strerror or error}. Close any program that has "
            "it open, then run write again. No record was written."
        ) from None
    except (KeyError, IndexError, TypeError, ValueError, AttributeError, RecursionError):
        raise Stop(
            f"The saved data for {repository} could not be read. Run collect again. No record was written."
        ) from None
