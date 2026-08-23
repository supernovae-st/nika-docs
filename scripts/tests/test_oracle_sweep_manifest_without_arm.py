#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A project manifest is a manifest even when it carries no `arm:`.

The regression this pins: the first cut of `is_manifest_fence` tested for
an `arm:` key. That is a PROXY, and it held only because the one manifest
fence in the docs happens to arm something. A page documenting `traces:`
or `registry:` alone would have been routed to `nika check` — the nine-key
WORKFLOW envelope — and gone red on `ceiling`, blaming the page for a
defect that was the judge's.

The spec's discriminant is normative and covers 100% of documents
(01-envelope §The type discriminant): a `tasks:` key means WORKFLOW, its
absence means PROJECT. It was chosen because it survives when the filename
is gone — a registry blob, an HTTP body, `nika check -` on stdin, a fence
pasted into a chat.

The fence opens on the identity the released binary writes
(`nika init --project-file` → `nika: my-project`). `nika: v1` is the
retired schema tag; the sister plant in
`test_oracle_sweep_retired_v1_tag.py` is the refusal cliquet.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2]
SWEEP = DOCS / "scripts" / "oracle-sweep.py"
PLANT = DOCS / "getting-started" / "_mutation-manifest-no-arm.mdx"

# A project file with NO `arm:` — the exact shape the proxy misrouted.
#
# `ceiling:` and nothing else, deliberately. `traces:` would ALSO prove
# the routing, but the two parsers of `nika.yaml` disagree about it —
# `nika arm` refuses it `cadence.deferred-key · clé du round 2` while the
# spanned parser accepts it — and a routing test must not fail on someone
# else's divergence. That divergence is a finding of its own, not this
# test's subject.
NO_ARM_FENCE = """```yaml
nika: my-project
ceiling: 0.50
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


def test_a_manifest_without_arm_is_still_routed_to_the_project_judge() -> None:
    PLANT.write_text(NO_ARM_FENCE)
    try:
        result, output = run_sweep()
        # Routed, not blamed: it counts as a project shape and is not invalid.
        assert "project shapes" in output, output[-800:]
        assert result.returncode == 0, output[-800:]
        assert "_mutation-manifest-no-arm" not in output, output[-800:]
        # And specifically NOT judged by the workflow envelope.
        assert "NIKA-PARSE-005" not in output, output[-800:]
        assert "unknown field `ceiling`" not in output, output[-800:]
    finally:
        if PLANT.exists():
            PLANT.unlink()


if __name__ == "__main__":
    test_a_manifest_without_arm_is_still_routed_to_the_project_judge()
    print("ok · a manifest with no `arm:` still reaches the project judge")
