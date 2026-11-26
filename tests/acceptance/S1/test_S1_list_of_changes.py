"""S1, the list of changes: the owner's approved checks (dev-docs/stories/S1/story.md).

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
ACCOUNT_IDS = {"dana": 1001, "lee": 1002, "builder-bot": 1003}

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
    return {"login": login, "id": ACCOUNT_IDS[login], "type": "User"}


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


def history(repo: str, seed: int, steps: list[tuple[str, str, str, str, str]], squash: bool = False) -> dict[str, Any]:
    """The saved replies for one repository built from steps, oldest first:
    ("pr", number, opener, merger, merged at), ("push", commit, pusher, "", time) or ("force", "", pusher, "", time)."""
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
            parents = [tip] if squash else [tip, head]
            line += ([] if squash else work) + [commit(merge, parents, when)]
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
            replies[f"repos/{repo}/issues/{name}/timeline"] = []
            replies[f"repos/{repo}/commits/{head}/check-runs"] = {"total_count": 0, "check_runs": []}
            replies[f"repos/{repo}/commits/{head}/statuses"] = []
            events.append(event(seed + 100 * i, "pr_merge", tip, merge, when, merger))
            tip = merge
        elif kind == "push":
            pushed = commit(name, [tip], when)
            line.append(pushed)
            replies[f"repos/{repo}/compare/{tip}...{name}"] = {
                "status": "ahead",
                "total_commits": 1,
                "commits": [pushed],
            }
            events.append(event(seed + 100 * i, "push", tip, name, when, actor))
            tip = name
        else:
            brought = [commit(first, [root], when), commit(head, [first], when), commit(merge, [head], when)]
            replies[f"repos/{repo}/compare/{tip}...{merge}"] = {
                "status": "diverged",
                "total_commits": 3,
                "commits": brought,
            }
            events.append(event(seed + 100 * i, "force_push", tip, merge, when, actor))
            line = [line[0], *brought]
            tip = merge
    replies[f"repos/{repo}"] = {"full_name": repo, "default_branch": "main", "private": False, "created_at": CREATED}
    replies[f"repos/{repo}/pulls"] = pulls[::-1]
    replies[f"repos/{repo}/activity"] = events[::-1]
    replies[f"repos/{repo}/commits"] = line[::-1]
    return replies


def shop() -> dict[str, Any]:
    """acme/shop with the example set's S1 facts (who merged, when); S2 to S4 add their own."""
    return history(
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


def changes_of(repo: str, table: list[dict[str, str]]) -> list[str]:
    return sorted(row["change"] for row in table if row["repository"] == repo)


def test_S1_C1_the_example_set_lists_exactly_eight_changes(tmp_path: Path) -> None:
    out = run_tool(tmp_path, ["acme/shop"], shop())
    table = rows(tmp_path, out)
    shown = [f"{row['repository']},{row['change']},{row['how']}" for row in table]
    assert "acme/shop,#11,pull request" in shown
    assert "acme/shop,a1b2c3d,pushed directly" in shown
    assert changes_of("acme/shop", table) == ["#11", "#12", "#13", "#14", "#15", "#16", "#18", "a1b2c3d"]
    assert out.returncode == 0, out.stderr


def test_S1_C2_a_change_let_in_at_the_period_end_is_not_listed(tmp_path: Path) -> None:
    out = run_tool(tmp_path, ["acme/shop"], shop())
    assert "acme/shop: 8 changes (7 pull requests, 1 commit pushed directly)" in screen(out)
    assert "#17" not in changes_of("acme/shop", rows(tmp_path, out))


def test_S1_C3_squash_and_merge_commit_projects_list_each_pull_request_once(tmp_path: Path) -> None:
    steps = [
        ("pr", "1", "dana", "lee", "2026-11-06T10:00:00Z"),
        ("pr", "2", "lee", "dana", "2026-11-08T10:00:00Z"),
    ]
    replies = history("acme/squash", 0x2000, steps, squash=True) | history("acme/joined", 0x3000, steps)
    out = run_tool(tmp_path, ["acme/squash", "acme/joined"], replies)
    assert "acme/squash: 2 changes (2 pull requests, 0 commits pushed directly)" in screen(out)
    assert "acme/joined: 2 changes (2 pull requests, 0 commits pushed directly)" in screen(out)
    table = rows(tmp_path, out)
    assert changes_of("acme/squash", table) == ["#1", "#2"]
    assert changes_of("acme/joined", table) == ["#1", "#2"]
    assert [row for row in table if row["how"] == "pushed directly"] == []


def test_S1_C4_rewritten_history_is_listed_on_its_own(tmp_path: Path) -> None:
    steps = [
        ("pr", "1", "dana", "lee", "2026-11-05T10:00:00Z"),
        ("force", "", "lee", "", "2026-11-20T09:00:00Z"),
    ]
    out = run_tool(tmp_path, ["acme/rewritten"], history("acme/rewritten", 0x4000, steps))
    assert "acme/rewritten: history rewritten on 2026-11-20 at 09:00 UTC by lee, 3 commits brought in" in screen(out)
    assert changes_of("acme/rewritten", rows(tmp_path, out)) == ["#1"]


def test_S1_C5_a_project_the_sign_in_cannot_read_stops_collecting(tmp_path: Path) -> None:
    out = run_tool(tmp_path, ["acme/shop", "acme/secret"], shop())
    assert "Cannot read acme/secret with your GitHub sign-in. No record was written." in screen(out)
    assert out.returncode != 0
    assert not (tmp_path / "record" / "record.md").exists()
    assert not (tmp_path / "record" / "changes.csv").exists()
    assert list((tmp_path / "record").glob("*")) == []
