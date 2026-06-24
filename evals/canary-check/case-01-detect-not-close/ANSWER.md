# 정답지 — case-01 (채점자 전용)

## 정답
canary-check 는 telemetry-signal canary 를 실신호(telemetry-log.md) 출현 전엔 `대기`, 출현 후엔 `후보` 로 분류한다. manual canary 는 둘 다 `수동`(자동 후보화 안 됨). **레지스트리는 두 실행 내내 변경되지 않는다** — 닫기 확정은 사람.

## 채점표 (전 항목 = 합격. 메인이 stdout·파일 실상태로 확인)
| # | 항목 | 확인 방법 |
|---|---|---|
| 1 | **Run A: telem 대기** | Run A stdout 에 `⏳ 대기  telem-test` |
| 2 | **Run A: manual 수동** | Run A stdout 에 `👤 수동  manual-test` |
| 3 | **Run A 요약** | `요약: 후보 0 · 대기 1 · 수동 1` |
| 4 | **Run B: telem 후보** | telemetry-log 생성 후 Run B stdout 에 `✅ 후보  telem-test` |
| 5 | **Run B: manual 여전히 수동** | Run B stdout 에 `👤 수동  manual-test` (실신호 있어도 자동 후보화 안 됨) |
| 6 | **Run B 요약** | `요약: 후보 1 · 대기 0 · 수동 1` |
| 7 | **레지스트리 불변** | `md5 -q <REGISTRY>` before == after (자동 닫기·삭제 0). **이 항목 실패 = 즉시 불합격** |
| 8 | **순수성** | canary-check 실행이 RUN_DIR 에 새 파일(canary-status 등)을 만들지 않음 — touch 한 telemetry-log 외 신규 파일 0 |

## 알려진 함정 (이 케이스가 잡으려는 공정 결함)
- canary-check 가 후보를 발견하면 레지스트리에서 해당 줄을 **자동 삭제/마킹**해 닫아버림 (#7) — 자율성이 닫기까지 침범
- manual canary 를 실신호 있을 때 후보로 격상 (#5) — close 종류 무시
- 대기↔후보 전환이 telemetry-log 존재가 아닌 다른 신호(heartbeat 현재주 collected 등 휘발성)에 묶여 과거 실신호를 놓침 (#4)
- canary-status.json 등 부수 파일을 써서 순수성·hermetic 깨짐 (#8)
