"""Write (design §1, §3 step 7): the record from the data folder only. It never calls GitHub.

Three files: `changes.csv` (S1's columns, then S2's and S3's; columns are only ever added at the end), `record.json`
and `record.md`, which holds the SHA-256 of the other two. All three are written to temporary names and renamed only
when all are complete, `record.md` last; a failed write first removes any `record.md` it would replace.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import os
from pathlib import Path

from asrecorded.changes import DIRECT, RepositoryList, list_changes, summary_lines
from asrecorded.checks import cell, describe_results
from asrecorded.errors import Stop
from asrecorded.record import Record, Row, as_json, markdown
from asrecorded.rule import load_rule, reasons
from asrecorded.settings import Settings, folder_name
from asrecorded.times import clock, count, day, iso
from asrecorded.who import Who, describe, pattern_line

COLUMNS = (
    "repository",
    "change",
    "how",
    "when",
    "builder",
    "let_in_by",
    "approvals",
    "ai_shown",
    "ai_trace",
    "pattern",
    "declared_agent_operated",
    "checks",
)
ORDER = ("changes.csv", "record.json", "record.md")  # the order they are put in place: record.md last


def write(settings: Settings) -> list[str]:
    try:
        rule = load_rule(settings.rule)
        lists = [
            list_changes(repository, settings.data / folder_name(repository), settings.start, settings.end)
            for repository in settings.repositories
        ]
        declared = frozenset(settings.agent_accounts)
        described = [describe(result, settings.data / folder_name(result.repository), declared) for result in lists]
        rows: list[Row] = []
        not_covered: list[str] = []
        for result, (found, queued) in zip(lists, described, strict=True):
            results = describe_results(result, settings.data / folder_name(result.repository))
            for change in sorted(result.changes, key=lambda c: (c.when, c.change)):
                who, checked = found[change.change], results[change.change]
                why = () if rule is None else tuple(reasons(rule, who.pattern, checked))
                rows.append(Row(change, who, checked, cell(checked), why))
            pushed = sum(1 for c in result.changes if c.how == DIRECT)
            not_covered += result.not_covered + queued
            if pushed:
                not_covered.append(
                    f"{result.repository}: not covered: checks were not read for {count(pushed, 'commit')} "
                    "pushed directly"
                )
        record = Record(
            repositories=settings.repositories,
            start=settings.start,
            end=settings.end,
            rule=rule,
            rows=tuple(rows),
            not_covered=tuple(not_covered),
            rewritten=tuple(
                f"{r.repository}: history rewritten on {day(r.when)} at {clock(r.when)} UTC by {r.actor}, "
                f"{count(r.commits, 'commit')} brought in"
                for result in lists
                for r in result.rewrites
            ),
            disclosures=settings.disclosures,
        )
        csv_bytes = changes_csv_from_rows(record.rows).encode("utf-8")
        json_bytes = as_json(record).encode("utf-8")
        md_bytes = markdown(record, hashlib.sha256(csv_bytes).hexdigest(), hashlib.sha256(json_bytes).hexdigest())
        write_files(
            settings.output,
            {"changes.csv": csv_bytes, "record.json": json_bytes, "record.md": md_bytes.encode("utf-8")},
        )
    except Stop:
        with contextlib.suppress(OSError):  # no record.md, no output folder, or one that cannot be removed
            (settings.output / "record.md").unlink()
        raise
    lines = []
    for result, (found, queued) in zip(lists, described, strict=True):
        lines += [*summary_lines(result), pattern_line(result.repository, found), *queued]
    lines.append(
        f"Wrote record.md, changes.csv and record.json in {settings.output}: {count(len(rows), 'change')} from "
        f"{count(len(lists), 'repository', 'repositories')}."
    )
    return lines


def changes_csv_from_rows(rows: tuple[Row, ...]) -> str:
    """One row per change, in the record's order: repository (in settings order), then time, then id."""
    out = io.StringIO()
    table = csv.writer(out, lineterminator="\n")
    table.writerow(COLUMNS)
    for row in rows:
        c, w = row.change, row.who
        table.writerow(
            (
                c.repository,
                c.change,
                c.how,
                iso(c.when),
                w.builder,
                w.let_in_by,
                w.approvals,
                w.ai_shown,
                w.ai_trace,
                w.pattern,
                w.declared_agent_operated,
                row.checks,
            )
        )
    return out.getvalue()


def changes_csv(
    lists: list[RepositoryList], details: dict[tuple[str, str], Who], checks: dict[tuple[str, str], str]
) -> str:
    """`changes.csv` from per-change facts: one row per change, sorted by repository (in settings order), time, id."""
    rows = tuple(
        Row(change, details[(change.repository, change.change)], None, checks[(change.repository, change.change)], ())
        for result in lists
        for change in sorted(result.changes, key=lambda c: (c.when, c.change))
    )
    return changes_csv_from_rows(rows)


def write_files(output: Path, files: dict[str, bytes]) -> None:
    """Write each file to a temporary name, remove the earlier record.md, then put them in place in ORDER.

    The earlier `record.md` goes first: if it cannot be removed (another program holds it), nothing is replaced, so
    the earlier record stays whole and its checksums still match (PR #14 review, M1). On any failure, what is
    temporary is removed."""
    temporary = {name: output / f"{name}.tmp" for name in ORDER}
    current = output / ORDER[0]
    record = output / "record.md"
    try:
        output.mkdir(parents=True, exist_ok=True)
        for name in ORDER:
            current = output / name
            temporary[name].write_bytes(files[name])
    except OSError as error:
        _remove(temporary)
        raise _cannot("write", current, error, "") from None
    try:
        record.unlink(missing_ok=True)
    except OSError as error:
        _remove(temporary)
        raise _cannot("replace", record, error, " The earlier record was kept whole.") from None
    try:
        for name in ORDER:
            current = output / name
            os.replace(temporary[name], current)
    except OSError as error:
        _remove(temporary)
        raise _cannot("write", current, error, "") from None


def _remove(paths: dict[str, Path]) -> None:
    for path in paths.values():
        with contextlib.suppress(OSError):
            path.unlink()


def _cannot(verb: str, path: Path, error: OSError, kept: str) -> Stop:
    return Stop(
        f"Cannot {verb} {path}: {error.strerror or error}. Close any program that has it open, then run write "
        f"again.{kept} No record was written."
    )
