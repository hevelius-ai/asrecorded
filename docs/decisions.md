# Decision log

Every decision: the choice, what it covers, why, the date and what would reopen it. Decided items are frozen. Only evidence reopens one: a failing test, a measurement, a real user's problem, a fact shown false. A different opinion goes on the parking list (`docs/parking.md`).

Source of A1 to A12, M1 to M5 and Q1 to Q3: the owner's requirements, version 1.4, 26 Nov 2026. Each is reopened only by evidence.

## Made before the build

| # | Decision | Why |
| --- | --- | --- |
| A1 | AsRecorded is its own repository and its own tool. No file in `hevelius-ai/asbuild` changes, not even one setting | AsBuild v0.4.2 is a finished product. Its README line "AsBuild does not check who built a change and who merged it" is held by its own locked test. The new tool is independent and must work however a product was built and merged |
| A2 | Any GitHub repository, nothing installed in it | A check is a check; the tool must not be tied to one way of building |
| A3 | Facts first; exceptions only against the owner's own written rule | A fully automated team is shown as what it is, not as failing |
| A4 | Read-only. Only GET requests to GitHub. No writes to any repository it reads | Safety, and it is what makes "nothing installed" true |
| A5 | An AI model is never called at run time. Same input, same record | The record must be reproducible |
| A6 | GitHub only, pull requests into the default branch, plus direct pushes to it | Build for the first user (Hevelius). Other hosts are parked |
| A7 | Free and open source, MIT, copyright Hevelius AI Group LLC | Same as AsBuild |
| A8 | AsRecorded holds no code that is specific to AsBuild. It runs on any repository with nothing else installed, and its README says so on the first screen | The tool must not be tied to AsBuild; the two answer different questions |
| A9 | AsRecorded's own repository is built with AsBuild v0.4.2 wired in. This is how it is built, not what it needs. AsBuild itself is not changed: a problem found in it is written down (`docs/asbuild-in-practice.md`), not fixed here | A test of AsBuild in practice on a second real project, started from an empty repository |
| A10 | Logins in the record come only from actions GitHub authenticates: opening a pull request, approving it, merging it. The author fields of a commit are text that anyone can set. They are used only as AI markers, and a login that comes from them alone is never printed. S0 proves how GitHub makes the link and proposes the exact rule; the owner decides | 43 commits in heveliusai.com carry the author name "Claude", and GitHub links them to the login `claude`, which belongs to an unrelated person. A public record must never name a stranger as a builder |
| A11 | When an account declared as agent-operated merges its own change, with no approval and no auto-merge, the pattern is "One account". The row and the totals also say that the account is declared agent-operated | The history shows one account built and merged. It cannot show whether the agent or a person signed in as that account pressed merge |
| A12 | No pull request titles in any output: the number and a link only | Meets M4's rule for the private repository with no special code; titles can hold private words |
| M1 | Name: AsRecorded | It keeps a record and checks nothing |
| M2 | Repository `hevelius-ai/asrecorded`, public from the first commit. The builder may create it and push its first commit (licence and README stub); everything after goes through pull requests | Owner's decision |
| M3 | Built with AsBuild v0.4.2 wired into the new repository. Each story is two pull requests: the checks, then the build | A test of AsBuild in practice |
| M4 | First record's repositories: asbuild, asbuild-demo, asbuild-demo-ts, aschecked, heveliusai.com, asrecorded, and the private auto-job-search with its titles withheld | Hevelius's own repositories |
| M5 | The AsBuild-verdict story is dropped; it is on the parking list | The tool must not be tied to AsBuild |
| Q1 | A declared agent account that merges its own change, with no approval and no auto-merge: "One account", with the declared agent-operated mark (A11) | Owner, 26 Nov 2026 |
| Q2 | Fable 5.2 reviews the Opus 5.5 builds (high effort for pull requests, extra high for designs); the walker also runs on Fable 5.2 | Owner, 26 Nov 2026 |
| Q3 | The owner's time zone is US Eastern; records stay in UTC | Owner, 26 Nov 2026 |
| B1 | Budget: 20 agent hours (report at 16, hard stop 22); owner 3.5 hours; review cost $80; 10 working days; 4 calendar weeks from the first build commit | Re-agreed by the owner on 26 Nov 2026 after the three cuts (`docs/parking.md`) |

## Made during the build

| # | Date | Decision | Covers | Why | Reopen if |
| --- | --- | --- | --- | --- | --- |
