"""Who built a change, who let it in, approvals, AI shown and the pattern (design §3 steps 2 to 4), from saved data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from asrecorded.changes import Change, RepositoryList
from asrecorded.errors import Stop
from asrecorded.times import parse
from asrecorded.who import Who, describe, pattern_line

MERGED = "2026-11-10T10:00:00Z"
HEAD, EARLIER = "h" * 40, "e" * 40
IDS = {
    "dana": 1001,
    "lee": 1002,
    "builder-bot": 1003,
    "review-bot[bot]": 1004,
    "deps[bot]": 1006,
    "merger[bot]": 1007,
    "github-merge-queue[bot]": 118344674,
}
DECLARED = frozenset({"builder-bot"})
CLAUDE = "work\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"


def account(login: str) -> dict[str, Any]:
    oid = {"Copilot": 198982749}.get(login, IDS.get(login, 9999))
    return {"login": login, "id": oid, "type": "Bot" if login.endswith("[bot]") or login == "Copilot" else "User"}


def piece(message: str = "work") -> dict[str, Any]:
    return {"sha": HEAD, "commit": {"message": message, "author": {"name": "x", "email": "noreply@github.com"}}}


def review(login: str, when: str = "2026-11-10T09:00:00Z", state: str = "APPROVED", on: str = HEAD) -> dict[str, Any]:
    return {"id": 1, "user": account(login), "state": state, "commit_id": on, "submitted_at": when}


def event(kind: str, login: str, when: str = "2026-11-10T09:30:00Z") -> dict[str, Any]:
    return {"event": kind, "actor": account(login), "created_at": when}


def merged(login: str) -> dict[str, Any]:
    return {"event": "merged", "actor": account(login), "commit_id": "m" * 40, "created_at": MERGED}


def committed() -> dict[str, Any]:
    return {"event": "committed", "sha": HEAD, "message": "work"}  # no actor, as GitHub gives it


def pull_request(
    tmp: Path,
    opener: str,
    merger: str,
    reviews: list[dict[str, Any]] | None = None,
    timeline: list[dict[str, Any]] | None = None,
    pieces: list[dict[str, Any]] | None = None,
    number: int = 11,
) -> Change:
    base = tmp / "pr" / str(number)
    base.mkdir(parents=True, exist_ok=True)
    detail = {
        "number": number,
        "merged_at": MERGED,
        "head": {"sha": HEAD},
        "user": account(opener),
        "merged_by": account(merger),
    }
    files = {
        "pull.json": detail,
        "reviews.json": reviews or [],
        "timeline.json": [committed(), merged(merger)] if timeline is None else timeline,
        "commits.json": pieces or [piece()],
    }
    for name, value in files.items():
        (base / name).write_text(json.dumps(value), encoding="utf-8")
    return Change("acme/shop", f"#{number}", "pull request", parse(MERGED))


def one(tmp: Path, change: Change, declared: frozenset[str] = DECLARED) -> Who:
    details, _ = describe(RepositoryList("acme/shop", [change]), tmp, declared)
    return details[change.change]


def test_a_person_who_approves_another_persons_change_makes_two_people(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "dana", "dana", [review("lee")]))
    assert who == Who("dana", "dana", "lee (on the merged version)", "not shown", "", "Two people", "")


def test_a_person_merging_by_hand_a_declared_accounts_change_makes_agent_and_person(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "builder-bot", "lee"))
    assert (who.builder, who.let_in_by, who.pattern) == ("builder-bot", "lee", "Agent and person")
    assert (who.ai_shown, who.ai_trace, who.declared_agent_operated) == ("yes", "declared agent-operated account", "")


def test_a_dependency_bot_is_the_automated_side_but_shows_no_ai(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "deps[bot]", "lee"))
    assert (who.pattern, who.ai_shown, who.ai_trace) == ("Agent and person", "not shown", "")


def test_approvals_only_from_agents_make_ai_reviewer_only(tmp_path: Path) -> None:
    change = pull_request(tmp_path, "builder-bot", "builder-bot", [review("review-bot[bot]"), review("builder-bot")])
    who = one(tmp_path, change)
    assert who.pattern == "AI reviewer only"
    assert who.approvals == "review-bot[bot] (on the merged version); builder-bot (on the merged version)"


def test_auto_merge_switched_on_makes_automatic_and_names_who(tmp_path: Path) -> None:
    timeline = [committed(), event("auto_merge_enabled", "dana"), merged("dana")]
    who = one(tmp_path, pull_request(tmp_path, "builder-bot", "dana", timeline=timeline))
    assert (who.let_in_by, who.pattern) == ("auto-merge switched on by dana", "Automatic, no approval")


def test_auto_merge_switched_off_before_the_merge_is_a_hand_merge(tmp_path: Path) -> None:
    timeline = [event("auto_squash_enabled", "dana"), event("auto_merge_disabled", "dana"), merged("lee")]
    who = one(tmp_path, pull_request(tmp_path, "dana", "lee", timeline=timeline))
    assert (who.let_in_by, who.pattern) == ("lee", "Two people")


def test_auto_merge_after_the_merged_entry_is_not_read(tmp_path: Path) -> None:
    timeline = [merged("lee"), event("auto_rebase_enabled", "lee")]
    who = one(tmp_path, pull_request(tmp_path, "dana", "lee", timeline=timeline))
    assert (who.let_in_by, who.pattern) == ("lee", "Two people")


def test_a_timeline_with_no_merged_entry_is_read_whole(tmp_path: Path) -> None:
    for timeline in ([event("auto_merge_enabled", "dana")], []):
        who = one(tmp_path, pull_request(tmp_path, "builder-bot", "dana", timeline=timeline))
        expected = "Automatic, no approval" if timeline else "Agent and person"
        assert who.pattern == expected


def test_a_merge_queue_makes_automatic_and_gets_a_not_covered_line(tmp_path: Path) -> None:
    timeline = [event("auto_merge_enabled", "dana"), event("added_to_merge_queue", "dana"), merged("dana")]
    change = pull_request(tmp_path, "builder-bot", "dana", timeline=timeline)
    details, not_covered = describe(RepositoryList("acme/shop", [change]), tmp_path, DECLARED)
    assert (details["#11"].let_in_by, details["#11"].pattern) == (
        "merge queue: added by dana",
        "Automatic, no approval",
    )
    assert not_covered == ["acme/shop: not covered: #11 was let in by a merge queue, which this record does not follow"]


def test_a_change_taken_out_of_the_merge_queue_and_merged_by_hand(tmp_path: Path) -> None:
    timeline = [event("added_to_merge_queue", "dana"), event("removed_from_merge_queue", "dana"), merged("lee")]
    change = pull_request(tmp_path, "dana", "lee", timeline=timeline)
    details, not_covered = describe(RepositoryList("acme/shop", [change]), tmp_path, DECLARED)
    assert (details["#11"].let_in_by, details["#11"].pattern, not_covered) == ("lee", "Two people", [])


def test_an_agent_merging_a_change_it_did_not_open_is_automatic(tmp_path: Path) -> None:
    assert one(tmp_path, pull_request(tmp_path, "dana", "builder-bot")).pattern == "Automatic, no approval"


def test_a_bot_merging_its_own_change_is_automatic(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "merger[bot]", "merger[bot]"))
    assert (who.let_in_by, who.pattern) == ("merger[bot]", "Automatic, no approval")


def test_one_account_is_marked_declared_only_for_a_declared_account(tmp_path: Path) -> None:
    declared = one(tmp_path, pull_request(tmp_path, "builder-bot", "builder-bot"))
    assert (declared.pattern, declared.declared_agent_operated) == ("One account", "yes")
    person = one(tmp_path, pull_request(tmp_path, "dana", "dana", pieces=[piece(CLAUDE)], number=13))
    assert (person.pattern, person.declared_agent_operated) == ("One account", "")
    assert (person.ai_shown, person.ai_trace) == ("yes", "commit marker: Claude (Anthropic)")


def test_approvals_that_do_not_count(tmp_path: Path) -> None:
    late = review("lee", "2026-11-10T11:00:00Z")
    dismissed = review("lee", state="DISMISSED")
    other = review("lee", state="COMMENTED")
    ghost = review("lee") | {"user": None}
    who = one(tmp_path, pull_request(tmp_path, "dana", "dana", [late, dismissed, other, ghost]))
    assert (who.approvals, who.pattern) == ("", "One account")


def test_an_approval_on_an_earlier_version_counts_and_says_so(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "dana", "dana", [review("lee", on=EARLIER)]))
    assert (who.approvals, who.pattern) == ("lee (on an earlier version)", "Two people")


def test_each_approver_is_listed_once_by_their_last_approval_in_time_order(tmp_path: Path) -> None:
    reviews = [
        review("lee", "2026-11-10T08:00:00Z"),
        review("review-bot[bot]", "2026-11-10T07:00:00Z"),
        review("lee", "2026-11-09T08:00:00Z", on=EARLIER),
    ]
    who = one(tmp_path, pull_request(tmp_path, "dana", "dana", reviews))
    assert who.approvals == "review-bot[bot] (on the merged version); lee (on the merged version)"


def test_a_listed_coding_agent_account_and_a_commit_marker_are_both_shown_account_first(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "Copilot", "lee", pieces=[piece(CLAUDE)]))
    assert who.ai_trace == "coding agent account: GitHub Copilot; commit marker: Claude (Anthropic)"
    declared = one(tmp_path, pull_request(tmp_path, "builder-bot", "lee", pieces=[piece(CLAUDE)], number=12))
    assert declared.ai_trace == "declared agent-operated account; commit marker: Claude (Anthropic)"


def test_a_direct_push_has_no_builder_and_names_the_pusher(tmp_path: Path) -> None:
    plain = Change("acme/shop", "a1b2c3d", "pushed directly", parse(MERGED), account("lee"), piece())
    marked = Change("acme/shop", "b1b2c3d", "pushed directly", parse(MERGED), account("builder-bot"), piece(CLAUDE))
    details, _ = describe(RepositoryList("acme/shop", [plain, marked]), tmp_path, DECLARED)
    assert details["a1b2c3d"] == Who(
        "no pull request: not shown", "pushed by lee", "", "not shown", "", "No pull request", ""
    )
    assert details["b1b2c3d"].ai_trace == "declared agent-operated account; commit marker: Claude (Anthropic)"


def test_the_screen_counts_one_account_and_the_declared_ones_among_them(tmp_path: Path) -> None:
    changes = [
        pull_request(tmp_path, "builder-bot", "builder-bot", number=18),
        pull_request(tmp_path, "dana", "dana", number=13),
        pull_request(tmp_path, "dana", "lee", number=11),
    ]
    details, _ = describe(RepositoryList("acme/shop", changes), tmp_path, DECLARED)
    assert pattern_line("acme/shop", details) == "acme/shop: One account 2 (1 declared agent-operated)"
    assert pattern_line("acme/none", {}) == "acme/none: One account 0 (0 declared agent-operated)"


def test_a_missing_saved_file_stops_with_a_plain_sentence(tmp_path: Path) -> None:
    change = pull_request(tmp_path, "dana", "dana")
    (tmp_path / "pr" / "11" / "reviews.json").unlink()
    with pytest.raises(Stop) as stop:
        describe(RepositoryList("acme/shop", [change]), tmp_path, DECLARED)
    assert stop.value.message == (
        "The saved data for acme/shop is missing pr/11/reviews.json. Run collect again. No record was written."
    )


def test_saved_data_of_the_wrong_shape_stops_with_a_plain_sentence(tmp_path: Path) -> None:
    change = pull_request(tmp_path, "dana", "dana")
    (tmp_path / "pr" / "11" / "pull.json").write_text(json.dumps({"number": 11}), encoding="utf-8")
    with pytest.raises(Stop) as stop:
        describe(RepositoryList("acme/shop", [change]), tmp_path, DECLARED)
    assert stop.value.message == (
        "The saved data for acme/shop could not be read. Run collect again. No record was written."
    )


QUEUE_BOT = "github-merge-queue[bot]"


def test_github_removing_the_change_from_the_queue_as_it_merges_it_is_still_a_merge_queue(tmp_path: Path) -> None:
    """As microsoft/vscode #350667 (27 Nov 2026): added by a person, removed by GitHub's queue bot, then merged."""
    timeline = [event("added_to_merge_queue", "dana"), event("removed_from_merge_queue", QUEUE_BOT), merged("dana")]
    change = pull_request(tmp_path, "dana", "dana", timeline=timeline)
    details, not_covered = describe(RepositoryList("acme/shop", [change]), tmp_path, DECLARED)
    assert (details["#11"].let_in_by, details["#11"].pattern) == (
        "merge queue: added by dana",
        "Automatic, no approval",
    )
    assert len(not_covered) == 1


def test_a_draft_review_with_no_time_is_not_counted_and_stops_nothing(tmp_path: Path) -> None:
    draft = {"id": 2, "user": account("lee"), "state": "PENDING", "commit_id": HEAD}  # no submitted_at
    who = one(tmp_path, pull_request(tmp_path, "dana", "dana", [draft, review("review-bot[bot]")]))
    assert (who.approvals, who.pattern) == ("review-bot[bot] (on the merged version)", "AI reviewer only")


def test_a_saved_file_that_cannot_be_opened_stops_with_a_plain_sentence(tmp_path: Path) -> None:
    change = pull_request(tmp_path, "dana", "dana")
    reviews = tmp_path / "pr" / "11" / "reviews.json"
    reviews.unlink()
    reviews.mkdir()  # opening it fails as a locked file does on Windows
    with pytest.raises(Stop) as stop:
        describe(RepositoryList("acme/shop", [change]), tmp_path, DECLARED)
    assert stop.value.message.startswith("Cannot read the saved data for acme/shop: ")
    assert stop.value.message.endswith(
        "Close any program that has it open, then run write again. No record was written."
    )


def test_saved_data_nested_too_deep_stops_with_a_plain_sentence(tmp_path: Path) -> None:
    change = pull_request(tmp_path, "dana", "dana")
    (tmp_path / "pr" / "11" / "timeline.json").write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
    with pytest.raises(Stop) as stop:
        describe(RepositoryList("acme/shop", [change]), tmp_path, DECLARED)
    assert stop.value.message == (
        "The saved data for acme/shop could not be read. Run collect again. No record was written."
    )


def test_a_declared_account_is_matched_whatever_the_letter_case(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "builder-bot", "builder-bot"), frozenset({"Builder-Bot"}))
    assert (who.ai_trace, who.pattern, who.declared_agent_operated) == (
        "declared agent-operated account",
        "One account",
        "yes",
    )


def test_an_auto_merge_or_queue_entry_with_no_account_is_still_automatic(tmp_path: Path) -> None:
    for kind, words in (("auto_merge_enabled", "auto-merge switched on"), ("added_to_merge_queue", "merge queue")):
        timeline = [{"event": kind, "actor": None, "created_at": "2026-11-10T09:30:00Z"}, merged("dana")]
        who = one(tmp_path, pull_request(tmp_path, "builder-bot", "dana", timeline=timeline))
        assert (who.let_in_by, who.pattern) == (f"{words} (account not shown)", "Automatic, no approval")


def test_auto_squash_and_auto_rebase_switch_auto_merge_on(tmp_path: Path) -> None:
    for kind in ("auto_squash_enabled", "auto_rebase_enabled"):
        timeline = [event(kind, "dana"), merged("dana")]
        who = one(tmp_path, pull_request(tmp_path, "builder-bot", "dana", timeline=timeline))
        assert (who.let_in_by, who.pattern) == ("auto-merge switched on by dana", "Automatic, no approval")


def test_an_approval_by_another_declared_account_is_not_a_persons(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "dana", "dana", [review("builder-bot")]))
    assert who.pattern == "AI reviewer only"


def test_an_approval_given_in_the_same_second_as_the_merge_is_not_counted(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "dana", "dana", [review("lee", MERGED)]))
    assert (who.approvals, who.pattern) == ("", "One account")


def test_a_direct_push_by_a_declared_account_is_not_marked_declared_agent_operated(tmp_path: Path) -> None:
    pushed = Change("acme/shop", "c1b2c3d", "pushed directly", parse(MERGED), account("builder-bot"), piece())
    details, _ = describe(RepositoryList("acme/shop", [pushed]), tmp_path, DECLARED)
    assert details["c1b2c3d"] == Who(
        "no pull request: not shown",
        "pushed by builder-bot",
        "",
        "yes",
        "declared agent-operated account",
        "No pull request",
        "",
    )


def test_a_listed_coding_agent_that_is_also_declared_shows_one_account_kind(tmp_path: Path) -> None:
    who = one(tmp_path, pull_request(tmp_path, "Copilot", "lee"), frozenset({"Copilot"}))
    assert who.ai_trace == "coding agent account: GitHub Copilot"
