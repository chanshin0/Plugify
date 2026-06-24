#!/usr/bin/env bash
# plugify heartbeat — 자기 박동(★2-P2, SYSTEM.md §6 ★2). launchd/cron 이 주기 호출.
#
# telemetry-digest(P1)를 돌리고 결과 요약을 heartbeat.json 으로 남긴다 — 현황판(status.sh)이
# 읽어 "마지막 박동" 을 보여준다(박동→현황판→사람, 안 닫는 자동화 금지).
#
# ⚠ launchd 함정: 최소 PATH(/usr/bin:/bin)라 jq(@/opt/homebrew/bin)·perl 경로를 못 찾는다.
#    → 여기서 PATH 를 보정하지 않으면 telemetry-digest 가 "jq 필요" 로 조용히 죽는다.
#
# 규율: 박동은 트리거·관찰만 — 합격판정·승격·push 는 안 한다(P1 불변식 그대로 상속).
# 사용: bash scripts/heartbeat.sh [PROJECTS_DIR]   (기본 ~/Projects)
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

HQ="$(cd "$(dirname "$0")/.." && pwd)"
PROJECTS_DIR="${1:-$HOME/Projects}"
DIGEST_DIR="${PLUGIFY_TELEMETRY_DIR:-$HQ/telemetry}"
WEEK="$(date +%G-W%V)"
NOW_ISO="$(date '+%Y-%m-%dT%H:%M:%S%z')"   # BSD date 이식(-Iseconds 는 GNU 전용)
NOW="$(date '+%Y-%m-%d %H:%M')"
RECORD="$DIGEST_DIR/heartbeat.json"
LOG="$DIGEST_DIR/heartbeat.log"

mkdir -p "$DIGEST_DIR"

# telemetry-digest 실행(같은 DIGEST_DIR 공유) — stdout 캡처해 로그 보존 + 요약 파싱.
out="$(PLUGIFY_TELEMETRY_DIR="$DIGEST_DIR" bash "$HQ/scripts/telemetry-digest.sh" "$PROJECTS_DIR" 2>&1)"
rc=$?
printf '\n──── 박동 %s (rc=%s) ────\n%s\n' "$NOW" "$rc" "$out" >> "$LOG"

# 집계는 다이제스트 헤더(내가 통제하는 안정 포맷)에서 — stdout grep 보다 견고.
digest="$DIGEST_DIR/digest-$WEEK.md"
hdr="$(grep -m1 '관찰.*지점.*건너뜀' "$digest" 2>/dev/null || true)"
collected="$(printf '%s' "$hdr" | sed -nE 's/.*관찰 ([0-9]+)지점.*/\1/p')"; collected="${collected:-0}"
skipped="$(printf '%s' "$hdr" | sed -nE 's/.*건너뜀 ([0-9]+)지점.*/\1/p')"; skipped="${skipped:-0}"

# 박동 기록 — 현황판이 읽는 단일 포인터(멱등 덮어쓰기).
cat > "$RECORD" <<JSON
{
  "last_run": "$NOW_ISO",
  "week": "$WEEK",
  "collected": $collected,
  "skipped": $skipped,
  "rc": $rc,
  "digest": "$digest"
}
JSON

echo "박동 완료 $NOW · 관찰 ${collected}지점 · skip ${skipped} · 기록 $RECORD"
exit "$rc"
