"""record.md and record.json (design §3 step 7; the S4 sample the owner approved), from the rows alone."""

from __future__ import annotations

import json

from asrecorded.changes import Change
from asrecorded.record import Record, Row, as_json, markdown
from asrecorded.rule import Rule
from asrecorded.times import parse
from asrecorded.who import Who

PUSHED = Who("no pull request: not shown", "pushed by lee", "", "not shown", "", "No pull request", "")
SUM_CSV, SUM_JSON = "a" * 64, "b" * 64


def row(
    repo: str,
    change: str,
    when: str,
    who: Who,
    results: tuple[tuple[str, str], ...] | None,
    checks: str,
    reasons: tuple[str, ...] = (),
) -> Row:
    how = "pushed directly" if results is None else "pull request"
    commit = {"sha": change + "e" * 33} if results is None else None
    actor = {"login": "lee"} if results is None else None
    push = f"{'1' * 40}...{change}{'e' * 33}" if results is None else None
    return Row(Change(repo, change, how, parse(when), actor, commit, push), who, results, checks, reasons)


ROWS = (
    row(
        "acme/shop",
        "#11",
        "2026-11-02T10:00:00Z",
        Who("dana", "dana", "lee (on the merged version)", "not shown", "", "Two people", ""),
        (("ci", "success"),),
        "ci: success",
    ),
    row(
        "acme/shop",
        "#13",
        "2026-11-04T10:00:00Z",
        Who("bot", "bot", "", "yes", "declared agent-operated account", "One account", "yes"),
        (("ci", "failure"), ("lint", "success")),
        "ci: failure; lint: success",
        (
            'the pattern "One account" is not allowed by the rule.',
            'the required check "ci" did not end in success on the merged version (it shows: failure).',
        ),
    ),
    row("acme/shop", "a1b2c3d", "2026-11-03T10:00:00Z", PUSHED, None, "checks not read for a direct push"),
    row(
        "acme/other",
        "#2",
        "2026-11-05T10:00:00Z",
        Who("dana", "auto-merge switched on by lee", "", "not shown", "", "Automatic, no approval", ""),
        (),
        "no checks ran on the merged version",
        ('the pattern "Automatic, no approval" is not allowed by the rule.',),
    ),
    row(
        "acme/other",
        "#3",
        "2026-11-06T10:00:00Z",
        Who("dana", "lee", "", "not shown", "", "Two people", ""),
        (("a|b", "success"),),
        "a|b: success",
    ),
)
RECORD = Record(
    repositories=("acme/shop", "acme/other"),
    start=parse("2026-11-01T00:00:00Z"),
    end=parse("2026-12-01T00:00:00Z"),
    rule=Rule(("Two people", "Agent and person"), ("ci",)),
    rows=ROWS,
    not_covered=("acme/shop: not covered: checks were not read for 1 commit pushed directly",),
    rewritten=("acme/other: history rewritten on 2026-11-20 at 09:00 UTC by lee, 3 commits brought in",),
    disclosures=("One person directs the agent account.",),
)

EXPECTED = f"""# Record of changes

Repositories: acme/shop, acme/other. Period: 2026-11-01 00:00 UTC (included) to 2026-12-01 00:00 UTC (not included).

## Totals

- Changes: 5 (4 through a pull request, 1 pushed directly)
- Pushed directly: 1 commit in 1 push
- AI shown: 1
- Exceptions under the rule: 2

## Patterns

- Two people: 2
- Agent and person: 0
- AI reviewer only: 0
- Automatic, no approval: 1
- One account: 1, of which 1 declared agent-operated
- No pull request: 1

## Checks on the merged version

- a\\|b: success 1
- ci: failure 1, success 1
- lint: success 1
- No checks ran: 1
- Not read (pushed directly): 1

## Exceptions under the rule

The rule allows the patterns Two people and Agent and person, and requires the check ci.

### acme/shop

- #13: the pattern "One account" is not allowed by the rule. The required check "ci" did not end in success on the \
merged version (it shows: failure).

### acme/other

- #2: the pattern "Automatic, no approval" is not allowed by the rule.

## Every change

| Repository | Change | When (UTC) | How | Built by | Let in by | Approvals | AI shown | Pattern | Checks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acme/shop | [#11](https://github.com/acme/shop/pull/11) | 2026-11-02 10:00 | pull request | dana | dana \
| lee (on the merged version) | not shown | Two people | ci: success |
| acme/shop | [#13](https://github.com/acme/shop/pull/13) | 2026-11-04 10:00 | pull request | bot | bot |  | yes \
| One account | ci: failure; lint: success |
| acme/shop | [a1b2c3d](https://github.com/acme/shop/commit/a1b2c3d{"e" * 33}) | 2026-11-03 10:00 \
| pushed directly | no pull request: not shown | pushed by lee |  | not shown | No pull request \
| checks not read for a direct push |
| acme/other | [#2](https://github.com/acme/other/pull/2) | 2026-11-05 10:00 | pull request | dana \
| auto-merge switched on by lee |  | not shown | Automatic, no approval | no checks ran on the merged version |
| acme/other | [#3](https://github.com/acme/other/pull/3) | 2026-11-06 10:00 | pull request | dana | lee |  \
| not shown | Two people | a\\|b: success |

## History rewritten

- acme/other: history rewritten on 2026-11-20 at 09:00 UTC by lee, 3 commits brought in

## What was not covered

- acme/shop: not covered: checks were not read for 1 commit pushed directly

## What this record cannot show

- AI use that leaves no trace in the history
- whether an approver read or understood the change
- whether the checks were good checks
- which workflow posted a check of a given name
- two accounts held by one person, unless declared
- anything outside the listed repositories or outside GitHub
- history that was rewritten

## Disclosures

- One person directs the agent account.

## Checksums

- changes.csv SHA-256: {SUM_CSV}
- record.json SHA-256: {SUM_JSON}
"""


def test_the_record_in_plain_words_with_a_rule() -> None:
    assert markdown(RECORD, SUM_CSV, SUM_JSON) == EXPECTED


def test_without_a_rule_there_are_no_exceptions_and_empty_sections_are_left_out() -> None:
    bare = Record(RECORD.repositories, RECORD.start, RECORD.end, None, ROWS, (), (), ())
    text = markdown(bare, SUM_CSV, SUM_JSON)
    assert "Exceptions" not in text
    assert "## History rewritten" not in text
    assert "## Disclosures" not in text
    assert "## What was not covered\n\n- Nothing.\n\n## What this record cannot show" in text


def test_the_record_for_programs_holds_the_same_facts() -> None:
    text = as_json(RECORD)
    assert text == as_json(RECORD)
    data = json.loads(text)
    assert text == json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    assert data["repositories"] == ["acme/shop", "acme/other"]
    assert data["period"] == {"start": "2026-11-01T00:00:00Z", "end": "2026-12-01T00:00:00Z"}
    assert data["rule"] == {"allowed_patterns": ["Two people", "Agent and person"], "required_checks": ["ci"]}
    assert data["totals"] == {
        "changes": 5,
        "pull_requests": 4,
        "pushed_directly": 1,
        "pushes": 1,
        "ai_shown": 1,
        "exceptions": 2,
    }
    assert data["patterns"]["One account"] == {"changes": 1, "declared_agent_operated": 1}
    assert data["patterns"]["Two people"] == {"changes": 2, "declared_agent_operated": 0}
    assert data["checks"] == {
        "by_name": [
            {"name": "a|b", "results": {"success": 1}},
            {"name": "ci", "results": {"failure": 1, "success": 1}},
            {"name": "lint", "results": {"success": 1}},
        ],
        "no_checks_ran": 1,
        "not_read_pushed_directly": 1,
    }
    first = data["changes"][0]
    assert first == {
        "repository": "acme/shop",
        "change": "#11",
        "link": "https://github.com/acme/shop/pull/11",
        "how": "pull request",
        "when": "2026-11-02T10:00:00Z",
        "builder": "dana",
        "let_in_by": "dana",
        "approvals": "lee (on the merged version)",
        "ai_shown": "not shown",
        "ai_trace": "",
        "pattern": "Two people",
        "declared_agent_operated": "",
        "checks": "ci: success",
        "exceptions": [],
    }
    assert data["changes"][1]["exceptions"] == list(ROWS[1].reasons)
    assert data["not_covered"] == list(RECORD.not_covered)
    assert data["history_rewritten"] == list(RECORD.rewritten)
    assert data["disclosures"] == list(RECORD.disclosures)
    bare = json.loads(as_json(Record(RECORD.repositories, RECORD.start, RECORD.end, None, ROWS, (), (), ())))
    assert bare["rule"] is None
    assert bare["totals"]["exceptions"] is None


def test_a_repository_with_no_exception_gets_no_sub_heading() -> None:
    quiet = tuple(r for r in ROWS if r.change.repository == "acme/shop") + (ROWS[4],)
    text = markdown(Record(RECORD.repositories, RECORD.start, RECORD.end, RECORD.rule, quiet, (), (), ()), "", "")
    assert "### acme/shop" in text
    assert "### acme/other" not in text


def test_pushes_are_counted_beside_the_commits_they_brought(tmp_path: object) -> None:
    two = row("acme/shop", "b1b2c3d", "2026-11-03T10:00:00Z", PUSHED, None, "checks not read for a direct push")
    same_push = Row(
        Change("acme/shop", "b1b2c3d", "pushed directly", two.change.when, {"login": "lee"}, {"sha": "b1"}, "p1"),
        PUSHED,
        None,
        "checks not read for a direct push",
        (),
    )
    also = Row(
        Change("acme/shop", "c1b2c3d", "pushed directly", two.change.when, {"login": "lee"}, {"sha": "c1"}, "p1"),
        PUSHED,
        None,
        "checks not read for a direct push",
        (),
    )
    record = Record(RECORD.repositories, RECORD.start, RECORD.end, None, (same_push, also), (), (), ())
    assert "- Pushed directly: 2 commits in 1 push\n" in markdown(record, "", "")
    assert json.loads(as_json(record))["totals"]["pushes"] == 1
    none = Record(RECORD.repositories, RECORD.start, RECORD.end, None, (ROWS[0],), (), (), ())
    assert "- Pushed directly: 0 commits in 0 pushes\n" in markdown(none, "", "")


def test_two_check_names_that_differ_only_in_a_hidden_word_are_not_merged() -> None:
    both = row(
        "acme/shop",
        "#20",
        "2026-11-02T10:00:00Z",
        ROWS[0].who,
        (("all required jobs approved", "success"), ("all required jobs passed", "failure")),
        "",
    )
    record = Record(RECORD.repositories, RECORD.start, RECORD.end, None, (both,), (), (), ())
    text = markdown(record, "", "")
    hidden = "all required jobs [a word this record does not use]"
    assert f"- {hidden}: success 1\n- {hidden}: failure 1\n" in text
    names = json.loads(as_json(record))["checks"]["by_name"]
    assert names == [{"name": hidden, "results": {"success": 1}}, {"name": hidden, "results": {"failure": 1}}]


def test_the_same_push_in_two_repositories_is_two_pushes() -> None:
    shop = Row(
        Change("acme/shop", "b1b2c3d", "pushed directly", ROWS[2].change.when, {"login": "lee"}, {"sha": "b1"}, "p1"),
        PUSHED,
        None,
        "checks not read for a direct push",
        (),
    )
    mirror = Row(
        Change("acme/other", "b1b2c3d", "pushed directly", ROWS[2].change.when, {"login": "lee"}, {"sha": "b1"}, "p1"),
        PUSHED,
        None,
        "checks not read for a direct push",
        (),
    )
    record = Record(RECORD.repositories, RECORD.start, RECORD.end, None, (shop, mirror), (), (), ())
    assert "- Pushed directly: 2 commits in 2 pushes\n" in markdown(record, "", "")
