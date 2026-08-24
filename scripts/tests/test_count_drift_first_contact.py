#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A first-contact page teaching a retired front door must go red.

The line a stranger is told to type moved twice in three releases
(`nika try 01-hello` -> `nika new hello`) and these pages kept teaching the
old one, because a fenced command cannot interpolate and so the string is
unavoidably duplicated. count-drift check (g) is what owns it now.

Both directions, because a gate proven one way proves nothing:
  a planted stale command on a first-contact page   -> RED, naming file:line
  the same command on an examples/ page             -> GREEN (that page is
    teaching ITS OWN slug, which is right, and widening the gate onto it
    would only teach people to mute it)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
GATE = DOCS / "scripts" / "count-drift-gate.py"
SNAP = DOCS / "snippets" / "_status-snapshot.mdx"
FIRST_CONTACT_PLANT = DOCS / "getting-started" / "_mutation-stale-front-door.mdx"
EXAMPLES_PLANT = DOCS / "examples" / "_mutation-own-slug.mdx"


def _projected_first_command() -> str:
    m = re.search(r'firstCommand:\s*"([^"]+)"', SNAP.read_text(encoding="utf-8"))
    assert m, "the snapshot carries no firstCommand — run scripts/mintlify-snapshot.sh"
    return m.group(1)


def _run() -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(GATE)], cwd=DOCS, capture_output=True, text=True
    )
    return r.returncode, r.stdout + r.stderr


def _fence(cmd: str) -> str:
    return f"```bash\n{cmd}\n```\n"


def test_stale_front_door_is_red_and_named() -> None:
    """A page a stranger lands on may only teach the projected command."""
    projected = _projected_first_command()
    # a command that is NOT the projected one, whatever the projection is today
    stale = "nika new hello" if projected != "nika new hello" else "nika try 01-hello"
    FIRST_CONTACT_PLANT.write_text(_fence(stale), encoding="utf-8")
    try:
        code, out = _run()
        assert code == 1, out[-1200:]
        assert "_mutation-stale-front-door.mdx" in out, out[-1200:]
        assert stale in out and projected in out, out[-1200:]
    finally:
        FIRST_CONTACT_PLANT.unlink(missing_ok=True)


def test_an_examples_page_keeps_its_own_slug() -> None:
    """The gate must not widen onto pages that teach their own example."""
    EXAMPLES_PLANT.write_text(_fence("nika try some-example-slug"), encoding="utf-8")
    try:
        code, out = _run()
        assert code == 0, out[-1200:]
        assert "_mutation-own-slug.mdx" not in out, out[-1200:]
    finally:
        EXAMPLES_PLANT.unlink(missing_ok=True)


if __name__ == "__main__":
    test_stale_front_door_is_red_and_named()
    test_an_examples_page_keeps_its_own_slug()
    print("ok · a stale front door is red and named · an example keeps its slug")
