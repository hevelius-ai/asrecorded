"""Write (design §1, §3 step 7): the record from the data folder only. It never calls GitHub.

S1 writes `changes.csv` with the columns repository, change, how and when; later stories add columns at the end.
Files are written to a temporary name and renamed when complete; a failed write first removes any `record.md` it
would replace.
"""

from __future__ import annotations

import contextlib
import csv
import os
from pathlib import Path

from asrecorded.changes import RepositoryList, list_changes, summary_lines
from asrecorded.errors import Stop
from asrecorded.settings import Settings, folder_name
from asrecorded.times import count, iso

COLUMNS = ("repository", "change", "how", "when")


def write(settings: Settings) -> list[str]:
    try:
        lists = [
            list_changes(repository, settings.data / folder_name(repository), settings.start, settings.end)
            for repository in settings.repositories
        ]
        path = write_changes(settings.output, lists)
    except Stop:
        with contextlib.suppress(FileNotFoundError, NotADirectoryError):  # no record.md, or no output folder
            (settings.output / "record.md").unlink()
        raise
    lines = [line for result in lists for line in summary_lines(result)]
    total = sum(len(result.changes) for result in lists)
    lines.append(f"Wrote {path}: {count(total, 'change')} from {count(len(lists), 'repository', 'repositories')}.")
    return lines


def write_changes(output: Path, lists: list[RepositoryList]) -> Path:
    """One row per change, sorted by repository (in settings order), then time, then id."""
    final = output / "changes.csv"
    temporary = output / "changes.csv.tmp"
    try:
        output.mkdir(parents=True, exist_ok=True)
        with temporary.open("w", encoding="utf-8", newline="") as f:
            table = csv.writer(f, lineterminator="\n")
            table.writerow(COLUMNS)
            for result in lists:
                for change in sorted(result.changes, key=lambda c: (c.when, c.change)):
                    table.writerow((change.repository, change.change, change.how, iso(change.when)))
        os.replace(temporary, final)
    except OSError as error:
        with contextlib.suppress(FileNotFoundError, NotADirectoryError):
            temporary.unlink()
        raise Stop(
            f"Cannot write {final}: {error.strerror or error}. Close any program that has it open, then run write "
            "again. No record was written."
        ) from None
    return final
