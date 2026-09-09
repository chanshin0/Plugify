#!/usr/bin/env bash
# codex-worker.sh — Claude 세션이 격리 워커로 Codex 를 띄우는 표준 진입점 (2026-09-09)
#
# 정책 정본: AGENTS.md §설계 원칙 "Claude 세션 워커 = Codex 우선" · ~/.claude/CLAUDE.md §워커 정책.
# 존재 이유: "워커 완료" 판정을 에이전트 보고가 아니라 코드로 내린다 — 트레이스 마지막 줄의
# CODEX_EXIT=<n> 과 산출 슬롯 비어있지 않음을 이 스크립트가 기록·판정하고, 메인은 그것만 대조한다.
#
# 사용:
#   codex-worker.sh --cd <작업루트> --prompt-file <지시문> --out <최종메시지 파일> [옵션]
#   (Claude 에서는 Bash run_in_background 로 띄운다 — 레인 15~25분, 도구 상한 10분)
#
# 옵션:
#   --prompt <text>     --prompt-file 대신 인라인 지시문
#   --slot <file>       워커가 채워야 할 산출 슬롯. 실행 후 비어 있으면 exit 3 (scaffold P3 "빈 슬롯 = 실패")
#   --agent <name>      $CODEX_HOME/agents/<name>.toml(dual-block SSOT 생성물)의 model/effort/sandbox_mode 를
#                       기본값으로 쓰고 developer_instructions 를 지시문 앞에 붙인다
#   --model <slug>      기본 gpt-6-astra   (--agent 값보다 우선)
#   --effort <lvl>      기본 medium        (low|medium|high|xhigh|max — ultra 는 자동 위임 모드라 금지)
#   --sandbox <mode>    기본 workspace-write (read-only|workspace-write|danger-full-access)
#   --network           workspace-write 샌드박스에서 네트워크 허용 (npm install 등)
#   --web               실시간 웹 검색 허용 (codex 의 native web_search 도구 — 조사 레인)
#   --browser           Aside 브라우저 MCP(`aside mcp`, 도구 repl)를 붙인다 — 사용자의 로그인된 실제 브라우저에서
#                       콘솔·폼·확인 작업. 셸 `aside` CLI 는 샌드박스가 데몬·키체인을 막아 불통이라 MCP 경유만.
#                       지시문 앞에 브라우저 레인 규칙(승인 경계에서 멈춤·탭 정리)을 붙인다
#   --schema <file>     최종 메시지를 이 JSON Schema 모양으로 강제 (--out 을 Read 해 구조화 반환으로 씀)
#   --add-dir <dir>     추가 쓰기 허용 디렉터리 (반복 가능)
#   --retry <slug|auto> 실패(exit≠0, 타임아웃·미설치 제외) 시 다른 모델로 1회 재시도. 기본 auto
#                       (gpt-6-astra ↔ 그 외는 gpt-6-astra). --no-retry 로 끔
#   --trace <file>      stdout/stderr 트레이스 (기본 <out>.trace)
#   --timeout <sec>     기본 2400 (40분). 초과 시 TERM→KILL, exit 124 (재시도 없음)
#   --dry-run           실행 없이 해석된 명령을 출력하고 조립된 지시문을 <out>.prompt 에 남긴다
#
# 종료 코드: codex exit 그대로 / 슬롯 비면 3 / 타임아웃 124 / 인자 오류 2 / codex 미설치 127.
# 트레이스: 시도마다 "[codex-worker] attempt N …", 재시도 시 CODEX_RETRY=<model>, 마지막 줄 CODEX_EXIT=<n>.
# 메인은 CODEX_EXIT 와 슬롯 크기를 직접 확인한다(보고를 믿지 않는다).
set -u

DEFAULT_MODEL="gpt-6-astra"
DEFAULT_EFFORT="medium"
DEFAULT_SANDBOX="workspace-write"
DEFAULT_TIMEOUT=2400

CD="" PROMPT_FILE="" PROMPT_TEXT="" OUT="" SLOT="" AGENT="" MODEL="" EFFORT="" SANDBOX="" TRACE="" SCHEMA=""
NETWORK=0 WEB=0 BROWSER=0 DRY=0 TIMEOUT="$DEFAULT_TIMEOUT" RETRY="auto"
ADD_DIRS=()
ASIDE_BIN="${ASIDE_BIN:-$HOME/.local/bin/aside}"

# --browser 일 때 지시문 맨 앞에 붙는 레인 규칙 (정본: AGENTS.md 워커 규칙 · 메모리 browser-work-use-aside)
BROWSER_RULES='# 브라우저 레인 규칙 (codex-worker --browser)
- 브라우저 조작은 MCP 서버 "aside" 의 `repl` 도구(Playwright 스타일 JS — openTab/snapshot/page/listBrowserTabs/attachBrowserTab/closeTab)로만 한다. 이 브라우저는 사용자의 로그인 세션을 가진 실제 브라우저다.
- 셸에서 `aside` CLI 를 실행하지 마라(샌드박스에서 데몬·키체인 접근 불가 — 실패한다).
- 페이지 읽기는 `snapshot(page)` 우선, 스크린샷은 필요할 때만.
- 결제·로그인/계정 변경·메시지/메일 전송·삭제·게시·비가역 콘솔 변경은 실행하지 말고, 그 직전 상태와 필요한 동작을 최종 답에 적고 멈춘다(사용자 승인 경계). 유튜브 업로드는 브라우저로 하지 않는다(공식 API 전용).
- 마치면 네가 연 탭은 닫고, 사용자가 원래 열어둔 탭은 건드리지 않는다.'

usage() { sed -n '2,34p' "$0" | sed 's/^# \{0,1\}//'; }
die()   { echo "[codex-worker] $*" >&2; exit 2; }
now()   { date '+%Y-%m-%d %H:%M:%S'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --cd)          CD="${2:-}"; shift 2 ;;
    --prompt-file) PROMPT_FILE="${2:-}"; shift 2 ;;
    --prompt)      PROMPT_TEXT="${2:-}"; shift 2 ;;
    --out)         OUT="${2:-}"; shift 2 ;;
    --slot)        SLOT="${2:-}"; shift 2 ;;
    --agent)       AGENT="${2:-}"; shift 2 ;;
    --model)       MODEL="${2:-}"; shift 2 ;;
    --effort)      EFFORT="${2:-}"; shift 2 ;;
    --sandbox)     SANDBOX="${2:-}"; shift 2 ;;
    --network)     NETWORK=1; shift ;;
    --web)         WEB=1; shift ;;
    --browser)     BROWSER=1; shift ;;
    --schema)      SCHEMA="${2:-}"; shift 2 ;;
    --add-dir)     ADD_DIRS+=("${2:-}"); shift 2 ;;
    --retry)       RETRY="${2:-}"; shift 2 ;;
    --no-retry)    RETRY=""; shift ;;
    --trace)       TRACE="${2:-}"; shift 2 ;;
    --timeout)     TIMEOUT="${2:-}"; shift 2 ;;
    --dry-run)     DRY=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

[ -n "$CD" ]  || die "--cd <작업루트> 가 필요하다"
[ -d "$CD" ]  || die "--cd 경로가 디렉터리가 아니다: $CD"
[ -n "$OUT" ] || die "--out <최종메시지 파일> 이 필요하다"
if [ -n "$PROMPT_FILE" ] && [ -n "$PROMPT_TEXT" ]; then die "--prompt-file 과 --prompt 는 하나만"; fi
if [ -z "$PROMPT_FILE" ] && [ -z "$PROMPT_TEXT" ]; then die "--prompt-file 또는 --prompt 가 필요하다"; fi
if [ -n "$PROMPT_FILE" ] && [ ! -s "$PROMPT_FILE" ]; then die "지시문 파일이 없거나 비어 있다: $PROMPT_FILE"; fi
if [ -n "$SCHEMA" ] && [ ! -s "$SCHEMA" ]; then die "--schema 파일이 없거나 비어 있다: $SCHEMA"; fi
if [ "$BROWSER" -eq 1 ] && [ ! -x "$ASIDE_BIN" ]; then die "--browser: aside CLI 가 없다: $ASIDE_BIN (ASIDE_BIN 으로 지정 가능)"; fi
case "$TIMEOUT" in ''|*[!0-9]*) die "--timeout 은 초 단위 정수: $TIMEOUT" ;; esac

CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
AGENT_INSTR=""   # --agent 에서 뽑은 developer_instructions (임시 파일 경로)

# --agent: dual-block SSOT 생성물(agents/<name>.toml)에서 기본값·지시문을 가져온다.
if [ -n "$AGENT" ]; then
  AGENT_TOML="$CODEX_HOME_DIR/agents/$AGENT.toml"
  [ -f "$AGENT_TOML" ] || die "에이전트 정의가 없다: $AGENT_TOML (Plugify scripts/install.sh 로 생성)"
  AGENT_INSTR="$(mktemp "${TMPDIR:-/tmp}/codex-worker-instr.XXXXXX")"
  AGENT_META="$(python3 - "$AGENT_TOML" "$AGENT_INSTR" <<'PY'
import sys, tomllib
path, instr_out = sys.argv[1], sys.argv[2]
with open(path, "rb") as f:
    d = tomllib.load(f)
with open(instr_out, "w", encoding="utf-8") as f:
    f.write(d.get("developer_instructions", "").strip())
print(d.get("model", ""), d.get("model_reasoning_effort", ""), d.get("sandbox_mode", ""))
PY
)" || die "에이전트 toml 파싱 실패: $AGENT_TOML"
  set -- $AGENT_META
  [ -z "$MODEL" ]   && MODEL="${1:-}"
  [ -z "$EFFORT" ]  && EFFORT="${2:-}"
  [ -z "$SANDBOX" ] && SANDBOX="${3:-}"
fi

MODEL="${MODEL:-$DEFAULT_MODEL}"
EFFORT="${EFFORT:-$DEFAULT_EFFORT}"
SANDBOX="${SANDBOX:-$DEFAULT_SANDBOX}"
TRACE="${TRACE:-$OUT.trace}"

case "$EFFORT" in
  low|medium|high|xhigh|max) ;;
  ultra) die "effort 'ultra' 는 자동 위임 모드 — 서브에이전트 금지 (AGENTS.md 모델 티어)" ;;
  *) die "지원하지 않는 effort: $EFFORT" ;;
esac
case "$SANDBOX" in
  read-only|workspace-write|danger-full-access) ;;
  *) die "지원하지 않는 sandbox: $SANDBOX" ;;
esac

# 재시도 모델 결정 (auto: astra 가 실패하면 terra, 그 외 티어가 실패하면 astra)
case "$RETRY" in
  "")   RETRY_MODEL="" ;;
  auto) if [ "$MODEL" = "gpt-6-astra" ]; then RETRY_MODEL="gpt-5.6-terra"; else RETRY_MODEL="gpt-6-astra"; fi ;;
  *)    RETRY_MODEL="$RETRY" ;;
esac
[ "$RETRY_MODEL" = "$MODEL" ] && RETRY_MODEL=""

# 지시문 조립: [브라우저 레인 규칙] + [에이전트 지시문] + 이번 작업 지시
PROMPT_TMP="$(mktemp "${TMPDIR:-/tmp}/codex-worker-prompt.XXXXXX")"
{
  if [ "$BROWSER" -eq 1 ]; then
    printf '%s\n\n---\n\n' "$BROWSER_RULES"
  fi
  if [ -n "$AGENT_INSTR" ] && [ -s "$AGENT_INSTR" ]; then
    cat "$AGENT_INSTR"
    printf '\n\n---\n\n# 이번 작업 지시\n\n'
  fi
  if [ -n "$PROMPT_FILE" ]; then cat "$PROMPT_FILE"; else printf '%s\n' "$PROMPT_TEXT"; fi
} > "$PROMPT_TMP"
[ -n "$AGENT_INSTR" ] && rm -f "$AGENT_INSTR"

# 명령 조립 — $1 = 모델
build_cmd() {
  CMD=(codex exec --ephemeral --skip-git-repo-check --color never
       -C "$CD" --sandbox "$SANDBOX" -m "$1"
       -c "model_reasoning_effort=\"$EFFORT\""
       -c 'approval_policy="never"'
       -o "$OUT")
  [ "$NETWORK" -eq 1 ] && CMD+=(-c 'sandbox_workspace_write.network_access=true')
  [ "$WEB" -eq 1 ]     && CMD+=(-c 'web_search="live"')
  if [ "$BROWSER" -eq 1 ]; then
    # MCP 서버 프로세스는 codex 가 샌드박스 밖에서 띄우므로 로컬 데몬·키체인 접근이 된다(2026-09-09 실측).
    # tools.repl.approval_mode=approve 가 없으면 approval_policy=never 와 충돌해 호출이 거부된다.
    CMD+=(-c "mcp_servers.aside.command=\"$ASIDE_BIN\""
          -c 'mcp_servers.aside.args=["mcp"]'
          -c 'mcp_servers.aside.startup_timeout_sec=60'
          -c 'mcp_servers.aside.tools.repl.approval_mode="approve"')
  fi
  [ -n "$SCHEMA" ]     && CMD+=(--output-schema "$SCHEMA")
  for d in "${ADD_DIRS[@]:-}"; do [ -n "$d" ] && CMD+=(--add-dir "$d"); done
  CMD+=(-)
}

if [ "$DRY" -eq 1 ]; then
  build_cmd "$MODEL"
  mkdir -p "$(dirname "$OUT")"
  cp "$PROMPT_TMP" "$OUT.prompt"; rm -f "$PROMPT_TMP"
  printf 'DRY_RUN model=%s effort=%s sandbox=%s network=%s web=%s browser=%s schema=%s retry=%s timeout=%s\n' \
    "$MODEL" "$EFFORT" "$SANDBOX" "$NETWORK" "$WEB" "$BROWSER" "${SCHEMA:-none}" "${RETRY_MODEL:-none}" "$TIMEOUT"
  printf 'CMD:'; printf ' %q' "${CMD[@]}"; printf ' < %q > %q 2>&1\n' "$OUT.prompt" "$TRACE"
  printf 'PROMPT: %s (%s bytes)\n' "$OUT.prompt" "$(wc -c < "$OUT.prompt" | tr -d ' ')"
  exit 0
fi

command -v codex >/dev/null 2>&1 || { mkdir -p "$(dirname "$TRACE")"; echo "CODEX_EXIT=127 (codex not installed)" > "$TRACE"; rm -f "$PROMPT_TMP"; echo "[codex-worker] codex 미설치" >&2; exit 127; }

mkdir -p "$(dirname "$OUT")" "$(dirname "$TRACE")"
{
  printf '[codex-worker] start %s\n' "$(now)"
  printf '[codex-worker] model=%s effort=%s sandbox=%s network=%s web=%s browser=%s schema=%s retry=%s cd=%s\n' \
    "$MODEL" "$EFFORT" "$SANDBOX" "$NETWORK" "$WEB" "$BROWSER" "${SCHEMA:-none}" "${RETRY_MODEL:-none}" "$CD"
  [ -n "$AGENT" ] && printf '[codex-worker] agent=%s\n' "$AGENT"
} > "$TRACE"

# 한 번 실행 — $1 = 모델, $2 = 시도 번호. 결과는 RC 에.
run_attempt() {
  local model="$1" n="$2" pid elapsed=0
  build_cmd "$model"
  : > "$OUT"
  printf '[codex-worker] attempt %s start %s model=%s\n' "$n" "$(now)" "$model" >> "$TRACE"
  "${CMD[@]}" < "$PROMPT_TMP" >> "$TRACE" 2>&1 &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$elapsed" -ge "$TIMEOUT" ]; then
      kill -TERM "$pid" 2>/dev/null; sleep 5; kill -KILL "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      RC=124
      printf '[codex-worker] attempt %s end %s rc=124 (timeout %ss)\n' "$n" "$(now)" "$TIMEOUT" >> "$TRACE"
      return
    fi
    sleep 5; elapsed=$((elapsed + 5))
  done
  wait "$pid"; RC=$?
  if [ -n "$SLOT" ] && [ "$RC" -eq 0 ]; then
    local sb; sb=$(wc -c < "$SLOT" 2>/dev/null | tr -d ' '); sb="${sb:-0}"
    [ "$sb" -eq 0 ] && RC=3
  fi
  printf '[codex-worker] attempt %s end %s rc=%s\n' "$n" "$(now)" "$RC" >> "$TRACE"
}

RETRIED=""
run_attempt "$MODEL" 1
if [ "$RC" -ne 0 ] && [ "$RC" -ne 124 ] && [ -n "$RETRY_MODEL" ]; then
  RETRIED="$RETRY_MODEL"
  printf 'CODEX_RETRY=%s (attempt 1 rc=%s)\n' "$RETRY_MODEL" "$RC" >> "$TRACE"
  run_attempt "$RETRY_MODEL" 2
fi
rm -f "$PROMPT_TMP"

OUT_BYTES=$(wc -c < "$OUT" 2>/dev/null | tr -d ' ')
SLOT_BYTES=""
[ -n "$SLOT" ] && { SLOT_BYTES=$(wc -c < "$SLOT" 2>/dev/null | tr -d ' '); SLOT_BYTES="${SLOT_BYTES:-0}"; }
{
  printf '[codex-worker] end %s out=%s bytes' "$(now)" "${OUT_BYTES:-0}"
  [ -n "$SLOT" ] && printf ' slot=%s bytes' "$SLOT_BYTES"
  printf '\nCODEX_EXIT=%s' "$RC"
  [ "$RC" -eq 3 ] && printf ' (empty slot: %s)' "$SLOT"
  printf '\n'
} >> "$TRACE"

printf 'CODEX_EXIT=%s out=%s (%s bytes)' "$RC" "$OUT" "${OUT_BYTES:-0}"
[ -n "$SLOT" ]    && printf ' slot=%s (%s bytes)' "$SLOT" "$SLOT_BYTES"
[ -n "$RETRIED" ] && printf ' retry=%s' "$RETRIED"
printf ' trace=%s\n' "$TRACE"
exit "$RC"
