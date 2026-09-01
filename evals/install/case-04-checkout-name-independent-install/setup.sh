#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
test -f "$ROOT/scripts/install-session-hooks.py"
test -f "$ROOT/scripts/sync-agents.py"
test -f "$ROOT/scripts/workspace-session-start.py"
test -f "$ROOT/evals/install/case-04-checkout-name-independent-install/check-install-path.py"
printf 'RUN_DIR=%s\n' "$ROOT"
