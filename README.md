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

각 스킬 상세는 `skills/<name>/SKILL.md` 참조.
