# AsRecorded: the design for S1 to S4

Version 1, 26 Nov 2026. It builds on the requirements (version 1.4), the facts table (`docs/spike-S0.md`) and the decision log (`docs/decisions.md`); where they decide something, this file follows them and names the decision. It designs this release only. Open points are marked "to prove".

## 1. What a user sees and does

Three commands, run from a copy of this repository with Python 3.12 or newer and the `gh` command signed in. Nothing else is installed.

| Command | What it does |
| --- | --- |
| `python -m asrecorded run settings.toml` | Collect, then write: the one command in "done" line 1 |
| `python -m asrecorded collect settings.toml` | Reads GitHub and saves the raw replies in the data folder. Writes no record |
| `python -m asrecorded write settings.toml` | Writes the record from the data folder only. Never calls GitHub |

Each prints a few plain lines: what it read or wrote, and where. A failure prints one plain sentence and exits with a non-zero code; it never leaves a half-written record (files are written to a temporary name and then renamed).

**The settings file (TOML, read with the standard library):**

```toml
repositories = ["hevelius-ai/asbuild", "hevelius-ai/aschecked"]
start = "2026-11-10T00:00:00Z"          # included
end = "2026-11-27T00:00:00Z"            # excluded
agent_accounts = ["heveliusai-dev"]     # declared agent-operated (A11)
disclosures = ["One person directs the agent account and holds the merging account."]
data = "data"                            # where collect saves the raw replies
output = "record"                        # where write puts the three files
rule = "rule.toml"                       # optional; leave out for no exceptions section
```

**The rule file (optional):**

```toml
allowed_patterns = ["Two people", "Agent and person"]
required_checks = ["ci"]
```

Relative paths are read from the settings file's folder. Times are UTC with a `Z`; anything else is refused with a plain message.

## 2. Collect (S1, S3): what is read and saved

All reads go through one function, `github.get(path)`, which runs `gh api --method GET --paginate --slurp <path>` and nothing else. A test reads the package's code and fails on any other process call or network use (S4 criterion 5).

For each repository, into `<data>/<owner>__<name>/`:

| File | Call | Why |
| --- | --- | --- |
| `repo.json` | `repos/{r}` | The default branch; readable at all (S1-3) |
| `pulls.json` | `repos/{r}/pulls?state=closed&base={default}&per_page=100` | Every merged pull request (row 1 of the facts table) |
| `activity.json` | `repos/{r}/activity?ref={default}&per_page=100` | Pushes, merges and force pushes with the account that made them (S0-1, S0-2) |
| `main_commits.json` | `repos/{r}/commits?sha={default}&per_page=100` | The cross-check walk of the first-parent line (S0-1) |
| `pr/{n}/pull.json`, `commits.json`, `reviews.json`, `timeline.json` | the pull request, its commits, reviews and timeline | Opener, merger, auto-merge and queue events, approvals, AI markers |
| `pr/{n}/check_runs.json`, `status.json` | `commits/{head}/check-runs`, `commits/{head}/status` | Checks on the merged version (S3, S0-5) |
| `push/{after}.json` | `compare/{before}...{after}` (or `commits?sha={after}` for a branch's creation) | The commits a push brought in (S0-4) |

Only pull requests merged in the period, and pushes in the period, get their detail files. The first repository that cannot be read stops collection with "Cannot read <owner/name> with your GitHub sign-in. No record was written." (S1-3). A repository whose activity history does not reach back to the period's start, while the repository is older than it, is still collected; the record then says so under "What was not covered" (S0-1).

Raw replies are saved as GitHub returned them, with one change: JSON is written with sorted keys and two-space indent, so that the same replies give the same files.

## 3. Write (S1 to S4): from saved data to the record

Plain functions, each reading only what the one before it gives, so each story can be tested on saved data alone:

1. **The list of changes (S1).** Each merged pull request whose `merged_at` is in the period and whose base is the default branch. Then each commit brought in by a `push` or `branch_creation` entry stamped in the period that is no pull request's merge commit and no commit that GitHub's "pull requests for this commit" maps to a merged pull request (rebase merges). Force pushes in the period go to "History rewritten", with the time, the account and the number of commits brought in; those commits are not changes (S0-2). Every commit on the first-parent line in the period that none of this explains gets a "not covered" line. Ids: `#11` for a pull request, the first 7 characters of the hash for a commit. A change appears once by construction (a set keyed by repository and id), and a test checks it.
2. **Who and what (S2).** For a pull request: who opened it and the account type (the builder, `user`); who merged it and the type (`merged_by`); auto-merge switched on, and by whom, from the timeline's `auto_*_enabled` events not followed by `auto_merge_disabled`; a merge queue from `added_to_merge_queue` (one "not covered" line, by the cut); approvals from reviews in state `APPROVED` (never `DISMISSED`), each marked "on the merged version" when its commit is the head (S0-6). For a direct push: builder "no pull request: not shown", "pushed by" the activity history's account (S0-4). Logins come only from these authenticated actions (S0-3, A10).
3. **AI shown (S2, S0-7).** Yes when the opener is on the fixed list of coding agents (recognised by account id, from the vendors' own pages: `docs/spike-S0.md` row 5) or is declared in the settings; or a commit carries a `Co-Authored-By` line or an author name that names a listed tool. The row says which of the three it was, by kind and tool name, never by a commit's login. Otherwise "AI not shown".
4. **The pattern (S2).** The first that fits, in order: No pull request; Two people / Agent and person (a person, meaning an account of type `User` that is not declared, who did not open it, gave an approval or merged it by hand; "Agent and person" when AI is shown or a bot opened it); AI reviewer only (the only approvals came from bots or declared accounts); Automatic, no approval (no approval, and auto-merge was on or a bot merged: R1); One account (with the declared mark when the account is declared: A11). Wording as in decision S0-7.
5. **Checks (S3, S0-5).** From the head commit's check runs and commit statuses that started before the merge: the last run of each name; "not finished at the merge" when it ended after; "no checks ran on the merged version" when there are none. Names and results are shown as GitHub gives them; a check named `AsBuild` is one more name.
6. **The rule (S4).** When a rule file is given: a change is an exception when its pattern is not allowed, or a required check did not end in `success` on the merged version. Each exception's reason is one plain sentence.
7. **The three files (S4).** `changes.csv` (one row per change; columns only ever added at the end, so earlier stories' checks keep working), `record.json` (the same, plus totals and the rewrite and not-covered lists, sorted keys), and `record.md` (plain words, as listed in section 7 of the requirements, with the fixed section "What this record cannot show" from one constant and the SHA-256 of the other two files). Rows are sorted by repository (in settings order), then time, then id. No clock is read when writing: the only times are those in the saved data.

## 4. Where each story's checks look

A story's checks run the commands the way a user does (`python -m asrecorded ...`) on saved data that the test writes into a temporary folder, using the invented repositories `acme/shop` and others. They never call GitHub. Collection is tested with a stand-in `gh`: the tool takes the program name from the `ASRECORDED_GH` setting in its environment when it is set (default `gh`), and the test points it at a small script that answers from files or refuses a repository. This is the one seam added for tests.

- **S1:** the screen summary of `write` and `changes.csv`'s `repository`, `change`, `how` and `when` columns; the stop message of `collect`.
- **S2:** `changes.csv`'s builder, let-in, approval, AI and pattern columns.
- **S3:** `changes.csv`'s checks column.
- **S4:** the three files whole.

## 5. Premortem for the release

| How it could fail | What answers it |
| --- | --- |
| A check silently does not run: `write` finds no data and writes an empty record | `write` refuses a data folder that is missing a listed repository's `repo.json`, `pulls.json` or `activity.json`, and the record states how many repositories and changes it read; a test |
| A change is counted twice or missed (the aschecked rewrite) | The list comes from the activity history (S0-1); the cross-check reports what it cannot explain; S1's checks; the release's ten-row re-check |
| A stranger's login is printed (the `claude` case) | Logins only from authenticated actions (S0-3); S2-3's check; a test over the three files that no login appears that is not an opener, merger, reviewer, auto-merge enabler or pusher in the saved data |
| The record claims more than the history shows | The fixed limits section; the wording check (S4-4); patterns are facts, never grades |
| The same data gives different bytes | No clock at write time; sorted rows and keys; LF line ends; S4-3's check runs `write` twice and compares |

## 6. To prove during the build

- How far back the activity history goes (seen to 8 Oct 2026; GitHub's pages do not say).
- That `--paginate --slurp` gives one list for every endpoint used (seen in S0 for pulls, commits and activity; to check for reviews, timeline and check runs on a pull request with more than 100 of them, using a public repository).
