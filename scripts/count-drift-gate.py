#!/usr/bin/env python3
# count-drift-gate.py — the count-rot ratchet.
#
# Frontmatter descriptions cannot interpolate CANON, so any hand-typed
# count there WILL rot (empirical: "14 canonical providers" survived two
# provider promotions). Six checks:
#   (a) no .mdx frontmatter description: carries a number before a VOLATILE
#       noun — one that a projection tracks, or one known to move with no
#       projection to point at. Digits AND number-words ("eight providers"
#       rots exactly like "8 providers").
#   (b) snippets/_canon.mdx exists and carries "builtins:" (the CANON
#       projection every count-quoting page imports)
#   (c) every hand-typed MCP tool count ("8 tools" / "eight nika_*") in
#       page bodies equals what `nika mcp` actually serves — the 2026-07-09
#       deslop pass found the count written 5x with no wire assertion
#   (d) page BODIES: a hand-typed count for a phrase a snippet already
#       projects must equal the projection. The 2026-07-27 pass found
#       guides/patterns.mdx interpolating {SHOWCASE.count} on line 15 and
#       hard-typing "20 real jobs" on line 337 — the projection was RIGHT
#       THERE and the gate could not see the body. Frozen history
#       (<Update> blocks) and fenced code are skipped: dated entries and
#       CLI transcripts are evidence, not claims.
#   (e) the CANON.verbs tripwire. Check (a) deliberately lets "four verbs"
#       stand in descriptions — the 4 verbs are a locked language contract
#       (a verb = a distinct native execution model), not a moving count.
#       That exemption is only safe while it stays true, so the gate
#       asserts it instead of trusting it.
#   (f) every {STATUS.x} / {CANON.x} / {SHOWCASE.x} a page interpolates
#       must EXIST in its snippet. Dropping a key renders the literal
#       string "undefined" on a public page, and nothing else notices.
# Exit 0 clean · 1 findings. Stdlib only (check c skips if nika absent).

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
         "twelve": 12}
NUM = r"(?:\d+|" + "|".join(WORDS) + r")"

# Nouns that MOVE. Either a projection tracks them (so a description should
# not restate them) or they are known-volatile with no projection to point
# at (so a description cannot state them safely at all).
#
# Deliberately ABSENT — structural constants, not counts. They belong in
# prose and have nowhere to interpolate from:
#   layers (six + the L0.5 half) · gates (12 per admission) · patterns
#   (the FCI set) · verbs (see check (e), which asserts rather than trusts)
# The 0.109 flag-day moved four more nouns in one release (fourteen envelope
# keys became nine · four value authorities became three · six binding
# namespaces became five · eighteen task modifiers became eleven): a
# description that spells any of them is the next « 14 canonical
# providers ». They are language facts, not projections — a page body may
# state them next to the fence that proves them, a description may not.
VOLATILE_NOUNS = (
    r"(?:canonical\s+)?providers?|builtins?|extract modes?|templates?|"
    r"error codes?|error namespaces?|capability rules?|hygiene vectors?|"
    r"ADRs?|decision records?|crates?|showcase workflows?|"
    r"MCP servers?|MCP server entries|satellites?|"
    r"(?:value\s+)?authorit(?:y|ies)|(?:task\s+)?modifiers?|"
    r"(?:binding\s+|value\s+)?namespaces?|(?:envelope\s+|top-level\s+)?keys?"
)
COUNT_RE = re.compile(rf"\b{NUM}[- ]+(?:{VOLATILE_NOUNS})\b", re.I)

# Check (d): body phrases specific enough to have exactly one meaning.
# Each maps to the snippet key that owns the number. Deliberately narrow —
# a bare "N providers" is ambiguous (17 canonical language providers vs 38
# catalog TOML records vs 23 sharing the openai-chat dialect vs the 15 the
# embedded pack ships), and a gate that guesses between them is worse than
# no gate. These phrases do not collide.
BODY_CLAIMS = [
    (r"real jobs", "SHOWCASE.count"),
    (r"showcase workflows?", "SHOWCASE.count"),
    (r"full tiered workflows?", "SHOWCASE.count"),
    (r"composition patterns?", "PATTERNS.count"),
    (r"registered (?:v[\d.]+ )?codes?", "CANON.errorCodes"),
    (r"hygiene vectors?", "STATUS.hygieneVectors"),
    (r"capability rules?", "STATUS.capabilityRules"),
    (r"crates admitted", "STATUS.cratesAdmitted"),
    (r"admitted crates", "STATUS.cratesAdmitted"),
]
FENCE_RE = re.compile(r"^\s*```")
UPDATE_OPEN_RE = re.compile(r"<Update\b")
UPDATE_CLOSE_RE = re.compile(r"</Update>")
# A table row whose FIRST cell carries a year is a timeline entry — "23 crates
# admitted in twelve days" was true in June 2026 and must stay that way.
DATED_ROW_RE = re.compile(r"^\s*\|[^|]*\b(?:19|20)\d\d\b")
KEY_REF_RE = re.compile(r"\{?\b(STATUS|CANON|SHOWCASE)\.([A-Za-z][A-Za-z0-9]*)")
SNIPPETS = {"STATUS": "snippets/_status-snapshot.mdx",
            "CANON": "snippets/_canon.mdx",
            "SHOWCASE": "snippets/_showcase.mdx"}
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


def snippet_values() -> dict[str, int]:
    """Every scalar the three snippets project, as NAMESPACE.key -> int.

    Plus PATTERNS.count, derived by counting the numbered headings in
    guides/patterns.mdx — the page IS the registry of composition patterns,
    so the count that page's siblings quote has a real source.
    """
    values: dict[str, int] = {}
    for ns, rel in SNIPPETS.items():
        path = ROOT / rel
        if not path.is_file():
            continue
        for m in re.finditer(r"^\s*([A-Za-z][A-Za-z0-9]*)\s*:\s*\"?(\d+)\"?\s*,",
                             path.read_text(encoding="utf-8"), re.M):
            values[f"{ns}.{m.group(1)}"] = int(m.group(2))

    patterns_page = ROOT / "guides" / "patterns.mdx"
    if patterns_page.is_file():
        n = len(re.findall(r"^## \d+ ",
                           patterns_page.read_text(encoding="utf-8"), re.M))
        if n:
            values["PATTERNS.count"] = n
    return values


def snippet_keys(ns: str) -> set[str]:
    """Keys a snippet actually defines — any key, not just numeric ones."""
    path = ROOT / SNIPPETS[ns]
    if not path.is_file():
        return set()
    return set(re.findall(r"^\s*([A-Za-z][A-Za-z0-9]*)\s*:",
                          path.read_text(encoding="utf-8"), re.M))


def claim_lines(text: str):
    """Yield (lineno, line) for prose that ASSERTS something.

    Skips fenced code (CLI transcripts quote real output — evidence, not a
    claim), <Update> blocks, and dated timeline rows (both are frozen
    history per AGENTS.md rule 1: their numbers were true when written).
    """
    in_fence = in_update = False
    for i, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or DATED_ROW_RE.match(line):
            continue
        if UPDATE_OPEN_RE.search(line):
            in_update = True
        if in_update:
            if UPDATE_CLOSE_RE.search(line):
                in_update = False
            continue
        yield i, line


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

    values = snippet_values()

    # (e) the tripwire that keeps check (a)'s `verbs` exemption honest.
    verbs = values.get("CANON.verbs")
    if verbs is None:
        findings.append("snippets/_canon.mdx: no numeric `verbs:` — check (a)'s "
                        "verb exemption can no longer be verified")
    elif verbs != 4:
        findings.append(
            f"CANON.verbs is {verbs}, not 4 — the locked 4-verb contract moved. "
            "Every description that spells the verb count in words is now stale: "
            "grep -riE '(four|[0-9]+) verbs' --include=*.mdx . and fix them, then "
            "update this gate's exemption.")

    # (d) body claims a projection already owns.
    body_pats = [(re.compile(rf"\b({NUM})[- ]+({phrase})\b", re.I), key)
                 for phrase, key in BODY_CLAIMS]
    for page in sorted(ROOT.rglob("*.mdx")):
        rel = page.relative_to(ROOT)
        if rel.parts[0] == "snippets":
            continue
        for lineno, line in claim_lines(page.read_text(encoding="utf-8")):
            for pat, key in body_pats:
                for m in pat.finditer(line):
                    expected = values.get(key)
                    if expected is None:
                        continue
                    token = m.group(1).lower()
                    n = WORDS.get(token, None)
                    if n is None:
                        n = int(token)
                    if n != expected:
                        findings.append(
                            f"{rel}:{lineno}: hand-typed {m.group(0)!r} but "
                            f"{key} projects {expected} — interpolate "
                            f"{{{key}}} instead of re-typing it")

    # (f) interpolated keys that do not exist render as "undefined".
    defined = {ns: snippet_keys(ns) for ns in SNIPPETS}
    for page in sorted(ROOT.rglob("*.mdx")):
        rel = page.relative_to(ROOT)
        if rel.parts[0] == "snippets":
            continue
        text = page.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            for ns, key in KEY_REF_RE.findall(line):
                if defined[ns] and key not in defined[ns]:
                    findings.append(
                        f"{rel}:{lineno}: references {ns}.{key}, which "
                        f"{SNIPPETS[ns]} does not define — this renders the "
                        f"literal text 'undefined' on a public page")

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
