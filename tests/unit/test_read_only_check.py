"""Tests for scripts/read_only_check.py: a check of the package's own code (S4, design §2)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import read_only_check  # noqa: E402

PACKAGE = Path(__file__).resolve().parents[2] / "asrecorded"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "read_only_check.py"


def package(tmp: Path, planted: str | None = None, name: str = "planted.py") -> Path:
    copy = tmp / "asrecorded"
    shutil.copytree(PACKAGE, copy, ignore=shutil.ignore_patterns("__pycache__"))
    if planted is not None:
        (copy / name).write_text(planted, encoding="utf-8")
    return copy


def test_the_package_reads_github_only_with_gh_api_get() -> None:
    found, files = read_only_check.check(PACKAGE)
    assert found == []
    assert files >= 10


@pytest.mark.parametrize(
    "planted",
    [
        'import subprocess\nsubprocess.run(["gh", "api", "--method", "POST", "x"])\n',
        'import subprocess\nsubprocess.run(["gh", "api", "-X", "PATCH", "x"])\n',
        'import subprocess\nsubprocess.run(["gh", "api", "--method=DELETE", "x"])\n',
        'import subprocess\nsubprocess.run(["gh", "api", "--method", "GET", "-f", "a=b", "x"])\n',
        'import subprocess\nsubprocess.run(["gh", "issue", "close", "1"])\n',
        'import subprocess\nsubprocess.Popen(["git", "push"])\n',
        'from subprocess import check_output\ncheck_output(["ls"])\n',
        'import subprocess as sp\nsp.call(["ls"])\n',
        'import os\nos.system("gh api -X POST x")\n',
        'import os\nos.popen("ls")\n',
        'import os\nos.execv("/bin/ls", ["ls"])\n',
        "import urllib.request\n",
        "from http import client\n",
        "import socket\n",
        "import requests\n",
        'import asyncio\nasyncio.create_subprocess_exec("ls")\n',
        'import importlib\nimportlib.import_module("subprocess")\n',
        '__import__("socket")\n',
        "import subprocess\nsubprocess.run()\n",
        "import subprocess\nsubprocess.run(command)\n",
    ],
)
def test_any_other_process_call_or_network_use_is_found(tmp_path: Path, planted: str) -> None:
    found, _ = read_only_check.check(package(tmp_path, planted))
    assert found, planted
    assert all(line.startswith("planted.py:") for line in found), found


def test_a_call_that_is_not_a_read_inside_github_py_is_found(tmp_path: Path) -> None:
    copy = package(tmp_path)
    text = (copy / "github.py").read_text(encoding="utf-8")
    (copy / "github.py").write_text(text.replace('"--method", "GET"', '"--method", "POST"'), encoding="utf-8")
    found, _ = read_only_check.check(copy)
    assert found and all(line.startswith("github.py:") for line in found), found


def test_a_file_it_cannot_read_as_python_is_found(tmp_path: Path) -> None:
    found, _ = read_only_check.check(package(tmp_path, "def (:\n"))
    assert found == ["planted.py:1: cannot be read as Python, so it cannot be checked"]


def test_the_command_says_what_it_found_and_exits_with_a_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert read_only_check.main([str(PACKAGE)]) == 0
    assert capsys.readouterr().out.startswith(f"Every call to GitHub in {PACKAGE} is gh api --method GET (")
    assert read_only_check.main([str(package(tmp_path, "import socket\nimport ssl\n"))]) == 1
    out = capsys.readouterr().out
    assert "planted.py:1: imports socket, a network module" in out
    assert out.rstrip().endswith("2 calls or imports that are not reads of GitHub. Fix them before merging.")
    assert read_only_check.main([str(package(tmp_path / "one", "import socket\n"))]) == 1
    assert (
        capsys.readouterr()
        .out.rstrip()
        .endswith("1 call or import that is not a read of GitHub. Fix it before merging.")
    )
    assert read_only_check.main([]) == 2
    assert "Use: python scripts/read_only_check.py <package folder>" in capsys.readouterr().err
    assert read_only_check.main([str(tmp_path / "none")]) == 2
    assert "is not a folder" in capsys.readouterr().err


def test_the_script_runs_as_a_command() -> None:
    done = subprocess.run([sys.executable, str(SCRIPT), str(PACKAGE)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
