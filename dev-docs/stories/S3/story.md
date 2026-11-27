# S3: Checks on the merged version

## Request (the owner's words, unchanged)

As a reader, I want to see which checks ran on the version that was merged and how they ended.

1. Given #16, when checks are read, then `ci` shows as failed on the merged version.
2. Given a pull request whose checks passed on an earlier commit and did not run on the last one, when checks are read, then the row says no checks ran on the merged version.
3. Given no checks at all, when the row is written, then it says "no checks ran", not "passed".
4. Given a repository that uses AsBuild, when checks are read, then the check named "AsBuild" is shown by name and result like any other check, with no special handling.

## Criteria

| ID | Criterion | Cites |
| --- | --- | --- |
| S3-C1 | Given saved GitHub replies for `acme/shop` (the example set; on #16's last commit, a check run `ci` that started and completed before the merge with the conclusion `failure`) and the period 2026-11-01T00:00:00Z to 2026-12-01T00:00:00Z, `python -m asrecorded run settings.toml` writes `changes.csv` whose `checks` column reads `ci: failure` for #16 | Request, sentences 1 and 2 |
| S3-C2 | For `acme/checks`, #2's checks ran on an earlier commit (a check run `ci`, `success`) and none on its last commit; #2's `checks` reads `no checks ran on the merged version` | Request, sentence 3 |
| S3-C3 | For `acme/checks`, #3 has no check run and no commit status on any commit; its `checks` reads `no checks ran on the merged version`, and no `checks` cell holds the word `passed` | Request, sentence 4 |
| S3-C4 | For `acme/checks`, #4's last commit has two check runs that completed with `success` before the merge, `AsBuild` and `ci`; its `checks` reads `AsBuild: success; ci: success` | Request, sentence 5 |

## Plain checklist (approved by the owner; the receipt quotes it word for word)

| ID | plain: | Examples (approved) |
| --- | --- | --- |
| S3-C1 | With the saved example data for the shop project, #16 shows its `ci` check failed on the version that was let in (merged). | `#16 checks: ci: failure` |
| S3-C2 | When a pull request's checks ran on an earlier piece of work (commit) and none ran on the last one, its row says no checks ran on the version that was let in. | `acme/checks #2 checks: no checks ran on the merged version` |
| S3-C3 | A pull request with no checks at all says the same, and never "passed". | `acme/checks #3 checks: no checks ran on the merged version` |
| S3-C4 | A check named "AsBuild" is shown by its name and result like any other check. | `acme/checks #4 checks: AsBuild: success; ci: success` |

Each example is written as the change (with its project when it is not the shop project), the column of `changes.csv`, a colon and the cell. The new column, after `declared_agent_operated`, is `checks`.

Where these checks depart from the request, as agreed with the owner on 27 Nov 2026:

- Sentences 3 and 4 (S3-C2, S3-C3) give the same words, `no checks ran on the merged version`. The tool reads only the checks on a pull request's last commit (design section 2 and section 3 step 5, S0-5), so it cannot tell "ran on an earlier commit" from "never ran"; the words hold "no checks ran", as sentence 4 asks.
- Sentences 3 to 5 use a small new example project, `acme/checks`, because the example set has no pull request of those kinds.

## Not in this story

- A result is written as GitHub gives it (`success`, `failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `action_required`; for a commit status `success`, `failure`, `error`), never as "passed" (a banned word).
- Several checks in one cell: `name: result`, sorted by name, joined by `; `.
- For each name, the last check run that started before the merge; one that started before it and completed after it reads `not finished at the merge`; one that started after the merge is not read (S0-5). Commit statuses: for each context, the last entry created before the merge; `pending` reads `not finished at the merge`.
- A direct push: `checks not read for a direct push`; `record.md`'s "What was not covered" says so (S4).
- The other example rows: #11, #12, #13, #14, #15 and #18 read `ci: success`.
- `record.md`'s checks summary and the rule's required checks: S4.
- The checks run the tool with a stand-in for `gh`, named in `ASRECORDED_GH` (design section 4); they never call GitHub.
