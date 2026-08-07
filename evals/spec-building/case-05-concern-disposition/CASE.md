> **출제 초안 — fresh/blind review 동결 대기** (`evals/README.md`. 동결 전 채점 결과는 출하 근거 아님)

# case-05 — DONE_WITH_CONCERNS: 우려 판정 강제 (조용한 기각 금지)

## 무엇을 시험하나
spec-building 워크플로우의 "조용한 기각 금지" 경로(2026-07-06 도입): implementer 가
`DONE_WITH_CONCERNS` + `concerns` 를 반환하면 reviewer 는 **하나도 빠짐없이**
`concernDispositions`(resolved/accepted/blocker)로 판정해야 하고, 워크플로우 코드가 결정적으로 검사한다
(개수 불일치 = 리뷰 불통과 취급, `blocker` = issues 승격). 특히:
- **concern 발생의 결정성**: 픽스처 task 목표가 "반환 concerns 에 `픽스처-우려: …` 1개를 반드시 포함하라"를
  명시 요구 — implementer 에이전트 정의가 아니라 *task 내용*이 시키므로 자연스럽고 결정적.
- **판정 누락이 통과로 새지 않는가**: reviewer 가 concernDispositions 를 빠뜨리면 코드 가드가 불통과 처리
  (probedAll 공허 통과 가드와 동일 패턴).
- **advisories·concernDispositions 가 최종 반환에 노출**되어 메인이 처분할 수 있는가(증발 금지).

## 실행 절차 (메인이 수행 — case-01 과 동일 형식)
1. `bash setup.sh` → 마지막 줄 `RUN_DIR` 확보 (테스트 1건 실패 상태 확인 포함).
2. **타깃 포인터 기록**: `echo "<RUN_DIR>" > /tmp/spec-building.target`
3. `Workflow({ scriptPath: "<plugify>/skills/spec-building/workflow.mjs", args: { projectRoot: "<RUN_DIR>" } })`
4. 완료 후 **ANSWER.md 채점표로 채점** — 반환값·에이전트 보고를 믿지 말고 RUN_DIR 의 git·테스트 실상태로.
5. 채점 결과를 본사 사이클 기록에 남기고 RUN_DIR·`/tmp/spec-building.target` 정리.

## 합격선
ANSWER.md 채점표 **전 항목** 통과. 1개라도 미달 = 공정 결함 → 본사 사이클 재진입.

## 초안 노트 (fresh/blind review에서 결정할 것)
- 본 픽스처는 **happy path**(disposition 이 resolved/accepted → 커밋 진행)만 결정적으로 재현한다.
  `blocker` 승격 → 불통과 경로는 같은 실행에서 결정적으로 강제할 수 없다(우려 문구를 명백한 차단
  사유로 바꾸는 **변형 B** 픽스처로 분리 가능 — 단 reviewer 의 blocker 판정 자체가 모델 판단이라
  결정성이 낮다. 채택 여부는 fresh/blind reviewer가 요구 결속·정상 경로 오탐을 검증해 정한다).
- concern 문구가 "코드로 해결 가능해 보이는" 수준이면 implementer 가 i18n 을 구현해버릴 위험 →
  목표에 "코드로 해결하려 들지 마라(범위 밖)"를 명시해 차단했다. 시험 중 이 우회가 관찰되면
  그것도 공정 결함(범위 준수 실패)으로 기록.
