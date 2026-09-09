#!/usr/bin/env bash
# Phase 1 러너 — 문제집 케이스를 "기본(vanilla)" Claude Code / Codex 팔로 실행하고 증거·메트릭을 남긴다.
# 사용: bash run-arm.sh <claude-vanilla|codex-vanilla> <case-key> [model]
#   case-key = spec-building__case-01 | spec-building__case-03 | live-verify__case-01
#            | perf-review__case-01 | service-planning__case-01 | tech-deciding__case-01
# 전제: prep-clean-envs.sh 가 만든 CLEAN_CLAUDE_CFG / CLEAN_CODEX_HOME 환경변수(또는 /tmp/ab-clean-envs.env).
# 팔은 프롬프트 파일 1개(prompts/<case-key>.md)만 받는다 — ANSWER·스킬 본문 비공개. 개입 없음(헤드리스).
set -euo pipefail
ARM="${1:?arm}"; KEY="${2:?case-key}"; MODEL="${3:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../../.." && pwd)"
[ -f /tmp/ab-clean-envs.env ] && source /tmp/ab-clean-envs.env
SKILL="${KEY%%__*}"; CASE="${KEY##*__}"
CASE_DIR="$(ls -d "$ROOT/evals/$SKILL/$CASE"-* | head -1)"
PROMPT_FILE="$HERE/prompts/$KEY.md"; [ -f "$PROMPT_FILE" ] || { echo "no prompt: $PROMPT_FILE" >&2; exit 2; }
OUT="$HERE/runs/$KEY/$ARM"; mkdir -p "$OUT"

# ── 픽스처 부트스트랩 (케이스 setup.sh 그대로) ──
SETUP_LOG="$(bash "$CASE_DIR/setup.sh" 2>&1)"; echo "$SETUP_LOG" > "$OUT/setup.log"
WORK="$(echo "$SETUP_LOG" | grep -E '^(RUN_DIR|WORK)=' | tail -1 | cut -d= -f2-)"
ORIGIN="$(echo "$SETUP_LOG" | grep -E '^ORIGIN_DIR=' | tail -1 | cut -d= -f2- || true)"
[ -d "$WORK" ] || { echo "setup failed: no WORK dir" >&2; exit 3; }
echo "WORK=$WORK" > "$OUT/env.txt"; [ -n "$ORIGIN" ] && echo "ORIGIN=$ORIGIN" >> "$OUT/env.txt"
if [ -d "$WORK/.git" ]; then
  git -C "$WORK" rev-parse HEAD > "$OUT/head-before.txt"
  git -C "$WORK" -c user.email=eval@local -c user.name=eval status --porcelain > "$OUT/status-before.txt" || true
fi

# ── 실행 (헤드리스, 개입 0) ──
PROMPT="$(cat "$PROMPT_FILE")"
START=$(date +%s)
case "$ARM" in
  claude-vanilla)
    : "${CLEAN_CLAUDE_CFG:?run prep-clean-envs.sh first}"
    MODEL="${MODEL:-claude-fable-5-1}"
    ( cd "$WORK" && CLAUDE_CONFIG_DIR="$CLEAN_CLAUDE_CFG" claude -p "$PROMPT" \
        --dangerously-skip-permissions --output-format json --model "$MODEL" --max-turns 200 < /dev/null \
        > "$OUT/result.json" 2> "$OUT/stderr.log" ) || echo "claude exit=$?" >> "$OUT/stderr.log"
    python3 - "$OUT" <<'PY'
import json,sys,os
out=sys.argv[1]
try: d=json.load(open(os.path.join(out,'result.json')))
except Exception as ex: d={'result':'','is_error':True,'terminal_reason':'unparseable: '+str(ex)[:80]}
open(os.path.join(out,'final.md'),'w').write(d.get('result') or '')
u=d.get('usage',{})
m={'arm':'claude-vanilla','model':list(d.get('modelUsage',{}).keys()),'cost_usd':d.get('total_cost_usd'),
   'duration_ms':d.get('duration_ms'),'api_ms':d.get('duration_api_ms'),'turns':d.get('num_turns'),
   'is_error':d.get('is_error'),'terminal':d.get('terminal_reason'),
   'input_tokens':u.get('input_tokens'),'output_tokens':u.get('output_tokens'),
   'cache_read':u.get('cache_read_input_tokens'),'cache_write':u.get('cache_creation_input_tokens'),
   'subagents':(d.get('subagent_stats') or {}).get('spawned')}
json.dump(m,open(os.path.join(out,'metrics.json'),'w'),ensure_ascii=False,indent=1)
PY
    ;;
  codex-vanilla)
    : "${CLEAN_CODEX_HOME:?run prep-clean-envs.sh first}"
    ( cd "$WORK" && CODEX_HOME="$CLEAN_CODEX_HOME" codex exec --ephemeral --skip-git-repo-check -C "$WORK" \
        --dangerously-bypass-approvals-and-sandbox ${MODEL:+-m "$MODEL"} --json -o "$OUT/final.md" "$PROMPT" < /dev/null \
        > "$OUT/events.jsonl" 2> "$OUT/stderr.log" ) || echo "codex exit=$?" >> "$OUT/stderr.log"
    python3 - "$OUT" <<'PY'
import json,sys,os
out=sys.argv[1]; tot={}; turns=0; model=None
for line in open(os.path.join(out,'events.jsonl'),encoding='utf-8',errors='replace'):
    try: e=json.loads(line)
    except Exception: continue
    if e.get('type')=='turn.completed':
        turns+=1
        for k,v in (e.get('usage') or {}).items(): tot[k]=tot.get(k,0)+(v or 0)
    if e.get('type')=='thread.started': model=e.get('model') or model
m={'arm':'codex-vanilla','model':model,'turns':turns,**{('tok_'+k):v for k,v in tot.items()}}
json.dump(m,open(os.path.join(out,'metrics.json'),'w'),ensure_ascii=False,indent=1)
PY
    ;;
  *) echo "unknown arm $ARM" >&2; exit 2;;
esac
END=$(date +%s)
python3 - "$OUT" "$START" "$END" <<'PY'
import json,sys,os
out,s,e=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]); p=os.path.join(out,'metrics.json')
m=json.load(open(p)); m['wall_s']=e-s; json.dump(m,open(p,'w'),ensure_ascii=False,indent=1)
PY

# ── 사후 증거 (에이전트 보고가 아니라 실상태) ──
if [ -d "$WORK/.git" ]; then
  git -C "$WORK" log --oneline --all > "$OUT/git-log.txt"
  git -C "$WORK" status --porcelain > "$OUT/status-after.txt" || true
  git -C "$WORK" diff "$(cat "$OUT/head-before.txt")" > "$OUT/diff-vs-start.patch" || true
  git -C "$WORK" diff > "$OUT/diff-worktree.patch" || true
  git -C "$WORK" show --stat --format='%H %s' HEAD > "$OUT/head-show.txt" || true
fi
[ -n "$ORIGIN" ] && git -C "$ORIGIN" log --oneline --all > "$OUT/origin-log.txt" || true
find "$WORK" -type f -not -path '*/.git/*' -not -path '*/node_modules/*' | sed "s|$WORK/||" | sort > "$OUT/files-after.txt"
echo "DONE $ARM $KEY → $OUT (WORK=$WORK)"
cat "$OUT/metrics.json"