#!/usr/bin/env bash
# plugify status — 시스템 한눈에 보기 (★2-P0 현황판, SYSTEM.md §6 ★2)
# 흩어진 상태(본사 evals·첫 실전 관찰·백로그 + 각 지점 STATE·git)를 한 화면으로 모은다.
# "살아 움직이는 시스템"의 토대: 먼저 *보여야* 루프(피드백·자기시계)를 건다.
# 사용: bash scripts/status.sh
set -uo pipefail

HQ="$(cd "$(dirname "$0")/.." && pwd)"

# <repo> → "브랜치 @해시 (clean|dirty N)"
git_line() {
  local d="$1" br hash n
  br=$(git -C "$d" rev-parse --abbrev-ref HEAD 2>/dev/null) || { echo "(git 아님)"; return; }
  hash=$(git -C "$d" rev-parse --short HEAD 2>/dev/null)
  n=$(git -C "$d" status --porcelain 2>/dev/null | grep -c . || true)
  if [ "${n:-0}" -eq 0 ]; then echo "$br @$hash · clean"; else echo "$br @$hash · dirty($n)"; fi
}

echo "═══════════════════════════════════════════════════════"
echo "  PLUGIFY 시스템 현황판   ($(git -C "$HQ" log -1 --format='%cd' --date=format:'%Y-%m-%d %H:%M' 2>/dev/null))"
echo "═══════════════════════════════════════════════════════"

# ── 본사 ────────────────────────────────────────────────
echo ""
echo "■ 본사 (plugify) — $(git_line "$HQ")"

echo "  · 문제집(evals):"
for skill in "$HQ"/evals/*/; do
  [ -d "$skill" ] || continue
  n=$(find "$skill" -maxdepth 1 -type d -name 'case-*' 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 0 ] && echo "      $(basename "$skill"): ${n}케이스"
done

# 첫 실전 관찰 (정본 = SYSTEM.md §3.1 불릿 — 2026-07-03 레지스트리 격하) — 닫기 = 사람(줄 제거)
echo "  · 첫 실전 관찰 (닫기=사람, 정본=SYSTEM.md §3.1):"
awk '/^### 3\.1 첫 실전 관찰/{f=1;next} f&&/^#/{exit} f&&/^- /' "$HQ/SYSTEM.md" 2>/dev/null | sed 's/^- /    ⏳ /'
[ -z "$(awk '/^### 3\.1 첫 실전 관찰/{f=1;next} f&&/^#/{exit} f&&/^- /' "$HQ/SYSTEM.md" 2>/dev/null)" ] && echo "    (열린 첫 실전 관찰 없음)"

# 박동(heartbeat) — 자기 시계 마지막 실행 + launchd 등록 여부 (★2-P2)
hb="$HQ/telemetry/heartbeat.json"
if [ -f "$hb" ] && command -v jq >/dev/null 2>&1; then
  echo "  · 박동: $(jq -r '.last_run' "$hb") · 관찰 $(jq -r '.collected' "$hb")지점·skip $(jq -r '.skipped' "$hb")"
elif [ -f "$hb" ]; then
  echo "  · 박동: $(grep -m1 last_run "$hb" | sed -E 's/.*"last_run": *"([^"]*)".*/\1/')"
else
  echo "  · 박동: 미실행"
fi
if launchctl list 2>/dev/null | grep -q com.plugify.heartbeat; then
  echo "      launchd: 등록됨(주간 월 09:00)"
else
  echo "      launchd: 미등록 — ❄ 냉동(2026-07-03, 해동 조건: 지점 telemetry.sh 실구현 → heartbeat-ctl.sh install)"
fi

echo "  · 다음 큰 방향(SYSTEM §6 ★):"
grep -E "^★" "$HQ/SYSTEM.md" 2>/dev/null | sed -E 's/\*\*//g; s/^/      /'

# ── 지점 ────────────────────────────────────────────────
echo ""
echo "■ 지점 (제품 레포 — ~/Projects/*/.planning/STATE.md)"
found=0
for state in "$HOME"/Projects/*/.planning/STATE.md; do
  [ -f "$state" ] || continue
  found=1
  repo="$(cd "$(dirname "$state")/.." && pwd)"
  echo ""
  echo "  ▸ $(basename "$repo") — $(git_line "$repo")"
  # "## 다음 task" 뒤 첫 의미 줄(하위 ### 헤더·빈줄 건너뜀)
  task=$(awk '
    /^## 다음 task/ {f=1; next}
    f && /^## / {exit}
    f { if (/^### / || !NF) next; gsub(/^[#> *_-]+/,""); print; exit }
  ' "$state")
  [ -n "$task" ] && echo "      다음: ${task:0:90}"
done
[ "$found" -eq 0 ] && echo "  (없음)"

echo ""
echo "═══════════════════════════════════════════════════════"
