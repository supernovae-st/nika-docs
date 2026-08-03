#!/usr/bin/env python3
"""teach-parity: the CLI surface and the docs match, BOTH directions.

Direction 1 · every subcommand the binary ships has a row in
reference/cli.mdx. A verb a reader cannot find is a verb they do not use.

Direction 2 · every subcommand the docs HAND a reader in a shell fence
resolves. One direction alone is blind in one eye: the first cannot see
a taught command that no longer exists, the second cannot see a shipped
command nobody wrote down. A reader copying a "## Run it" block must
never meet a dead end the surface swore was live.

Both directions read the SAME derivation — the released binary's own
`--help`. Zero hand-maintained lists, so the gate cannot rot into a
mirror of what it is meant to judge. Soft-skips when the binary is
absent (CI without brew).
"""

import os
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


# A shell fence (```sh · ```bash · ```console · ```shell) is a block the
# reader COPIES. Everything else is prose about commands, not an offer.
SHELL_FENCE = re.compile(r"```(?:sh|bash|console|shell)[^\n]*\n(.*?)```", re.DOTALL)
# `nika <sub>` at the head of a copyable line. A `$`/`>` prompt is
# tolerated; a continuation (`--flag`) or a comment is not a command.
TAUGHT_CALL = re.compile(r"^\s*(?:[$>]\s*)?nika\s+([a-z][a-z0-9-]*)", re.M)


def taught_subcommands() -> dict[str, list[str]]:
    """Every `nika <sub>` handed to a reader in a shell fence → its files."""
    found: dict[str, list[str]] = {}
    for path in sorted(DOCS_ROOT.rglob("*.mdx")):
        if "node_modules" in path.parts:
            continue
        for body in SHELL_FENCE.findall(path.read_text(encoding="utf-8")):
            for sub in TAUGHT_CALL.findall(body):
                where = str(path.relative_to(DOCS_ROOT))
                if where not in found.setdefault(sub, []):
                    found[sub].append(where)
    return found


def door_exists(sub: str) -> bool:
    """Does `nika <sub>` resolve? PROBED, never inferred from `--help`.

    `--help` lists the operator surface, not the whole surface: `catalog`
    and `completions` both answer rc=0 while staying hidden from it. A
    gate that read the help text alone would condemn two live doors —
    measured 2026-08-03, the first run of this direction did exactly
    that, and the docs it accused were right.
    """
    return (
        subprocess.run(
            ["nika", sub, "--help"],
            capture_output=True,
            text=True,
            env={"NO_COLOR": "1", "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        ).returncode
        == 0
    )


def main() -> int:
    if shutil.which("nika") is None:
        print("teach-parity: SKIP (nika binary absent — run where the release is installed)")
        return 0
    released = released_subcommands()
    taught = CLI_MDX.read_text()

    # Direction 1 · every released subcommand has its row.
    missing = [
        sub
        for sub in released
        if not re.search(rf"\| *`nika {re.escape(sub)}[ `\[]", taught)
    ]
    # Direction 2 · every subcommand a shell fence hands out still exists.
    # `--version`/`--help` style calls never reach here (the pattern wants
    # a bare word). The authority is the PROBE, not the help text — the
    # help lists the operator surface, the binary has more doors.
    dead = {
        sub: files
        for sub, files in taught_subcommands().items()
        if sub not in EXEMPT and not door_exists(sub)
    }

    if missing:
        print(
            "teach-parity: RED — released subcommand(s) with no reference/cli.mdx row: "
            + " · ".join(missing)
        )
    if dead:
        for sub, files in sorted(dead.items()):
            print(
                f"teach-parity: RED — the docs hand `nika {sub}`, which the released "
                f"binary does not have: {' · '.join(files)}"
            )
    if missing or dead:
        return 1
    print("teach-parity: GREEN — the CLI surface and the docs match, both directions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
