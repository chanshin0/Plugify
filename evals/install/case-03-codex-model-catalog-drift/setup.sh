#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
test -f "$ROOT/scripts/sync-agents.py"
test -f "$ROOT/scripts/workspace-session-start.py"
test -f "$ROOT/scripts/test-workspace-session-start.py"
test -f "$ROOT/evals/install/case-03-codex-model-catalog-drift/check-drift.py"
printf 'RUN_DIR=%s\n' "$ROOT"
