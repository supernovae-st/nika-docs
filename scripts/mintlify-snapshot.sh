#!/usr/bin/env bash
# Regenerate the release-tracked fields of snippets/_status-snapshot.mdx from
# the downloadable binary a reader installs — not engine main.
#
# Always (gh):           version + lastUpdated  from GitHub latest release
# When nika is on PATH:  engineSha + providers + firstCommand from that binary
#                        (`nika --version` · `nika catalog --json` · bare `nika`)
#
# firstCommand is read from a bare `nika` in an EMPTY directory on a scratch
# HOME — what a stranger sees, not what this laptop has wired. It moved twice
# in three releases (`nika try 01-hello` -> `nika new hello`) while the pages
# kept teaching the old one, so it stopped being something anyone types.
#
# Crate / test / ADR / hygiene totals do NOT project from the binary.
# They stay in this file only because frozen pages still interpolate them.
# Do not copy them onto reference/status.mdx.
#
# Usage: bash scripts/mintlify-snapshot.sh
#        NIKA_BIN=/path/to/nika bash scripts/mintlify-snapshot.sh
set -euo pipefail

cd "$(dirname "$0")/.."

tag="$(gh release view --repo supernovae-st/nika --json tagName --jq .tagName)"
version="${tag#v}"
today="$(date +%Y-%m-%d)"
snap="snippets/_status-snapshot.mdx"

[ -f "$snap" ] || { echo "mintlify-snapshot: $snap not found" >&2; exit 1; }

perl -pi -e "s/(version:\\s*)\"[^\"]*\"/\${1}\"$version\"/" "$snap"
perl -pi -e "s/(lastUpdated:\\s*)\"[^\"]*\"/\${1}\"$today\"/" "$snap"

echo "mintlify-snapshot: version -> $version · lastUpdated -> $today (latest release $tag)"

nika_bin="${NIKA_BIN:-}"
if [ -z "$nika_bin" ] && command -v nika >/dev/null 2>&1; then
  nika_bin=$(command -v nika)
fi
if [ -z "$nika_bin" ]; then
  echo "mintlify-snapshot: nika not on PATH — engineSha/providers left untouched"
  exit 0
fi

python3 - "$snap" "$nika_bin" <<'PY'
import json, os, re, subprocess, sys
snap, nika = sys.argv[1], sys.argv[2]
ver = subprocess.check_output([nika, "--version"], text=True).strip()
# nika 0.114.0 (b1154df75)
m = re.search(r"\(([^)]+)\)", ver)
sha = m.group(1) if m else ""
catalog = json.loads(subprocess.check_output([nika, "catalog", "--json"], text=True))
n_providers = len(catalog["providers"])
text = open(snap, encoding="utf-8").read()
if "engineSha:" in text:
    text = re.sub(r'(engineSha:\s*)"[^"]*"', rf'\1"{sha}"', text)
else:
    text = re.sub(r'(version: "[^"]*",\n)', rf'\1  engineSha: "{sha}",\n', text, count=1)
text = re.sub(r'(providers:\s*)\d+', rf'\g<1>{n_providers}', text)

# firstCommand — the stranger's screen (empty cwd · scratch HOME · no keys).
# ONE reader, shared with count-drift-gate check (g): two would be a mirror.
sys.path.insert(0, os.path.dirname(os.path.abspath(snap)) + "/../scripts")
from first_command import read_first_command, KNOWN_LABELS  # noqa: E402
first = read_first_command(nika)
if not first:
    sys.exit("mintlify-snapshot: no known 'what to type next' label on the welcome "
             f"screen. Known: {KNOWN_LABELS}. Teach the new shape in "
             "scripts/first_command.py before the pages go stale.")
text = re.sub(r'(firstCommand:\s*)"[^"]*"', rf'\1"{first}"', text)
open(snap, "w", encoding="utf-8").write(text)
print(f"mintlify-snapshot: engineSha -> {sha} · providers -> {n_providers} · "
      f"firstCommand -> {first} (from {ver})")
PY
