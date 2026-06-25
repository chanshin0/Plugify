#!/usr/bin/env bash
# service-planning eval case-01 부트스트랩 — 초안 기획서(심은 누락 포함)를 /tmp 격리 사본으로.
# completeness-critic 는 파일만 읽으므로 git 불필요. 사용: bash setup.sh → 마지막 줄 PLAN 경로.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-svcplan-c01.XXXXXX)"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
echo "심은 누락: 캡처화면 UI 5상태 미흡(cat4) · 예외플로우 누락(cat5) · 가짜 PMF 주장(정직성)"
echo "오탐 함정(정당 제외): 역할(cat2) · 인증/계정(스캐폴딩) — 둘 다 '(스코프상 제외)' 명시됨"
echo "PLAN=$RUN_DIR/기획서.md"
echo "RUN_DIR=$RUN_DIR"
