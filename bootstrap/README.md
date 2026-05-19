# plugify

> Claude Code 마켓플레이스 [chanshin0/Plugify](https://github.com/chanshin0/Plugify) 한 줄 설치 도구.

## 사용

```bash
# 1. 마켓플레이스만 등록 (project scope = ./.claude/settings.json)
npx plugify

# 2. 마켓플레이스 등록 + 플러그인 활성화 (가장 일반적)
npx plugify install scenario-first

# 3. user-global scope (모든 프로젝트에 적용)
npx plugify install scenario-first --global

# 4. 등록 해제
npx plugify --uninstall
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
    "scenario-first@plugify": true
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

| 이름 | 설명 |
|---|---|
| `scenario-first` | Job Story → GWT 자동 게이트 5단계 파이프라인 (throw / expand / spec / goal / review) |

전체 카탈로그는 [Plugify 레포 README](https://github.com/chanshin0/Plugify) 참조.

## 옛 방식 (수동)

```bash
claude plugin marketplace add chanshin0/Plugify
claude plugin install scenario-first@plugify
```

`npx plugify install scenario-first` 한 줄로 동일.

## License

MIT
