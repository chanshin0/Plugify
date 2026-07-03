#!/usr/bin/env bash
# spec-building eval case-03 부트스트랩 — 라이브 게이트(Phase C) 픽스처.
# RUN_DIR(작업 클론, task 브랜치 체크아웃) + RUN_DIR-origin.git(bare 원격) 구성.
# 사용: bash setup.sh → 마지막 줄에 RUN_DIR 출력.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-specb-c03.XXXXXX)"
ORIGIN_DIR="$RUN_DIR-origin.git"

git init -q --bare -b main "$ORIGIN_DIR"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
chmod +x "$RUN_DIR/.planning/preview.sh"
cd "$RUN_DIR"
git init -q -b main
git add -A
git commit -qm "픽스처 초기 상태 (인사말 버그 — 라이브 게이트 task)"
git remote add origin "$ORIGIN_DIR"
git push -q -u origin main            # main 은 원격에 존재(=prod 가정, 불변이어야 함)
git checkout -q -b task/greeting-fix  # 작업 브랜치 — 워크플로우가 push 할 대상

echo "버그 재현: h1 = $(grep -o '<h1>[^<]*' site/index.html)"
echo "ORIGIN_DIR=$ORIGIN_DIR"
echo "RUN_DIR=$RUN_DIR"
