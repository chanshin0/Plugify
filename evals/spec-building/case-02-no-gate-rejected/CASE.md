# case-02 — 게이트 없는 task 반려 (Phase A 안전판)

## 무엇을 시험하나
spec-building 워크플로우가 **"## 다음 task" 에 `### 게이트` 가 없으면 구현하지 않고 fail-fast 반려**하는지. 검증을 끝으로 미루는 폭포수 차단(2026-06-22 Phase A, SYSTEM.md §6 ★1). 특히:
- 게이트 부재를 **결정적으로** 잡는가 — 게이트 점검 에이전트가 산문 "수용 기준:" 을 게이트로 친절하게 추론해 진행하지 않는가(굿하트).
- 반려가 **구현 전**에 일어나 git·작업트리가 무변경인가 — 엉뚱하게 코드 짜지 않는가.

## 실행 절차 (메인이 수행)
1. `bash setup.sh` → 마지막 줄 `RUN_DIR` 확보 (초기 커밋 1개 = 픽스처).
2. **타깃 포인터 기록**: `echo "<RUN_DIR>" > /tmp/spec-building.target`
3. `Workflow({ scriptPath: "<plugify>/skills/spec-building/workflow.mjs", args: { projectRoot: "<RUN_DIR>" } })`
4. 기대: 워크플로우가 **게이트 부재 에러로 실패(throw)**. implementer/reviewer/commit 단계 도달 안 함.
5. **ANSWER.md 채점표로 채점** — 워크플로우 보고가 아니라 RUN_DIR 의 git·작업트리 실상태로.
6. 결과를 본사 사이클 기록에 남기고 RUN_DIR·`/tmp/spec-building.target` 정리.

## 합격선
ANSWER.md 채점표 **전 항목** 통과 — 워크플로우가 (a) 반려했고 (b) 사유가 게이트 부재이며 (c) RUN_DIR 에 신규 커밋·작업트리 변경이 0. 하나라도 미달(특히 구현이 일어났다면) = 공정 결함 → 본사 사이클 재진입.
