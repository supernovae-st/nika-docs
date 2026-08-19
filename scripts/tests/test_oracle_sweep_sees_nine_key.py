#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The sweep must see a nine-key fence and refuse leftover on_finally.

Plan L6b · refuter 2026-08-19: `"nika: v1" in b` went blind on `nika: hello`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
SWEEP = DOCS / "scripts" / "oracle-sweep.py"
PLANT = DOCS / "getting-started" / "_mutation-hello-finally.mdx"

FENCE = """```yaml
nika: hello
model: mock/echo
tasks:
  greet:
    infer: { prompt: "hi", model: mock/echo }
    on_finally:
      - exec: { command: ["true"] }
```
"""


def test_nine_key_plus_on_finally_is_invalid() -> None:
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
        assert "_mutation-hello-finally" in out, out[-800:]
        assert "on_finally" in out or "PARSE" in out, out[-800:]
    finally:
        if PLANT.exists():
            PLANT.unlink()


if __name__ == "__main__":
    test_nine_key_plus_on_finally_is_invalid()
    print("ok · nine-key fence + on_finally is visible and red")
