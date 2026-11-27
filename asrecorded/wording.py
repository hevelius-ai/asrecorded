"""The wording rules for every file (BRD section 7): the banned words and email addresses.

A name the record shows as GitHub gives it (a check's name) may hold one; it is printed with only that part replaced
(the owner's choice S4-W1 C), so the rest of the name still tells checks apart. A word ends at any character that is
not a letter or a digit, the underscore included: `checks_passed` holds "passed".
"""

from __future__ import annotations

import re

WORD = "[a word this record does not use]"
ADDRESS = "[address not shown]"

_EDGE_BEFORE, _EDGE_AFTER = r"(?<![^\W_])", r"(?![^\W_])"
BANNED = re.compile(
    _EDGE_BEFORE + r"(approved|compliant|certified|secure|safe|audited|passed|no[\s_-]+ai)" + _EDGE_AFTER,
    re.IGNORECASE,
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def mask(text: str) -> str:
    """The text with each email address and each banned word replaced, the rest kept."""
    return BANNED.sub(WORD, EMAIL.sub(ADDRESS, text))


def found(text: str) -> list[str]:
    """What in the text breaks the wording rules, each kind once, in the order first met."""
    kinds: list[str] = []
    for match in re.finditer(f"{BANNED.pattern}|(?P<email>{EMAIL.pattern})", text, re.IGNORECASE):
        kind = "an email address" if match.group("email") else f'the word "{match.group(1).lower()}"'
        if kind not in kinds:
            kinds.append(kind)
    return kinds
