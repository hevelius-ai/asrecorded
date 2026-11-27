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
| 2026-11-26 to 27 | `/asbuild:verdict`, PR #7 (S1 build) | PROVEN at each of five heads: 1d71248 (149 other tests, 0 broken), cda334b (164), ae3848a (173), 61cd16c (183) and 235736e (186); each said "S1-C1 to C5 work". The verdict arrived within a few minutes of CI each time | 0 |
| 2026-11-27 | `/asbuild:story` S2, PR #8 | `asbuild_story_check.py S2 --lock` passed (5 checks, 5 tests). **Got in the way (our slip):** the first lock was taken before lint, which then found one line over 120 characters; nothing was committed, so the two lock lines were removed, the file formatted and the lock taken again. Lint now runs before the lock | 0 |
| 2026-11-27 | Changing locked tests before the story merge, PR #8 | The procedure worked as written this time: with the owner's permission (PR8-3A), the deny line was removed, a new headless session made the fixes, and `--lock` put the line back (5 checks, 5 tests). One of the fixes reworded an approved line, so the owner approved the new words first | 0 |
| 2026-11-27 | Story PR #8, AsBuild's note | WAITING FOR YOU, as for every story pull request; GitHub showed it as a yellow pending check beside our two red gates (the locked tests, D-CI1). **Confusing for the owner:** "2 failing" on a pull request they are asked to merge; one line in the action block explained it. The owner merged it at 17:23 UTC | 0 |
| 2026-11-27 | `/asbuild:verdict`, PR #9 (S2 build) | PROVEN at each of three heads: 3027b92 (220 other tests, 0 broken), 5f9e388 (232) and d2b64f4 (233); each said "S2-C1 to C5 work". The verdict came about two minutes after the push each time | 0 |
| 2026-11-27 | `/asbuild:verdict`, PR #10 (a fix no story covers) | WAITING FOR YOU, `NO_STORY` (branch `fix/read-errors`); 240 other tests, 0 broken. Expected: the owner's merge is the decision, as for PRs #1, #3, #4 and #6 | 0 |
| 2026-11-27 | `/asbuild:story` S3, PR #11 | `asbuild_story_check.py S3 --lock` passed on the first run (4 checks, 4 tests); lint ran before the lock this time. The owner approved the four lines with no question asked: the agreed design had settled every open point. WAITING FOR YOU on the story pull request, as always | 0 |
| 2026-11-27 | `/asbuild:verdict`, PR #12 (S3 build) | PROVEN at each of three heads: 1e8ce0e (251 other tests, 0 broken), a1eb8b8 (255) and 26e3d4e (255, a docs-only commit); each said "S3-C1 to C4 work" | 0 |
| 2026-11-27 | `/asbuild:story` S4, PR #13 | `asbuild_story_check.py S4 --lock` passed on the first run (5 checks, 5 tests). A check that a test of the code itself exists (line 5) had to fail before the build: written as a script the build adds (`scripts/read_only_check.py`), proved on the package and on copies with planted calls that are not reads | 0 |
| 2026-11-27 | Changing locked tests before the story merge, PR #13 | The procedure as for S1 and S2 (owner's permission PR13-2A, a new session, `--lock`). **Got in the way:** an empty `.git/index.lock`, left by a git command interrupted at the end of the fix session, stopped the first commit; it was removed after checking no git process ran | 0 |

## Summary (written at the release)

- What worked:
- What got in the way:
- What a new user would trip on:
