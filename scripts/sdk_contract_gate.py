#!/usr/bin/env python3
"""Refuse retired pre-0.116 SDK contracts in active public documentation."""

from __future__ import annotations

import pathlib
import re
import sys
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACTIVE_ROOTS = ("sdk", "snippets", "reference", "integrations")
HISTORICAL_ALLOWLIST = (
    "sdk/history/",
    "reference/history/",
    "integrations/history/",
)


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]


RULES = (
    Rule("split local class", re.compile(r"\bLocalNika\b")),
    Rule("split local import", re.compile(r"@supernovae-st/nika-client/local")),
    Rule("buffered terminal shortcut", re.compile(r"\brunToEnd\b")),
    Rule("invented plan method", re.compile(r"\bdryRunPlan\b")),
    Rule("retired jobs namespace", re.compile(r"\bnika\.jobs\b")),
    Rule("retired workflows namespace", re.compile(r"\bnika\.workflows\b")),
    Rule("retired environment constructor", re.compile(r"\bNika\.fromEnv\b")),
    Rule("invented webhook verifier", re.compile(r"\bNika\.verifyWebhook\b")),
    Rule("invented collection helper", re.compile(r"\brunAndCollect\b")),
    Rule("retired outcome promise", re.compile(r"\b(?:handle|run)\.outcome\b")),
    Rule("invented version method", re.compile(r"\bnika\.version\s*\(")),
    Rule("invented health method", re.compile(r"\bnika\.health\s*\(")),
    Rule("invented golden method", re.compile(r"\bnika\.test\s*\(")),
    Rule("receipt-free verification", re.compile(r"\btraceVerify\s*\(\s*\)")),
    Rule("path verification", re.compile(r"\btraceVerify\s*\(\s*['\"]")),
    Rule(
        "retired error taxonomy",
        re.compile(
            r"\b(?:NikaAPIError|NikaConnectionError|NikaTimeoutError|"
            r"NikaJobError|NikaJobCancelledError)\b"
        ),
    ),
    Rule(
        "cancel described as missing",
        re.compile(r"(?i)(?:cancel.{0,80}(?:404|absent)|(?:404|absent).{0,80}cancel)"),
    ),
)


def active_documents(root: pathlib.Path = ROOT) -> list[pathlib.Path]:
    docs: list[pathlib.Path] = []
    for dirname in ACTIVE_ROOTS:
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("*.mdx"):
            rel = path.relative_to(root).as_posix()
            if rel.startswith(HISTORICAL_ALLOWLIST):
                continue
            docs.append(path)
    return sorted(docs)


def findings(root: pathlib.Path = ROOT) -> list[str]:
    failures: list[str] = []
    for path in active_documents(root):
        rel = path.relative_to(root).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for rule in RULES:
                if rule.pattern.search(line):
                    failures.append(f"{rel}:{line_number}: {rule.name}: {line.strip()}")
    return failures


def main() -> int:
    failures = findings()
    if failures:
        print("sdk-contract-gate: retired contract found", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"sdk-contract-gate: GREEN ({len(active_documents())} active MDX files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
