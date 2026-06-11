#!/usr/bin/env bash
# perf-review eval case-01 부트스트랩.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-perfr-c01.XXXXXX)"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
cd "$RUN_DIR"
git init -q && git add -A && git commit -qm "픽스처 초기 상태"
node --check server.js && node --check db.js
echo "RUN_DIR=$RUN_DIR"
