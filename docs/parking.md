# Parking list

Not designed, not reviewed, not built. One line each, with its reason. An item leaves this list only with the owner's yes.

- Other hosts (GitLab, Bitbucket, Azure DevOps): the first user is on GitHub (A6).
- Deploy and release records; tickets and requirements links: outside the history of the default branch.
- A GitHub Action, a schedule, a dashboard, a web page, a plugin or skill wrapper: one command is enough for the first user.
- Mapping to more than one published catalogue; any wording that a record "meets" a rule: the record shows facts, not compliance.
- Signing, attestations, tamper-proof storage: not needed for the first record.
- Detecting AI use from the code itself; any AI summary of the record: the tool reads history only, and never calls an AI model (A5).
- Branch-protection and ruleset settings: they need admin rights to read.
- Any change to AsBuild (A1, A9).
- Reading AsBuild's saved verdict files, or showing an AsBuild verdict whose origin was checked (M5).
- Statistics on samples; trend charts across periods.
- `docs/relates-to.md` (the record's facts against the FINOS catalogue): writing, not building; the design session writes it after the first record (cut by the owner, 26 Nov 2026).
- A rule option that requires an approval on the merged version (an approval on an earlier version is counted and shown instead; S0-6, owner, 26 Nov 2026).
- Merge queues: if no Hevelius repository uses one, a pull request merged through a queue gets one "not covered" line instead of support (cut by the owner, 26 Nov 2026).
- Speed on very long histories: the first-parent walk checks a list, so 60,000 main-line commits take about 15 seconds (build S1 review round 1, P1, 26 Nov 2026).
