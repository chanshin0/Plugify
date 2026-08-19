#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
test -f "$ROOT/scripts/install.sh"
test -f "$ROOT/scripts/workspace-session-start.py"
test -f "$ROOT/scripts/test-workspace-session-start.py"
test -f "$ROOT/scripts/test-install-contracts.mjs"
echo "RUN_DIR=$ROOT"
