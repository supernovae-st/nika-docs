#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The docs gate must reject the retired `nika new --from` form."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
GATE = DOCS / "scripts" / "teach-parity.py"
PLANT = DOCS / "getting-started" / "_mutation-retired-new.mdx"


def test_retired_new_form_is_visible_and_red() -> None:
    PLANT.write_text("Run `nika new --from chain` to begin.\n", encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(GATE)],
            cwd=DOCS,
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 1, output[-800:]
        assert "retired `nika new --from`" in output, output[-800:]
        assert "_mutation-retired-new.mdx:1" in output, output[-800:]
    finally:
        if PLANT.exists():
            PLANT.unlink()


if __name__ == "__main__":
    test_retired_new_form_is_visible_and_red()
    print("ok · retired nika new --from is visible and red")
