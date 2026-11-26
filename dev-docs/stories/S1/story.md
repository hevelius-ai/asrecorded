# S1: The list of changes

## Request (the owner's words, unchanged)

As the owner, I want every change that reached the default branch in a period listed exactly once, so that nothing is left out of the record.

1. Given the example set, when the list is built, then it holds #11 to #16, #18 and commit `a1b2c3d`, and not #17.
2. Given a repository that merges by squash and one that merges with merge commits, when the list is built, then each pull request appears once and none of its commits appears as a direct push.
3. Given a repository the sign-in cannot read, when collection runs, then it stops and names the repository, and writes no record.

## Criteria

| ID | Criterion | Cites |
| --- | --- | --- |
| S1-C1 | Given saved GitHub replies for `acme/shop` (the example set) and the period 2026-11-01T00:00:00Z (included) to 2026-12-01T00:00:00Z (excluded), `python -m asrecorded run settings.toml` writes `changes.csv` whose `acme/shop` rows are exactly #11, #12, #13, #14, #15, #16 and #18 (how: `pull request`) and `a1b2c3d` (how: `pushed directly`) | Request, sentences 1 and 2 |
| S1-C2 | #17, merged at exactly 2026-12-01T00:00:00Z, has no row, and the screen shows the line `acme/shop: 8 changes (7 pull requests, 1 commit pushed directly)` | Request, sentence 2 |
| S1-C3 | For `acme/squash` (squash merges) and `acme/joined` (merge commits), each pull request has one row, no commit of a pull request has a `pushed directly` row, and the screen shows `acme/squash: 2 changes (2 pull requests, 0 commits pushed directly)` and `acme/joined: 2 changes (2 pull requests, 0 commits pushed directly)` | Request, sentence 3 |
| S1-C4 | For `acme/rewritten`, a force push on 2026-11-20 at 09:00 UTC by `lee` that brought in 3 commits is shown as `acme/rewritten: history rewritten on 2026-11-20 at 09:00 UTC by lee, 3 commits brought in`, and none of those commits has a row | Request, sentence 1; decision S0-2 |
| S1-C5 | When the sign-in cannot read `acme/secret`, `run` stops with a non-zero exit, shows `Cannot read acme/secret with your GitHub sign-in. No record was written.`, and writes neither `record.md` nor `changes.csv` | Request, sentence 4 |

## Plain checklist (approved by the owner; the receipt quotes it word for word)

| ID | plain: | Examples (approved) |
| --- | --- | --- |
| S1-C1 | With the saved example data for the shop project, 1 Nov to 1 Dec 2026, the list holds exactly 8 changes: #11, #12, #13, #14, #15, #16 and #18, and the piece of work `a1b2c3d` pushed straight to the main line (commit). | `acme/shop,#11,pull request` `acme/shop,a1b2c3d,pushed directly` |
| S1-C2 | #17, let in at exactly 1 Dec 2026 00:00:00 UTC (merged), is not in the list, because the end of the period is not part of it. | `acme/shop: 8 changes (7 pull requests, 1 commit pushed directly)` |
| S1-C3 | A project that squashes each pull request into one piece of work (squash merge), and one that joins them in with an extra piece of work (merge commit), each show every pull request once, and none of their pieces of work as pushed straight in. | `acme/squash: 2 changes (2 pull requests, 0 commits pushed directly)` `acme/joined: 2 changes (2 pull requests, 0 commits pushed directly)` |
| S1-C4 | When history was rewritten (force push), it is listed on its own, and what it brought back is not counted as changes. | `acme/rewritten: history rewritten on 2026-11-20 at 09:00 UTC by lee, 3 commits brought in` |
| S1-C5 | When your GitHub sign-in cannot read a project, collecting stops, names the project, and no record is written. | `Cannot read acme/secret with your GitHub sign-in. No record was written.` |

The examples of S1-C1 were shown to the owner as two rows, `acme/shop` `#11` `pull request` and `acme/shop` `a1b2c3d` `pushed directly`; each is written here as one example, the row's repository, change and how joined by commas, because a check holds at most three examples.

## Not in this story

- Who built each change, who let it in, approvals, AI shown and the pattern: S2. The checks on the merged version: S3. `record.md`, `record.json`, the totals and the rule: S4. This story writes `changes.csv` with the columns `repository`, `change`, `how` and `when` (UTC, as `2026-11-02T10:00:00Z`); later stories add columns at the end.
- The "not covered" lines of the cross-check (design §3 step 1) and the period's start are built and tested in the build's own tests, with no check here.
- The checks run the tool with a stand-in for `gh`, named in `ASRECORDED_GH` (design §4); they never call GitHub.
