#!/usr/bin/env bash
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-svcplan-c02.XXXXXX)"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
echo "REQUEST=$RUN_DIR/REQUEST.md"
echo "RUN_DIR=$RUN_DIR"
