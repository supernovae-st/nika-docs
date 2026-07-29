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
# The one deliberate red — the SEC-009 witness (NEP-0002): the spec keeps
# examples/release-radar.nika.yaml red on purpose (engine repo ·
# docs/plans/2026-07-28-verdict-coverage.md §DECIDED · SEC-009 — a prompt
# added just to turn it green would be ceremony on a file people copy), and
# the docs mirror that block verbatim. Inverted assertion, never a skip:
# the fence MUST fail with exactly this code — a green means the lane broke,
# any other code means a new defect is hiding behind the expected one.
DELIBERATE_RED = {"release-radar.nika.yaml": "NIKA-SEC-009"}
CODE = re.compile(r"NIKA-[A-Z]+-\d+")
# A fence may name its file (```yaml child.nika.yaml). Named fences are
# materialized as SIBLINGS before judging, so a composition parent can
# resolve `invoke: workflow: ./child.nika.yaml` — the multi-file examples
# get judged like every other block instead of being exempted.
NAMED = re.compile(r"^\s*([A-Za-z0-9._-]+\.nika\.yaml)\s*$")

bad = 0
total = 0
for fp in sorted(DOCS.rglob("*.mdx")):
    if "node_modules" in str(fp):
        continue
    fences = FENCE.findall(fp.read_text())
    runnable = [(i, b) for i, b in fences if "nika: v1" in b and not SKIP.search(i)]
    if not runnable:
        continue
    page_dir = tempfile.mkdtemp(prefix="oracle-")
    # every named block on the page is a sibling the others may reference
    for info, body in runnable:
        m = NAMED.match(info)
        if m:
            (pathlib.Path(page_dir) / m.group(1)).write_text(body)
    for info, body in runnable:
        total += 1
        m = NAMED.match(info)
        # re-assert THIS fence's bytes (pages reuse one filename across
        # progressive versions — each version is judged as itself)
        name = m.group(1) if m else f"block-{total}.nika.yaml"
        path = pathlib.Path(page_dir) / name
        path.write_text(body)
        r = subprocess.run(["nika", "check", str(path)], capture_output=True, text=True)
        expected = DELIBERATE_RED.get(name)
        if expected:
            emitted = {c for l in (r.stdout + r.stderr).splitlines() if "✖" in l
                       for c in CODE.findall(l)}
            if r.returncode == 0 or emitted != {expected}:
                bad += 1
                print(f"✗ {fp.relative_to(DOCS)}  [{name}] · deliberate red broke")
                print(f"   · expected exactly {expected} · got rc={r.returncode} "
                      f"{sorted(emitted) or 'no codes'}")
            continue
        if r.returncode != 0:
            bad += 1
            print(f"✗ {fp.relative_to(DOCS)}  [{name}]")
            for e in [l for l in (r.stdout + r.stderr).splitlines() if "✖" in l or "✗" in l][:3]:
                print(f"   · {e.strip()[:110]}")

print(f"oracle-sweep: {total} workflow blocks · {bad} invalid (judge: released `nika check`)")
sys.exit(1 if bad else 0)
