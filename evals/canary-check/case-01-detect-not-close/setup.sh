#!/usr/bin/env bash
# canary-check eval case-01 부트스트랩 — 격리 사본(레지스트리 2개 + 지점 1개, telemetry-log 없음).
# 사용: bash setup.sh  → PROJECTS_DIR·REGISTRY·RUN_DIR 출력.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-canary-c01.XXXXXX)"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
echo "초기: telemetry-log 없음(telem-test=대기 기대)"
echo "PROJECTS_DIR=$RUN_DIR/projects"
echo "REGISTRY=$RUN_DIR/canaries.jsonl"
echo "RUN_DIR=$RUN_DIR"
