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
# The raw replies carry email addresses and titles (A12): git ignores them wherever the folder lies. The same file
# marks a folder collect saved, the only kind of folder collect ever replaces.
MARKER = "# Saved by AsRecorded's collect: GitHub's raw replies, which hold email addresses. Never commit them.\n*\n"


def collect(settings: Settings) -> list[str]:
    final = settings.data
    if final.exists() and not _replaceable(final):
        raise Stop(
            f'The data folder {final} holds files that collect did not save. Name a new or empty folder as "data" '
            "in the settings. No record was written."
        )
    staging = final.with_name(final.name + ".collecting")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        (staging / ".gitignore").write_text(MARKER, encoding="utf-8", newline="\n")
        for repository in settings.repositories:
            _collect_repository(repository, settings, staging / folder_name(repository))
        _swap(staging, final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return [f"Saved GitHub's replies for {count(len(settings.repositories), 'repository', 'repositories')} in {final}."]


def _replaceable(folder: Path) -> bool:
    """An empty folder, or one an earlier collect saved."""
    if not folder.is_dir():
        return False
    marker = folder / ".gitignore"
    return not any(folder.iterdir()) or (marker.is_file() and marker.read_text(encoding="utf-8") == MARKER)


def _swap(staging: Path, final: Path) -> None:
    """Put the complete new folder in the data folder's place; on any failure keep the earlier one."""
    if not final.exists():
        staging.rename(final)
        return
    old = final.with_name(final.name + ".old")
    shutil.rmtree(old, ignore_errors=True)
    try:
        final.rename(old)
    except OSError as error:
        raise _kept(final, error) from None
    try:
        staging.rename(final)
    except OSError as error:
        old.rename(final)
        raise _kept(final, error) from None
    shutil.rmtree(old, ignore_errors=True)


def _kept(final: Path, error: OSError) -> Stop:
    return Stop(
        f"Cannot put the new data folder in place of {final}: {error.strerror or error}. "
        "The earlier data folder was kept. No record was written."
    )


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
            _save(folder / "push" / push_file(entry), _brought_in(r, entry))


def push_file(entry: dict[str, Any]) -> str:
    """One saved reply per push, named by its `before` and `after`: two pushes that end on the same commit (a push
    undone by a force push back) keep their own replies, and the same two ends always bring in the same commits."""
    return f"{entry['before']}...{entry['after']}.json"


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
