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
        'from os import system\nsystem("ls")\n',
        "import urllib.request\n",
        "from http import client\n",
        "import socket\n",
        "import requests\n",
        'import asyncio\nasyncio.create_subprocess_exec("ls")\n',
        'import importlib\nimportlib.import_module("subprocess")\n',
        '__import__("socket")\n',
        "import subprocess\nsubprocess.run()\n",
        "import subprocess\nsubprocess.run(command)\n",
        # PR #14 review round 1, H1: each of these passed the first version of the check
        'import subprocess\nrun = subprocess.run\nrun(["gh", "api", "-X", "POST", "repos/a/b/issues"])\n',
        'import subprocess\nsp = subprocess\nsp.run(["gh", "api", "-X", "POST", "x"])\n',
        'from subprocess import *\nrun(["gh", "api", "--method", "DELETE", "x"])\n',
        'import subprocess\ngetattr(subprocess, "run")(["gh", "api", "-X", "POST", "x"])\n',
        'import subprocess\ndef f(path):\n    command = ["gh", "api", "--method", "GET"]\n'
        '    command += ["-X", "POST", path]\n    subprocess.run(command)\n',
        'import subprocess\ndef f(path):\n    command = ["gh", "api", "--method", "GET", path]\n'
        '    command.append("--method=POST")\n    subprocess.run(command)\n',
        'import subprocess\ndef f(path):\n    command = ["gh", "api", "--method", "GET", path]\n'
        '    command.extend(["-f", "title=x", "-X", "POST"])\n    subprocess.run(command)\n',
        'import subprocess\ndef f(path, close):\n    command = ["gh", "api", "--method", "GET", path]\n    if close:\n'
        '        command = ["gh", "issue", "close", "1"]\n    subprocess.run(command)\n',
        'import subprocess\nEXTRA = ["-X", "POST"]\nsubprocess.run(["gh", "api", "--method", "GET", *EXTRA, "x"])\n',
        'import subprocess\nsubprocess.run(["gh", "api", "--method", "GET"] + ["-X", "POST", "x"])\n',
        'import subprocess\nsubprocess.run(["gh", "api", "--method", "GET", "-XPOST", "x"])\n',
        "import subprocess\ndef f(verb, path):\n"
        '    subprocess.run(["gh", "api", "--method", "GET", "--method", verb, path])\n',
        "import subprocess\ndef f(verb):\n"
        '    subprocess.run(["gh", "api", "--method", "GET", f"--method={verb}", "x"])\n',
        'import subprocess\nsubprocess.run(["gh", "api", "--method", "GET", "--input=body.json", "-XPATCH", "x"])\n',
        'import subprocess\nsubprocess.run(["git", "push", "origin", "api", "--method", "GET"])\n',
        'import subprocess\nsubprocess.run(["sh", "-c", "gh api -X POST x", "api", "--method", "GET"])\n',
        'exec("import subprocess")\n',
        'eval("1")\n',
        'import sys\nsys.modules["subprocess"].run(["gh", "api", "-X", "POST", "x"])\n',
        'import subprocess, functools\nfunctools.partial(subprocess.run, ["gh", "api", "-X", "POST", "x"])()\n',
        "import httplib2\n",
        "from github import Github\n",
        'import asyncio\nasync def f():\n    await asyncio.open_connection("api.github.com", 443, ssl=True)\n',
        'import webbrowser\nwebbrowser.open("https://github.com/a/b/issues/new")\n',
        'import builtins\nbuiltins.__import__("socket")\n',
        "import importlib.util\n",
        "import ctypes\n",
        "import _socket\n",
        'import subprocess\nsubprocess.run("gh api --method GET x", shell=True)\n',
        'import subprocess\nsubprocess.run(("gh", "api", "--method", "GET", "x"))\n',
        'import subprocess\nsubprocess.run(args=["gh", "api", "-X", "POST", "x"])\n',
        'import subprocess\nsubprocess.run(["gh", "api", "--method", "GET", "x"])\n',
        'import subprocess\nCMD = ["gh", "api", "--method", "GET", "x"]\ndef f():\n    subprocess.run(CMD)\n',
        "import subprocess\nclass A:\n    run = staticmethod(subprocess.run)\n",
        "import subprocess\nclass A:\n    sp = subprocess\n",
        "import os\nos.fork()\n",
        "import os\nf = os.system\n",
    ],
)
def test_any_other_process_call_or_network_use_is_found(tmp_path: Path, planted: str) -> None:
    found, _ = read_only_check.check(package(tmp_path, planted))
    assert found, planted
    assert all(line.startswith("planted.py:") for line in found), found


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('"--method", "GET"', '"--method", "POST"'),
        ('"--slurp", path]', '"--slurp", "-XPOST", path]'),
        ("        done = subprocess.run(", '        command += ["-X", "POST"]\n        done = subprocess.run('),
        ('"--paginate", "--slurp", path]', '"--paginate", "--slurp", path, *extra()]'),
        ("command, capture_output=True", "command, shell=True, capture_output=True"),
        ("import subprocess\n", "import subprocess\nrun = subprocess.run\n"),
    ],
)
def test_a_change_to_github_py_that_is_not_the_one_read_is_found(tmp_path: Path, old: str, new: str) -> None:
    copy = package(tmp_path)
    text = (copy / "github.py").read_text(encoding="utf-8")
    assert old in text
    (copy / "github.py").write_text(text.replace(old, new, 1), encoding="utf-8")
    found, _ = read_only_check.check(copy)
    assert found and all(line.startswith("github.py:") for line in found), found


def test_a_call_that_is_not_a_read_inside_github_py_is_found(tmp_path: Path) -> None:
    copy = package(tmp_path)
    text = (copy / "github.py").read_text(encoding="utf-8")
    (copy / "github.py").write_text(text.replace('"--method", "GET"', '"--method", "POST"'), encoding="utf-8")
    found, _ = read_only_check.check(copy)
    assert found and all(line.startswith("github.py:") for line in found), found


def test_a_file_it_cannot_read_as_python_is_found(tmp_path: Path) -> None:
    found, _ = read_only_check.check(package(tmp_path, "def (:\n"))
    assert found == ["planted.py:1: cannot be read as Python, so it cannot be checked"]
    copy = package(tmp_path / "bytes")
    (copy / "odd.py").write_bytes(b"import socket\n# \xff\xfe\n")
    found, _ = read_only_check.check(copy)
    assert found == ["odd.py:1: cannot be read as Python, so it cannot be checked"]


def test_the_command_says_what_it_found_and_exits_with_a_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert read_only_check.main([str(PACKAGE)]) == 0
    assert capsys.readouterr().out.startswith(f"Every call to GitHub in {PACKAGE} is gh api --method GET (")
    assert read_only_check.main([str(package(tmp_path, "import socket\nimport ssl\n"))]) == 1
    out = capsys.readouterr().out
    assert "planted.py:1: imports socket, which this check does not allow" in out
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


KNOWN_LIMITS = [
    'import os as o\no.system("gh api -X POST x")\n',
    'import os\ngetattr(os, "system")("gh api -X POST x")\n',
    'import os\nx = os\nx.system("gh api -X POST x")\n',
    'import shutil\nshutil.os.system("gh api -X POST x")\n',
    'from asrecorded import github\ngithub.subprocess.run(["gh", "api", "-X", "POST", "x"])\n',
    'from sys import modules\nmodules["subprocess"].run(["gh", "api", "-X", "POST", "x"])\n',
    'getattr(__builtins__, "__import__")("socket")\n',
    'import os\nvars(os)["system"]("gh api -X POST x")\n',
]


@pytest.mark.parametrize("planted", KNOWN_LIMITS)
def test_the_stated_limit_code_written_to_hide_a_call_is_not_found(tmp_path: Path, planted: str) -> None:
    """Decision S4-RO (the owner's choice PR14-2 B): the check reads code as written and does not follow where a name
    leads, so these forms, found by PR #14's review round 2, pass it. They are held here so that the limit is known
    and cannot change unseen: if the check is made to find one, move it to the list above."""
    found, _ = read_only_check.check(package(tmp_path, planted))
    assert found == []
