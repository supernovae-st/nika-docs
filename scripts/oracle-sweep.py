#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# oracle-sweep · every full ```yaml workflow block in the docs MUST run on
# the RELEASED binary (`nika check`) — docs are a baked visitor surface,
# and what a reader copies runs on THEIR installed nika (the copy-paste
# invariant). The ratified-grammar judging of the pack lives spec-side in
# the spec repo CI; judging a SERVED surface with the spec oracle is the
# wrong judge (empirical 2026-07-20: 56 fences green vs spec-HEAD, 56
# broken on every installed binary). Skips fences whose info-string marks
# them non-runnable (skeleton · illustration · modeline). At the release
# train nothing changes here — the released binary IS the moving truth.
# Exit 1 on any invalid block · exit 2 when no binary is on PATH.
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

DOCS = pathlib.Path(__file__).resolve().parent.parent

if shutil.which("nika") is None:
    print("oracle-sweep · no `nika` on PATH — the judge IS the released binary", file=sys.stderr)
    sys.exit(2)

SKIP = re.compile(r"skeleton|illustration|modeline", re.I)
FENCE = re.compile(r"```yaml([^\n]*)\n(.*?)```", re.DOTALL)

bad = 0
total = 0
for fp in sorted(DOCS.rglob("*.mdx")):
    if "node_modules" in str(fp):
        continue
    for info, body in FENCE.findall(fp.read_text()):
        if "nika: v1" not in body or SKIP.search(info):
            continue
        total += 1
        with tempfile.NamedTemporaryFile("w", suffix=".nika.yaml", delete=False) as f:
            f.write(body)
            path = f.name
        r = subprocess.run(["nika", "check", path], capture_output=True, text=True)
        if r.returncode != 0:
            bad += 1
            print(f"✗ {fp.relative_to(DOCS)}")
            for e in [l for l in (r.stdout + r.stderr).splitlines() if "✖" in l or "✗" in l][:3]:
                print(f"   · {e.strip()[:110]}")

print(f"oracle-sweep: {total} workflow blocks · {bad} invalid (judge: released `nika check`)")
sys.exit(1 if bad else 0)
