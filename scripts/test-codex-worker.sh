#!/usr/bin/env bash
# test-codex-worker.sh — codex-worker.sh 의 결정적 계약 회귀 (dry-run + 가짜 codex 실행, 실제 codex 호출 없음)
# 실행: bash scripts/test-codex-worker.sh   (통과 시 exit 0, 실패 시 실패 케이스 목록 + exit 1)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
W="$HERE/codex-worker.sh"
T="$(mktemp -d "${TMPDIR:-/tmp}/codex-worker-test.XXXXXX")"
trap 'rm -rf "$T"' EXIT
FAIL=0; PASS=0
ok()   { PASS=$((PASS+1)); }
fail() { FAIL=$((FAIL+1)); echo "  ✗ $1" >&2; }
check() { # check <케이스> <조건 결과 0/1>
  if [ "$2" -eq 0 ]; then ok; else fail "$1"; fi
}

mkdir -p "$T/run/prompts" "$T/run/outputs" "$T/codex-home/agents" "$T/bin"
printf '지시문은 outputs/a.md 에 Write.\n' > "$T/run/prompts/a.md"
printf '{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}\n' > "$T/schema.json"
cat > "$T/codex-home/agents/fake.toml" <<'EOF'
name = "fake"
description = "테스트용"
model = "gpt-5.6-sol"
model_reasoning_effort = "xhigh"
sandbox_mode = "read-only"
developer_instructions = """
너는 **테스트 에이전트**다. 경로는 C:\\tmp 처럼 백슬래시가 있을 수 있다.
"""
EOF
# 가짜 codex: FAKE_CODEX_FAIL_TIMES 번째 호출까지 exit 1, 그 뒤 -o 파일에 ok 를 쓰고 exit 0. FAKE_CODEX_SLEEP 초 대기.
cat > "$T/bin/codex" <<'EOF'
#!/usr/bin/env bash
n=$(cat "$FAKE_CODEX_COUNT" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$FAKE_CODEX_COUNT"
out=""; while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift 2 ;; *) shift ;; esac; done
cat > /dev/null
[ -n "${FAKE_CODEX_SLEEP:-}" ] && sleep "$FAKE_CODEX_SLEEP"
if [ "$n" -le "${FAKE_CODEX_FAIL_TIMES:-0}" ]; then echo "fake failure $n"; exit 1; fi
[ -n "$out" ] && printf 'ok' > "$out"
echo "fake done $n"; exit 0
EOF
chmod +x "$T/bin/codex"

# 1. 기본값: gpt-6-astra / medium / workspace-write, approval never, 프롬프트 파일 조립, retry auto→terra
o="$(bash "$W" --cd "$T/run" --prompt-file "$T/run/prompts/a.md" --out "$T/run/outputs/a.last.md" --dry-run 2>&1)"; rc=$?
check "1a 기본 dry-run exit 0"            "$([ $rc -eq 0 ]; echo $?)"
check "1b 기본 모델 gpt-6-astra"          "$(grep -q -- '-m gpt-6-astra' <<<"$o"; echo $?)"
check "1c 기본 effort medium"             "$(grep -q 'model_reasoning_effort=\\"medium\\"' <<<"$o"; echo $?)"
check "1d 기본 sandbox workspace-write"   "$(grep -q -- '--sandbox workspace-write' <<<"$o"; echo $?)"
check "1e approval_policy never 고정"     "$(grep -q 'approval_policy=\\"never\\"' <<<"$o"; echo $?)"
check "1f --ephemeral·--skip-git-repo-check" "$(grep -q -- '--ephemeral --skip-git-repo-check' <<<"$o"; echo $?)"
check "1g 조립 프롬프트 = 지시문 파일"     "$(diff -q "$T/run/prompts/a.md" "$T/run/outputs/a.last.md.prompt" >/dev/null; echo $?)"
check "1h 기본은 network·web·schema 없음"  "$(! grep -q -E 'network_access|web_search|output-schema' <<<"$o"; echo $?)"
check "1i 기본 retry auto → gpt-5.6-terra" "$(grep -q 'retry=gpt-5.6-terra' <<<"$o"; echo $?)"

# 2. --agent: toml 의 model/effort/sandbox 가 기본값, developer_instructions 가 앞에 붙고 백슬래시 복원, retry auto→astra
o="$(CODEX_HOME="$T/codex-home" bash "$W" --cd "$T/run" --agent fake --prompt-file "$T/run/prompts/a.md" --out "$T/run/outputs/b.last.md" --dry-run 2>&1)"; rc=$?
check "2a agent dry-run exit 0"           "$([ $rc -eq 0 ]; echo $?)"
check "2b agent 모델 gpt-5.6-sol"         "$(grep -q -- '-m gpt-5.6-sol' <<<"$o"; echo $?)"
check "2c agent effort xhigh"             "$(grep -q 'model_reasoning_effort=\\"xhigh\\"' <<<"$o"; echo $?)"
check "2d agent sandbox read-only"        "$(grep -q -- '--sandbox read-only' <<<"$o"; echo $?)"
check "2e 지시문이 프롬프트 앞에"          "$(head -1 "$T/run/outputs/b.last.md.prompt" | grep -q '테스트 에이전트'; echo $?)"
check "2f 백슬래시 복원(C:\\tmp)"          "$(grep -q 'C:\\tmp' "$T/run/outputs/b.last.md.prompt"; echo $?)"
check "2g 작업 지시가 뒤에"                "$(grep -q '이번 작업 지시' "$T/run/outputs/b.last.md.prompt" && grep -q 'outputs/a.md' "$T/run/outputs/b.last.md.prompt"; echo $?)"
check "2h 비-astra 티어 retry auto → astra" "$(grep -q 'retry=gpt-6-astra' <<<"$o"; echo $?)"

# 3. 명시 플래그가 agent 값보다 우선 + --network/--web/--schema/--retry/--no-retry
o="$(CODEX_HOME="$T/codex-home" bash "$W" --cd "$T/run" --agent fake --model gpt-6-astra --effort high --sandbox workspace-write --network --web --schema "$T/schema.json" --retry gpt-5.5 --prompt 'x' --out "$T/run/outputs/c.last.md" --dry-run 2>&1)"
check "3a 명시 모델 우선"                 "$(grep -q -- '-m gpt-6-astra' <<<"$o"; echo $?)"
check "3b 명시 effort 우선"               "$(grep -q 'model_reasoning_effort=\\"high\\"' <<<"$o"; echo $?)"
check "3c 명시 sandbox 우선"              "$(grep -q -- '--sandbox workspace-write' <<<"$o"; echo $?)"
check "3d --network → network_access=true" "$(grep -q 'sandbox_workspace_write.network_access=true' <<<"$o"; echo $?)"
check "3e --web → web_search=live"        "$(grep -q 'web_search=\\"live\\"' <<<"$o"; echo $?)"
check "3f --schema → --output-schema"     "$(grep -q -- "--output-schema $T/schema.json" <<<"$o"; echo $?)"
check "3g --retry 명시 모델"              "$(grep -q 'retry=gpt-5.5' <<<"$o"; echo $?)"
o="$(bash "$W" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/c2.last.md" --no-retry --dry-run 2>&1)"
check "3h --no-retry → retry=none"        "$(grep -q 'retry=none' <<<"$o"; echo $?)"
check "3h2 기본은 aside MCP 주입 없음"      "$(! grep -q 'mcp_servers.aside' <<<"$o"; echo $?)"
printf '#!/bin/sh\nexit 0\n' > "$T/bin/aside"; chmod +x "$T/bin/aside"
o="$(ASIDE_BIN="$T/bin/aside" bash "$W" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/c4.last.md" --browser --dry-run 2>&1)"
check "3j --browser → aside MCP command 주입" "$(grep -q "mcp_servers.aside.command=\\\\\"$T/bin/aside\\\\\"" <<<"$o"; echo $?)"
check "3k --browser → args=[mcp]·approval approve" "$(grep -q -F 'mcp_servers.aside.args=\[\"mcp\"\]' <<<"$o" && grep -q -F 'tools.repl.approval_mode=\"approve\"' <<<"$o"; echo $?)"
check "3l --browser → 레인 규칙이 프롬프트 앞에" "$(head -1 "$T/run/outputs/c4.last.md.prompt" | grep -q '브라우저 레인 규칙' && grep -q '승인 경계' "$T/run/outputs/c4.last.md.prompt"; echo $?)"
check "3m --browser dry-run 표시 browser=1"  "$(grep -q 'browser=1' <<<"$o"; echo $?)"
ASIDE_BIN="$T/nope-aside" bash "$W" --cd "$T/run" --prompt 'x' --out "$T/o" --browser --dry-run >/dev/null 2>&1; check "3n --browser 인데 aside 없음 거부(exit 2)" "$([ $? -eq 2 ]; echo $?)"
o="$(bash "$W" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/c3.last.md" --retry gpt-6-astra --dry-run 2>&1)"
check "3i retry 모델 = 본 모델이면 none"   "$(grep -q 'retry=none' <<<"$o"; echo $?)"

# 4. 거부 조건
bash "$W" --cd "$T/run" --prompt 'x' --out "$T/o" --effort ultra --dry-run >/dev/null 2>&1; check "4a effort ultra 거부(exit 2)" "$([ $? -eq 2 ]; echo $?)"
bash "$W" --cd "$T/run" --out "$T/o" --dry-run >/dev/null 2>&1;                  check "4b 지시문 없음 거부(exit 2)" "$([ $? -eq 2 ]; echo $?)"
bash "$W" --prompt 'x' --out "$T/o" --dry-run >/dev/null 2>&1;                   check "4c --cd 없음 거부(exit 2)"   "$([ $? -eq 2 ]; echo $?)"
bash "$W" --cd "$T/run" --prompt 'x' --out "$T/o" --sandbox yolo --dry-run >/dev/null 2>&1; check "4d 미지원 sandbox 거부(exit 2)" "$([ $? -eq 2 ]; echo $?)"
CODEX_HOME="$T/codex-home" bash "$W" --cd "$T/run" --agent nope --prompt 'x' --out "$T/o" --dry-run >/dev/null 2>&1; check "4e 없는 agent 거부(exit 2)" "$([ $? -eq 2 ]; echo $?)"
bash "$W" --cd "$T/run" --prompt 'x' --out "$T/o" --timeout abc --dry-run >/dev/null 2>&1; check "4f timeout 비정수 거부(exit 2)" "$([ $? -eq 2 ]; echo $?)"
bash "$W" --cd "$T/run" --prompt 'x' --out "$T/o" --schema "$T/nope.json" --dry-run >/dev/null 2>&1; check "4g 없는 schema 거부(exit 2)" "$([ $? -eq 2 ]; echo $?)"

# 5. codex 미설치 → CODEX_EXIT=127 트레이스 (실행 경로, PATH 비움)
PATH="/usr/bin:/bin" bash "$W" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/d.last.md" >/dev/null 2>&1; rc=$?
check "5a codex 미설치 exit 127"           "$([ $rc -eq 127 ]; echo $?)"
check "5b 트레이스에 CODEX_EXIT=127"        "$(grep -q '^CODEX_EXIT=127' "$T/run/outputs/d.last.md.trace"; echo $?)"

# 6. 가짜 codex 로 실행 경로: 재시도·슬롯·타임아웃
fake() { # fake <fail_times> <sleep> <count_file> <args...>
  local ft="$1" sl="$2" cf="$3"; shift 3
  PATH="$T/bin:$PATH" FAKE_CODEX_FAIL_TIMES="$ft" FAKE_CODEX_SLEEP="$sl" FAKE_CODEX_COUNT="$cf" bash "$W" "$@" >/dev/null 2>&1
}
fake 0 "" "$T/c6a" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/e.last.md"; rc=$?
check "6a 1회 성공 → exit 0"               "$([ $rc -eq 0 ]; echo $?)"
check "6b -o 파일에 최종 메시지"            "$([ "$(cat "$T/run/outputs/e.last.md")" = "ok" ]; echo $?)"
check "6c 호출 1회"                        "$([ "$(cat "$T/c6a")" = "1" ]; echo $?)"
check "6d 트레이스 CODEX_EXIT=0·재시도 없음" "$(grep -q '^CODEX_EXIT=0' "$T/run/outputs/e.last.md.trace" && ! grep -q 'CODEX_RETRY' "$T/run/outputs/e.last.md.trace"; echo $?)"

fake 1 "" "$T/c6e" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/f.last.md"; rc=$?
check "6e 1회 실패 → 자동 재시도 성공 exit 0" "$([ $rc -eq 0 ]; echo $?)"
check "6f 호출 2회"                        "$([ "$(cat "$T/c6e")" = "2" ]; echo $?)"
check "6g 트레이스 CODEX_RETRY=gpt-5.6-terra" "$(grep -q '^CODEX_RETRY=gpt-5.6-terra' "$T/run/outputs/f.last.md.trace"; echo $?)"
check "6h 2차 시도가 terra 로"              "$(grep -q 'attempt 2 start .* model=gpt-5.6-terra' "$T/run/outputs/f.last.md.trace"; echo $?)"

fake 1 "" "$T/c6i" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/g.last.md" --no-retry; rc=$?
check "6i --no-retry → 실패 그대로 exit 1"  "$([ $rc -eq 1 ]; echo $?)"
check "6j --no-retry 호출 1회"              "$([ "$(cat "$T/c6i")" = "1" ]; echo $?)"

fake 2 "" "$T/c6k" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/h.last.md"; rc=$?
check "6k 2회 실패 → exit 1 (재시도는 1회만)" "$([ $rc -eq 1 ] && [ "$(cat "$T/c6k")" = "2" ]; echo $?)"

fake 0 "" "$T/c6l" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/i.last.md" --slot "$T/run/outputs/never.md"; rc=$?
check "6l 빈 슬롯 → 재시도 후에도 exit 3"    "$([ $rc -eq 3 ] && [ "$(cat "$T/c6l")" = "2" ]; echo $?)"
check "6m 트레이스 empty slot 표기"          "$(grep -q '^CODEX_EXIT=3 (empty slot' "$T/run/outputs/i.last.md.trace"; echo $?)"

fake 0 30 "$T/c6n" --cd "$T/run" --prompt 'x' --out "$T/run/outputs/j.last.md" --timeout 5; rc=$?
check "6n 타임아웃 → exit 124"              "$([ $rc -eq 124 ]; echo $?)"
check "6o 타임아웃은 재시도 없음(호출 1회)"   "$([ "$(cat "$T/c6n")" = "1" ] && ! grep -q 'CODEX_RETRY' "$T/run/outputs/j.last.md.trace"; echo $?)"
check "6p 트레이스 CODEX_EXIT=124"           "$(grep -q '^CODEX_EXIT=124' "$T/run/outputs/j.last.md.trace"; echo $?)"

echo "codex-worker tests: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
