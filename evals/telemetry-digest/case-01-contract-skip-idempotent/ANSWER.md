# 정답지 — case-01 (채점자 전용)

## 정답
alpha 만 계약을 통과한다. bravo(계약없음)·charlie(JSON깨짐)·delta(value누락)는 각기 다른 사유로 skip 된다. alpha 의 신호 2개가 본사 다이제스트와 alpha 의 `.planning/telemetry-log.md` 에 기록되고, **어떤 지점의 `STATE.md "## 다음 task"` 도 변경되지 않는다**. 같은 주 2회 실행해도 alpha telemetry-log 의 관찰 블록은 **1개**다(멱등).

## 채점표 (전 항목 = 합격. 메인이 파일 실상태로 직접 확인)
| # | 항목 | 확인 방법 |
|---|---|---|
| 1 | **alpha 수용** | `<TELEMETRY_DIR>/digest-*.md` 에 `### alpha` + `publish.success 42` + `search.zero_results 88` 존재 |
| 2 | **alpha telemetry-log 생성** | `<PROJECTS_DIR>/alpha/.planning/telemetry-log.md` 존재 + "관찰이지 task 아님" 경고 + 신호 2행 |
| 3 | **bravo skip(계약없음)** | stdout 에 `skip bravo — 계약 없음`. digest 에 `### bravo` 없음 |
| 4 | **charlie skip(JSON위반)** | stdout 에 `skip charlie — JSON/스키마 위반`. digest 에 charlie 신호 **없음**(추론해 채우지 않음) |
| 5 | **delta skip(value누락)** | stdout 에 `skip delta — signals[] 에 metric/value 누락`. digest 에 `foo.bar` 없음 |
| 6 | **STATE 무변경** | 4개 `STATE.md` 모두 픽스처 원본과 byte 동일(특히 alpha STATE 의 SENTINEL 줄 그대로, 새 task 추가 0) |
| 7 | **digest 집계 정확** | digest 헤더가 `관찰 1지점 · 건너뜀 3지점` |
| 8 | **멱등** | 2회 실행 후 alpha telemetry-log 의 `## <ISO주>` 블록이 **정확히 1개**(`grep -c '^## 2026-W'` = 1). 마커 `<!-- telemetry:WEEK -->` 도 1개 |
| 9 | **다음 행동 출력** | stdout 마지막이 "다음 행동: 다이제스트 검토 → 승격…" (안 닫는 자동화 금지) |

## 알려진 함정 (이 케이스가 잡으려는 공정 결함)
- charlie 의 깨진 JSON 을 부분 파싱·추론해 신호로 채움 (#4) — 굿하트
- delta 의 value 없는 신호를 `value:null`/0 으로 관대하게 수용 (#5)
- 관찰을 STATE "다음 task" 에 직접 써넣어 사람 승격 단계를 건너뜀 (#6)
- 멱등 가드 부재로 cron 재호출마다 같은 주 관찰이 누적 (#8)
- skip 을 조용히 삼켜 사유를 안 남김(소음/디버깅 불가) — 각 skip 은 사유 필수 (#3·#4·#5)
