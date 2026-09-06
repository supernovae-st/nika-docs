#!/usr/bin/env python3
"""first_command.py — read the front door off a binary, in one place.

The line a stranger is told to type moved twice in three releases
(`nika try 01-hello` -> `nika new hello`) while these pages kept teaching the
old one. It is projected now, and this is the ONE reader: the snapshot writes
what it returns (scripts/mintlify-snapshot.sh) and the gate re-asserts it
against the installed release (count-drift-gate check g). Two readers would
be a mirror to keep in sync, which is the defect one layer up.

The read is deliberately the STRANGER's: an empty working directory and a
scratch HOME, so no wired editor and no exported key can change the answer.
"""

import re
import subprocess
import tempfile

# Read only the current released label. A new shape must replace it deliberately:
# falling through silently would leave whatever string is already on the page,
# which is exactly the failure this file exists to end.
OFFER_LABELS = (
    (re.compile(r"^Next:$"), "current first-wow cascade"),
)


def read_first_command(nika: str) -> str:
    """The first `nika ...` line the binary offers, or '' if no label matches."""
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as work:
        env = {"HOME": home, "PATH": "/usr/bin:/bin", "TERM": "dumb", "NO_COLOR": "1"}
        screen = subprocess.run(
            [nika], cwd=work, env=env, text=True, capture_output=True,
            check=True, timeout=10,
        ).stdout.splitlines()
    for i, line in enumerate(screen):
        if not any(p.match(line.strip()) for p, _ in OFFER_LABELS):
            continue
        for nxt in screen[i + 1:]:
            t = nxt.strip()
            if not t:
                continue
            if not t.startswith("nika "):
                break
            return t.split("#")[0].strip()
        break
    return ""


KNOWN_LABELS = " · ".join(f"{p.pattern} ({since})" for p, since in OFFER_LABELS)
