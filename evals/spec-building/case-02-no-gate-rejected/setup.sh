#!/usr/bin/env bash
# spec-building eval case-02 부트스트랩 — 게이트 없는(구식 형식) task 픽스처를 /tmp 격리 사본으로 git 초기화.
# 사용: bash setup.sh  → 마지막 줄 RUN_DIR 출력. 기대 결과: 워크플로우가 게이트 부재로 반려(구현 안 함).
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-specb-c02.XXXXXX)"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
cd "$RUN_DIR"
git init -q
git add -A
git commit -qm "픽스처 초기 상태 (다음 task 가 구식 형식 — ### 게이트 없음)"
echo "초기 상태 (커밋 1개여야 정상):"
git log --oneline
echo "RUN_DIR=$RUN_DIR"
