# case-01 — canary 닫기 후보 탐지하되 닫지는 않음 (★2-P3)

## 무엇을 시험하나
`scripts/canary-check.sh` 가 canary 닫기 신호를 **탐지**하되 **닫기는 사람에게 남기는지**. 특히:
- **상태 전환**: telemetry-signal canary 가 실신호 출현 전엔 `대기`, 출현 후엔 `후보` 로 바뀌는가.
- **manual 은 자동 후보 안 됨** — 실신호가 있어도 manual canary 는 계속 `수동`.
- **닫기 ≠ 자동** (핵심 불변식): canary-check 가 레지스트리를 **변경하지 않는가**(자동 닫기·삭제 금지). P1 "승격은 사람" 의 형제.
- **순수성**: canary-check 는 stdout 외 아무 파일도 안 쓴다.

## 실행 절차 (메인이 수행)
1. `bash setup.sh` → `PROJECTS_DIR`·`REGISTRY`·`RUN_DIR` 확보.
2. 레지스트리 해시 기록: `md5 -q <REGISTRY>` (before).
3. **Run A** (telemetry-log 없음):
   `PLUGIFY_CANARY_REGISTRY=<REGISTRY> bash <plugify>/scripts/canary-check.sh <PROJECTS_DIR>`
   기대: `telem-test=대기`, `manual-test=수동`, `요약: 후보 0 · 대기 1 · 수동 1`.
4. **실신호 출현 모사**: `touch <PROJECTS_DIR>/branch1/.planning/telemetry-log.md`
5. **Run B** (같은 명령): 기대 `telem-test=후보`, `manual-test=수동`, `요약: 후보 1 · 대기 0 · 수동 1`.
6. 레지스트리 해시 (after) — **before 와 동일**(자동 닫기 안 함).
7. ANSWER.md 채점표로 채점 → `RUN_DIR` 정리.

## 합격선
ANSWER.md 채점표 **전 항목** 통과. 특히 레지스트리가 두 실행에 걸쳐 byte 불변이어야 함(canary-check 가 닫기를 자동 수행하면 = 공정 결함, 본사 사이클 재진입).
