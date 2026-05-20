# Plugify

> 개인 스킬 자산 모음 + Claude Code 마켓플레이스. 기타 도구(스코어링·토큰효율·슬라이드·셀프리뷰 등) 정본 1곳, 플러그인 단위로 묶어서 어디서든 install.

> **참고**: scenario-first 5 스킬은 2026-05-19 부로 이 마켓플레이스를 떠나 자기완결 시드 [scenario-first-development-template](https://github.com/chanshin0/scenario-first-development-template) (GitHub template repo) 로 이동했다. 사유 + 자세한 절차는 그 레포의 `.harness/EVOLUTION/001-self-contained-migration.md` 참조. Plugify 는 그 외 5 스킬의 마켓플레이스로 정체성을 좁힌다.

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
│   └── marketplace.json              # 마켓플레이스 카탈로그 (현재 plugins 비어있음 — 정본 직접 사용)
├── skills/                            # 정본 스킬 (평면)
│   ├── ai-readiness-cartography/
│   ├── improve-token-efficiency/
│   ├── presentation_slides/
│   ├── push-experience/
│   └── self-review/
└── plugins/                           # 번들 단위 마켓플레이스 노출 (현재 비어있음 — 필요 시 추가)
```

## 사용 — 개인 정본 직접 사용 (기본)

정본을 그대로 `~/.claude/skills/` 로 symlink:

```bash
for d in skills/*/; do
  name=$(basename "$d")
  ln -s "$PWD/$d" "$HOME/.claude/skills/$name"
done
```

## 사용 — 마켓플레이스 install (현재 비어있음)

`plugins/` 가 비어있어 현재 install 대상 번들이 없다. 추후 새 번들이 추가되면 다음 방식 가능:

```bash
# Python · uv 진영
uvx cc-plugify install <bundle-name>

# 수동
claude plugin marketplace add chanshin0/Plugify
claude plugin install <bundle-name>@plugify
```

CLI 상세: [bootstrap-py/README.md](bootstrap-py/README.md) (Python) · [bootstrap/README.md](bootstrap/README.md) (Node)

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

각 스킬 상세는 `skills/<name>/SKILL.md`. scenario-first 5 스킬은 [scenario-first-development-template](https://github.com/chanshin0/scenario-first-development-template) 로 이동.

## 플러그인 카탈로그

현재 비어있음. `marketplace.json` 의 `plugins` 배열에 새 번들 entry 를 추가하면 활성화.

## 설계 원칙

1. **정본 1곳** — 모든 스킬은 `skills/<name>/SKILL.md` 평면. 사본 금지.
2. **플러그인은 큐레이션** — 정본을 묶음 단위로 노출. symlink 로 참조.
3. **빌드 step 없음** — marketplace root 안의 symlink dereference 에 의존. 사람이 동기화하지 않음.
4. **마켓플레이스 = 같은 레포** — cross-repo 참조는 git-subdir 이 sparse-clone 하면서 symlink 가 깨진다. 한 레포 안에 다 둔다.
