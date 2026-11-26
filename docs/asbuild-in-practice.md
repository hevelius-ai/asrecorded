# AsBuild in practice

A log of using AsBuild v0.4.2 to build this repository: each verdict, each time AsBuild waited for the owner and why, each wrong or confusing result, and the minutes lost. Nothing here is fixed in AsBuild (A1, A9); each problem goes to the owner.

## Known before the first story

- The story checklist bans the words merge, commit, branch and test outside brackets. This tool's checks are about merges and commits, so most checklist lines will need those words in brackets.

## Log

| Date (UTC) | Step | What happened | Minutes lost |
| --- | --- | --- | --- |
| 2026-11-26 | `/asbuild:setup` | Exit 0 on the first try. It pushed the branch `asbuild-setup` and opened GitHub's "new pull request" page for the owner; the owner opens and merges the pull request. That makes the owner the account that opened it as well as the one that merged it (PR #2, merged 16:22 UTC) | 0 |
| 2026-11-26 | `/asbuild:verdict`, PR #1 (docs only) | First verdict: WAITING FOR YOU, `NO_STORY` (branch `docs/S0`) and `NO_RESULTS`; 0 other tests. Expected: no story covers a docs-only pull request, so the owner's merge is the decision. While it waits, the AsBuild check's result is `action_required` ("AsBuild: WAITING FOR YOU"). A second push (`e3ecfda`) gave the same verdict | 0 |
| 2026-11-26 | `/asbuild:verdict`, PR #3 (tooling) | WAITING FOR YOU: `PROTECTED_CHANGED` for `.github/workflows/ci.yml`, `pyproject.toml` and `requirements-dev.txt`, plus `NO_STORY`. Expected: AsBuild protects files that decide how tests run, so the owner's merge is the decision. **Confusing:** the summary says "other tests: 0 run, 0 broken" although its own run of the full suite produced a results file (`pr_xml: true`) and the suite holds 23 tests | 0 |
| 2026-11-26 | `/asbuild:verdict`, PR #4 (design, docs only) | WAITING FOR YOU: `NO_STORY`, as for PR #1. Expected | 0 |
| 2026-11-26 | `/asbuild:story` S1, PR #5 | `asbuild_story_check.py S1 --lock` passed on the first run (5 checks, 5 tests). **Got in the way:** a check holds at most three examples, so the owner's two-row example for line 1 had to be written as one example per row, each row's repository, change and how joined by commas (noted in `story.md`) | 0 |
| 2026-11-26 | Story PR #5, our own `ci` | **Got in the way:** a story pull request's locked tests fail by design until the build merges, so this repository's own gate, which runs every test, is red on every story pull request and on `main` until the build merges. Before PR #6, that red step also skipped the history check. The owner chose to accept the red step and to run the history check even when an earlier step fails (D-CI1) | 0 |
| 2026-11-26 | Changing locked tests before the story merge, PR #5 | AsBuild's procedure is: remove the deny line, change the test in a new session, rerun the check. **Got in the way:** Claude Code's auto mode refused the builder's removal of the deny line until the owner gave explicit permission in chat ("2A"); with it, the line was removed, the round 1 fixes made, and `--lock` put the line back (5 checks, 5 tests). The test edits then worked in the same session, with no new one; the session had been started outside this repository's folder, which may be why (not proved) | 0 |
| 2026-11-26 | Story PR #5, AsBuild's note | WAITING FOR YOU, as the skill says for a story pull request. The owner merged it at 22:00 UTC | 0 |
| 2026-11-26 | `/asbuild:verdict`, PR #6 (tooling T2) | WAITING FOR YOU: `PROTECTED_CHANGED` for `ci.yml` and `pyproject.toml`, `NO_STORY`. Expected | 0 |

## Summary (written at the release)

- What worked:
- What got in the way:
- What a new user would trip on:
