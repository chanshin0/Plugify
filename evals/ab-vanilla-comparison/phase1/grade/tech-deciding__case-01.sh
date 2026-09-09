#!/usr/bin/env bash
# 채점(결정적 항목) — ANSWER B1 B3(섹션·URL≥3) B5(서버형 키워드). A1/A2/B2/B4 는 워크플로우 전용 또는 수동.
source "$(dirname "$0")/_lib.sh"; W="${1:?WORK}"; cd "$W"; A=.planning/decisions/001-memo-search.md
[ -f "$A" ] && ok "B1 ADR 실재 ($A, $(wc -l < $A) lines)" || { fail "B1 ADR 없음 — .planning 아래: $(find .planning -type f | tr '\n' ' ')"; summary; exit 0; }
for k in "컨텍스트|Context|배경" "결정|Decision" "근거|Rationale|출처" "대안|Alternatives|탈락" "뒤집|Revisit|재검토|번복"; do grep -qiE "$k" "$A" && ok "B3 섹션: $k" || fail "B3 섹션 누락: $k"; done
U=$(LC_ALL=C grep -oE 'https?://[^ )>\]]+' "$A" | sort -u | wc -l | tr -d ' '); [ "$U" -ge 3 ] && ok "B3 출처 URL $U개" || fail "B3 출처 URL $U개 (<3)"
grep -iE 'elasticsearch|meilisearch|typesense|opensearch|solr' "$A" | grep -viE '탈락|대안|제외|not|금지|서버' | grep -q . && echo "  B5 수동: 서버형 검색엔진 언급 있음 — 결정인지 탈락인지 확인" || ok "B5 서버형 엔진을 결정으로 선정한 흔적 없음(수동 확인 병행)"
echo "--- 결정 문장 후보:"; grep -nE '결정|Decision' "$A" | head -5
summary
