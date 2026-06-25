#!/usr/bin/env bash
# Regenerate the release-tracked fields of snippets/_status-snapshot.mdx from the
# latest PUBLISHED nika release — the version users actually install (brew / curl),
# not main's `-dev`. This is the user-docs source of truth for "what's the current
# version", so it tracks the tag, derived from the public GitHub release API (no
# engine checkout needed — that cross-repo dependency is why the old generator rotted).
#
# Auto-derived here: `version` + `lastUpdated`. The count fields (crates, tests,
# clippy, adrs, providers, hygiene) are a hand-maintained periodic snapshot — a
# standalone docs checkout can't cheaply read the engine workspace — refresh them
# by hand when they drift materially.
#
# Usage: bash scripts/mintlify-snapshot.sh   (requires an authenticated `gh`)
set -euo pipefail

cd "$(dirname "$0")/.."

tag="$(gh release view --repo supernovae-st/nika --json tagName --jq .tagName)"
version="${tag#v}"
today="$(date +%Y-%m-%d)"
snap="snippets/_status-snapshot.mdx"

[ -f "$snap" ] || { echo "mintlify-snapshot: $snap not found" >&2; exit 1; }

perl -pi -e "s/(version:\\s*)\"[^\"]*\"/\${1}\"$version\"/" "$snap"
perl -pi -e "s/(lastUpdated:\\s*)\"[^\"]*\"/\${1}\"$today\"/" "$snap"

echo "mintlify-snapshot: version -> $version - lastUpdated -> $today (latest release $tag)"
