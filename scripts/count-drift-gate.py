#!/usr/bin/env python3
# count-drift-gate.py — the count-rot ratchet.
#
# Frontmatter descriptions cannot interpolate CANON, so any hand-typed
# count there WILL rot (empirical: "14 canonical providers" survived two
# provider promotions). Two checks:
#   (a) no .mdx frontmatter description: carries a number immediately
#       before "providers" / "builtins" / "extract modes"
#   (b) snippets/_canon.mdx exists and carries "builtins:" (the CANON
#       projection every count-quoting page imports)
# Exit 0 clean · 1 findings. Stdlib only.

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COUNT_RE = re.compile(r"\b\d+\s+(?:canonical\s+)?(?:providers|builtins|extract modes)", re.I)


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

    if findings:
        print("count-drift-gate · FAIL")
        for f in findings:
            print(f"  ✗ {f}")
        return 1
    print("count-drift-gate · OK (descriptions count-free · _canon.mdx present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
