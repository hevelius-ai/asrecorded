"""`record.md` (plain words) and `record.json` (for programs), from the rows alone (design §3 step 7, S4).

`record.md` follows the sample the owner approved for S4: its headings, words and order. It lists every change
(S4-Q1 A), because a reader with only this file must find which changes were let in automatically and who approved
a named one. No clock is read: the only times are those in the saved data, so the same data gives the same bytes.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from asrecorded.changes import DIRECT, Change
from asrecorded.checks import Results
from asrecorded.rule import PATTERNS, Rule, sentence
from asrecorded.times import clock, count, day, iso
from asrecorded.who import ONE_ACCOUNT, Who
from asrecorded.wording import mask

CANNOT_SHOW = (
    "AI use that leaves no trace in the history",
    "whether an approver read or understood the change",
    "whether the checks were good checks",
    "which workflow posted a check of a given name",
    "two accounts held by one person, unless declared",
    "anything outside the listed repositories or outside GitHub",
    "history that was rewritten",
)  # BRD section 7, word for word, in its order
HEADER = ("Repository", "Change", "When (UTC)", "How", "Built by", "Let in by", "Approvals", "AI shown", "Pattern")


@dataclass(frozen=True)
class Row:
    change: Change
    who: Who
    results: Results | None  # None for a direct push
    checks: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Record:
    repositories: tuple[str, ...]
    start: datetime
    end: datetime
    rule: Rule | None
    rows: tuple[Row, ...]
    not_covered: tuple[str, ...]
    rewritten: tuple[str, ...]
    disclosures: tuple[str, ...]


def link(change: Change) -> str:
    if change.how == DIRECT:
        commit = cast(dict[str, Any], change.commit)  # every direct push carries its commit (changes.py)
        return f"https://github.com/{change.repository}/commit/{commit['sha']}"
    return f"https://github.com/{change.repository}/pull/{change.change.removeprefix('#')}"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _period(record: Record) -> str:
    return (
        f"Period: {day(record.start)} {clock(record.start)} UTC (included) to "
        f"{day(record.end)} {clock(record.end)} UTC (not included)."
    )


def _checks(rows: tuple[Row, ...]) -> tuple[list[tuple[str, Counter[str]]], int, int]:
    """Results per check, kept apart by the real name and shown by the printed one: two names that differ only in a
    hidden word stay two lines (PR #14 review, M5)."""
    by_name: dict[str, Counter[str]] = {}
    none_ran = not_read = 0
    for row in rows:
        if row.results is None:
            not_read += 1
        elif not row.results:
            none_ran += 1
        for name, state in row.results or ():
            by_name.setdefault(name, Counter())[state] += 1
    shown = sorted(by_name.items(), key=lambda item: (mask(item[0]).casefold(), mask(item[0]), item[0]))
    return [(mask(name), states) for name, states in shown], none_ran, not_read


def _pushes(rows: tuple[Row, ...]) -> int:
    return len({r.change.push for r in rows if r.change.how == DIRECT})


def _sentences(reasons: tuple[str, ...]) -> str:
    """Each reason after the first starts a new sentence, so it starts with a capital letter."""
    return " ".join(r if i == 0 else r[:1].upper() + r[1:] for i, r in enumerate(reasons))


def _exceptions(record: Record, rule: Rule) -> list[str]:
    lines = ["## Exceptions under the rule", "", sentence(rule), ""]
    for repository in record.repositories:
        mine = [row for row in record.rows if row.change.repository == repository and row.reasons]
        pulls = sorted((r for r in mine if r.change.how != DIRECT), key=lambda r: int(r.change.change[1:]))
        pushes = sorted((r for r in mine if r.change.how == DIRECT), key=lambda r: (r.change.when, r.change.change))
        if pulls or pushes:
            lines += [f"### {repository}", ""]
            lines += [f"- {r.change.change}: {_sentences(r.reasons)}" for r in pulls + pushes]
            lines.append("")
    return lines


def markdown(record: Record, csv_sum: str, json_sum: str) -> str:
    rows = record.rows
    pulls = sum(1 for r in rows if r.change.how != DIRECT)
    patterns = Counter(r.who.pattern for r in rows)
    declared = sum(1 for r in rows if r.who.pattern == ONE_ACCOUNT and r.who.declared_agent_operated)
    by_name, none_ran, not_read = _checks(rows)
    lines = ["# Record of changes", "", f"Repositories: {', '.join(record.repositories)}. {_period(record)}", ""]
    lines += [
        "## Totals",
        "",
        f"- Changes: {len(rows)} ({pulls} through a pull request, {len(rows) - pulls} pushed directly)",
    ]
    lines.append(f"- Pushed directly: {count(len(rows) - pulls, 'commit')} in {count(_pushes(rows), 'push', 'pushes')}")
    lines.append(f"- AI shown: {sum(1 for r in rows if r.who.ai_shown == 'yes')}")
    if record.rule is not None:
        lines.append(f"- Exceptions under the rule: {sum(1 for r in rows if r.reasons)}")
    lines += ["", "## Patterns", ""]
    for pattern in PATTERNS:
        extra = f", of which {declared} declared agent-operated" if pattern == ONE_ACCOUNT else ""
        lines.append(f"- {pattern}: {patterns[pattern]}{extra}")
    lines += ["", "## Checks on the merged version", ""]
    for name, states in by_name:
        counts = sorted(states.items(), key=lambda item: (-item[1], item[0]))
        lines.append(f"- {_cell(name)}: " + ", ".join(f"{state} {n}" for state, n in counts))
    lines += [f"- No checks ran: {none_ran}", f"- Not read (pushed directly): {not_read}", ""]
    if record.rule is not None:
        lines += _exceptions(record, record.rule)
    lines += ["## Every change", "", "| " + " | ".join((*HEADER, "Checks")) + " |", "|" + " --- |" * 10]
    for r in rows:
        c, w = r.change, r.who
        cells = (
            c.repository,
            f"[{c.change}]({link(c)})",
            f"{day(c.when)} {clock(c.when)}",
            c.how,
            w.builder,
            w.let_in_by,
            w.approvals,
            w.ai_shown,
            w.pattern,
            r.checks,
        )
        lines.append("| " + " | ".join(_cell(x) for x in cells) + " |")
    lines.append("")
    if record.rewritten:
        lines += ["## History rewritten", "", *(f"- {x}" for x in record.rewritten), ""]
    lines += ["## What was not covered", "", *(f"- {x}" for x in record.not_covered or ("Nothing.",)), ""]
    lines += ["## What this record cannot show", "", *(f"- {x}" for x in CANNOT_SHOW), ""]
    if record.disclosures:
        lines += ["## Disclosures", "", *(f"- {x}" for x in record.disclosures), ""]
    lines += ["## Checksums", "", f"- changes.csv SHA-256: {csv_sum}", f"- record.json SHA-256: {json_sum}"]
    return "\n".join(lines) + "\n"


def as_json(record: Record) -> str:
    rows = record.rows
    pulls = sum(1 for r in rows if r.change.how != DIRECT)
    by_name, none_ran, not_read = _checks(rows)
    data: dict[str, Any] = {
        "repositories": list(record.repositories),
        "period": {"start": iso(record.start), "end": iso(record.end)},
        "rule": None
        if record.rule is None
        else {
            "allowed_patterns": list(record.rule.allowed),
            "required_checks": [mask(name) for name in record.rule.required],
        },
        "totals": {
            "changes": len(rows),
            "pull_requests": pulls,
            "pushed_directly": len(rows) - pulls,
            "pushes": _pushes(rows),
            "ai_shown": sum(1 for r in rows if r.who.ai_shown == "yes"),
            "exceptions": None if record.rule is None else sum(1 for r in rows if r.reasons),
        },
        "patterns": {
            pattern: {
                "changes": sum(1 for r in rows if r.who.pattern == pattern),
                "declared_agent_operated": sum(
                    1 for r in rows if r.who.pattern == pattern and r.who.declared_agent_operated
                ),
            }
            for pattern in PATTERNS
        },
        "checks": {
            "by_name": [{"name": name, "results": dict(states)} for name, states in by_name],
            "no_checks_ran": none_ran,
            "not_read_pushed_directly": not_read,
        },
        "changes": [
            {
                "repository": r.change.repository,
                "change": r.change.change,
                "link": link(r.change),
                "how": r.change.how,
                "when": iso(r.change.when),
                "builder": r.who.builder,
                "let_in_by": r.who.let_in_by,
                "approvals": r.who.approvals,
                "ai_shown": r.who.ai_shown,
                "ai_trace": r.who.ai_trace,
                "pattern": r.who.pattern,
                "declared_agent_operated": r.who.declared_agent_operated,
                "checks": r.checks,
                "exceptions": list(r.reasons),
            }
            for r in rows
        ],
        "not_covered": list(record.not_covered),
        "history_rewritten": list(record.rewritten),
        "disclosures": list(record.disclosures),
    }
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
