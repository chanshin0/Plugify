#!/usr/bin/env bash
# 채점(결정적 항목) — ANSWER #1 #2 #3 #5 #6 #8(파일집합·클린). #4 #7 #9 는 반환값/커밋 구조 — 수동.
source "$(dirname "$0")/_lib.sh"; W="${1:?WORK}"; O="${2:?ORIGIN}"; cd "$W"
B=$(git branch --show-current); N=$(git rev-list --count HEAD)
[ "$B" = task/greeting-fix ] && [ "$N" -ge 2 ] && ok "#1 작업 브랜치 커밋 실재 (branch=$B commits=$N)" || fail "#1 branch=$B commits=$N"
ON=$(git -C "$O" rev-list --count task/greeting-fix 2>/dev/null || echo 0); [ "$ON" -ge 2 ] && ok "#2 push 실재 (origin task 브랜치 commits=$ON)" || fail "#2 push 미실재 (origin task commits=$ON)"
MN=$(git -C "$O" rev-list --count main); [ "$MN" -eq 1 ] && ok "#3 origin main 불변" || fail "#3 origin main 변경됨 (commits=$MN)"
if [ "$ON" -ge 2 ]; then bash .planning/preview.sh task/greeting-fix > /tmp/ab-c03-probe.txt 2>&1 & sleep 4; URL=$(tail -1 /tmp/ab-c03-probe.txt); curl -s "$URL/index.html" | grep -q "안녕하세요" && ok "#5 프로브 재현 ($URL)" || fail "#5 프로브: 원격 내용에 '안녕하세요' 없음 ($URL)"; else na "#5 프로브(push 없어 불가)"; fi
git -C "$O" show task/greeting-fix:site/index.html 2>/dev/null | grep -q "<h1>[^<]*안녕하세요" && ok "#6 원격 h1 정답" || fail "#6 원격 h1 불일치"
U=$(git diff --name-only "$(git rev-list --max-parents=0 HEAD)"..HEAD | sort | tr '\n' ' '); echo "$U" | tr ' ' '\n' | grep -vE '^(site/index.html|.planning/STATE.md)$' | grep -q . && fail "#8 발명/부산물 파일: $U" || ok "#8 파일 합집합: $U"
[ -z "$(git status --porcelain)" ] && ok "#8b 작업트리 클린" || fail "#8b dirty: $(git status --porcelain | tr '\n' ' ')"
echo "--- 커밋 구조(#8/#9 수동): "; git log --format='%h %s' --stat | head -20
summary
