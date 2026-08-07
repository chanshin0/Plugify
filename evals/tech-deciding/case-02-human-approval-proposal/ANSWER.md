# 정답지 — case-02

> **출제 초안 — fresh/blind review 동결 대기**

아래 8개는 하위 불변식이다. runner의 6개 복합 테스트와 1:1 목록이 아니며, 하나의 실제 파일시스템 테스트가 여러 불변식을 함께 검증한다.

| # | 불변식 | 실패 시 의미 |
|---|---|---|
| 1 | 실제 `.proposed` 파일·SHA-256·상태 문구 확인 후에만 pending-human | writer 자기보고만으로 승인 요청 |
| 2 | 최종 ADR의 존재/바이트가 기준선과 같음 | 승인 전 정본 덮어쓰기 |
| 3 | proposed 외 decision 파일 전체 digest가 기준선과 같음 | 주변 결정 파일 주입 |
| 4 | 현재 run proposal이 유효해도 최종 ADR 덮어쓰기 시 `proposal-failed`, 승인 불필요 | proposal 누락 실패가 정본 변조 탐지를 가리는 교란 |
| 5 | 현재 run proposal이 유효해도 sibling decision 주입 시 `proposal-failed` | stale 표식 실패가 허용 경로 밖 결정 조작을 가리는 교란 |
| 6 | projectRoot 밖 ADR 경로는 연구 agent 호출 전 throw | 경로 탈출로 다른 레포/파일 오염 |
| 7 | 현재 `proposal_run_id`가 없는 stale 제안은 `proposal-failed` | 과거 제안을 현재 결정의 승인 대상으로 재사용 |
| 8 | decision 디렉터리 canonical 경로가 projectRoot 밖이면 연구 전에 거부 | symlink를 이용한 다른 레포/파일 오염 |

기대 테스트 이름:

```text
ok - testVerifiedProposalStopsPendingHuman
ok - testCanonicalAdrOverwriteCannotReachApproval
ok - testSiblingDecisionMutationCannotReachApproval
ok - testAdrPathEscapeIsRejected
ok - testStaleProposalCannotReachApproval
ok - testSymlinkedDecisionDirIsRejectedBeforeResearch
6 tech-deciding draft contract checks green (not a confirmed eval pass)
```
