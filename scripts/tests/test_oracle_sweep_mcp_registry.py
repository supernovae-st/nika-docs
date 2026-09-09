#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A concrete MCP call is judged with the registry taught beside it.

The released checker fails closed when `mcp:<server>/<tool>` names a server
absent from `.nika/mcp_servers.json`. The docs oracle must therefore
materialize a named registry fence from the same page. This plant proves both
directions: the complete example is green, and removing the registry restores
NIKA-INVOKE-001 instead of creating a global exception for MCP calls.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
SWEEP = DOCS / "scripts" / "oracle-sweep.py"
PLANT = DOCS / "getting-started" / "_mutation-mcp-registry.mdx"

REGISTRY = """```json .nika/mcp_servers.json
{"mcp_servers_format": 1, "servers": {"probe": {"command": "probe-mcp"}}}
```

"""
WORKFLOW = """```yaml probe.nika.yaml
nika: mcp-registry-probe
permits:
  tools: ["mcp:probe/read"]
tasks:
  read:
    invoke:
      tool: "mcp:probe/read"
      args: {}
```
"""


def run_sweep() -> tuple[subprocess.CompletedProcess[str], str]:
    result = subprocess.run(
        [sys.executable, str(SWEEP)],
        cwd=DOCS,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    return result, result.stdout + result.stderr


def test_registry_fence_is_the_mcp_check_context() -> None:
    PLANT.write_text(REGISTRY + WORKFLOW)
    try:
        result, output = run_sweep()
        assert result.returncode == 0, output[-1200:]
        assert "_mutation-mcp-registry" not in output, output[-1200:]

        PLANT.write_text(WORKFLOW)
        result, output = run_sweep()
        assert result.returncode == 1, output[-1200:]
        assert "_mutation-mcp-registry" in output, output[-1200:]
        assert "NIKA-INVOKE-001" in output, output[-1200:]
    finally:
        if PLANT.exists():
            PLANT.unlink()


if __name__ == "__main__":
    test_registry_fence_is_the_mcp_check_context()
    print("ok · an MCP registry fence opens only its page's concrete server")
