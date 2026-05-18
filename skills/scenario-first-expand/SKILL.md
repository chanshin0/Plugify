---
name: scenario-first-expand
description: 시나리오-First 개발 1.5단계. Job Story를 (a) User Story Mapping의 backbone + walking skeleton, (b) Example Mapping의 Rules + Examples + Questions로 확장하고, Questions는 메타 인터뷰로 사용자에게 되묻고, Examples는 Given-When-Then으로 변환해 자동 게이트 단위를 확정한다. USM(Jeff Patton 2014) + Example Mapping(Matt Wynne 2015) + Dan North의 BDD GWT(2006)를 결합한 결정성 있는 확장 절차.
---

# scenario-first-expand

## 목적

`scenario-first-throw`로 받은 Job Story를 **자동 게이트 단위(Given-When-Then)** 까지 결정성 있게 확장한다. 즉흥적 분해 금지 — 정해진 기법(USM + Example Mapping)으로 매번 같은 절차.

원리:
- Job Story(왜·언제, 사용자 머리) → Given-When-Then(어떻게 동작, 실행 가능) 단방향 변환
- 변환 사이에 USM(범위) + Example Mapping(구체 예시) + 메타 인터뷰(의도 명시화)를 끼움
- 결과는 walking skeleton = 최소 동작 1개씩 묶은 MVP 슬라이스

## 트리거

수동 호출만:

| 인자 | 동작 |
|---|---|
| `/scenario-first-expand <NNN>` | `.scenarios/throws/NNN-*.md` 확장 |
| `/scenario-first-expand --rerun <NNN>` | 이미 확장된 것 재실행 (백업 후 덮어쓰기) |

자동 트리거 금지.

## 사전 점검

```bash
test -f .scenarios/throws/NNN-*.md   # 입력 존재 확인
mkdir -p .scenarios/expanded
```

throws에 해당 ID 없으면 에러.

## Workflow

### 1. Job Story 로드

`.scenarios/throws/NNN-*.md`에서 Job Story와 원본 메모 추출.

### 2. User Story Mapping (Jeff Patton 2014)

**Backbone 도출**: Job Story의 `so I can <결과>`에 도달하기 위한 사용자 행동의 큰 단계를 시간순(좌→우)으로 배치.

예시 backbone:
```
[로그인] → [검색] → [결과 확인] → [선택] → [결과 사용]
```

**Walking skeleton**: 각 backbone 단계마다 **최소 동작 1개씩**. 이게 MVP 슬라이스.

규칙:
- backbone은 5~9개 정도가 가독성 좋음 (Miller's 7±2)
- walking skeleton 항목은 명사형이 아닌 **동사 + 명사** ("이메일 입력", "검색 결과 보기")
- 한 단계에 N개 동작이 있어도 walking skeleton에는 가장 핵심 1개만

### 3. Example Mapping (Matt Wynne 2015)

각 walking skeleton 항목에 대해 4색 카드 생성:

- 🟦 **Rule**: 비즈니스/UX 규칙 ("이메일 형식이 잘못되면 거부")
- 🟩 **Example**: 구체 사례 ("user@example.com → 통과", "user@ → 거부")
- 🟥 **Question**: 모호하거나 사용자만 결정 가능한 것
- 🟨 **Story**: 추가로 분리할 만한 스토리 (다음 사이클로 미룸)

Claude가 1차 초안을 생성하되, Question은 반드시 1개 이상 남긴다(완벽주의 회피).

### 4. 메타 인터뷰 (Questions 해소)

Question 카드를 사용자에게 한 번에 1개씩 제시:

```
[Question 1/3]
Walking skeleton: "검색 결과 보기"
물음: 결과가 0건일 때 어떻게 보여줄까요? (placeholder / 추천 / 에러 메시지)
```

답을 받으면:
- 명확한 답 → Rule로 승격
- 추가 분기 → Example로 추가
- "지금 결정 못 함" → Story로 이동(다음 사이클)

cf. `scenario-first-throw`와 짝을 이루는 메타 패턴 — 첫독자 리뷰 아이디어(`01KRX3XFK`)의 본 단계 적용.

### 5. Given-When-Then 변환

남은 Example 카드 → GWT 시나리오로 1:1 변환:

```gherkin
Scenario: <Example 한 줄 요약>
  Given <전제 — Rule + 사전 상태>
  When <Walking skeleton 동작>
  Then <Example의 기대 결과>
```

변환 규칙:
- Given은 Rule + 사전 상태를 합쳐 한 문장
- When은 walking skeleton의 동사+명사 그대로
- Then은 Example의 기대 결과 한 문장
- 시나리오 ID = `<NNN>.<backbone번호>.<step번호>.<example번호>`

복수 시나리오면 Scenario Outline + Examples 테이블 권장.

### 6. 사용자 확인

생성된 GWT 시나리오 전체를 보여주고:
- accept → 7번
- 수정 → diff로 수정 받기
- reject → Question 추가 후 4번 재시작

### 7. 저장

`.scenarios/expanded/NNN-<slug>.md`:

```markdown
---
id: <NNN>
throw_id: <NNN>
created_at: <ISO8601>
status: expanded
spec_id: null
---

# 확장: <Job Story 한 줄>

## Job Story (원본)
When ..., I want to ..., so I can ...

## Backbone
1. <단계>
2. ...

## Walking skeleton
- 1.1 <동작>
- 2.1 <동작>
...

## Example Mapping
### <walking skeleton 항목>
- Rule: ...
- Example: ...
- Question (해소): ...
- Story (이월): ...

## Given-When-Then 시나리오
\`\`\`gherkin
Scenario: ...
  Given ...
  When ...
  Then ...
\`\`\`
```

throws의 frontmatter도 갱신:
```
expanded_to: .scenarios/expanded/NNN-<slug>.md
```

### 8. 응답

```
✓ expanded/NNN  Backbone N단계, walking skeleton M개, GWT 시나리오 K개
Open questions: <남은 Story 카드 개수>
Next: /scenario-first-spec NNN
```

## 산출

- `.scenarios/expanded/NNN-<slug>.md`
- 갱신된 `.scenarios/throws/NNN-*.md` frontmatter
- 응답 요약

## 다음 단계

- `scenario-first-spec` — GWT → PRD/ARCH/비기능/운영 spec 도출

## 금지 사항

- USM/Example Mapping 단계 건너뛰기 (즉흥 분해 금지 — 결정성 깎임)
- Question 카드 0개 (완벽주의 의심)
- GWT 시나리오를 manual 테스트로 만들기 (자동 게이트 단위여야 함)
- 페르소나 등장
- backbone 10개 초과 (너무 큰 슬라이스)
