# case-01 — 병렬 위임 골격 선행 (초안 — fresh/blind review 동결 전 출하 근거 금지)

> ⚠ **이 케이스는 초안이다. fresh/blind reviewer가 사용자 요구 결속과 Goodhart 우회를 확인해 동결하기 전 결과는 출하 근거가 아니다** (`evals/README.md`).

## 무엇을 시험하나
scaffold 스킬을 받은 실행 에이전트가 일회성 병렬 위임 요청에서 **에이전트 발사 전에** run 골격을 세우고, 산출물을 슬롯에 착지시키고, raw 전문을 메인이 나르지 않는지.

## 실행 절차
1. 격리 작업 디렉토리 `/tmp/scaffold-eval-<ts>/` 를 만든다 (레포 아님 — 위치 규약상 개인 경로 분기를 타지만, 시험에서는 이 디렉토리를 run 상위로 강제 지정).
2. 실행 에이전트(sonnet)에게 scaffold SKILL.md 본문 + 다음 요청을 준다:
   "정적 사이트 생성기 3개(Hugo·Astro·Eleventy)를 각각 조사해서 블로그용 추천을 정리해줘. run 디렉토리는 /tmp/scaffold-eval-<ts>/ 아래에."
3. 실행이 끝나면 채점자는 ANSWER.md 채점표를 **실상태**(파일시스템·대화 로그)로 대조한다.

## 합격선 (초안)
ANSWER.md 채점표 전 항목 통과. confirmed 합격선 완화는 사람 승인, 그 밖 초안 결속·해석은 fresh/blind reviewer가 판정한다.
