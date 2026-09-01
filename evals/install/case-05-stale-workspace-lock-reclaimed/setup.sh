#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
test -f "$ROOT/scripts/workspace-session-start.py"
test -f "$ROOT/scripts/test-workspace-session-start.py"
test -f "$ROOT/evals/install/case-05-stale-workspace-lock-reclaimed/check-stale-lock.py"
printf 'RUN_DIR=%s\n' "$ROOT"
