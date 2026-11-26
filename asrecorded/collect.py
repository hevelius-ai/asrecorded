"""Collect (design §2): read GitHub and save the raw replies; write no record.

Collect writes into a new folder beside the data folder and puts it in the data folder's place only when every
repository is complete, so a failed collect leaves the data folder as it was (design §1).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from asrecorded import github
from asrecorded.errors import Stop
from asrecorded.settings import Settings, folder_name
from asrecorded.times import count, parse

ZERO = "0" * 40
PUSHES = {"push", "force_push", "branch_creation"}


def collect(settings: Settings) -> list[str]:
    final = settings.data
    staging = final.with_name(final.name + ".collecting")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        # The raw replies carry email addresses and titles (A12): git ignores them wherever the folder lies.
        (staging / ".gitignore").write_text("*\n", encoding="utf-8", newline="\n")
        for repository in settings.repositories:
            _collect_repository(repository, settings, staging / folder_name(repository))
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    _swap(staging, final)
    return [f"Saved GitHub's replies for {count(len(settings.repositories), 'repository', 'repositories')} in {final}."]


def _swap(staging: Path, final: Path) -> None:
    if final.exists():
        old = final.with_name(final.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        final.rename(old)
        staging.rename(final)
        shutil.rmtree(old)
    else:
        staging.rename(final)


def _collect_repository(repository: str, settings: Settings, folder: Path) -> None:
    try:
        info = github.get_object(f"repos/{repository}")
    except github.Refused:
        raise Stop(f"Cannot read {repository} with your GitHub sign-in. No record was written.") from None
    default = info.get("default_branch")
    if not isinstance(default, str):
        raise Stop(f"GitHub's reply for {repository} names no default branch. No record was written.")
    try:
        _collect_replies(repository, default, info, settings, folder)
    except github.Refused as refused:
        raise Stop(f"GitHub did not answer {refused.path}: {refused.message}. No record was written.") from None
    except (KeyError, TypeError, ValueError):
        raise Stop(f"GitHub's replies for {repository} had an unexpected shape. No record was written.") from None


def _collect_replies(repository: str, default: str, info: dict[str, Any], settings: Settings, folder: Path) -> None:
    r = f"repos/{repository}"
    _save(folder / "repo.json", info)
    pulls = github.get_list(f"{r}/pulls?state=closed&base={default}&per_page=100")
    _save(folder / "pulls.json", pulls)
    activity = github.get_list(f"{r}/activity?ref={default}&per_page=100")
    _save(folder / "activity.json", activity)
    _save(folder / "main_commits.json", github.get_list(f"{r}/commits?sha={default}&per_page=100"))
    for pull in pulls:
        merged_at = pull.get("merged_at")
        if merged_at and _inside(merged_at, settings):
            n, head, base = pull["number"], pull["head"]["sha"], folder / "pr" / str(pull["number"])
            _save(base / "pull.json", github.get_object(f"{r}/pulls/{n}"))
            _save(base / "commits.json", github.get_list(f"{r}/pulls/{n}/commits?per_page=100"))
            _save(base / "reviews.json", github.get_list(f"{r}/pulls/{n}/reviews?per_page=100"))
            _save(base / "timeline.json", github.get_list(f"{r}/issues/{n}/timeline?per_page=100"))
            _save(
                base / "check_runs.json",
                github.get_check_runs(f"{r}/commits/{head}/check-runs?filter=all&per_page=100"),
            )
            _save(base / "statuses.json", github.get_list(f"{r}/commits/{head}/statuses?per_page=100"))
    for entry in activity:
        if entry["activity_type"] in PUSHES and _inside(entry["timestamp"], settings):
            _save(folder / "push" / f"{entry['after']}.json", _brought_in(r, entry))


def _brought_in(r: str, entry: dict[str, Any]) -> list[Any]:
    """The commits a push, a force push or a branch's creation brought in."""
    before, after = entry["before"], entry["after"]
    whole = f"{r}/commits?sha={after}&per_page=100"
    if entry["activity_type"] == "branch_creation" or before == ZERO:
        return github.get_list(whole)
    try:
        return github.get_compare(f"{r}/compare/{before}...{after}")
    except github.Refused as refused:
        if not refused.message.startswith("No common ancestor"):
            raise
        return github.get_list(whole)


def _inside(text: str, settings: Settings) -> bool:
    return settings.start <= parse(text) < settings.end


def _save(path: Path, value: Any) -> None:
    """Saved as GitHub returned it, with sorted keys and two-space indent, so the same replies give the same files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
