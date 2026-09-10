#!/usr/bin/env python3
"""teach-parity: the CLI surface and the docs match, BOTH directions.

Direction 1 · every subcommand the binary ships has a row in
reference/cli.mdx. A verb a reader cannot find is a verb they do not use.

Direction 2 · every subcommand the docs HAND a reader in a shell fence
resolves. One direction alone is blind in one eye: the first cannot see
a taught command that no longer exists, the second cannot see a shipped
command nobody wrote down. A reader copying a "## Run it" block must
never meet a dead end the surface swore was live.

The positional `nika new <intent> [dest]` door also gets one explicit
tombstone: live pages may not teach its retired `--from` flag. Release
history is exempt because it records the migration.

Both directions read the SAME derivation — the released binary's own
`--help --all` command inventory. NIKA_BIN selects an explicit absolute
engine path; otherwise the gate resolves `nika` on PATH once and uses it
for every probe.
Soft-skips only when no explicit binary was supplied and PATH has none.
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


def resolve_nika() -> str | None:
    """An explicit judge never silently falls back to another installation."""
    explicit = os.environ.get("NIKA_BIN")
    if explicit is not None:
        path = pathlib.Path(explicit)
        if not path.is_absolute():
            raise ValueError("NIKA_BIN must be an absolute executable path")
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"NIKA_BIN is not an executable file: {explicit}")
        return str(path)
    found = shutil.which("nika")
    return str(pathlib.Path(found).absolute()) if found else None


def released_subcommands(binary: str) -> list[str]:
    out = subprocess.run(
        [binary, "--help", "--all"],
        capture_output=True,
        text=True,
        env={**os.environ, "NO_COLOR": "1"},
        check=True,
        timeout=10,
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
    if not subs:
        raise ValueError("selected engine --help --all did not list any subcommands")
    return [s for s in subs if s not in EXEMPT]


# A shell fence (```sh · ```bash · ```console · ```shell) is a block the
# reader COPIES. Everything else is prose about commands, not an offer.
SHELL_FENCE = re.compile(r"```(?:sh|bash|console|shell)[^\n]*\n(.*?)```", re.DOTALL)
# `nika <sub>` at the head of a copyable line. A `$`/`>` prompt is
# tolerated; a continuation (`--flag`) or a comment is not a command.
TAUGHT_CALL = re.compile(r"^\s*(?:[$>]\s*)?nika\s+([a-z][a-z0-9-]*)", re.M)
RETIRED_NEW_FORM = re.compile(r"nika new[^\n`]*--from")


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


def retired_new_forms() -> list[str]:
    """Live pages that still hand readers the pre-positional creation flag."""
    findings = []
    for path in sorted(DOCS_ROOT.rglob("*.mdx")):
        if "node_modules" in path.parts or "changelog" in path.parts:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, 1):
            if RETIRED_NEW_FORM.search(line):
                findings.append(f"{path.relative_to(DOCS_ROOT)}:{line_number}")
    return findings


def door_exists(binary: str, sub: str) -> bool:
    """Does `nika <sub>` resolve? PROBED, never inferred from `--help`.

    The compact top-level `--help` is a teaching card. The full inventory
    comes from `--help --all`, but each taught command still gets its own
    probe so command resolution is tested independently of that listing.
    """
    return (
        subprocess.run(
            [binary, sub, "--help"],
            capture_output=True,
            text=True,
            env={**os.environ, "NO_COLOR": "1"},
            timeout=10,
        ).returncode
        == 0
    )


def main() -> int:
    try:
        binary = resolve_nika()
        if binary is None:
            print("teach-parity: SKIP (nika binary absent — run where the release is installed)")
            return 0
        return judge(binary)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"teach-parity: RED — cannot judge selected engine: {error}", file=sys.stderr)
        return 1


def judge(binary: str) -> int:
    released = released_subcommands(binary)
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
    # full inventory and per-command probe must agree on the selected binary.
    dead = {
        sub: files
        for sub, files in taught_subcommands().items()
        if sub not in EXEMPT and not door_exists(binary, sub)
    }
    retired_new = retired_new_forms()

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
    if retired_new:
        print(
            "teach-parity: RED — live docs still teach retired `nika new --from`: "
            + " · ".join(retired_new)
        )
    if missing or dead or retired_new:
        return 1
    print("teach-parity: GREEN — the CLI surface and the docs match, both directions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
