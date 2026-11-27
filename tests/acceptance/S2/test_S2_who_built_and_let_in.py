"""S2, who built it, who let it in, and the pattern: the owner's approved checks (dev-docs/stories/S2/story.md).

Each check runs the tool the way a user does, `python -m asrecorded run settings.toml`, in a temporary folder. GitHub
is never called: `ASRECORDED_GH` names a stand-in for `gh` that answers read requests from saved replies, in the
form `gh api --paginate --slurp` gives them (a list of pages), and answers any other path as GitHub answers a
repository the sign-in cannot read.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
START, END = "2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z"
CREATED = "2026-10-20T10:00:00Z"
ZERO = "0" * 40
A1B2C3D = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
ACCOUNTS = {
    "dana": (1001, "User"),
    "lee": (1002, "User"),
    "builder-bot": (1003, "User"),
    "review-bot[bot]": (1004, "Bot"),
    "stranger": (1005, "User"),
    "web-flow": (19864447, "User"),
}
CLAUDE_LINE = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"

STAND_IN = """
import json
import sys
from pathlib import Path

here = Path(__file__).parent
args = sys.argv[1:]
with (here / "calls.txt").open("a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
writes = {"POST", "PUT", "PATCH", "DELETE", "-f", "-F", "--field", "--raw-field", "--input"}
if not args or args[0] != "api" or writes.intersection(args):
    print("stand-in gh: only read requests are answered", file=sys.stderr)
    sys.exit(1)
replies = json.loads((here / "replies.json").read_text(encoding="utf-8"))
path = args[-1].split("?", 1)[0].strip("/")
if path not in replies:
    print(json.dumps([{"message": "Not Found", "documentation_url": "https://docs.github.com/rest", "status": "404"}]))
    print("gh: Not Found (HTTP 404)", file=sys.stderr)
    sys.exit(1)
print(json.dumps([replies[path]]))
"""


def sha(n: int) -> str:
    return f"{n:07x}" + "e" * 33


def account(login: str) -> dict[str, Any]:
    oid, kind = ACCOUNTS[login]
    return {"login": login, "id": oid, "type": kind}


def commit(oid: str, parents: list[str], when: str) -> dict[str, Any]:
    return {
        "sha": oid,
        "parents": [{"sha": p} for p in parents],
        "commit": {
            "message": "work",
            "author": {"name": "dana", "date": when},
            "committer": {"name": "dana", "date": when},
        },
        "author": None,
        "committer": None,
    }


def event(oid: int, kind: str, before: str, after: str, when: str, actor: str) -> dict[str, Any]:
    return {
        "id": oid,
        "before": before,
        "after": after,
        "ref": "refs/heads/main",
        "timestamp": when,
        "activity_type": kind,
        "actor": account(actor),
    }


def history(repo: str, seed: int, steps: list[tuple[str, str, str, str, str]]) -> dict[str, Any]:
    """The saved replies for one repository built from steps, oldest first:
    ("pr", number, opener, merger, merged at) or ("push", commit, pusher, "", time).
    Each pull request is merged with a merge commit and has no approval; its timeline holds the `merged` event."""
    root = sha(seed)
    line = [commit(root, [], CREATED)]
    events = [event(seed, "branch_creation", ZERO, root, CREATED, "dana")]
    pulls: list[dict[str, Any]] = []
    replies: dict[str, Any] = {}
    tip = root
    for i, (kind, name, actor, merger, when) in enumerate(steps, start=1):
        first, head, merge = sha(seed + 100 * i + 1), sha(seed + 100 * i + 2), sha(seed + 100 * i + 3)
        if kind == "pr":
            work = [commit(first, [tip], when), commit(head, [first], when)]
            line += [*work, commit(merge, [tip, head], when)]
            pull = {
                "number": int(name),
                "state": "closed",
                "merged_at": when,
                "closed_at": when,
                "merge_commit_sha": merge,
                "base": {"ref": "main"},
                "head": {"ref": f"work-{name}", "sha": head},
                "user": account(actor),
                "html_url": f"https://github.com/{repo}/pull/{name}",
            }
            pulls.append(pull)  # GitHub's list of pull requests does not say who merged them; the detail does
            replies[f"repos/{repo}/pulls/{name}"] = pull | {
                "merged": True,
                "merged_by": account(merger),
                "commits": len(work),
            }
            replies[f"repos/{repo}/pulls/{name}/commits"] = work
            replies[f"repos/{repo}/pulls/{name}/reviews"] = []
            replies[f"repos/{repo}/issues/{name}/timeline"] = [
                {"event": "merged", "actor": account(merger), "commit_id": merge, "created_at": when}
            ]
            replies[f"repos/{repo}/commits/{head}/check-runs"] = {"total_count": 0, "check_runs": []}
            replies[f"repos/{repo}/commits/{head}/statuses"] = []
            events.append(event(seed + 100 * i, "pr_merge", tip, merge, when, merger))
            tip = merge
        else:
            pushed = commit(name, [tip], when)
            line.append(pushed)
            replies[f"repos/{repo}/compare/{tip}...{name}"] = {
                "status": "ahead",
                "total_commits": 1,
                "commits": [pushed],
            }
            events.append(event(seed + 100 * i, "push", tip, name, when, actor))
            tip = name
    replies[f"repos/{repo}"] = {"full_name": repo, "default_branch": "main", "private": False, "created_at": CREATED}
    replies[f"repos/{repo}/pulls"] = pulls[::-1]
    replies[f"repos/{repo}/activity"] = events[::-1]
    replies[f"repos/{repo}/commits"] = line[::-1]
    return replies


def approve(replies: dict[str, Any], repo: str, number: str, reviewer: str, when: str) -> None:
    """An approval on the pull request's last commit (the merged version), given before the merge."""
    head = replies[f"repos/{repo}/pulls/{number}"]["head"]["sha"]
    replies[f"repos/{repo}/pulls/{number}/reviews"].append(
        {
            "id": 5000 + int(number),
            "user": account(reviewer),
            "state": "APPROVED",
            "commit_id": head,
            "submitted_at": when,
        }
    )


def shop() -> dict[str, Any]:
    """acme/shop, the example set of the requirements (section 8), with the facts S2 reads."""
    replies = history(
        "acme/shop",
        0x1000,
        [
            ("pr", "11", "dana", "dana", "2026-11-02T10:00:00Z"),
            ("pr", "12", "builder-bot", "lee", "2026-11-03T10:00:00Z"),
            ("pr", "13", "dana", "dana", "2026-11-04T10:00:00Z"),
            ("push", A1B2C3D, "lee", "", "2026-11-09T10:00:00Z"),
            ("pr", "14", "builder-bot", "builder-bot", "2026-11-10T10:00:00Z"),
            ("pr", "15", "builder-bot", "dana", "2026-11-12T10:00:00Z"),
            ("pr", "16", "builder-bot", "lee", "2026-11-14T10:00:00Z"),
            ("pr", "18", "builder-bot", "builder-bot", "2026-11-20T10:00:00Z"),
            ("pr", "17", "dana", "dana", END),
        ],
    )
    approve(replies, "acme/shop", "11", "lee", "2026-11-02T09:00:00Z")
    approve(replies, "acme/shop", "14", "review-bot[bot]", "2026-11-10T09:00:00Z")
    approve(replies, "acme/shop", "16", "lee", "2026-11-14T09:00:00Z")
    # 13: one of its commits names an AI tool in a Co-Authored-By line
    marked = replies["repos/acme/shop/pulls/13/commits"][1]["commit"]
    marked["message"] = f"work\n\n{CLAUDE_LINE}\n"
    # 15: dana switched auto-merge on before the merge
    replies["repos/acme/shop/issues/15/timeline"].insert(
        0, {"event": "auto_merge_enabled", "actor": account("dana"), "created_at": "2026-11-12T09:00:00Z"}
    )
    # 18: GitHub links the author field of one of its commits to `stranger`, who took no action on it
    linked = replies["repos/acme/shop/pulls/18/commits"][0]
    linked["commit"]["author"]["name"] = "stranger"
    linked["author"] = account("stranger")
    return replies


def updated() -> dict[str, Any]:
    """acme/updated: lee brings #3 up to date with the main line ("update branch"), then merges it by hand."""
    replies = history(
        "acme/updated",
        0x5000,
        [
            ("pr", "2", "lee", "dana", "2026-11-06T10:00:00Z"),
            ("pr", "3", "dana", "lee", "2026-11-08T10:00:00Z"),
        ],
    )
    main_before = replies["repos/acme/updated/pulls/2"]["merge_commit_sha"]
    first, head = replies["repos/acme/updated/pulls/3/commits"]
    update = commit(sha(0x5000 + 250), [first["sha"], main_before], "2026-11-07T10:00:00Z")
    update["commit"]["message"] = "Merge branch 'main' into work-3"
    update["commit"]["author"]["name"] = "lee"
    update["commit"]["committer"]["name"] = "GitHub"
    update["author"] = account("lee")
    update["committer"] = account("web-flow")
    for listed in (head, *(c for c in replies["repos/acme/updated/commits"] if c["sha"] == head["sha"])):
        listed["parents"] = [{"sha": update["sha"]}]
    replies["repos/acme/updated/pulls/3/commits"] = [first, update, head]
    replies["repos/acme/updated/pulls/3"]["commits"] = 3
    main_line = replies["repos/acme/updated/commits"]
    main_line.insert(next(i for i, c in enumerate(main_line) if c["sha"] == head["sha"]) + 1, update)
    return replies


def run_tool(tmp: Path, repositories: list[str], replies: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    (tmp / "replies.json").write_text(json.dumps(replies), encoding="utf-8")
    stand_in = tmp / "gh_stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    listed = ", ".join(f'"{r}"' for r in repositories)
    settings = tmp / "settings.toml"
    settings.write_text(
        f'repositories = [{listed}]\nstart = "{START}"\nend = "{END}"\nagent_accounts = ["builder-bot"]\n'
        'disclosures = []\ndata = "data"\noutput = "record"\n',
        encoding="utf-8",
    )
    env = dict(
        os.environ,
        ASRECORDED_GH=json.dumps([sys.executable, str(stand_in)]),
        GH_HOST="asrecorded-test.invalid",  # if gh itself were ever run, it could not reach GitHub
        PYTHONIOENCODING="utf-8",
    )
    return subprocess.run(
        [sys.executable, "-m", "asrecorded", "run", str(settings)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


def screen(out: subprocess.CompletedProcess[str]) -> list[str]:
    return [line.strip() for line in (out.stdout + "\n" + out.stderr).splitlines()]


def rows(tmp: Path, out: subprocess.CompletedProcess[str]) -> list[dict[str, str]]:
    path = tmp / "record" / "changes.csv"
    calls = tmp / "calls.txt"
    asked = calls.read_text(encoding="utf-8") if calls.is_file() else "(nothing asked)\n"
    assert path.is_file(), (
        f"no changes.csv was written (exit {out.returncode})\n{out.stdout}\n{out.stderr}\nasked of gh:\n{asked}"
    )
    with path.open(encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


COLUMNS = ["builder", "let_in_by", "approvals", "ai_shown", "ai_trace", "pattern", "declared_agent_operated"]


def cells(table: list[dict[str, str]]) -> list[str]:
    """Every S2 cell as `<change> <column>: <cell>`, and as `<project> <change> <column>: <cell>`."""
    shown = []
    for row in table:
        for column in COLUMNS:
            cell = row.get(column, "(no such column)")
            shown.append(f"{row['change']} {column}: {cell}")
            shown.append(f"{row['repository']} {row['change']} {column}: {cell}")
    return shown


def test_S2_C1_each_change_in_the_example_set_shows_its_pattern(tmp_path: Path) -> None:
    out = run_tool(tmp_path, ["acme/shop"], shop())
    table = rows(tmp_path, out)
    shown = cells(table)
    assert "#11 pattern: Two people" in shown
    assert "#15 let_in_by: auto-merge switched on by dana" in shown
    assert "a1b2c3d pattern: No pull request" in shown
    patterns = {row["change"]: row.get("pattern", "(no such column)") for row in table}
    assert patterns == {
        "#11": "Two people",
        "#12": "Agent and person",
        "#13": "One account",
        "#14": "AI reviewer only",
        "#15": "Automatic, no approval",
        "#16": "Agent and person",
        "#18": "One account",
        "a1b2c3d": "No pull request",
    }
    assert out.returncode == 0, out.stderr


def test_S2_C2_update_branch_does_not_make_the_merger_a_builder(tmp_path: Path) -> None:
    out = run_tool(tmp_path, ["acme/updated"], updated())
    shown = cells(rows(tmp_path, out))
    assert "acme/updated #3 builder: dana" in shown
    assert "acme/updated #3 let_in_by: lee" in shown
    assert out.returncode == 0, out.stderr


def test_S2_C3_a_login_from_a_commit_author_field_is_never_printed(tmp_path: Path) -> None:
    out = run_tool(tmp_path, ["acme/shop"], shop())
    shown = cells(rows(tmp_path, out))
    assert "#18 builder: builder-bot" in shown
    written = sorted(p for p in (tmp_path / "record").rglob("*") if p.is_file())
    assert written, "the output folder holds no file"
    for path in written:
        assert "stranger" not in path.read_text(encoding="utf-8", errors="replace"), path.name
    assert not [line for line in screen(out) if "stranger" in line]


def test_S2_C4_the_row_says_whether_ai_is_shown_and_which_kind(tmp_path: Path) -> None:
    out = run_tool(tmp_path, ["acme/shop"], shop())
    shown = cells(rows(tmp_path, out))
    assert "#11 ai_shown: not shown" in shown
    assert "#11 ai_trace: " in shown
    assert "#13 ai_shown: yes" in shown
    assert "#13 ai_trace: commit marker: Claude (Anthropic)" in shown


def test_S2_C5_a_declared_account_merging_its_own_change_is_counted_under_both(tmp_path: Path) -> None:
    out = run_tool(tmp_path, ["acme/shop"], shop())
    shown = cells(rows(tmp_path, out))
    assert "#18 pattern: One account" in shown
    assert "#18 declared_agent_operated: yes" in shown
    assert "acme/shop: One account 2 (1 declared agent-operated)" in screen(out)
