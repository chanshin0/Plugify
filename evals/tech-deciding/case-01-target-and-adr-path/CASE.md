# case-01 — 타깃 해석 fail-fast + ADR 절대경로 (tech-deciding)

## 무엇을 시험하나
2026-06-11 이식된 타깃픽스 3종의 회귀 케이스:
- **args JSON-문자열 정규화** — 하니스가 args 를 문자열로 전달해도 question/projectRoot 가 살아야 함
- **타깃/질문 해석 fail-fast** — args·포인터 둘 다 없으면 조사(researcher 병렬 위임) 진입 전 즉시 실패. placeholder question·`'.'` 폴백으로 비싼 실행 낭비 금지 (spec-building 2026-06-11 첫 실전 관찰 사고 계열)
- **ADR 절대경로 기록** — adrPath 상대경로가 projectRoot 기준으로 정규화되어 타깃 레포에만 생성 (2026-06-05 M2: 상대경로 Write → 엉뚱한 디렉토리 위험)

## 실행 절차 (메인이 수행)
0. `bash setup.sh` → 출력 마지막 줄의 `RUN_DIR` 확보
1. **Part A (음성 — fail-fast)**: `rm -f /tmp/tech-deciding.target` 후 **args 없이** 실행:
   `Workflow({ scriptPath: "<plugify>/skills/tech-deciding/workflow.mjs" })`
   → 기대: 타깃 해석(probe) 직후 에러 종료. Research 이후 단계 에이전트 실행 0.
2. **Part B (양성 — 풀사이클)**: 포인터 기록 후 실행 (question 은 아래 고정 문구):
   ```
   echo '{"question":"로컬 마크다운 메모 수천 개의 한국어 전문검색을 어떤 라이브러리/방식으로 구현할지 — Node 단일 프로세스 CLI, 오프라인, 외부 서버 금지","projectRoot":"<RUN_DIR>","adrPath":".planning/decisions/001-memo-search.md"}' > /tmp/tech-deciding.target
   Workflow({ scriptPath: "<plugify>/skills/tech-deciding/workflow.mjs", args: <동일 JSON> })
   ```
3. 완료 후 **ANSWER.md 채점표로 채점** — 워크플로우 반환·에이전트 보고를 믿지 말고 RUN_DIR·plugify·cwd 의 실상태로.
4. 채점 결과를 본사 사이클 기록에 남기고 RUN_DIR 과 `/tmp/tech-deciding.target` 정리.

## 합격선
ANSWER.md 채점표 **전 항목** 통과. 1개라도 미달 = 공정 결함 → 본사 사이클 재진입.
