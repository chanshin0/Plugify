# cc-skills-repo

chanshin0 의 Claude Code 개인 스킬 모음 (public bucket).

## 개요

이 repo 는 **스킬 버킷** 이다. 개별 스킬을 자유롭게 추가하고, 어떤 스킬을 어디에 노출할지는 별도의 marketplace repo 에서 큐레이션한다.

## 구조

```
.
├── .claude-plugin/plugin.json
└── skills/
    ├── ai-readiness-cartography/
    ├── improve-token-efficiency/
    ├── presentation_slides/
    ├── push-experience/
    ├── scenario-first-throw/
    ├── scenario-first-expand/
    ├── scenario-first-spec/
    ├── scenario-first-goal/
    ├── scenario-first-review/
    └── self-review/
```

## 설치 (개인 사용)

```
/plugin marketplace add chanshin0/cc-skills-repo
/plugin install cc-skills-repo@cc-skills-repo
```

## 큐레이션 사용 (마켓플레이스에서 골라쓰기)

별도 marketplace.json 에서 `strict: false` 로 노출할 스킬만 골라낼 수 있다:

```json
{
  "name": "my-curated-skills",
  "source": { "source": "github", "repo": "chanshin0/cc-skills-repo" },
  "skills": ["./skills/self-review", "./skills/presentation_slides"],
  "strict": false
}
```

## 스킬

| 이름 | 설명 |
|---|---|
| `ai-readiness-cartography` | repo AI-readiness 스코어링 + HTML 대시보드 |
| `improve-token-efficiency` | Claude Code 세션 토큰/비용 효율 분석 리포트 |
| `presentation_slides` | YouTube 영상용 다크 테마 HTML 슬라이드 자동 생성 |
| `push-experience` | (확인 필요 — TODO) |
| `self-review` | 직전 답변 3라운드 비판적 재검토 (R1/R2/R3) |
| `scenario-first-throw` | 시나리오-First 개발 1단계 — Job Story 캡처 |
| `scenario-first-expand` | 시나리오-First 개발 1.5단계 — USM + Example Mapping → GWT |
| `scenario-first-spec` | 시나리오-First 개발 2단계 — PRD/ARCH/NONFUNC/OPS 4슬롯 도출 |
| `scenario-first-goal` | 시나리오-First 개발 3단계 — GWT E2E 자동 변환 + goal-directed loop |
| `scenario-first-review` | 시나리오-First 개발 4단계 — 본인 사용 체크리스트 + 5 Whys 라우팅 |

각 스킬 상세는 `skills/<name>/SKILL.md` 참조.

## 시나리오-First 개발 파이프라인

`scenario-first-*` 5개 스킬은 한 시스템이다. 사용 순서:

```
1. /scenario-first-throw   "<쓰는 모습>"     → Job Story 캡처
2. /scenario-first-expand  NNN                → USM + Example Mapping → GWT
3. /scenario-first-spec    NNN                → PRD/ARCH/NONFUNC/OPS
4. /scenario-first-goal    NNN                → E2E 변환 + 구현 + 게이트 통과
5. /scenario-first-review  NNN                → 본인 사용 + 5 Whys 라우팅
   ├─ 통과 → 1로 (다음 backbone 슬라이스)
   └─ 실패 → 라우팅(1/2/3 단계로)
```

철학:
- SoT는 코드도 spec도 아니고 **유저가 결과를 어떻게 쓰는지의 narrative**
- Job Story(사용자 입력) + Given-When-Then(자동 게이트) 이중 표현
- 누적 시나리오 = 누적 spec (regression이 게이트에 흡수)
- 실패 라우팅은 5 Whys로 3분류 (시나리오/spec/구현)
- 본인 직접 사용(4단계)을 매 cycle 돌리는 게 시스템 생사
