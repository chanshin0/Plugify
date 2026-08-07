> **출제 초안 — fresh/blind review 동결 대기** (2026-08-06)

# case-02 — 기술 결정은 제안으로 멈추고 사람 승인 뒤 확정

## 무엇을 시험하나

`tech-deciding`이 조사·종합 결과를 최종 ADR로 자동 확정하지 않고 다음 계약을 지키는지 검사한다.

1. 결과는 최종 경로가 아니라 `<adrPath>.proposed`에 실제 기록한다.
2. 제안 문서 상태는 `제안 — 사용자 승인 전`이며 독립 read-only 증거가 SHA-256과 상태를 확인한다.
3. 최종 `<adrPath>`와 다른 decision 파일이 기준선에서 바뀌지 않아야 `pending-human`, `approval.required=true`다.
4. writer가 현재 run에 결속된 유효 proposal을 쓰면서도 최종 ADR을 덮어쓰거나 sibling decision을 만들면 `proposal-failed`, `approval.required=false`다. proposal 누락/오래된 표식이 다른 가드 실패를 가리지 않아야 한다.
5. `../`로 projectRoot 밖을 가리키는 ADR 경로는 조사 전에 거부한다.
6. 과거 실행의 `.proposed`가 남아 있어도 현재 `proposal_run_id`가 없으면 `pending-human`으로 승격하지 않는다.
7. decision 디렉터리가 symlink로 projectRoot 밖을 가리키면 연구·쓰기 전에 canonical 경로 검사에서 거부한다.

## 실행 절차

```bash
node scripts/test-tech-deciding-contracts.mjs
```

## 합격선

- 6개 실제 파일시스템 테스트가 모두 `ok`이고 프로세스 종료 코드가 0이어야 한다.
- assertion 삭제·최종 ADR 자동 확정 허용으로의 완화는 사람 재승인 없이는 금지한다.

위 7개 상위 요구를 `ANSWER.md`의 8개 하위 불변식으로 풀었고, runner의 6개 복합 테스트가 여러 불변식을 함께 검증한다. 세 숫자는 1:1 목록의 개수가 아니다.
