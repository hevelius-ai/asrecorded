"""`python -m asrecorded run|collect|write settings.toml` (design §1)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from asrecorded import collect, output
from asrecorded.errors import Stop
from asrecorded.settings import Settings, load

USAGE = "Use: python -m asrecorded run|collect|write settings.toml"

COMMANDS: dict[str, Callable[[Settings], list[str]]] = {
    "run": lambda settings: collect.collect(settings) + output.write(settings),
    "collect": lambda settings: collect.collect(settings),
    "write": lambda settings: output.write(settings),
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] not in COMMANDS:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        lines = COMMANDS[args[0]](load(Path(args[1])))
    except Stop as stop:
        print(stop.message, file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
