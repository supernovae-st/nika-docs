#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Execute only the explicit offline first-workflow examples and judge their results.

The larger oracle sweep checks syntax. This runner checks the documented outputs,
real execution events and trace integrity. It never executes arbitrary shell fences
or the later provider-installation instructions. Evidence is retained in --output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "getting-started/first-workflow.mdx"
EXPECTED = [
    {"greeting": "mock(echo) · Hello, butterfly."},
    {
        "greeting": "mock(echo) · Hello, butterfly.",
        "repeated": "mock(echo) · Received: mock(echo) · Hello, butterfly.",
    },
    {"result": {"label": "butterfly"}},
]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    page = PAGE.read_text()
    fences = re.findall(r"```yaml ([^\n]+)\n(.*?)\n```", page, re.S)
    if len(fences) != len(EXPECTED):
        raise SystemExit("The first-workflow examples changed; review the business oracles.")
    (output / "first-workflow.mdx").write_text(page)
    (output / "runner.py").write_bytes(Path(__file__).read_bytes())
    rows = []
    for number, ((filename, source), expected) in enumerate(zip(fences, EXPECTED), 1):
        # Exact allowlist: the runner's authority cannot expand with a docs edit.
        if filename not in {"hello.nika", "structured.nika"}:
            raise SystemExit(f"Unreviewed filename: {filename}")
        if "model: mock/echo" not in source or len(re.findall(r"\bmodel:", source)) != 1:
            raise SystemExit("Only the reviewed mock route is authorized by this runner.")
        case = output / str(number)
        case.mkdir()
        home = case / "home"
        home.mkdir()
        (case / filename).write_text(source + "\n")
        env = {
            "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
            "HOME": str(home), "NIKA_KEYCHAIN": "off", "NIKA_TUI": "0",
            "NO_COLOR": "1", "NIKA_RUN_KEY_FILE": str(home / "absent.key"),
            "NIKA_RUN_PUB_FILE": str(home / "absent.pub"),
        }
        commands = []

        def call(label: str, arguments: list[str]) -> subprocess.CompletedProcess:
            result = subprocess.run(
                [str(binary), *arguments], cwd=case, env=env,
                stdin=subprocess.DEVNULL, capture_output=True, timeout=45,
            )
            (case / f"{label}.stdout").write_bytes(result.stdout)
            (case / f"{label}.stderr").write_bytes(result.stderr)
            commands.append({"label": label, "argv": arguments, "exit": result.returncode})
            return result

        call("check", ["check", filename])
        audit = call("authority", ["check", filename, "--json"])
        report = json.loads(audit.stdout)
        requirements = report.get("requirements", {})
        models = requirements.get("models", [])
        effects = report.get("certificate", {}).get("effect_calls")
        if (
            audit.returncode != 0 or not models
            or any(row.get("model") != "mock/echo" for row in models)
            or requirements.get("secrets") != []
            or effects != {"constant": 0, "terms": []}
        ):
            raise SystemExit("The reviewed offline, effect-free authority no longer holds.")
        run = call("run", ["run", filename, "--json"])
        events = [json.loads(line) for line in run.stdout.splitlines() if line.strip()]
        settled = [row for row in events if row.get("kind") == "run_settled"]
        trace_files = list((case / ".nika/traces").glob("*.ndjson"))
        before = {str(path.relative_to(case)): digest(path) for path in trace_files}
        verify = call("verify", ["trace", "verify"])
        after = {str(path.relative_to(case)): digest(path) for path in trace_files}
        if number == 1:
            call("explain", ["explain", filename])
            call("inspect", ["inspect", filename, "--format", "mermaid"])
        actual = settled[0].get("outputs") if len(settled) == 1 else None
        passed = (
            all(command["exit"] == 0 for command in commands)
            and len(settled) == 1 and settled[0].get("status") == "succeeded"
            and actual == expected and len(trace_files) == 1 and before == after
            and settled[0].get("evidence") == "unsealed"
        )
        rows.append({
            "case": number, "filename": filename, "expected": expected,
            "actual": actual, "commands": commands,
            "trace_sha256": after, "verification_preserved_evidence": before == after,
            "passed": passed,
        })
    receipt = {
        "binary": str(binary), "binary_sha256": digest(binary),
        "page_sha256": digest(PAGE), "runner_sha256": digest(Path(__file__)),
        "cases": rows, "passed": sum(row["passed"] for row in rows),
        "total": len(rows),
        "scope": "Public offline examples only; no provider, authenticated seal or V9 certification claim.",
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
