# cc-plugify (Python · uv 진영)

> Claude Code 마켓플레이스 [chanshin0/Plugify](https://github.com/chanshin0/Plugify) 한 줄 설치 도구. `uvx` 로 즉시 실행.

Node 진영 같은 도구는 npm 패키지 [`cc-plugify`](https://www.npmjs.com/package/cc-plugify) (npx) — 동일한 동작·동일한 settings.json 형식.

## 사용

```bash
# 1. 마켓플레이스만 등록 (project scope = ./.claude/settings.json)
uvx cc-plugify

# 2. 마켓플레이스 등록 + 플러그인 활성화 (가장 일반적)
uvx cc-plugify install <plugin>

# 3. user-global scope (모든 프로젝트에 적용)
uvx cc-plugify install <plugin> --global

# 4. 등록 해제
uvx cc-plugify --uninstall
```

`uv` 가 없으면:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 동작

`.claude/settings.json` 의 두 키를 멱등하게 갱신:

```json
{
  "extraKnownMarketplaces": {
    "plugify": {
      "source": { "source": "github", "repo": "chanshin0/Plugify" }
    }
  },
  "enabledPlugins": {
    "<plugin>@plugify": true
  }
}
```

이후 Claude Code 재시작 시:
1. 신뢰 다이얼로그 (한 번)
2. 마켓플레이스 자동 등록
3. `enabledPlugins` 의 플러그인 자동 install 제안

## Project vs Global

| Scope | 위치 | 용도 |
|---|---|---|
| project (기본) | `./.claude/settings.json` | 이 프로젝트만. commit 하면 팀 공유 |
| `--global` | `~/.claude/settings.json` | 이 머신의 모든 프로젝트 |

## 사용 가능한 플러그인

현재 등록된 번들 없음 (scenario-first 는 [scenario-first-development-template](https://github.com/chanshin0/scenario-first-development-template) 로 이전).
전체 카탈로그는 [Plugify 레포 README](https://github.com/chanshin0/Plugify) · `marketplace.json` 의 `plugins` 배열 참조.

## 옛 방식 (수동)

```bash
claude plugin marketplace add chanshin0/Plugify
claude plugin install <plugin>@plugify
```

`uvx cc-plugify install <plugin>` 한 줄로 동일.

## License

MIT
