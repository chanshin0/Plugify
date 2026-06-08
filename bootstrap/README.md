# plugify

> [chanshin0/Plugify](https://github.com/chanshin0/Plugify) 의 스킬·에이전트를 **Claude Code 와 Codex 양쪽에** 단일 소스(SSOT)로 설치하는 한 줄 도구.

## 사용

```bash
# 정본 레포를 clone/locate 한 뒤 install.sh 실행 (claude + codex 셋업)
npx plugify

# (추가) Claude 마켓플레이스도 등록 — project scope
npx plugify --register

# (추가) Claude 마켓플레이스 등록 — user-global
npx plugify --register -g

npx plugify --help
```

## 동작

`npx plugify` 는:

1. **정본 레포를 안정 경로에 둔다.** 기존 클론(예: Claude 마켓플레이스 카피)을 자동 탐지해 재사용하고, 없으면 `~/.plugify` 로 clone 한다. (npx 자체는 임시 캐시에서 도는데, 거기서 install.sh 를 돌리면 심링크가 캐시 삭제 시 dangling 되므로 안정 경로가 필수.)
2. `git pull` (로컬 변경 있으면 건너뜀).
3. `<repo>/scripts/install.sh` 실행 →
   - 스킬을 `~/.claude/skills` + `~/.codex/skills` 양쪽에 심링크
   - 에이전트를 `~/.claude/agents/*.md` + `~/.codex/agents/*.toml` 로 생성 (dual-block SSOT 에서)

설치 후 **Claude/Codex 세션 재시작** 시 반영된다 (SessionStart 훅이 `sync-agents.py --ensure` 로 매 세션 self-heal).

## 왜 한 파일이 아니라 "생성"인가

Claude 에이전트는 `.md`(frontmatter+본문), Codex 에이전트는 `.toml`(`developer_instructions` 필드)로 **포맷이 다르고**, Codex 는 심링크된 에이전트 toml 을 무시한다([openai/codex#15345](https://github.com/openai/codex/issues/15345)). 그래서 한 파일을 공유할 수 없고, **단일 SSOT(`*/agents/*.md`, dual-block frontmatter) → 각 툴 네이티브로 생성**한다. 스킬(`SKILL.md`)은 양쪽 포맷이 같아 심링크로 공유된다.

## Env

| 변수 | 용도 |
|---|---|
| `PLUGIFY_HOME` | 정본 레포 경로 강제 (기본: 기존 클론 자동탐지 → 없으면 `~/.plugify`) |
| `CLAUDE_CONFIG_DIR` | Claude 설정 디렉터리 (기본 `~/.claude`) |
| `CODEX_HOME` | Codex 설정 디렉터리 (기본 `~/.codex`) |

## 요구사항

`git`, `bash`, `python3`, Node.js 18+. (install.sh·sync-agents.py 가 bash/python3 사용 — macOS/Linux.)

## License

MIT
