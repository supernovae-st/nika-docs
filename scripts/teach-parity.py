#!/usr/bin/env python3
"""teach-parity: every RELEASED subcommand has a row in reference/cli.mdx.

The inverse of oracle-sweep (which proves taught things EXIST): this gate
proves existing things are TAUGHT. Born 2026-07-12 from the empirical
catch that `nika context` shipped in 0.99.0 with no cli.mdx row, and the
same-night merges (model · registry refs) would have repeated the class
at the next release.

Derives the subcommand set from the released binary on PATH (the same
truth source oracle-sweep uses) — zero hand-maintained lists here.
Soft-skips when the binary is absent (CI without brew).
"""

import pathlib
import re
import shutil
import subprocess
import sys

DOCS_ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI_MDX = DOCS_ROOT / "reference" / "cli.mdx"

# Not user-facing rows: clap's own help plumbing.
EXEMPT = {"help"}


def released_subcommands() -> list[str]:
    out = subprocess.run(
        ["nika", "--help"],
        capture_output=True,
        text=True,
        env={"NO_COLOR": "1", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    ).stdout
    subs = []
    in_commands = False
    for line in out.splitlines():
        if line.startswith("Commands:"):
            in_commands = True
            continue
        if in_commands:
            if line.startswith("Options:") or not line.strip():
                if subs:
                    break
                continue
            m = re.match(r"^  ([a-z][a-z0-9-]*)\s", line)
            if m:
                subs.append(m.group(1))
    return [s for s in subs if s not in EXEMPT]


def main() -> int:
    if shutil.which("nika") is None:
        print("teach-parity: SKIP (nika binary absent — run where the release is installed)")
        return 0
    taught = CLI_MDX.read_text()
    missing = [
        sub
        for sub in released_subcommands()
        if not re.search(rf"\| *`nika {re.escape(sub)}[ `\[]", taught)
    ]
    if missing:
        print(
            "teach-parity: RED — released subcommand(s) with no reference/cli.mdx row: "
            + " · ".join(missing)
        )
        return 1
    print("teach-parity: GREEN — every released subcommand is taught")
    return 0


if __name__ == "__main__":
    sys.exit(main())
