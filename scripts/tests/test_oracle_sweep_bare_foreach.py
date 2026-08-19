#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The sweep must redden a fragment fence that still ships scalar for_each.

A task-shaped yaml block never reaches `nika check` (no `nika:` envelope),
so PARSE-019 used to be invisible on the live teaching pages. The plant is
that class: a fragment with `for_each: ${{ … }}` + sibling knobs.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
SWEEP = DOCS / "scripts" / "oracle-sweep.py"
PLANT = DOCS / "getting-started" / "_mutation-bare-foreach.mdx"

FENCE = """```yaml
scrape_all:
  with:
    pages: ${{ tasks.discover.pages }}
  for_each: ${{ with.pages }}
  max_parallel: 5
  fail_fast: false
  invoke:
    tool: nika:fetch
    args: { url: "${{ item }}" }
```
"""


def test_bare_foreach_fragment_is_invalid() -> None:
    if not os.environ.get("NIKA_BIN") and not os.environ.get("PATH"):
        raise SystemExit("skip · no PATH")
    PLANT.write_text(FENCE)
    try:
        env = os.environ.copy()
        r = subprocess.run(
            [sys.executable, str(SWEEP)],
            cwd=DOCS,
            env=env,
            capture_output=True,
            text=True,
        )
        out = r.stdout + r.stderr
        assert r.returncode == 1, out[-800:]
        assert "_mutation-bare-foreach" in out, out[-800:]
        assert "for_each scalar" in out or "PARSE-019" in out, out[-800:]
    finally:
        if PLANT.exists():
            PLANT.unlink()


if __name__ == "__main__":
    test_bare_foreach_fragment_is_invalid()
    print("ok · fragment fence + scalar for_each is visible and red")
