#!/usr/bin/env python3
# count-drift-gate.py — the count-rot ratchet.
#
# Frontmatter descriptions cannot interpolate CANON, so any hand-typed
# count there WILL rot (empirical: "14 canonical providers" survived two
# provider promotions). Three checks:
#   (a) no .mdx frontmatter description: carries a number immediately
#       before "providers" / "builtins" / "extract modes"
#   (b) snippets/_canon.mdx exists and carries "builtins:" (the CANON
#       projection every count-quoting page imports)
#   (c) every hand-typed MCP tool count ("8 tools" / "eight nika_*") in
#       page bodies equals what `nika mcp` actually serves — the 2026-07-09
#       deslop pass found the count written 5x with no wire assertion
# Exit 0 clean · 1 findings. Stdlib only (check c skips if nika absent).

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COUNT_RE = re.compile(r"\b\d+\s+(?:canonical\s+)?(?:providers|builtins|extract modes)", re.I)
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
         "twelve": 12}
TOOLCOUNT_RE = re.compile(
    r"\b(\d+|" + "|".join(WORDS) + r")\s+(?:read-only\s+)?"
    r"(?:`nika_\*`\s+)?tools\b|"
    r"\b(\d+|" + "|".join(WORDS) + r")\s+`nika_\*`\s+names\b", re.I)


def served_tool_count() -> int | None:
    nika = shutil.which("nika")
    if not nika:
        return None
    handshake = "\n".join(json.dumps(m) for m in [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "gate", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]) + "\n"
    out = subprocess.run([nika, "mcp"], input=handshake, text=True,
                         capture_output=True, timeout=30)
    for line in out.stdout.splitlines():
        try:
            msg = json.loads(line.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if msg.get("id") == 2 and "result" in msg:
            return len(msg["result"].get("tools", []))
    return None


def frontmatter_description(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    for line in text[:end].splitlines():
        if line.startswith("description:"):
            return line[len("description:"):].strip()
    return None


def main() -> int:
    findings = []
    for page in sorted(ROOT.rglob("*.mdx")):
        desc = frontmatter_description(page.read_text(encoding="utf-8"))
        if desc and (m := COUNT_RE.search(desc)):
            rel = page.relative_to(ROOT)
            findings.append(f"{rel}: frontmatter description hand-types a count ({m.group(0)!r})")

    canon = ROOT / "snippets" / "_canon.mdx"
    if not canon.is_file():
        findings.append("snippets/_canon.mdx: missing — regenerate from nika-spec canon-projectors.py")
    elif "builtins:" not in canon.read_text(encoding="utf-8"):
        findings.append("snippets/_canon.mdx: no `builtins:` key — stale or truncated projection")

    served = served_tool_count()
    if served is None:
        print("  (tool-count check skipped — nika not on PATH)")
    else:
        # only lines that are ABOUT the oracle — "3 tools" in a workflow
        # example is a different noun entirely
        mcp_context = re.compile(r"nika_|mcp|oracle", re.I)
        for page in sorted(ROOT.rglob("*.mdx")):
            rel = page.relative_to(ROOT)
            for line in page.read_text(encoding="utf-8").splitlines():
                if not mcp_context.search(line):
                    continue
                for m in TOOLCOUNT_RE.finditer(line):
                    token = (m.group(1) or m.group(2)).lower()
                    n = WORDS.get(token) or int(token)
                    if n != served:
                        findings.append(
                            f"{rel}: says {m.group(0)!r} but `nika mcp` "
                            f"serves {served} — update the prose")

    if findings:
        print("count-drift-gate · FAIL")
        for f in findings:
            print(f"  ✗ {f}")
        return 1
    print("count-drift-gate · OK (descriptions count-free · _canon.mdx present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
