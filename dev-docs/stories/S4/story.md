# S4: The record, the rule and the limits

## Request (the owner's words, unchanged)

As the owner, I want one command that writes the three files, so that I can publish the record or hand it to a reader.

1. Given the example set and its rule, when the record is written, then `record.md` shows the expected totals and lists the six exceptions, each with its reason in plain words.
2. Given the same saved data and no rule file, when the record is written, then there is no exceptions section and the patterns are still counted.
3. Given the same saved data, when the command runs twice, then the three files are identical byte for byte, and `record.md` holds the checksums of the other two.
4. Given any output, when the wording check runs, then none of the banned words in section 7 appears, no email address appears, and the fixed section "What this record cannot show" is present word for word.
5. Given the command's own code, when the test suite runs, then a test fails if any call to GitHub is not a read.

## Criteria

| ID | Criterion | Cites |
| --- | --- | --- |
| S4-C1 | Given saved GitHub replies for `acme/shop` (the example set, with S2's and S3's facts), the period 2026-11-01T00:00:00Z to 2026-12-01T00:00:00Z, `builder-bot` declared, and a rule file allowing "Two people" and "Agent and person" and requiring the check `ci`, `python -m asrecorded run settings.toml` writes `record.md` holding the lines `- Changes: 8 (7 through a pull request, 1 pushed directly)`, `- AI shown: 6` and `- Exceptions under the rule: 6`; under `## Exceptions under the rule` (any `### ` sub-heading aside), exactly these six reasons, in this order (pull requests by number, then commits pushed directly by time): `- #13: the pattern "One account" is not allowed by the rule.`, `- #14: the pattern "AI reviewer only" is not allowed by the rule.`, `- #15: the pattern "Automatic, no approval" is not allowed by the rule.`, `- #16: the required check "ci" did not end in success on the merged version (it shows: failure).`, `- #18: the pattern "One account" is not allowed by the rule.` and `- a1b2c3d: the pattern "No pull request" is not allowed by the rule.`; and under `## Every change`, one table row per change, #11's reading `\| acme/shop \| [#11](https://github.com/acme/shop/pull/11) \| 2026-11-02 10:00 \| pull request \| dana \| dana \| lee (on the merged version) \| not shown \| Two people \| ci: success \|` | Request, sentences 1 and 2 |
| S4-C2 | With the same saved replies and no rule file, `record.md` has no `## Exceptions under the rule` section and no line holding the word "Exceptions", and holds the lines `- One account: 2, of which 1 declared agent-operated` and `- Automatic, no approval: 1` | Request, sentence 3 |
| S4-C3 | Running `python -m asrecorded write settings.toml` again on the same saved data leaves `record.md`, `changes.csv` and `record.json` byte for byte as the first run wrote them, and `record.md` holds the lines `- changes.csv SHA-256: ` and `- record.json SHA-256: `, each followed by that file's SHA-256 checksum in lower-case hexadecimal | Request, sentence 4 |
| S4-C4 | In a record whose saved data holds a check named with the word "passed", a check named `checks_passed` and a commit status whose name holds an email address, no file of the record holds the words approved, compliant, certified, secure, safe, audited or passed (as whole words, in any letter case, where any character that is not a letter or a digit, the underscore included, ends a word, so `checks_passed` holds "passed"), the words "no AI", or an email address. The record's files are the files in the output folder (`output` in the settings); the raw replies in the data folder are not part of the record. `record.md` holds `## What this record cannot show`, and its lines from there up to the next `## ` heading or the end, blank lines aside, are BRD section 7's seven items, one per line, word for word and in order, and nothing else (an eighth item fails), among them `- anything outside the listed repositories or outside GitHub` | Request, sentence 5 |
| S4-C5 | `python scripts/read_only_check.py asrecorded` exits 0 and its output holds `gh api --method GET`; run on a copy of the package with one added call that is not a read (a `gh api` call with `--method POST`, a `gh api` call with `-X PATCH`, or an import of `urllib.request`), it exits with a non-zero code and names the added file; and run on a copy whose own `github.py` makes one call that is not a read (its `"--method", "GET"` made `"--method", "POST"`), it exits with a non-zero code and names `github.py` | Request, sentence 6 |

## Plain checklist (approved by the owner; the receipt quotes it word for word)

| ID | plain: | Examples (approved) |
| --- | --- | --- |
| S4-C1 | With the saved example data for the shop project and its rule, the record shows the totals, lists the six exceptions each with its reason, and lists every change. | `- Changes: 8 (7 through a pull request, 1 pushed directly)` `- #16: the required check "ci" did not end in success on the merged version (it shows: failure).` `\| acme/shop \| [#11](https://github.com/acme/shop/pull/11) \| 2026-11-02 10:00 \| pull request \| dana \| dana \| lee (on the merged version) \| not shown \| Two people \| ci: success \|` |
| S4-C2 | With the same data and no rule, the record has no exceptions section and still counts the patterns. | `- One account: 2, of which 1 declared agent-operated` `- Automatic, no approval: 1` |
| S4-C3 | Running the command twice on the same saved data gives the same three files, byte for byte, and the record holds the checksums of the other two. | `- changes.csv SHA-256: ` |
| S4-C4 | No file of the record holds a banned word or an email address, and the section "What this record cannot show" is there word for word. | `## What this record cannot show` `- anything outside the listed repositories or outside GitHub` |
| S4-C5 | A check of the tool's own code fails if any call to GitHub is not a read. | `gh api --method GET` |

S4-C3's example is followed, in the record, by the file's checksum, which cannot be known before the file is written; the check computes it from the file.

Where these checks depart from the request, as agreed with the owner on 27 Nov 2026:

- Sentences 1 and 2 (S4-C1): `record.md` also lists every change in a table (`## Every change`), which BRD section 7 does not list. "Done" line 3 needs it: a reader with only `record.md` must answer which changes were let in automatically and who approved a named change (owner's choice S4-Q1 A).
- Sentence 5 (S4-C4): "any output" is made concrete with saved data that would break the rules if printed as given: a check named `all required jobs passed` (as astral-sh/uv has) and a commit status whose name holds an email address. Such words are replaced in every file (owner's choice S4-W1 C; see below).
- Sentence 6 (S4-C5): "a test fails if any call to GitHub is not a read" is a script the suite runs, `scripts/read_only_check.py`, which reads the package's code; the check proves it on the package and on copies with one added call that is not a read.

## Not in this story

- A banned word inside a check's name is replaced by `[a word this record does not use]`, the rest of the name kept (`all required jobs [a word this record does not use]: success`); an email address in any printed name by `[address not shown]` (owner's choice S4-W1 C). The rule file still matches a required check by its real name.
- `record.json`: the same rows as `changes.csv` plus the totals, the pattern counts, the checks summary, the exceptions, "not covered", "history rewritten", the disclosures and the rule, with sorted keys and no time read from the clock.
- The headings, words and order of `record.md` as in the sample the owner saw (`drafts/S4-checklist.md`, owner's kit); "History rewritten" and "Disclosures" appear only when there is something to list. "What was not covered" names that checks were not read for the commits pushed directly (design section 3 step 5), and says `Nothing.` only when there is nothing to list (the approved sample's `Nothing.` for the example set is superseded by the design). With one or more repositories, each repository's exceptions sit under a `### <repository>` sub-heading inside `## Exceptions under the rule`.
- A disclosure holding a banned word or an email address is refused with a plain message naming which (design section 1).
- Exception reasons: the pattern first, then each required check, one sentence each (design section 3 step 6); a direct push is an exception only when "No pull request" is not allowed.
- A rule file that names an unknown pattern or is not valid TOML is refused with a plain message.
- What the read-only check looks for, beyond the three planted cases: any other process call or network use in the package (design section 2).
- The checks run the tool with a stand-in for `gh`, named in `ASRECORDED_GH` (design section 4); they never call GitHub.
