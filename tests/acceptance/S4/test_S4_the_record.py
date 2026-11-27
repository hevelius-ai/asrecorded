"""S4, the record, the rule and the limits: the owner's approved checks (dev-docs/stories/S4/story.md).

Each check runs the tool the way a user does, `python -m asrecorded run settings.toml` (and `write`), in a temporary
folder. GitHub is never called: `ASRECORDED_GH` names a stand-in for `gh` that answers read requests from saved
replies, in the form `gh api --paginate --slurp` gives them (a list of pages), and answers any other path as GitHub
answers a repository the sign-in cannot read. The saved replies follow S2's and S3's.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
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
API = "https://api.github.com"

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


def hours_before(when: str, hours: int) -> str:
    moment = datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=hours)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def dated(c: dict[str, Any], when: str) -> None:
    c["commit"]["author"]["date"] = c["commit"]["committer"]["date"] = when


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
    Each pull request's two commits are made two hours before it is merged with a merge commit; it has no approval.
    The timelines are added last, by `timelines`, once the commits and reviews are final."""
    root = sha(seed)
    line = [commit(root, [], CREATED)]
    events = [event(seed, "branch_creation", ZERO, root, CREATED, "dana")]
    pulls: list[dict[str, Any]] = []
    replies: dict[str, Any] = {}
    tip = root
    for i, (kind, name, actor, merger, when) in enumerate(steps, start=1):
        first, head, merge = sha(seed + 100 * i + 1), sha(seed + 100 * i + 2), sha(seed + 100 * i + 3)
        if kind == "pr":
            made = hours_before(when, 2)
            work = [commit(first, [tip], made), commit(head, [first], made)]
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


def identity(person: dict[str, str]) -> dict[str, str]:
    """A commit's git author or committer as the timeline gives it: name, address and date, no GitHub account."""
    address = "noreply@github.com" if person["name"] == "GitHub" else f"{person['name']}@example.invalid"
    return {"name": person["name"], "email": address, "date": person["date"]}


def timelines(replies: dict[str, Any], repo: str, auto_merge: dict[str, tuple[str, str]] | None = None) -> None:
    """Each pull request's timeline (`issues/{n}/timeline`) in the shape GitHub's REST timeline gives, in time order:
    one `committed` entry per commit of the pull request, one `reviewed` entry per review, `auto_merge_enabled` when
    `auto_merge` names who switched it on and when, then `merged` and `closed`.

    The shapes are taken from real replies: `committed`, `reviewed`, `merged` and `closed` from the saved replies
    under spike/raw (for example hevelius-ai/aschecked #3's timeline.json: committed, committed, reviewed, merged,
    closed); `reviewed` and `auto_merge_enabled` also from primer/react #8795, and `reviewed`, `merged` and `closed`
    from electron/electron #56067, both read with `gh api --method GET` on 27 Nov 2026. A `committed` entry has no
    `actor`, `created_at` or `id`; a `reviewed` entry has `user` and `submitted_at`, no `actor` or `created_at`, and
    its `state` in lower case (`approved`), where the reviews list says `APPROVED`."""
    for pull in replies[f"repos/{repo}/pulls"]:
        n = pull["number"]
        detail = replies[f"repos/{repo}/pulls/{n}"]
        pull_url = f"{API}/repos/{repo}/pulls/{n}"
        entries: list[tuple[str, dict[str, Any]]] = []
        for c in replies[f"repos/{repo}/pulls/{n}/commits"]:
            oid = c["sha"]
            entries.append(
                (
                    c["commit"]["committer"]["date"],
                    {
                        "event": "committed",
                        "sha": oid,
                        "node_id": f"C_{oid[:16]}",
                        "url": f"{API}/repos/{repo}/git/commits/{oid}",
                        "html_url": f"https://github.com/{repo}/commit/{oid}",
                        "author": identity(c["commit"]["author"]),
                        "committer": identity(c["commit"]["committer"]),
                        "tree": {"sha": oid[::-1], "url": f"{API}/repos/{repo}/git/trees/{oid[::-1]}"},
                        "message": c["commit"]["message"],
                        "parents": [
                            {
                                "sha": p["sha"],
                                "url": f"{API}/repos/{repo}/git/commits/{p['sha']}",
                                "html_url": f"https://github.com/{repo}/commit/{p['sha']}",
                            }
                            for p in c["parents"]
                        ],
                        "verification": {
                            "verified": False,
                            "reason": "unsigned",
                            "signature": None,
                            "payload": None,
                            "verified_at": None,
                        },
                    },
                )
            )
        for r in replies[f"repos/{repo}/pulls/{n}/reviews"]:
            page = f"https://github.com/{repo}/pull/{n}#pullrequestreview-{r['id']}"
            entries.append(
                (
                    r["submitted_at"],
                    {
                        "event": "reviewed",
                        "id": r["id"],
                        "node_id": f"PRR_{r['id']}",
                        "user": r["user"],
                        "body": None,
                        "commit_id": r["commit_id"],
                        "submitted_at": r["submitted_at"],
                        "updated_at": r["submitted_at"],
                        "state": r["state"].lower(),
                        "html_url": page,
                        "pull_request_url": pull_url,
                        "author_association": "NONE" if r["user"]["type"] == "Bot" else "MEMBER",
                        "_links": {"html": {"href": page}, "pull_request": {"href": pull_url}},
                    },
                )
            )
        if auto_merge and str(n) in auto_merge:
            who, when = auto_merge[str(n)]
            entries.append((when, issue_event(repo, 8_000_000 + 10 * n, "auto_merge_enabled", account(who), when)))
        when, merger, merge = detail["merged_at"], detail["merged_by"], detail["merge_commit_sha"]
        merged = issue_event(repo, 8_000_000 + 10 * n + 1, "merged", merger, when, merge)
        closed = issue_event(repo, 8_000_000 + 10 * n + 2, "closed", merger, when) | {
            "state_reason": None,
            "intent": None,
        }
        entries += [(when, merged), (when, closed)]
        entries.sort(key=lambda pair: pair[0])  # stable: entries of the same time keep the order above
        replies[f"repos/{repo}/issues/{n}/timeline"] = [entry for _, entry in entries]


def issue_event(
    repo: str, oid: int, kind: str, actor: dict[str, Any], when: str, merge: str | None = None
) -> dict[str, Any]:
    """A timeline entry of an issue event (`auto_merge_enabled`, `merged`, `closed`), as GitHub gives it."""
    return {
        "id": oid,
        "node_id": f"IE_{oid}",
        "url": f"{API}/repos/{repo}/issues/events/{oid}",
        "event": kind,
        "actor": actor,
        "commit_id": merge,
        "commit_url": f"{API}/repos/{repo}/commits/{merge}" if merge else None,
        "created_at": when,
        "performed_via_github_app": None,
    }


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
    # 18: GitHub links the author field of one of its commits to `stranger`, who took no action on it
    linked = replies["repos/acme/shop/pulls/18/commits"][0]
    linked["commit"]["author"]["name"] = "stranger"
    linked["author"] = account("stranger")
    # 15: dana switched auto-merge on before the merge
    timelines(replies, "acme/shop", auto_merge={"15": ("dana", "2026-11-12T09:00:00Z")})
    return replies


def check_run(oid: int, name: str, head: str, conclusion: str, started: str, completed: str) -> dict[str, Any]:
    """One check run as GitHub's `commits/{ref}/check-runs` lists it (the fields a reader of results uses)."""
    return {
        "id": oid,
        "name": name,
        "head_sha": head,
        "status": "completed",
        "conclusion": conclusion,
        "started_at": started,
        "completed_at": completed,
        "app": {"id": 15368, "slug": "github-actions", "name": "GitHub Actions"},
        "html_url": f"https://github.com/acme/runs/{oid}",
    }


def give_checks(replies: dict[str, Any], repo: str, ref: str, runs: list[dict[str, Any]]) -> None:
    replies[f"repos/{repo}/commits/{ref}/check-runs"] = {"total_count": len(runs), "check_runs": runs}


def shop_with_checks() -> dict[str, Any]:
    """acme/shop with `ci` on each pull request's last commit, started and completed before the merge: #16 failed,
    the others succeeded (requirements, section 8)."""
    replies = shop()
    for i, pull in enumerate(replies["repos/acme/shop/pulls"]):
        head, merged = pull["head"]["sha"], pull["merged_at"]
        result = "failure" if pull["number"] == 16 else "success"
        run = check_run(7000 + i, "ci", head, result, hours_before(merged, 1), hours_before(merged, 1)[:14] + "10:00Z")
        give_checks(replies, "acme/shop", head, [run])
    return replies


def shop_for_the_wording_check() -> dict[str, Any]:
    """The example set, plus what would break the wording rules if printed as given: on #12's last commit, a check
    run named with the word "passed" (as every recent astral-sh/uv pull request has) and a commit status whose name
    holds an email address."""
    replies = shop_with_checks()
    head = replies["repos/acme/shop/pulls/12"]["head"]["sha"]
    runs = replies[f"repos/acme/shop/commits/{head}/check-runs"]["check_runs"]
    runs.append(
        check_run(7400, "all required jobs passed", head, "success", "2026-11-03T09:00:00Z", "2026-11-03T09:05:00Z")
    )
    give_checks(replies, "acme/shop", head, runs)
    address = "ops" + "@" + "example.invalid"
    replies[f"repos/acme/shop/commits/{head}/statuses"] = [
        {
            "id": 9400,
            "node_id": "SC_9400",
            "url": f"https://api.github.com/repos/acme/shop/statuses/{head}",
            "state": "success",
            "description": "deployed",
            "target_url": None,
            "context": f"deploy ({address})",
            "created_at": "2026-11-03T09:06:00Z",
            "updated_at": "2026-11-03T09:06:00Z",
            "creator": account("lee"),
        }
    ]
    return replies


RULE = 'allowed_patterns = ["Two people", "Agent and person"]\nrequired_checks = ["ci"]\n'


def run_tool(tmp: Path, replies: dict[str, Any], rule: bool, command: str = "run") -> subprocess.CompletedProcess[str]:
    (tmp / "replies.json").write_text(json.dumps(replies), encoding="utf-8")
    stand_in = tmp / "gh_stand_in.py"
    stand_in.write_text(STAND_IN, encoding="utf-8")
    settings = tmp / "settings.toml"
    text = (
        f'repositories = ["acme/shop"]\nstart = "{START}"\nend = "{END}"\nagent_accounts = ["builder-bot"]\n'
        'disclosures = []\ndata = "data"\noutput = "record"\n'
    )
    if rule:
        (tmp / "rule.toml").write_text(RULE, encoding="utf-8")
        text += 'rule = "rule.toml"\n'
    settings.write_text(text, encoding="utf-8")
    env = dict(
        os.environ,
        ASRECORDED_GH=json.dumps([sys.executable, str(stand_in)]),
        GH_HOST="asrecorded-test.invalid",  # if gh itself were ever run, it could not reach GitHub
        PYTHONIOENCODING="utf-8",
    )
    return subprocess.run(
        [sys.executable, "-m", "asrecorded", command, str(settings)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


def record(tmp: Path, out: subprocess.CompletedProcess[str]) -> list[str]:
    path = tmp / "record" / "record.md"
    assert path.is_file(), f"no record.md was written (exit {out.returncode})\n{out.stdout}\n{out.stderr}"
    return path.read_text(encoding="utf-8").splitlines()


def section(lines: list[str], heading: str) -> list[str]:
    """The lines under a `## ` heading, up to the next one."""
    if heading not in lines:
        return []
    start = lines.index(heading) + 1
    after = [i for i in range(start, len(lines)) if lines[i].startswith("## ")]
    return lines[start : after[0] if after else len(lines)]


EXCEPTIONS = "## Exceptions under the rule"
CANNOT_SHOW = [
    "## What this record cannot show",
    "",
    "- AI use that leaves no trace in the history",
    "- whether an approver read or understood the change",
    "- whether the checks were good checks",
    "- which workflow posted a check of a given name",
    "- two accounts held by one person, unless declared",
    "- anything outside the listed repositories or outside GitHub",
    "- history that was rewritten",
]
BANNED = re.compile(r"\b(approved|compliant|certified|secure|safe|audited|passed)\b|\bno AI\b", re.IGNORECASE)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def test_S4_C1_the_record_shows_the_totals_the_six_exceptions_and_every_change(tmp_path: Path) -> None:
    out = run_tool(tmp_path, shop_with_checks(), rule=True)
    lines = record(tmp_path, out)
    assert "- Changes: 8 (7 through a pull request, 1 pushed directly)" in lines
    assert "- AI shown: 6" in lines
    assert "- Exceptions under the rule: 6" in lines
    reasons = [line for line in section(lines, EXCEPTIONS) if line.startswith("- ")]
    assert '- #16: the required check "ci" did not end in success on the merged version (it shows: failure).' in reasons
    assert [line.split(":")[0] for line in reasons] == ["- #13", "- #14", "- #15", "- #16", "- #18", "- a1b2c3d"]
    rows = [line for line in section(lines, "## Every change") if line.startswith("| acme/shop |")]
    assert (
        "| acme/shop | [#11](https://github.com/acme/shop/pull/11) | 2026-11-02 10:00 | pull request | dana | dana "
        "| lee (on the merged version) | not shown | Two people | ci: success |"
    ) in rows
    assert len(rows) == 8
    assert out.returncode == 0, out.stderr


def test_S4_C2_without_a_rule_there_is_no_exceptions_section_and_patterns_are_counted(tmp_path: Path) -> None:
    out = run_tool(tmp_path, shop_with_checks(), rule=False)
    lines = record(tmp_path, out)
    assert "- One account: 2, of which 1 declared agent-operated" in lines
    assert "- Automatic, no approval: 1" in lines
    assert EXCEPTIONS not in lines
    assert out.returncode == 0, out.stderr


def test_S4_C3_two_runs_give_the_same_files_and_the_record_holds_the_checksums(tmp_path: Path) -> None:
    first = run_tool(tmp_path, shop_with_checks(), rule=True)
    lines = record(tmp_path, first)
    names = ["record.md", "changes.csv", "record.json"]
    before = {
        name: (tmp_path / "record" / name).read_bytes() for name in names if (tmp_path / "record" / name).is_file()
    }
    assert sorted(before) == sorted(names), f"files written: {sorted(before)}"
    again = run_tool(tmp_path, shop_with_checks(), rule=True, command="write")
    after = {name: (tmp_path / "record" / name).read_bytes() for name in names}
    assert after == before, again.stderr
    csv_sum = hashlib.sha256(before["changes.csv"]).hexdigest()
    json_sum = hashlib.sha256(before["record.json"]).hexdigest()
    assert f"- changes.csv SHA-256: {csv_sum}" in lines
    assert f"- record.json SHA-256: {json_sum}" in lines


def test_S4_C4_no_banned_word_or_email_address_and_the_fixed_section_word_for_word(tmp_path: Path) -> None:
    out = run_tool(tmp_path, shop_for_the_wording_check(), rule=True)
    lines = record(tmp_path, out)
    start = lines.index("## What this record cannot show") if "## What this record cannot show" in lines else 0
    assert lines[start : start + len(CANNOT_SHOW)] == CANNOT_SHOW
    assert "- anything outside the listed repositories or outside GitHub" in lines
    written = sorted(p for p in (tmp_path / "record").rglob("*") if p.is_file())
    assert [p.name for p in written] == ["changes.csv", "record.json", "record.md"]
    for path in written:
        text = path.read_text(encoding="utf-8")
        assert not BANNED.findall(text), (path.name, BANNED.findall(text))
        assert not EMAIL.findall(text), path.name
    assert out.returncode == 0, out.stderr


PLANTED = {
    "a gh api call with --method POST": (
        'import subprocess\n\nsubprocess.run(["gh", "api", "--method", "POST", "repos/a/b/issues"])\n'
    ),
    "a gh api call with -X PATCH": 'import subprocess\n\nsubprocess.run(["gh", "api", "-X", "PATCH", "repos/a/b"])\n',
    "an import of urllib.request": "import urllib.request\n",
}


def read_only_check(folder: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "read_only_check.py"), str(folder)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )


def test_S4_C5_a_check_of_the_tools_own_code_fails_on_any_call_that_is_not_a_read(tmp_path: Path) -> None:
    out = read_only_check(REPO_ROOT / "asrecorded")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "gh api --method GET" in out.stdout
    for name, code in PLANTED.items():
        copy = tmp_path / name.replace(" ", "_").replace(".", "_") / "asrecorded"
        shutil.copytree(REPO_ROOT / "asrecorded", copy, ignore=shutil.ignore_patterns("__pycache__"))
        (copy / "planted.py").write_text(code, encoding="utf-8")
        found = read_only_check(copy)
        assert found.returncode != 0, name
        assert "planted.py" in found.stdout + found.stderr, name
