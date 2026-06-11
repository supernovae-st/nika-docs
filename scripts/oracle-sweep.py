#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# oracle-sweep · every full ```yaml workflow block in the docs MUST validate
# against the spec oracle. Skips fences whose info-string marks them as
# non-runnable (skeleton · illustration · modeline). Round-8 ratchet: the
# introduction page shipped an invalid workflow (missing edges · ghost
# exec.args) for weeks — entry-surface YAML now has the same gate as the
# showcase corpus. Exit 1 on any invalid block.
import json
import pathlib
import re
import subprocess
import sys
import tempfile

DOCS = pathlib.Path(__file__).resolve().parent.parent
SPEC = DOCS.parent / "spec"
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
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(body)
            path = f.name
        r = subprocess.run(
            [sys.executable, str(SPEC / "conformance" / "runner.py"), "validate", path],
            capture_output=True, text=True)
        try:
            v = json.loads(r.stdout)
        except json.JSONDecodeError:
            print(f"✗ {fp.relative_to(DOCS)} · runner crash")
            bad += 1
            continue
        if not v["valid"]:
            bad += 1
            print(f"✗ {fp.relative_to(DOCS)}")
            for e in v["errors"][:3]:
                print(f"   · {e.get('detail', '')[:110]}")

print(f"oracle-sweep: {total} workflow blocks · {bad} invalid")
sys.exit(1 if bad else 0)
