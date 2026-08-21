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
# Fragments never reach `nika check` (no envelope), so a scalar
# `for_each: ${{ … }}` used to ship as live teaching while PARSE-019
# (and sibling knobs, PARSE-005) refuse it on the binary. Catch the
# dead form in EVERY yaml fence — skeleton/illustration/modeline
# included, because those pages are where a reader copies the shape.
BARE_FOREACH = re.compile(
    r"(?m)^[ \t]*for_each:[ \t]+(\$\{\{|\$[A-Za-z_]|[\[\'\"])"
)


def is_workflow_fence(body: str) -> bool:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return bool(ENVELOPE.match(line))
    return False


# A project manifest (`nika.yaml`) opens with the SAME `nika:` line as a
# workflow but is a different artifact. Every manifest first crosses a tiny
# offline dry run, which makes the released project parser judge all five
# shape keys. A manifest with a top-level `arm:` then also crosses `nika arm`,
# which owns cadence values and deliberately exposes any reader-convergence
# limit in the released binary.
#
# The discriminant is the SPEC's, normative and 100%-covering (01-envelope
# §The type discriminant) · a `tasks:` key means WORKFLOW, its absence
# means PROJECT. The first cut of this function tested for `arm:` instead,
# which is a PROXY: it happened to hold because the only manifest fence in
# the docs carries `arm:`, and it would have gone red the day a page
# documented `traces:` or `registry:` alone. The spec chose `tasks:`
# precisely because it survives when the filename is gone — a registry
# blob, an HTTP body, `nika check -` on stdin, a fence pasted in a chat.
# Anchored to the envelope's own indent, so a nested `tasks:` (a fence
# inside an <Accordion>, a `tasks:` under some other key) never qualifies.
def is_manifest_fence(body: str) -> bool:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not ENVELOPE.match(line):
            return False
        indent = line[: len(line) - len(line.lstrip())]
        return not re.search(r"(?m)^" + re.escape(indent) + r"tasks:", body)
    return False


def has_top_level_key(body: str, key: str) -> bool:
    """Does the project envelope carry `key:` at its own indentation?"""
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not ENVELOPE.match(line):
            return False
        indent = line[: len(line) - len(line.lstrip())]
        return bool(re.search(r"(?m)^" + re.escape(indent + key) + r":", body))
    return False


bad = 0
total = 0
manifests_total = 0
cadence_manifests_total = 0
for fp in sorted(DOCS.rglob("*.mdx")):
    if "node_modules" in str(fp):
        continue
    fences = FENCE.findall(fp.read_text())
    for info, body in fences:
        if BARE_FOREACH.search(body):
            bad += 1
            print(f"✗ {fp.relative_to(DOCS)}  [for_each scalar]")
            print("   · for_each: is a BLOCK (`items` · max_parallel · fail_fast) "
                  "· a bare ${{ }} is NIKA-PARSE-019 · knobs as siblings are NIKA-PARSE-005")
    enveloped = [(i, b) for i, b in fences
                 if is_workflow_fence(b) and not SKIP.search(i)]
    manifests = [(i, b) for i, b in enveloped if is_manifest_fence(b)]
    runnable = [(i, b) for i, b in enveloped if not is_manifest_fence(b)]
    for info, body in manifests:
        manifests_total += 1
        mdir = tempfile.mkdtemp(prefix="oracle-manifest-")
        (pathlib.Path(mdir) / "nika.yaml").write_text(body)
        (pathlib.Path(mdir) / "oracle.nika.yaml").write_text(
            "nika: docs-project-oracle\n"
            "model: mock/echo\n"
            "tasks:\n"
            "  probe:\n"
            "    infer: { prompt: project oracle, max_tokens: 1 }\n"
        )
        r = subprocess.run(
            [NIKA, "run", "oracle.nika.yaml", "--dry-run", "--plain"],
            cwd=mdir,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            bad += 1
            print(f"✗ {fp.relative_to(DOCS)}  [project shape]")
            for e in [l for l in (r.stdout + r.stderr).splitlines() if "✗" in l][:3]:
                print(f"   · {e.strip()[:110]}")
            continue
        if has_top_level_key(body, "arm"):
            cadence_manifests_total += 1
            r = subprocess.run([NIKA, "arm"], cwd=mdir, capture_output=True, text=True)
            if r.returncode != 0:
                bad += 1
                print(f"✗ {fp.relative_to(DOCS)}  [project cadence]")
                for e in [l for l in (r.stdout + r.stderr).splitlines() if "✗" in l][:3]:
                    print(f"   · {e.strip()[:110]}")
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

print(f"oracle-sweep: {total} workflow blocks · {manifests_total} project shapes "
      f"· {cadence_manifests_total} cadence manifests · {bad} invalid (judge: {NIKA})")
sys.exit(1 if bad else 0)
