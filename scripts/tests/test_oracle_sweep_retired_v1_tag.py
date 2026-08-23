#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A planted `nika: v1` project fence must fail on the released binary.

0.114.0 refuses that tag (`project.identity` · retired schema tag). The
six SDK pages taught it as a frozen mark; a reader who copied it believed
the product was broken. oracle-sweep already judges project fences against
the held binary — this plant is the cliquet so a seventh page cannot
return unnoticed. The fixture is the REFUSAL, not a valid example.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
SWEEP = DOCS / "scripts" / "oracle-sweep.py"
PLANT = DOCS / "getting-started" / "_mutation-retired-v1-tag.mdx"

RETIRED = """```yaml
nika: v1
ceiling: 0.50
```
"""


def test_retired_v1_project_tag_is_visible_and_red() -> None:
    if not os.environ.get("NIKA_BIN") and not os.environ.get("PATH"):
        raise SystemExit("skip · no PATH")
    PLANT.write_text(RETIRED, encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(SWEEP)],
            cwd=DOCS,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 1, output[-1200:]
        assert "_mutation-retired-v1-tag.mdx" in output, output[-1200:]
        assert "[project shape]" in output, output[-1200:]
        # 0.114.0 names the class; do not accept a silent count-only red.
        assert "retired schema tag" in output or "project.identity" in output, output[
            -1200:
        ]
    finally:
        if PLANT.exists():
            PLANT.unlink()


if __name__ == "__main__":
    test_retired_v1_project_tag_is_visible_and_red()
    print("ok · planted nika: v1 project fence is visible and red")
