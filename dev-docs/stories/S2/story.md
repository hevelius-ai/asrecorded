# S2: Who built it, who let it in, who approved, and the pattern

## Request (the owner's words, unchanged)

As a reader, I want each change to say who or what built it and let it in, so that I can see where no second person was involved.

1. Given the example set, when patterns are assigned, then each change gets the pattern in the table above.
2. Given a pull request where the person who merged it also clicked "update branch", when builders are worked out, then that merge commit does not make them a builder.
3. Given #18, when the row is written, then the builder is `builder-bot`, and the login `stranger`, which comes only from a commit's author field, appears in none of the three files.
4. Given a change with no AI marker, when the row is written, then it says "AI not shown", and the record's fixed section says what that does and does not mean.
5. Given #18, when patterns are assigned, then it is "One account", its row says the account is declared agent-operated, and the totals count it under both.

## Criteria

| ID | Criterion | Cites |
| --- | --- | --- |
| S2-C1 | Given saved GitHub replies for `acme/shop` (the example set: `builder-bot`, of type `User`, declared agent-operated in the settings; `lee` approves #11 and #16 on the merged version; `review-bot[bot]`, of type `Bot`, gives #14's only approval; `dana` switches auto-merge on for #15 before it is merged) and the period 2026-11-01T00:00:00Z to 2026-12-01T00:00:00Z, `python -m asrecorded run settings.toml` writes `changes.csv` whose `pattern` column reads `Two people` for #11, `Agent and person` for #12 and #16, `One account` for #13 and #18, `AI reviewer only` for #14, `Automatic, no approval` for #15 and `No pull request` for `a1b2c3d`; #15's `let_in_by` reads `auto-merge switched on by dana` | Request, sentences 1 and 2 |
| S2-C2 | For `acme/updated`, #3 is opened by `dana`; one of its commits is a merge of the main line into it ("update branch": two parents, committer `web-flow`, author field linked by GitHub to `lee`); `lee` merges it by hand. #3's `builder` reads `dana` and its `let_in_by` reads `lee` | Request, sentence 3 |
| S2-C3 | #18's `builder` reads `builder-bot`. One of #18's commits has an author field that GitHub links to `stranger`, an account that took no action on the pull request; the text `stranger` appears in no file in the output folder and nowhere on the screen | Request, sentence 4 |
| S2-C4 | #11, with no sign of AI, has `ai_shown` `not shown` and an empty `ai_trace`; #13, one of whose commits carries a `Co-Authored-By` line naming `Claude Opus 5.5` with Anthropic's no-reply address, has `ai_shown` `yes` and `ai_trace` `commit marker: Claude (Anthropic)` | Request, sentence 5 |
| S2-C5 | #18's `pattern` reads `One account` and its `declared_agent_operated` reads `yes`, and the screen shows the line `acme/shop: One account 2 (1 declared agent-operated)` | Request, sentence 6 |

## Plain checklist (approved by the owner; the receipt quotes it word for word)

| ID | plain: | Examples (approved) |
| --- | --- | --- |
| S2-C1 | With the saved example data for the shop project (`acme/shop`, 1 Nov to 1 Dec 2026), each change shows its pattern: #11 Two people; #12 and #16 Agent and person; #13 and #18 One account; #14 AI reviewer only; #15 Automatic, no approval; `a1b2c3d` No pull request. | `#11 pattern: Two people` `#15 let_in_by: auto-merge switched on by dana` `a1b2c3d pattern: No pull request` |
| S2-C2 | When the person who let a pull request in (merged) also brought it up to date with the main line ("update branch"), the builder is still the person who opened it. | `acme/updated #3 builder: dana` `acme/updated #3 let_in_by: lee` |
| S2-C3 | #18's builder is `builder-bot`. The account `stranger`, named only in the author line of one of its pieces of work (commit), appears in no file the tool writes and nowhere on the screen. | `#18 builder: builder-bot` |
| S2-C4 | A change with no sign of AI says "not shown" under "AI shown", and a change with a sign says what kind and which tool. | `#11 ai_shown: not shown` `#13 ai_shown: yes` `#13 ai_trace: commit marker: Claude (Anthropic)` |
| S2-C5 | #18 is "One account" and its row says the account is declared agent-operated, and the screen counts it under both. | `#18 pattern: One account` `#18 declared_agent_operated: yes` `acme/shop: One account 2 (1 declared agent-operated)` |

Each example is written as the change (with its project when it is not the shop project), the column of `changes.csv`, a colon and the cell, except the last of S2-C5, which is a line on the screen. The new columns, after `when`, are `builder`, `let_in_by`, `approvals`, `ai_shown`, `ai_trace`, `pattern` and `declared_agent_operated`.

Where these checks depart from the request, as agreed with the owner on 27 Nov 2026:

- Sentence 4 (S2-C3): this story writes only `changes.csv`. The check reads every file in the output folder and the screen, so `record.md` and `record.json` are covered from the day S4 writes them.
- Sentence 5 (S2-C4): the fixed section "What this record cannot show" is in `record.md`, which S4 writes; S4's request line 4 holds it word for word. This story checks the row. Under BRD section 7's rule ("AI shown: yes" or "not shown"), the row says it as the column `ai_shown` with the cell `not shown`.
- Sentence 6 (S2-C5): "the totals" are the new screen line here; `record.md`'s totals are S4's request line 1.
- Sentence 3 (S2-C2) needs a small new example project, `acme/updated`, because the example set has no pull request of that kind.

## Not in this story

- `approvals` lists each counted approval as `login (on the merged version)` or `login (on an earlier version)`, joined by `; ` and never with the word "approved"; empty when there is none.
- For a change with no pull request, `builder` reads `no pull request: not shown` and `let_in_by` reads `pushed by` and the login (`pushed by lee`) (S0-4). A pull request merged by hand has the merger's login in `let_in_by`; one let in by auto-merge has `auto-merge switched on by` and the login.
- Two kinds of AI sign on one row are both shown, in a fixed order, joined by `; `: a coding agent account (`coding agent account: <name>`) or a declared account (`declared agent-operated account`) first, then the commit marker (`declared agent-operated account; commit marker: Claude (Anthropic)`). This is the common case: 112 of Hevelius's 124 merged pull requests.
- The tool name comes from the fixed list's own entry, never from a commit's text. A Claude `Co-Authored-By` line names a model, so the entry is `Claude (Anthropic)`: true for every saved case and, with a space and brackets, never equal to a login (the `claude` stranger, A10).
- The build's own test that no stray login is printed (design section 5) compares the login cells, not a word search, because the word "Claude" is in the AI cell of most rows.
- `declared_agent_operated` is empty on every row where A11 does not apply, #12, #14, #15 and #16 included.
- `builder-bot` stays an account of type `User` in the example data, as in S1's locked data.
- The screen line of S2-C5 for a project with no "One account" change, and the other screen counts: the build's choice, tested in the build's own tests.
- Checks on the merged version: S3. `record.md`, `record.json`, the totals there, the rule and the exceptions: S4. A merge queue gets one "not covered" line (the owner's cut).
- The checks run the tool with a stand-in for `gh`, named in `ASRECORDED_GH` (design section 4); they never call GitHub.
