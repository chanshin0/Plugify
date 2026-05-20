# cc-plugify

> Claude Code 마켓플레이스 [chanshin0/Plugify](https://github.com/chanshin0/Plugify) 한 줄 설치 도구. npm 이름 충돌 회피로 `cc-` (Claude Code) prefix.

## 사용

```bash
# 1. 마켓플레이스만 등록 (project scope = ./.claude/settings.json)
npx cc-plugify

# 2. 마켓플레이스 등록 + 플러그인 활성화 (가장 일반적)
npx cc-plugify install <plugin>

# 3. user-global scope (모든 프로젝트에 적용)
npx cc-plugify install <plugin> --global

# 4. 등록 해제
npx cc-plugify --uninstall
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

`npx cc-plugify install <plugin>` 한 줄로 동일.

## License

MIT
