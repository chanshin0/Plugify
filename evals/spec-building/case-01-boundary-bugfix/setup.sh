#!/usr/bin/env bash
# spec-building eval case-01 부트스트랩 — 픽스처를 /tmp 격리 사본으로 git 초기화.
# 사용: bash setup.sh  → 마지막 줄에 RUN_DIR 출력. 결정적(타임스탬프 외 변수 없음).
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-specb-c01.XXXXXX)"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
cd "$RUN_DIR"
git init -q
git add -A
git commit -qm "픽스처 초기 상태 (경계 버그 심어짐 — 테스트 2건 실패)"
echo "버그 재현 (테스트 2건 실패해야 정상):"
node --test src/ 2>&1 | tail -2 || true
echo "RUN_DIR=$RUN_DIR"
