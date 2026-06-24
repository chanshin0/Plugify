# case-01 — telemetry 계약: 수용·skip·멱등·관찰≠task (★2-P1 backward edge)

## 무엇을 시험하나
`scripts/telemetry-digest.sh` 가 운영→기획 backward edge 를 **결정적으로** 닫는지. 특히:
- **계약 통과 지점만 수용** — 깨진/불완전 신호를 친절히 추론해 채우지 않는가(굿하트).
- **계약 없는/위반 지점은 skip + 사유** — alpha 만 수용, bravo·charlie·delta 는 각기 다른 사유로 건너뜀.
- **관찰 ≠ task** — 지점 `STATE.md "## 다음 task"` 를 절대 건드리지 않는가(승격은 사람).
- **멱등** — 같은 주 재실행 시 지점 telemetry-log 에 관찰 블록이 중복 append 되지 않는가(P2 cron 전제).

## 픽스처 지점 (4)
| 지점 | 계약 | 기대 |
|---|---|---|
| alpha | 정상 JSON, 신호 2개 | **수용** — digest + telemetry-log 기록 |
| bravo | telemetry.sh 없음 | skip "계약 없음" |
| charlie | 깨진 JSON | skip "JSON/스키마 위반" |
| delta | JSON 모양 OK, signals[] value 누락 | skip "metric/value 누락" |

## 실행 절차 (메인이 수행)
1. `bash setup.sh` → 마지막 줄들에서 `PROJECTS_DIR`·`TELEMETRY_DIR` 확보.
2. **1회차 실행**:
   `PLUGIFY_TELEMETRY_DIR=<TELEMETRY_DIR> bash <plugify>/scripts/telemetry-digest.sh <PROJECTS_DIR>`
3. **2회차 실행** (멱등 시험): 같은 명령 한 번 더.
4. **ANSWER.md 채점표로 채점** — 스크립트 stdout 보고가 아니라 **생성된 파일 실상태**로:
   - `<TELEMETRY_DIR>/digest-*.md`
   - `<PROJECTS_DIR>/alpha/.planning/telemetry-log.md` (블록 1개여야 — 2회 돌려도)
   - 각 지점 `STATE.md` 가 픽스처 원본과 동일(무변경)
5. 결과를 본사 사이클 기록에 남기고 `RUN_DIR` 정리.

## 합격선
ANSWER.md 채점표 **전 항목** 통과. 하나라도 미달(특히 깨진 신호 수용, STATE 변경, 멱등 깨짐) = 공정 결함 → 본사 사이클 재진입.
