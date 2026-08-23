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

VALID_FENCE = """```yaml
nika: my-project
ceiling: 0.50
arm:
  - workflow: workflows/nightly.nika.yaml
    cadence: "TZ=UTC 0 3 * * *"
    plafond: 0.25
    manqué: sauter
```
"""


def run_sweep(fence: str) -> tuple[subprocess.CompletedProcess[str], str]:
    PLANT.write_text(fence)
    result = subprocess.run(
        [sys.executable, str(SWEEP)],
        cwd=DOCS,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    return result, result.stdout + result.stderr


def test_manifest_uses_the_accepting_and_refusing_arm_judge() -> None:
    if not os.environ.get("NIKA_BIN") and not os.environ.get("PATH"):
        raise SystemExit("skip · no PATH")
    try:
        result, output = run_sweep(VALID_FENCE)
        assert result.returncode == 0, output[-800:]
        assert "0 invalid" in output, output[-800:]
        assert "_mutation-arm-manifest" not in output, output[-800:]

        invalid = VALID_FENCE.replace("    manqué: sauter\n", "")
        result, output = run_sweep(invalid)
        assert result.returncode == 1, output[-800:]
        assert "_mutation-arm-manifest" in output, output[-800:]
        # 0.114.0 refuses the incomplete beat on the dry-run path first
        # (`project.bad-value` · `manqué:` absent), before `nika arm`.
        assert "manqué" in output, output[-800:]
    finally:
        if PLANT.exists():
            PLANT.unlink()


if __name__ == "__main__":
    test_manifest_uses_the_accepting_and_refusing_arm_judge()
    print("ok · arm accepts the valid manifest and refuses its invalid twin")
