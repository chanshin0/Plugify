# case-01 — 따뜻한 대본을 발표자료가 아닌 삽화 서사로 만든다

## 사용자 요구에서 역산한 시험

플러기파이에 추가되는 스킬은 따뜻한 회고·간증 대본을 〈TV동화 행복한 세상〉에서 연상되는 **이야기+삽화+잔잔한 장면 전환**의 고수준 문법으로 바꾸되, 특정 방송 원화나 작가 화풍을 복제하지 않아야 한다. 기존 `presentation_slides`의 다크 카드·로드맵·발표 네비게이션과 결과·트리거가 분명히 달라야 한다.

## 실행 과제

1. `/Users/admin/Projects/Plugify/skills/illustrated-story-slides/SKILL.md`를 읽는다.
2. `fixture/raincoat-script.md`를 입력으로 `supporting-slides` 모드의 3~5장 삽화 서사 프로젝트를 격리된 임시 디렉토리에 만든다.
3. 생성 가능한 이미지 도구가 있으면 독창적 16:9 PNG 프레임을 실제로 만들고, 없으면 스토리보드까지만 만든 뒤 `visuals-pending`으로 정직하게 끝낸다. 무관한 스톡·방송 스틸·플레이스홀더를 완성 프레임으로 쓰지 않는다.
4. `deck.json`을 정본으로 `storyboard.md`, `captions.vtt`, `preview.html`, `sources.md`를 만든다.
5. 스킬의 계획·렌더 검증기를 실제 실행하고 결과를 남긴다.

이미지 도구가 없는 분기는 문구만 쓰지 말고 `production_status=visuals-pending` 상태에서 스킬의 storyboard-only 명령을 실제 실행해, 프레임 없이 `storyboard.md`·`captions.vtt`가 생성되고 `preview.html` 완성을 주장하지 않는지 확인한다.

구현 설명이나 ANSWER.md는 실행자에게 주지 않는다.

## 결정적 사전검사

```bash
node evals/illustrated-story-slides/case-01-narrative-not-presentation/check-contract.mjs --self-test
node evals/illustrated-story-slides/case-01-narrative-not-presentation/check-contract.mjs skills/illustrated-story-slides/SKILL.md
python3 evals/illustrated-story-slides/case-01-narrative-not-presentation/smoke-test.py
```

## 합격선

- 결정적 계약 검사와 도구 smoke test가 모두 0으로 끝난다.
- 실제 실행 결과가 ANSWER.md의 실상태·서사·비모방·경계 채점표를 전부 충족한다.
- 이미지 도구가 있었다면 렌더 프레임을 fresh/blind reviewer가 원 대본·`deck.json`과 대조한다.
- 이미지 도구가 없었다면 완성으로 오보고하지 않고 `visuals-pending`으로 닫혔는지만 판정하며, 렌더 품질 합격을 주장하지 않는다.
