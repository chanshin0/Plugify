#!/usr/bin/env bash
# telemetry-digest eval case-01 부트스트랩 — 격리 PROJECTS_DIR 사본 생성(실지점 무관).
# 지점 4개: alpha(정상)·bravo(계약없음)·charlie(JSON깨짐)·delta(value누락).
# 사용: bash setup.sh  → 마지막 줄들 PROJECTS_DIR·TELEMETRY_DIR 출력.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-telemetry-c01.XXXXXX)"
cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
# 실행권한 복원 (git/cp 모드 손실 대비)
chmod +x "$RUN_DIR"/projects/*/.planning/telemetry.sh 2>/dev/null || true
mkdir -p "$RUN_DIR/hq-telemetry"
echo "지점 픽스처:"
for d in "$RUN_DIR"/projects/*/; do
  b="$(basename "$d")"
  if [ -x "$d/.planning/telemetry.sh" ]; then echo "  $b — 계약 있음(telemetry.sh)"; else echo "  $b — 계약 없음"; fi
done
echo "PROJECTS_DIR=$RUN_DIR/projects"
echo "TELEMETRY_DIR=$RUN_DIR/hq-telemetry"
