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
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

DOCS = pathlib.Path(__file__).resolve().parent.parent

# The judge is the released binary. NIKA_BIN wins so CI and a local
# pin can name the same file without shuffling PATH.
NIKA = os.environ.get("NIKA_BIN") or shutil.which("nika")
if not NIKA:
    print("oracle-sweep · no `nika` on PATH or NIKA_BIN — the judge IS the released binary", file=sys.stderr)
    sys.exit(2)

SKIP = re.compile(r"skeleton|illustration|modeline", re.I)
FENCE = re.compile(r"```yaml([^\n]*)\n(.*?)```", re.DOTALL)
# No deliberate reds today. release-radar carried one (the SEC-009
# witness · verdict-coverage 2026-07-28 §DECIDED) until 2026-07-31, when
# the registry proof pass superseded it: the same file ships as an
# installable entry whose cert says conformance=pass, its two trifecta
# twins already carry the canonical NEP-0020 gate, and the refusal
# witness lives where witnesses belong — the spec's conformance fixture
# pair (trifecta-realized-flow-ungated / -human-gate-dominates). The
# inverted-assertion MECHANISM stays: register any future witness here
# as {"file.nika.yaml": "NIKA-CODE"} and a green means the lane broke.
DELIBERATE_RED: dict[str, str] = {}
CODE = re.compile(r"NIKA-[A-Z]+-\d+")
# A fence may name its file (```yaml child.nika.yaml). Named fences are
# materialized as SIBLINGS before judging, so a composition parent can
# resolve `invoke: workflow: ./child.nika.yaml` — the multi-file examples
# get judged like every other block instead of being exempted.
NAMED = re.compile(r"^\s*([A-Za-z0-9._-]+\.nika\.yaml)\s*$")
# The type discriminant is the FIRST content line matching `^\s*nika:\s`
# (spec 01). Leading indent is allowed: a fence inside an <Accordion>
# keeps its indent in the captured body, and a column-4 `nika: hello`
# is still a document. A nested `nika:` (goose extension, GitHub
# Actions job) is never the first content line, so it stays out. The
# old detector was `"nika: v1" in b` and made a nine-key fence
# (`nika: <name>`) invisible to this gate.
ENVELOPE = re.compile(r"^\s*nika:\s")


def is_workflow_fence(body: str) -> bool:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return bool(ENVELOPE.match(line))
    return False


bad = 0
total = 0
for fp in sorted(DOCS.rglob("*.mdx")):
    if "node_modules" in str(fp):
        continue
    fences = FENCE.findall(fp.read_text())
    runnable = [(i, b) for i, b in fences
                if is_workflow_fence(b) and not SKIP.search(i)]
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
        r = subprocess.run([NIKA, "check", str(path)], capture_output=True, text=True)
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

print(f"oracle-sweep: {total} workflow blocks · {bad} invalid (judge: {NIKA})")
sys.exit(1 if bad else 0)
