# AsRecorded: the design for S1 to S4

Version 1, 26 Nov 2026. It builds on the requirements (version 1.4), the facts table (`docs/spike-S0.md`) and the decision log (`docs/decisions.md`); where they decide something, this file follows them and names the decision. It designs this release only. Open points are marked "to prove".

## 1. What a user sees and does

Three commands, run from a copy of this repository with Python 3.12 or newer and the `gh` command signed in. Nothing else is installed.

| Command | What it does |
| --- | --- |
| `python -m asrecorded run settings.toml` | Collect, then write: the one command in "done" line 1 |
| `python -m asrecorded collect settings.toml` | Reads GitHub and saves the raw replies in the data folder. Writes no record |
| `python -m asrecorded write settings.toml` | Writes the record from the data folder only. Never calls GitHub |

Each prints a few plain lines: what it read or wrote, and where. A failure prints one plain sentence and exits with a non-zero code; it never leaves a half-written record: files are written to temporary names and renamed only when all three are complete, `record.md` last. A failed `write` (or the write step of `run`) first removes any `record.md` it would replace; a failed collect, alone or inside `run`, leaves the output folder untouched, since it writes nothing there.

**The settings file (TOML, read with the standard library):**

```toml
repositories = ["hevelius-ai/asbuild", "hevelius-ai/aschecked"]
start = "2026-11-10T00:00:00Z"          # included
end = "2026-11-27T00:00:00Z"            # excluded
agent_accounts = ["heveliusai-dev"]     # declared agent-operated (A11)
disclosures = ["One person directs the agent account and holds the merging account."]
data = "data"                            # optional (default "data"): where collect saves the raw replies
output = "record"                        # optional (default "record"): where write puts the three files
rule = "rule.toml"                       # optional; leave out for no exceptions section
```

`disclosures` are printed as written (requirements, section 7). Because they enter `record.md`, `write` refuses a disclosure that holds a banned word or an email address, with a plain message naming which one.

**The rule file (optional):**

```toml
allowed_patterns = ["Two people", "Agent and person"]
required_checks = ["ci"]
```

Relative paths are read from the settings file's folder. Times are UTC with a `Z`; anything else is refused with a plain message.

## 2. Collect (S1, S3): what is read and saved

All reads go through one function, `github.get(path)`, which runs `gh api --method GET --paginate --slurp <path>` and nothing else, and joins the pages it returns into one list (for check runs, the pages' `check_runs` lists; for a compare, its `commits`). A test reads the package's code and fails on any other process call or network use (S4 criterion 5).

For each repository, into `<data>/<owner>__<name>/`:

| File | Call | Why |
| --- | --- | --- |
| `repo.json` | `repos/{r}` | The default branch; readable at all (S1-3) |
| `pulls.json` | `repos/{r}/pulls?state=closed&base={default}&per_page=100` | Every merged pull request (row 1 of the facts table) |
| `activity.json` | `repos/{r}/activity?ref={default}&per_page=100` | Pushes, merges and force pushes with the account that made them (S0-1, S0-2) |
| `main_commits.json` | `repos/{r}/commits?sha={default}&per_page=100` | The cross-check walk of the first-parent line (S0-1) |
| `pr/{n}/pull.json`, `commits.json`, `reviews.json`, `timeline.json` | the pull request, its commits, reviews and timeline | Opener, merger, auto-merge and queue events, approvals, AI markers |
| `pr/{n}/check_runs.json`, `statuses.json` | `commits/{head}/check-runs?filter=all`, `commits/{head}/statuses` | Every run and every status entry on the merged version, with their times (S3, S0-5). The default `filter=latest` hides earlier runs of a name, and the combined `status` keeps one entry per name with no times: both proved on 26 Nov 2026 (home-assistant/core `f501d7d`: 34 against 61; kubernetes/kubernetes #144449: 15 against 84) |
| `push/{after}.json` | `compare/{before}...{after}`; for a branch's creation, and for a force push that GitHub answers with "No common ancestor" (aschecked, 26 Nov), `commits?sha={after}` instead | The commits a push or a force push brought in (S0-2, S0-4) |

Only pull requests merged in the period, and pushes in the period, get their detail files. "No common ancestor" is told apart from an unreadable repository by GitHub's message; an unreadable repository is caught earlier, at `repo.json`.

The data folder holds raw replies, which carry email addresses and titles (A12). On every run, collect writes a `.gitignore` holding `*` into the data folder, so that git ignores it wherever it lies. The first repository that cannot be read stops collection with "Cannot read <owner/name> with your GitHub sign-in. No record was written." (S1-3). A repository whose activity history does not reach back to the period's start, while the repository is older than it, is still collected; the record then says so under "What was not covered" (S0-1).

Raw replies are saved as GitHub returned them, with one change: JSON is written with sorted keys and two-space indent, so that the same replies give the same files.

## 3. Write (S1 to S4): from saved data to the record

Plain functions, each reading only what the one before it gives, so each story can be tested on saved data alone:

1. **The list of changes (S1).** Each merged pull request whose `merged_at` is in the period and whose base is the default branch. Then each commit brought in by a `push` or `branch_creation` entry stamped in the period, except the commits that are part of a merged pull request: those a `pr_merge` entry brought in (its range from `before` to `after` on the saved first-parent line, which also covers rebase merges), every merged pull request's `merge_commit_sha`, and every commit in a merged pull request's saved `commits.json`. The last two cover merge bots that land a pull request as a plain `push` (rust-lang/rust: its last 100 activity entries are all `push` by `rust-bors[bot]`; #165789's merge commit `e068f42` is one push's `after`, proved on 26 Nov 2026). Force pushes in the period go to "History rewritten", with the time, the account and the number of commits brought in; those commits are not changes (S0-2). Cross-check: the first-parent line is walked from the branch's last commit through each commit's first parent in `main_commits.json`; a commit on it that no activity entry brought in, and whose committer date falls in the period, gets a "not covered" line (the committer date is free text, used only for this line). Ids: `#11` for a pull request, the first 7 characters of the hash for a commit. A change appears once by construction (a set keyed by repository and id), and a test checks it.
2. **Who and what (S2).** For a pull request: who opened it and the account type (the builder, `user`); who merged it and the type (`merged_by`); whether auto-merge was on at the merge and who switched it on, from the last `auto_*_enabled` or `auto_merge_disabled` event before the `merged` event; a merge queue from `added_to_merge_queue` (one "not covered" line, by the cut). Approvals: reviews in state `APPROVED` (never `DISMISSED`) submitted before `merged_at`, each marked "on the merged version" when its commit is the head, else "on an earlier version" (S0-6); an approval given after the merge is not counted. For a direct push: builder "no pull request: not shown", "pushed by" the activity history's account (S0-4). Logins come only from these authenticated actions (S0-3, A10).
3. **AI shown (S2, S0-7).** Yes when the opener (or, for a direct push, the pusher) is on the fixed list of coding agents (recognised by account id, from the vendors' own pages: `docs/spike-S0.md` row 5) or is declared in the settings; or a commit carries a `Co-Authored-By` line or an author name that names a listed tool. The row says which it was, by kind and tool name, never by a commit's login. Otherwise "AI not shown".
4. **The pattern (S2).** Words used: a **person** is an account of type `User` not declared in the settings; an **agent** is a declared account or an account of type `Bot`; a merge is **by hand** when auto-merge was not on at the merge and no merge queue was used; an approval **counts** as in step 2. A direct push is "No pull request". For a pull request, the first row that fits (A11, R1, S0-7):

   | # | When | Pattern |
   | --- | --- | --- |
   | a | A person other than the opener gave a counted approval, or merged it by hand | "Agent and person" when AI is shown or an agent opened it, else "Two people" |
   | b | It has counted approvals, and every one is from an agent | AI reviewer only |
   | c | It has no counted approval, and auto-merge was on, or a merge queue was used, or an agent merged a change that agent did not open, or an account of type `Bot` merged it | Automatic, no approval |
   | d | Otherwise: the account that opened it merged it | One account (with "declared agent-operated" when that account is declared: A11) |

   Row d is reached only when the opener merged it: when someone else merged it, that someone is a person (row a) or an agent (row c). A declared account of type `Bot` that merges its own change is caught by row c's last clause; the example set's `builder-bot` is of type `User`, as `heveliusai-dev` is. The nine example rows give: #11 a (Two people), #12 a, #16 a (Agent and person), #14 b, #15 c (dana switched auto-merge on, so the merge is not by hand), #13 d, #18 d (declared), a1b2c3d No pull request; #17 is not listed.
5. **Checks (S3, S0-5).** For a pull request, on its head commit. Check runs: for each name, the last run that started before `merged_at`; its result when it completed before `merged_at`, else "not finished at the merge"; a run that started after the merge is ignored. Commit statuses (the full list): for each context, the last entry created before `merged_at`; its state, with `pending` shown as "not finished at the merge". "No checks ran on the merged version" when nothing remains. Names and results are shown as GitHub gives them; a check named `AsBuild` is one more name. For a direct push, checks are not read: the row says "checks not read for a direct push", and "What was not covered" says so.
6. **The rule (S4).** When a rule file is given: a pull request is an exception when its pattern is not allowed, or a required check did not end in `success` on the merged version; a direct push is an exception when "No pull request" is not allowed (required checks do not apply to it). When both apply, both reasons are given, the pattern first. Each reason is one plain sentence.
7. **The three files (S4).** `changes.csv` (one row per change; columns only ever added at the end, so earlier stories' checks keep working), `record.json` (the same, plus totals and the rewrite and not-covered lists, sorted keys), and `record.md` (plain words, as listed in section 7 of the requirements, with the fixed section "What this record cannot show" from one constant and the SHA-256 of the other two files). Rows are sorted by repository (in settings order), then time, then id. No clock is read when writing: the only times are those in the saved data.

## 4. Where each story's checks look

A story's checks run the commands the way a user does (`python -m asrecorded ...`) on saved data that the test writes into a temporary folder, using the invented repositories `acme/shop` and others. They never call GitHub. Collection is tested with a stand-in `gh`: when the environment holds `ASRECORDED_GH`, the tool reads it as a JSON list (a program and its leading arguments, for example the test's own Python and a stand-in script) and runs that in place of `gh`; the arguments go to the program as a list, never through a shell, so Windows' `&` and quoting play no part. The stand-in answers from files or refuses a repository. This is the one seam added for tests.

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
- That `--paginate --slurp` gives every page for each endpoint used (seen in S0 for pulls, commits and activity; to check for reviews, timeline, check runs and statuses on a pull request with more than 100 of them, using a public repository).
