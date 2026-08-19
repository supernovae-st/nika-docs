#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The sweep must route a project manifest to `nika arm`, not `nika check`."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
SWEEP = DOCS / "scripts" / "oracle-sweep.py"
PLANT = DOCS / "getting-started" / "_mutation-arm-manifest.mdx"

FENCE = """```yaml
nika: v1
ceiling: 0.50
arm:
  - workflow: workflows/nightly.nika.yaml
    cadence: "TZ=UTC 0 3 * * *"
    plafond: 0.25
```
"""


def test_invalid_manifest_is_named_and_refused() -> None:
    if not os.environ.get("NIKA_BIN") and not os.environ.get("PATH"):
        raise SystemExit("skip · no PATH")
    PLANT.write_text(FENCE)
    try:
        result = subprocess.run(
            [sys.executable, str(SWEEP)],
            cwd=DOCS,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 1, output[-800:]
        assert "_mutation-arm-manifest" in output, output[-800:]
        assert "project manifest" in output, output[-800:]
    finally:
        if PLANT.exists():
            PLANT.unlink()


if __name__ == "__main__":
    test_invalid_manifest_is_named_and_refused()
    print("ok · project manifest is judged by arm and its refusal is visible")
