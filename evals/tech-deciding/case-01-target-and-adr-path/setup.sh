#!/usr/bin/env bash
# tech-deciding eval case-01 부트스트랩 — 픽스처를 /tmp 격리 사본으로 git 초기화.
# 사용: bash setup.sh  → 마지막 줄에 RUN_DIR 출력. 결정적(타임스탬프 외 변수 없음).
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-techd-c01.XXXXXX)"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
cd "$RUN_DIR"
git init -q
git add -A
git commit -qm "픽스처 초기 상태 (기획 산출물만 — 기술 결정 전)"
echo "RUN_DIR=$RUN_DIR"
