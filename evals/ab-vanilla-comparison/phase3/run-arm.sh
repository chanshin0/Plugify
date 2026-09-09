#!/usr/bin/env bash
# Phase 3 러너 — 과제 1개를 팔 1개로 헤드리스 실행하고 스냅샷·메트릭·최종 메시지를 봉인한다.
# 사용: bash run-arm.sh <plugify|claude-vanilla|codex-vanilla> <01|02|03> <run번호> [--followup]
#   plugify        : 사용자의 평소 설정(~/.claude) 그대로 `claude -p` — 스킬·훅·전역 CLAUDE.md·Codex 워커 정책 포함
#   claude-vanilla : 깨끗한 CLAUDE_CONFIG_DIR (phase1/prep-clean-envs.sh 가 만든 것, /tmp/ab-clean-envs.env)
#   codex-vanilla  : 깨끗한 CODEX_HOME
# 실행 디렉터리는 ~/ab-phase3-runs/<task>/<arm>/run<k>/work (macOS /tmp 자동 정리 회피 — PREREG §3).
# 팔은 TASK-SPEC.md 전문만 프롬프트로 받는다. judge/·PREREG·FOLLOWUP 은 작업 디렉터리에 복사하지 않는다.
set -euo pipefail
ARM="${1:?arm}"; TASK="${2:?task 01|02|03}"; RUN="${3:?run k}"; MODE="${4:-main}"
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f /tmp/ab-clean-envs.env ] && source /tmp/ab-clean-envs.env
TASK_DIR="$(ls -d "$HERE/tasks/$TASK"-* | head -1)"; TASK_KEY="$(basename "$TASK_DIR")"
BASE="$HOME/ab-phase3-runs/$TASK_KEY/$ARM/run$RUN"; WORK="$BASE/work"; OUT="$BASE"
if [ "$MODE" = "--followup" ]; then
  # 후속 라운드: 본 실행 스냅샷 위에서 새 세션. 프롬프트 = FOLLOWUP-SEALED.md 의 해당 과제 인용문 한 줄.
  [ -d "$WORK" ] || { echo "본 실행 스냅샷 없음: $WORK" >&2; exit 3; }
  OUT="$BASE/followup"; mkdir -p "$OUT"
  PROMPT="$(awk -v k="## $TASK " '$0 ~ "^## "{on=($0 ~ "^"k)} on && /^> /{sub(/^> /,""); print}' "$HERE/FOLLOWUP-SEALED.md")"
  [ -n "$PROMPT" ] || { echo "후속 과제 문장을 못 찾음" >&2; exit 3; }
else
  [ -e "$WORK" ] && { echo "이미 존재: $WORK (다른 run 번호를 쓰거나 지워라)" >&2; exit 3; }
  mkdir -p "$WORK"
  # 팔에게 주는 것: TASK-SPEC.md + 입력 데이터/픽스처. judge/ 는 절대 복사하지 않는다.
  cp "$TASK_DIR/TASK-SPEC.md" "$WORK/"
  [ -d "$TASK_DIR/data" ] && cp -R "$TASK_DIR/data" "$WORK/data"
  if [ -d "$TASK_DIR/fixture" ]; then
    # INIT.sh 는 자기 디렉터리로 cd 하므로 레포 안의 fixture/ 를 git init 해 버린다 — 여기서는 인라인으로 초기화한다.
    cp -R "$TASK_DIR/fixture/." "$WORK/"; rm -f "$WORK/INIT.sh"
    ( cd "$WORK" && git init -q -b main && git add -A && git -c user.email=eval@local -c user.name=eval commit -qm "초기 상태" )
  else
    ( cd "$WORK" && git init -q -b main && git -c user.email=eval@local -c user.name=eval commit -q --allow-empty -m "빈 레포" )
  fi
  PROMPT="$(cat "$TASK_DIR/TASK-SPEC.md")"
fi
git -C "$WORK" rev-parse HEAD > "$OUT/head-before.txt"
git -C "$WORK" status --porcelain > "$OUT/status-before.txt" || true
echo "arm=$ARM task=$TASK_KEY run=$RUN mode=$MODE work=$WORK started=$(date -u +%FT%TZ)" | tee "$OUT/env.txt"

WALL_CAP="${WALL_CAP:-3600}"   # PREREG §3: 벽시계 60분 상한 — perl alarm 은 exec 후에도 살아남아 SIGALRM 으로 종료(exit 142)
START=$(date +%s)
case "$ARM" in
  plugify)
    # 평소 설정 그대로. 헤드리스라 승인 경계에서 멈추면 그 상태로 끝난다(A 축 데이터).
    ( cd "$WORK" && perl -e 'alarm shift; exec @ARGV' "$WALL_CAP" claude -p "$PROMPT" --dangerously-skip-permissions --output-format json --max-turns 300 < /dev/null \
        > "$OUT/result.json" 2> "$OUT/stderr.log" ) || echo "claude exit=$?" >> "$OUT/stderr.log"
    ;;
  claude-vanilla)
    : "${CLEAN_CLAUDE_CFG:?phase1/prep-clean-envs.sh 먼저}"
    ( cd "$WORK" && CLAUDE_CONFIG_DIR="$CLEAN_CLAUDE_CFG" perl -e 'alarm shift; exec @ARGV' "$WALL_CAP" claude -p "$PROMPT" --dangerously-skip-permissions \
        --output-format json --model claude-fable-5-1 --max-turns 300 < /dev/null \
        > "$OUT/result.json" 2> "$OUT/stderr.log" ) || echo "claude exit=$?" >> "$OUT/stderr.log"
    ;;
  codex-vanilla)
    : "${CLEAN_CODEX_HOME:?phase1/prep-clean-envs.sh 먼저}"
    ( cd "$WORK" && CODEX_HOME="$CLEAN_CODEX_HOME" perl -e 'alarm shift; exec @ARGV' "$WALL_CAP" codex exec --ephemeral --skip-git-repo-check -C "$WORK" \
        --dangerously-bypass-approvals-and-sandbox --json -o "$OUT/final.md" "$PROMPT" < /dev/null \
        > "$OUT/events.jsonl" 2> "$OUT/stderr.log" ) || echo "codex exit=$?" >> "$OUT/stderr.log"
    ;;
  *) echo "unknown arm $ARM" >&2; exit 2;;
esac
END=$(date +%s)

# ── 메트릭 (팔 보고가 아니라 실행기 출력) ──
python3 - "$ARM" "$OUT" "$START" "$END" <<'PY'
import json,sys,os
arm,out,s,e=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
m={'arm':arm,'wall_s':e-s}
if arm in ('plugify','claude-vanilla'):
    try: d=json.load(open(os.path.join(out,'result.json')))
    except Exception as ex: d={'result':'','is_error':True,'terminal_reason':'unparseable: '+str(ex)[:80]}
    open(os.path.join(out,'final.md'),'w').write(d.get('result') or '')
    u=d.get('usage',{})
    m.update({'model':list(d.get('modelUsage',{}).keys()),'cost_usd':d.get('total_cost_usd'),'duration_ms':d.get('duration_ms'),
      'api_ms':d.get('duration_api_ms'),'turns':d.get('num_turns'),'is_error':d.get('is_error'),'terminal':d.get('terminal_reason'),
      'input_tokens':u.get('input_tokens'),'output_tokens':u.get('output_tokens'),'cache_read':u.get('cache_read_input_tokens'),
      'cache_write':u.get('cache_creation_input_tokens'),'subagents':(d.get('subagent_stats') or {}).get('spawned'),'session_id':d.get('session_id')})
else:
    tot={}; turns=0; model=None
    for line in open(os.path.join(out,'events.jsonl'),encoding='utf-8',errors='replace'):
        try: ev=json.loads(line)
        except Exception: continue
        if ev.get('type')=='turn.completed':
            turns+=1
            for k,v in (ev.get('usage') or {}).items(): tot[k]=tot.get(k,0)+(v or 0)
        if ev.get('type')=='thread.started': model=ev.get('model') or model
    m.update({'model':model,'turns':turns,**{('tok_'+k):v for k,v in tot.items()}})
json.dump(m,open(os.path.join(out,'metrics.json'),'w'),ensure_ascii=False,indent=1)
PY

# ── 실상태 증거 + 스냅샷 봉인 (판정 전까지 열지 않는다) ──
git -C "$WORK" log --oneline --all > "$OUT/git-log.txt" || true
git -C "$WORK" status --porcelain > "$OUT/status-after.txt" || true
git -C "$WORK" diff "$(cat "$OUT/head-before.txt")" --stat > "$OUT/diff-stat.txt" || true
find "$WORK" -type f -not -path '*/.git/*' -not -path '*/node_modules/*' | sed "s|$WORK/||" | sort > "$OUT/files-after.txt"
# Codex 워커 트레이스(plugify 팔) — 워커 수·CODEX_EXIT 집계용
grep -rl 'CODEX_EXIT=' "$WORK" 2>/dev/null | sort > "$OUT/codex-worker-traces.txt" || true
tar -C "$BASE" -czf "$OUT/snapshot.tgz" work
shasum -a 256 "$OUT/snapshot.tgz" > "$OUT/snapshot.sha256"
echo "DONE $ARM $TASK_KEY run$RUN mode=$MODE → $OUT"; cat "$OUT/metrics.json"
