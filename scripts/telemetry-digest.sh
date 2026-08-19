#!/usr/bin/env bash
# plugify telemetry-digest — 운영→기획 backward edge (★2-P1, SYSTEM.md §6 ★2)
#
# ❄ 냉동(2026-07-03 YAGNI 리뷰): 지점 계약 0·실신호 0 상태의 선건축 — 주기 호출(박동) 해제됨.
#    스크립트·CONTRACT.md·eval 은 해동용으로 보존. 해동 조건 = 지점 telemetry.sh 실구현.
#
# 각 지점의 telemetry 계약(.planning/telemetry.sh)을 호출해 운영 신호를 모으고
#   (1) 본사 주간 다이제스트 telemetry/digest-<ISO주>.md
#   (2) 각 지점 기획 백로그 .planning/telemetry-log.md 에 "관찰" append
# 한다. 계약 없는 지점은 건너뛴다(사유 출력).
#
# 규율(SYSTEM §6 ★2): 자율성은 관찰까지만 — **관찰은 task 아님, 승격은 사람**.
# STATE "## 다음 task" 는 절대 건드리지 않는다. HQ 는 지점 repo 를 커밋하지 않는다
# (관찰만 떨구고 지점 세션이 검토·커밋). P2 cron 이 재호출하므로 **멱등**(ISO주 키 가드).
#
# 사용: bash scripts/telemetry-digest.sh [PROJECTS_DIR]
# 제품 지점 스캔 경로 우선순위: 인자 > PLUGIFY_PROJECTS_DIR > $HOME/Projects.
# 이 경로는 3-repo 개인 작업공간과 별개다.
#       eval 은 격리 디렉토리를 인자로 넘겨 실지점을 안 건드린다.
set -uo pipefail

HQ="$(cd "$(dirname "$0")/.." && pwd)"
PROJECTS_DIR="${1:-${PLUGIFY_PROJECTS_DIR:-$HOME/Projects}}"
WEEK="$(date +%G-W%V)"            # ISO 연-주 (멱등 가드 키)
NOW="$(date '+%Y-%m-%d %H:%M')"
DIGEST_DIR="${PLUGIFY_TELEMETRY_DIR:-$HQ/telemetry}"   # eval 은 격리 디렉토리로 오버라이드
DIGEST="$DIGEST_DIR/digest-$WEEK.md"
TIMEOUT_S=20

command -v jq >/dev/null 2>&1 || { echo "FATAL: jq 필요 (telemetry 계약 JSON 검증)"; exit 2; }

# 계약 실행 타임아웃 — macOS 기본엔 timeout 부재. perl alarm 으로 이식.
run_contract() { # $1 = repo_dir  →  stdout=계약출력, 반환=exit code
  ( cd "$1" && perl -e 'alarm shift @ARGV; exec @ARGV' "$TIMEOUT_S" ./.planning/telemetry.sh )
}

mkdir -p "$DIGEST_DIR"

echo "═══ telemetry-digest $WEEK ($NOW) · 대상 $PROJECTS_DIR ═══"

collected=0
skipped=0
digest_blocks=""

shopt -s nullglob
for planning in "$PROJECTS_DIR"/*/.planning; do
  [ -d "$planning" ] || continue
  repo_dir="$(cd "$planning/.." && pwd)"
  repo="$(basename "$repo_dir")"
  contract="$planning/telemetry.sh"

  # ── 계약 존재/실행권 ──
  if [ ! -x "$contract" ]; then
    if [ -f "$contract" ]; then reason="telemetry.sh 비실행(chmod +x 필요)"
    else reason="계약 없음(.planning/telemetry.sh 부재)"; fi
    echo "  skip $repo — $reason"
    skipped=$((skipped + 1)); continue
  fi

  # ── 계약 실행 ──
  out="$(run_contract "$repo_dir")"; rc=$?
  if [ $rc -ne 0 ]; then
    echo "  skip $repo — 계약 실행 실패(exit $rc; timeout/오류)"
    skipped=$((skipped + 1)); continue
  fi

  # ── 스키마 검증 (친절한 추론 금지 — 깨지면 skip) ──
  if ! printf '%s' "$out" | jq -e '(.repo|type=="string") and (.signals|type=="array")' >/dev/null 2>&1; then
    echo "  skip $repo — JSON/스키마 위반(repo:string·signals:array 필수)"
    skipped=$((skipped + 1)); continue
  fi
  if ! printf '%s' "$out" | jq -e 'all(.signals[]; has("metric") and has("value"))' >/dev/null 2>&1; then
    echo "  skip $repo — signals[] 에 metric/value 누락"
    skipped=$((skipped + 1)); continue
  fi

  # ── 신호 → markdown 테이블 ──
  gen_at="$(printf '%s' "$out" | jq -r '.generated_at // "?"')"
  win="$(printf '%s' "$out" | jq -r '.window_days // "?"')"
  nsig="$(printf '%s' "$out" | jq -r '.signals | length')"
  table="$(printf '%s' "$out" | jq -r '
    "| metric | value | note |", "|---|---|---|",
    (.signals[] | "| \(.metric) | \(.value) | \(.note // "") |")')"

  collected=$((collected + 1))
  digest_blocks+="### $repo  (window ${win}d · generated $gen_at · 신호 ${nsig}개)
$table

"

  # ── 지점 백로그 append (멱등: ISO주 마커 가드) ──
  log="$planning/telemetry-log.md"
  marker="<!-- telemetry:$WEEK -->"
  if [ -f "$log" ] && grep -qF "$marker" "$log"; then
    echo "  $repo — $WEEK 관찰 이미 기록됨(멱등: append 생략) · 신호 ${nsig}개"
  else
    if [ ! -f "$log" ]; then
      printf '# 운영 관찰 로그 (telemetry backward edge)\n\n> ⚠ **관찰이지 task 아님.** plugify `telemetry-digest` 가 자동 append 한다.\n> 기획 task 로 **승격은 사람** — 옮길 항목만 STATE "## 다음 task" 로 이동해야 구현 큐에 든다.\n\n' > "$log"
    fi
    printf '%s\n## %s (수집 %s)\n\n%s\n\n' "$marker" "$WEEK" "$NOW" "$table" >> "$log"
    echo "  $repo — 관찰 append → .planning/telemetry-log.md ($WEEK) · 신호 ${nsig}개"
  fi
done

# ── 본사 주간 다이제스트 (멱등: 그 주 파일 덮어쓰기 = 항상 최신) ──
{
  echo "# 운영 다이제스트 — $WEEK"
  echo ""
  echo "> backward edge (운영→기획). 수집 $NOW · 대상 \`$PROJECTS_DIR\`"
  echo "> 관찰 ${collected}지점 · 건너뜀 ${skipped}지점. **승격(→ 지점 STATE '다음 task')은 사람.**"
  echo ""
  if [ "$collected" -eq 0 ]; then
    echo "_운영 신호 0건._"
  else
    printf '%s' "$digest_blocks"
  fi
} > "$DIGEST"

# ── 다음 행동 (안 닫는 자동화 금지) ──
echo ""
if [ "$collected" -eq 0 ]; then
  echo "다음 행동: 운영 신호 0건. 지점이 .planning/telemetry.sh 계약 구현(규격 → telemetry/CONTRACT.md)"
  echo "  또는 실트래픽 생길 때까지 대기. (계약 없는 지점은 매 박동 skip)"
else
  echo "다음 행동: 다이제스트 검토 → 승격할 관찰만 지점 STATE '## 다음 task' 로 이동(사람)."
  echo "  다이제스트: $DIGEST"
fi
