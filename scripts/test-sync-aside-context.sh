#!/usr/bin/env bash
# sync-aside-context.py 회귀: 임시 ASIDE_HOME/CODEX_HOME 에서 합성·--check·--ensure 계약을 검증한다.
set -u
W="$(cd "$(dirname "$0")/.." && pwd)/scripts/sync-aside-context.py"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; fail=0
check() { if [ "$2" = "0" ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }

# 1) Aside 미설치 머신: --ensure 는 조용히 0
ASIDE_HOME="$T/no-aside" CODEX_HOME="$T/codex" python3 "$W" --ensure >/dev/null 2>&1; check "1 aside 없음 → ensure exit 0" "$?"

# 2) 합성: preamble + router 사본
mkdir -p "$T/aside/u/0" "$T/codex"; printf '# Router\n\n- office: `/x/office-context`\n' > "$T/codex/AGENTS.md"
o="$(ASIDE_HOME="$T/aside" CODEX_HOME="$T/codex" python3 "$W" 2>&1)"; check "2a 생성 exit 0" "$?"
f="$T/aside/u/0/AGENTS.md"
head -1 "$f" | grep -q 'plugify-aside-context:v1'; check "2b 마커가 첫 줄" "$?"
grep -q 'Aside 세션 공통 규칙' "$f" && grep -q 'Project "Workspace"' "$f"; check "2c preamble 포함" "$?"
grep -q 'begin: mirrored' "$f" && grep -q '/x/office-context' "$f" && grep -q 'end: mirrored' "$f"; check "2d router 사본이 마커 사이에" "$?"

# 3) 멱등: 재실행은 'up to date', ensure 는 무출력
o="$(ASIDE_HOME="$T/aside" CODEX_HOME="$T/codex" python3 "$W" 2>&1)"; grep -q 'up to date' <<<"$o"; check "3a 재실행 up to date" "$?"
o="$(ASIDE_HOME="$T/aside" CODEX_HOME="$T/codex" python3 "$W" --ensure 2>&1)"; [ -z "$o" ]; check "3b ensure 무출력" "$?"
ASIDE_HOME="$T/aside" CODEX_HOME="$T/codex" python3 "$W" --check >/dev/null 2>&1; check "3c check ok → 0" "$?"

# 4) 원본 변경 → stale → ensure 가 갱신
printf '\n- 추가 규칙\n' >> "$T/codex/AGENTS.md"
ASIDE_HOME="$T/aside" CODEX_HOME="$T/codex" python3 "$W" --check >/dev/null 2>&1; [ $? -eq 1 ]; check "4a stale → check exit 1" "$?"
ASIDE_HOME="$T/aside" CODEX_HOME="$T/codex" python3 "$W" --ensure >/dev/null 2>&1; grep -q '추가 규칙' "$f"; check "4b ensure 가 갱신" "$?"

# 5) router 없음 → exit 1
rm "$T/codex/AGENTS.md"; ASIDE_HOME="$T/aside" CODEX_HOME="$T/codex" python3 "$W" >/dev/null 2>&1; [ $? -eq 1 ]; check "5 router 없음 → exit 1" "$?"

echo "sync-aside-context tests: $pass passed, $fail failed"; [ "$fail" -eq 0 ]
