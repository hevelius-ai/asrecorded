# AsBuild in practice

A log of using AsBuild v0.4.2 to build this repository: each verdict, each time AsBuild waited for the owner and why, each wrong or confusing result, and the minutes lost. Nothing here is fixed in AsBuild (A1, A9); each problem goes to the owner.

## Known before the first story

- The story checklist bans the words merge, commit, branch and test outside brackets. This tool's checks are about merges and commits, so most checklist lines will need those words in brackets.

## Log

| Date (UTC) | Step | What happened | Minutes lost |
| --- | --- | --- | --- |
| 2026-11-26 | `/asbuild:setup` | Exit 0 on the first try. It pushed the branch `asbuild-setup` and opened GitHub's "new pull request" page for the owner; the owner opens and merges the pull request. That makes the owner the account that opened it as well as the one that merged it (PR #2, merged 16:22 UTC) | 0 |
| 2026-11-26 | `/asbuild:verdict`, PR #1 (docs only) | First verdict: WAITING FOR YOU, `NO_STORY` (branch `docs/S0`) and `NO_RESULTS`; 0 other tests. Expected: no story covers a docs-only pull request, so the owner's merge is the decision. While it waits, the AsBuild check's result is `action_required` ("AsBuild: WAITING FOR YOU"). A second push (`e3ecfda`) gave the same verdict | 0 |

## Summary (written at the release)

- What worked:
- What got in the way:
- What a new user would trip on:
