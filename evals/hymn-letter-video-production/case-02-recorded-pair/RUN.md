# 실행 manifest

호출자는 `candidate_skill_root`, `candidate_office_root`, `case_root`의
절대경로를 런 프롬프트로 제공한다. 기기 경로를 fixture에 고정하지 않는다.
실행 전 아래 파일들의 SHA-256을 수집해 run evidence로 보관한다.

## 고정 시험 자료

- CASE.md
- RUN.md
- fixture/inputs.json
- fixture/prior-491-edl.md
- fixture/prior-370-edl.md
- fixture/prior-tools-and-master.md

## 평가 대상 읽기 manifest

candidate_skill_root 기준:

- SKILL.md
- SKILL.md가 해당 작업에 필수로 지정하는 references

candidate_office_root 기준:

- AGENTS.md, POLICY.md
- godo-hymns/찬송편지-후속편-제작-플로우.md
- godo-hymns/찬송편지-1-6편-최종업로드-정본-2026-08-26.md
- godo-hymns/tools/hymn_letter_speech_master.py
- godo-hymns/catalogs/hymn-letter-track-catalog.v1.json
- godo-hymns/production-rules/final-amen-removal.md
- godo-hymns/찬송듣기-썸네일-결정규칙-v2.1-2026-08-28.md
- 후속편 플로우가 연결하는 현재 낭독·07/08 제작 규칙(연결된 경우)

프로젝트에 실전 output 자료가 없더라도 fixture의 과거 근거 세 문서는
읽을 수 있다. 이를 실제 media bytes를 읽은 것으로 표현하지 않는다.

## 실행·채점

1. 평가 실행자에게 CASE/RUN/fixture와 위 세 root만 제공한다. 다른 agent의
   답변, 수정 의도, 정답지, negative control은 제공하지 않는다.
2. 응답 JSON·근거 설명과 읽은 파일 해시를 run evidence에 보관한다.
3. check-plan.py를 응답 JSON에 실행한다.
4. 별도 채점자가 ANSWER.md의 의미 기준을 대조한다. 기계 PASS만으로 닫지 않는다.
5. 수정 전·후 동일 조건으로 실행했으면 각 결과를 그대로 기록한다. 수정 전이
   통과했다면 red→green 개선 증거라고 주장하지 않는다. 실전 사건 관찰과 이
   planning-only 시험은 독립 증거다.
