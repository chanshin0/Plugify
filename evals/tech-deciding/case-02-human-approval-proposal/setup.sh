#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
test -f "$ROOT/scripts/test-tech-deciding-contracts.mjs"
echo "RUN_DIR=$ROOT"
