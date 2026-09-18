#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Live old-suffix ratchet for issue #1684 (nika-docs).

Canonical executable Nika program source is lowercase ``*.nika``.
Projected showcase/template/error spans, changelog history, and spec
snapshots may still name the retired suffix until their owners re-project.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORBIDDEN = re.compile(r"\.nika\.ya?ml")
REGION_BEGIN = re.compile(r"\{/\*\s*([a-z0-9-]+):(?:dag-)?begin\b")
REGION_END = re.compile(r"\{/\*\s*([a-z0-9-]+):(?:dag-)?end\b")

EXCEPTIONS: list[dict] = [
    {
        "path": "scripts/suffix_ratchet.py",
        "match": r"\.nika\.ya?ml",
        "category": "negative-test",
        "reason": "the ratchet's own forbidden-pattern data",
        "owner": "nika-docs",
    },
    {
        "path": "scripts/tests/test_suffix_ratchet.py",
        "match": r"\.nika\.ya?ml",
        "category": "negative-test",
        "reason": "mutation fixture that must keep the retired spelling to prove detection",
        "owner": "nika-docs",
    },
    {
        "path": "scripts/verify-knowledge-source.py",
        "match": r"\*\.nika\.yaml",
        "category": "frozen-evidence",
        "reason": "still reads current spec template paths until nika-spec re-projects",
        "owner": "nika-docs / nika-spec",
    },
    {
        "path": "reference/arm.mdx",
        "match": r"\.nika\.ya?ml",
        "category": "frozen-evidence",
        "reason": "released engine project.arm.workflow still requires *.nika.yaml; moves with engine #1684",
        "owner": "nika engine cadence",
    },
    {
        "path": "sdk/operations/os-schedulers.mdx",
        "match": r"\.nika\.ya?ml",
        "category": "frozen-evidence",
        "reason": "released engine project.arm.workflow still requires *.nika.yaml; moves with engine #1684",
        "owner": "nika engine cadence",
    },
    {
        "path": "sdk/project/arm-registry.mdx",
        "match": r"\.nika\.ya?ml",
        "category": "frozen-evidence",
        "reason": "released engine project.arm.workflow still requires *.nika.yaml; moves with engine #1684",
        "owner": "nika engine cadence",
    },
    {
        "path": "sdk/project/nika-yaml.mdx",
        "match": r"\.nika\.ya?ml",
        "category": "frozen-evidence",
        "reason": "released engine project.arm.workflow still requires *.nika.yaml; moves with engine #1684",
        "owner": "nika engine cadence",
    },
    {
        "path": "scripts/tests/test_oracle_sweep_manifest.py",
        "match": r"\.nika\.ya?ml",
        "category": "frozen-evidence",
        "reason": "oracle-sweep plant matches the released project.arm.workflow suffix",
        "owner": "nika-docs / nika engine cadence",
    },
    {
        "path": "changelog/releases.mdx",
        "match": r"\.nika\.ya?ml",
        "category": "historical",
        "reason": "dated release notes describing the real old program suffix",
        "owner": "nika-docs changelog",
    },
    {
        "path_prefix": "snippets/data/",
        "match": r"\.nika\.ya?ml",
        "category": "frozen-evidence",
        "reason": "spec language/tool snapshots; re-project after nika-spec file-identity",
        "owner": "nika-spec projectors",
    },
    {
        "path_prefix": "reference/language/words/",
        "match": r"\.nika\.ya?ml",
        "category": "frozen-evidence",
        "reason": "knowledge-mirror of spec templates; re-project after nika-spec file-identity",
        "owner": "scripts/knowledge-mirror.py",
    },
    {
        "path": "api-reference/openapi.json",
        "match": r"\.nika\.ya?ml",
        "category": "frozen-evidence",
        "reason": "engine OpenAPI projection; regenerate after engine Serve cut",
        "owner": "nika engine OpenAPI",
    },
]


def tracked_files() -> list[pathlib.Path]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [ROOT / p.decode() for p in out.stdout.split(b"\0") if p]


def authored_lines(text: str) -> list[tuple[int, str]]:
    """Line numbers/text outside projected showcase/template/error spans."""
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    depth: list[str] = []
    for n, line in enumerate(lines, 1):
        begin = REGION_BEGIN.search(line)
        end = REGION_END.search(line)
        if begin and not depth:
            depth.append(begin.group(1))
            continue
        if depth:
            if end and end.group(1) == depth[-1]:
                depth.pop()
            elif begin:
                depth.append(begin.group(1))
            continue
        out.append((n, line))
    return out


def exception_for(rel: str, line: str) -> dict | None:
    for exc in EXCEPTIONS:
        if "path_prefix" in exc:
            if not rel.startswith(exc["path_prefix"]):
                continue
        elif exc.get("path") != rel:
            continue
        if re.search(exc["match"], line):
            return exc
    return None


def scan() -> list[str]:
    findings: list[str] = []
    used: set[tuple[str, str]] = set()
    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if FORBIDDEN.search(rel):
            exc = exception_for(rel, rel)
            if exc is None:
                findings.append(f"PATH {rel}: retired suffix in a tracked pathname")
            else:
                used.add((exc.get("path") or exc.get("path_prefix"), exc["match"]))
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError, OSError):
            continue
        for n, line in authored_lines(text):
            if not FORBIDDEN.search(line):
                continue
            exc = exception_for(rel, line)
            if exc is None:
                findings.append(f"{rel}:{n}: {line.strip()[:200]}")
            else:
                used.add((exc.get("path") or exc.get("path_prefix"), exc["match"]))
    declared = {(e.get("path") or e.get("path_prefix"), e["match"]) for e in EXCEPTIONS}
    for path, match in sorted(declared - used):
        findings.append(f"STALE EXCEPTION {path} match={match!r} — no remaining hit")
    return findings


def main() -> int:
    planted = "this-line-must-match .nika.yaml as a scanner self-check"
    if not FORBIDDEN.search(planted):
        print("suffix-ratchet: scanner no longer matches the retired spelling", file=sys.stderr)
        return 1
    findings = scan()
    if findings:
        print("suffix-ratchet: retired .nika.yaml / .nika.yml still live:", file=sys.stderr)
        for item in findings:
            print(f"  {item}", file=sys.stderr)
        return 1
    print("suffix-ratchet: ok — no live .nika.yaml / .nika.yml outside allowlisted exceptions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
