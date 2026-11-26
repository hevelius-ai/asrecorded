# AsRecorded plan (v2, 26 Nov 2026, matching the requirements version 1.4)

## Done, in three testable lines

1. `asrecorded run settings.toml` writes `record.md`, `changes.csv` and `record.json`, in which every change that reached the default branch in the period appears exactly once with its facts; `asrecorded write` on the same saved data gives the same files, byte for byte.
2. The first real record, for Hevelius's own repositories from 10 Nov 2026, is produced from live data; ten rows chosen by a fixed seed are re-derived by hand from GitHub by a fresh session and match; the record is committed under `records/`.
3. A fresh agent given only `record.md` answers the five set questions correctly in the user walkthrough.

## Budget (decision B1)

| Line | Budget | Report at | Hard stop |
| --- | --- | --- | --- |
| Agent hours | 20 | 16 | 22 |
| Owner hours | 3.5 | 3 | 4 |
| Review cost | $80 | $65 | $100 |
| Working days | 10 | 8 | 12 |

Estimate per step (agent hours): design and setup 2.0; S0 2.5; tooling 1.0; S1 3.5; S2 4.0; S3 2.0; S4 3.5; release 2.0 (after the cut of `docs/relates-to.md`); about 20 in all. At 1.5 times any step's estimate: stop and report.

## Records

- In this repository: `docs/plan.md`, `docs/decisions.md`, `docs/parking.md`, `docs/known-issues.md`, `docs/asbuild-in-practice.md`, `docs/spike-S0.md`.
- Outside it, never committed (they hold local paths): the control file, the log and the project's own skill.

## Step 0: repository (done)

1. Public `hevelius-ai/asrecorded` created; first commit (licence and README stub) on `main`.
2. `/asbuild:setup`: branch `asbuild-setup`, for the owner to open and merge.

## S0: spike (kill gate)

Throwaway code, outside the repository, never merged. Every "to prove" line of the requirements' section 6 is run with `gh api --method GET` against the M4 repositories; public repositories are used only where Hevelius has no case (auto-merge, merge queue, rebase merges, dismissed approvals). The coding agents' account names come from each vendor's own documents, with the URL and the date read. Output: `docs/spike-S0.md` (this pull request) and a decision for the owner on each fact that differs from the requirements. Stop and report.

## Tooling (after the kill gate, its own pull request)

`pyproject.toml` (Python 3.12 or newer; the standard library only at run time; development tools pinned to exact versions with hashes), the CI workflow (lint, format, types, tests with 100% coverage, the history check; Ubuntu and Windows), `scripts/history_check.py` (no email address except GitHub no-reply addresses, GitHub's own address on merges made on its site, and the attribution line, no local paths, no key patterns, across every commit's content and metadata).

## Design (frozen at the end of S0; open points marked "to prove")

- Commands: `asrecorded collect` (reads GitHub, saves the raw replies), `asrecorded write` (the record from the saved folder only), `asrecorded run` (both in turn). Settings in TOML; the rule in its own optional TOML file.
- Every GitHub call goes through one function that runs `gh api --method GET`. A test scans the code and fails on any other network or process call.
- Same bytes every time: rows sorted, JSON with sorted keys, LF line endings, no clock read at write time.
- Logins only from authenticated actions (A10); no titles (A12); no email; the fixed section "What this record cannot show" from one constant, held by a test.

## S1 to S4, the same loop for each

1. `/asbuild:story` on `story/S<n>`: the request is the requirements' story text, unchanged; the owner agrees 2 to 5 checks in chat, built from the example set; `tests/acceptance/S<n>` locked; the story pull request is reviewed independently; the owner merges it.
2. `build/S<n>`: a plan with a premortem in the pull request; unit tests first, seen failing; 100% coverage; CI; `/asbuild:verdict` after each push; review in a fresh Fable 5.2 session (at most three rounds); the owner merges.
3. Each AsBuild verdict, wait and minute lost goes in `docs/asbuild-in-practice.md`. Over 1.5 hours lost to AsBuild in all: report it.

- S1: the list of changes. S2: who opened, who let it in, approvals, AI markers, the pattern. S3: checks on the merged version. S4: the three files, the rule, the checksums, the wording check, the read-only test.

## Release

The first real record under `records/`, with the seed for the ten re-derived rows written in it; the fresh-session re-derivation; one user walkthrough (Fable 5.2 walker); the README with a short sample record and the line saying nothing else is needed; the summary of `docs/asbuild-in-practice.md`; cleanup.

## Report points

At 80% of any budget line; at 1.5 times a step's estimate; at the kill gate; whenever a fact differs from the requirements.
