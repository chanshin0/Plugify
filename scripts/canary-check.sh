#!/usr/bin/env bash
# plugify canary-check — canary 닫기 후보 탐지(★2-P3, SYSTEM.md §6 ★2).
#
# 레지스트리(telemetry/canaries.jsonl)의 각 canary 닫기 신호를 평가해
# 후보(ready)/대기(open)/수동(manual)으로 분류한다.
#
# ⚠ 순수 평가기 — 아무것도 쓰지 않는다(stdout 만). 레지스트리·SYSTEM 자동편집 금지.
#    닫기 확정은 사람(자율성은 탐지·표시까지만, P1 "승격은 사람" 의 형제 불변식).
#
# 닫기 신호 종류:
#   telemetry-signal : 어떤 지점이든 .planning/telemetry-log.md 존재 = 실신호 1회+ 발생
#                      (telemetry-digest 는 계약 통과·신호 수집 시에만 그 파일을 만든다)
#   manual           : 사람만 닫음(자동 탐지 대상 아님)
#
# 사용: bash scripts/canary-check.sh [PROJECTS_DIR]   (기본 ~/Projects)
set -uo pipefail
HQ="$(cd "$(dirname "$0")/.." && pwd)"
PROJECTS_DIR="${1:-$HOME/Projects}"
REG="${PLUGIFY_CANARY_REGISTRY:-$HQ/telemetry/canaries.jsonl}"

command -v jq >/dev/null 2>&1 || { echo "FATAL: jq 필요"; exit 2; }
if [ ! -f "$REG" ]; then echo "(canary 레지스트리 없음: $REG)"; echo "요약: 후보 0 · 대기 0 · 수동 0"; exit 0; fi

# telemetry-signal: 지점 telemetry-log.md 존재 = 실신호 출현(전 시스템 마일스톤)
telemetry_signal_met() {
  ls "$PROJECTS_DIR"/*/.planning/telemetry-log.md >/dev/null 2>&1
}

cand=0; open=0; man=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  id="$(jq -r '.id // "?"' <<<"$line" 2>/dev/null)" || { echo "  ! 레지스트리 줄 파싱 실패"; continue; }
  what="$(jq -r '.what // ""' <<<"$line")"
  close="$(jq -r '.close // "manual"' <<<"$line")"
  case "$close" in
    telemetry-signal)
      if telemetry_signal_met; then
        echo "  ✅ 후보  $id — telemetry 실신호 출현 → 확인 후 닫기(레지스트리에서 제거 = 사람)"
        cand=$((cand + 1))
      else
        echo "  ⏳ 대기  $id — $what"
        open=$((open + 1))
      fi ;;
    manual)
      echo "  👤 수동  $id — $what"
      man=$((man + 1)) ;;
    *)
      echo "  ? 미지원 close=$close  $id — 대기로 처리"
      open=$((open + 1)) ;;
  esac
done < "$REG"

echo "요약: 후보 $cand · 대기 $open · 수동 $man"
