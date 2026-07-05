#!/usr/bin/env bash
# spec-building eval case-05 부트스트랩 — DONE_WITH_CONCERNS(조용한 기각 금지) 경로 픽스처를 /tmp 격리 사본으로 git 초기화.
# 사용: bash setup.sh  → 마지막 줄 RUN_DIR 출력. 결정적(타임스탬프 외 변수 없음).
# 기대: task 목표가 concerns 1개 명시를 요구 → implementer DONE_WITH_CONCERNS → reviewer concernDispositions 1:1 판정 → 커밋.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-specb-c05.XXXXXX)"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
cd "$RUN_DIR"
git init -q
git add -A
git commit -qm "픽스처 초기 상태 (이름 인사 미구현 — 테스트 1건 실패, task 가 concerns 1개 보고를 명시 요구)"
echo "초기 상태 (테스트 1건 실패해야 정상):"
node --test src/*.test.js 2>&1 | tail -2 || true
echo "RUN_DIR=$RUN_DIR"
