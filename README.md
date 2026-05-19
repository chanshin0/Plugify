# Plugify

> 개인 스킬 자산 모음 + Claude Code 마켓플레이스. 정본 1곳, 플러그인 단위로 묶어서 어디서든 install.

## 개념 — 한 레포 두 역할

이 레포는 동시에 두 가지다:

1. **스킬 정본 버킷** — `skills/` 평면. 새 스킬 추가, 수정의 단일 출처.
2. **플러그인 마켓플레이스** — `.claude-plugin/marketplace.json` + `plugins/<bundle>/`. 정본 스킬들을 묶음 단위로 노출.

플러그인은 자기 `skills/` 안에 정본 스킬을 **symlink** 로 가리킨다. Claude Code 가 install 할 때 marketplace root 안 sibling symlink 를 자동으로 dereference 해서 실파일로 cache 에 박는다. 그래서:

- 정본 수정 → 새 커밋 → `/plugin marketplace update` → 사용자 cache 갱신 (빌드 step 없음)
- 다른 플러그인이 같은 스킬을 공유해도 OK (각자 자기 `skills/` 안에 symlink)
- 스킬 1개를 여러 플러그인에 박을 때 사본 동기화 부담 0

> 공식 문서 근거: [Plugin caching and file resolution](https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution) — "Elsewhere within the same marketplace: the symlink is dereferenced."

## 구조

```
.
├── .claude-plugin/
│   └── marketplace.json              # 마켓플레이스 카탈로그
├── skills/                            # 정본 스킬 (평면)
│   ├── ai-readiness-cartography/
│   ├── improve-token-efficiency/
│   ├── presentation_slides/
│   ├── push-experience/
│   ├── scenario-first-throw/
│   ├── scenario-first-expand/
│   ├── scenario-first-spec/
│   ├── scenario-first-goal/
│   ├── scenario-first-review/
│   └── self-review/
└── plugins/
    └── scenario-first/
        ├── .claude-plugin/plugin.json
        └── skills/
            ├── scenario-first-throw   → ../../../skills/scenario-first-throw
            ├── scenario-first-expand  → ../../../skills/scenario-first-expand
            ├── scenario-first-spec    → ../../../skills/scenario-first-spec
            ├── scenario-first-goal    → ../../../skills/scenario-first-goal
            └── scenario-first-review  → ../../../skills/scenario-first-review
```

## 사용 — npx 한 줄 (권장)

```bash
# 프로젝트 scope (./.claude/settings.json)
npx plugify install scenario-first

# 모든 프로젝트 (~/.claude/settings.json)
npx plugify install scenario-first --global
```

이후 Claude Code 재시작 시 trust dialog 한 번 → 마켓플레이스 등록 + 플러그인 install 자동 제안. 사용자 명령 0줄.

CLI 상세: [bootstrap/README.md](bootstrap/README.md)

## 사용 — 수동 (전통적)

```bash
claude plugin marketplace add chanshin0/Plugify
claude plugin install scenario-first@plugify
```

설치 후 `/scenario-first:scenario-first-throw` 등 namespace 된 스킬 사용 가능.

## 사용 — 개인 정본 직접 사용 (legacy)

마켓플레이스를 쓰지 않고 정본을 그대로 `~/.claude/skills/` 로 symlink 거는 방법도 그대로 지원된다 (이 레포의 원래 사용 패턴):

```bash
for d in skills/*/; do
  name=$(basename "$d")
  ln -s "$PWD/$d" "$HOME/.claude/skills/$name"
done
```

정본 위치가 안 바뀌었으므로 두 방식 공존.

## 플러그인 추가

새 묶음을 만들려면:

```
plugins/<bundle-name>/
├── .claude-plugin/
│   └── plugin.json              # name, description, author, license
└── skills/
    └── <skill-name>             → ../../../skills/<skill-name>   (symlink)
```

그 후 `.claude-plugin/marketplace.json` 의 `plugins` 배열에 entry 추가:

```json
{
  "name": "<bundle-name>",
  "source": "./plugins/<bundle-name>",
  "category": "productivity",
  "description": "..."
}
```

`claude plugin validate .` 로 검증 후 commit + push.

## 스킬 카탈로그

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

각 스킬 상세는 `skills/<name>/SKILL.md`.

## 플러그인 카탈로그

| 이름 | 묶인 스킬 | 설명 |
|---|---|---|
| `scenario-first` | scenario-first-{throw,expand,spec,goal,review} | 시나리오-First 개발 단방향 5단계 파이프라인 |

## 설계 원칙

1. **정본 1곳** — 모든 스킬은 `skills/<name>/SKILL.md` 평면. 사본 금지.
2. **플러그인은 큐레이션** — 정본을 묶음 단위로 노출. symlink 로 참조.
3. **빌드 step 없음** — marketplace root 안의 symlink dereference 에 의존. 사람이 동기화하지 않음.
4. **마켓플레이스 = 같은 레포** — cross-repo 참조는 git-subdir 이 sparse-clone 하면서 symlink 가 깨진다. 한 레포 안에 다 둔다.
