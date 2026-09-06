#!/usr/bin/env bash
# One atomic projection from a selected stable release and matching binary.
# The Python helper owns this transaction; first_command.py remains the ONE
# bare-screen reader shared with count-drift-gate. No snapshot is changed until
# every bounded probe passes. Matching a banner is not artifact provenance.
#
# Usage: NIKA_BIN=/absolute/path/to/nika bash scripts/mintlify-snapshot.sh
#        bash scripts/mintlify-snapshot.sh  # resolves PATH once; absence fails
set -euo pipefail

cd "$(dirname "$0")/.."
exec python3 scripts/mintlify_snapshot.py
