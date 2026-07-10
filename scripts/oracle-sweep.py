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
# The sibling spec checkout, through the repo-container law (D-2026-07-02-N1
# addendum): a repo dir may be FLAT (<repos>/spec) or a CONTAINER
# (<repos>/spec/repo) — and docs itself may sit at either depth. First
# candidate carrying the conformance runner wins; the 2026-07-10
# containerization broke the bare `DOCS.parent / "spec"` (every local
# sweep crashed 48/48 while CI, which lays out flat siblings, stayed green).
SPEC = next(
    (c for c in (
        DOCS.parent / "spec",                      # both flat
        DOCS.parent / "spec" / "repo",             # docs flat · spec container
        DOCS.parent.parent / "spec" / "repo",      # both containers
        DOCS.parent.parent / "spec",               # docs container · spec flat
    ) if (c / "conformance" / "runner.py").exists()),
    DOCS.parent / "spec",
)
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
