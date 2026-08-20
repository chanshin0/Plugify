#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
test -f "$ROOT/scripts/no-askpass.py"
test -f "$ROOT/scripts/workspace-migrate.py"
test -f "$ROOT/scripts/workspace-session-start.py"
test -f "$ROOT/evals/install/case-02-session-start-askpass-executable/check-boundary.py"
printf 'RUN_DIR=%s\n' "$ROOT"
