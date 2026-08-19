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
   - Claude `settings.json` + Codex `hooks.json`의 관리형 SessionStart 두 묶음을 **이번 설치에 사용한 같은 정본 레포**로 갱신(다른 훅 보존·멱등)

설치 후 **Claude/Codex 세션 재시작** 시 반영된다. 관리된 3-repo 형제
workspace에서는 `startup|resume`이 세 Git을 검증·fast-forward한 뒤 최신
자산을 재생성하고, `clear|compact`는 로컬 `sync-agents.py --ensure`만 실행한다.
이 단일-repo `npx` 설치처럼 workspace manifest와 두 brain이 없는 배치는
네트워크 갱신 없이 로컬 agent self-heal만 유지한다. Codex에서 훅 명령이
바뀌면 보안 경계상 `/hooks`에서 새 정의를 한 번 검토·신뢰해야 한다.

`Plugify`·`second_brain`·`godowon-office` 전체를 새 기기에 구성하려면 이
단일-repo 편의 도구가 아니라 정본의
[`docs/WORKSPACE_MIGRATION.md`](../docs/WORKSPACE_MIGRATION.md) 절차로 기기당
한 번 bootstrap한다. 계정 로그인은 clone·설정·Git 인증·hook trust를
다른 기기에 복제하지 않는다.

## 왜 한 파일이 아니라 "생성"인가

Claude 에이전트는 `.md`(frontmatter+본문), Codex 에이전트는 `.toml`(`developer_instructions` 필드)로 **포맷이 다르고**, Codex 는 심링크된 에이전트 toml 을 무시한다([openai/codex#15345](https://github.com/openai/codex/issues/15345)). 그래서 한 파일을 공유할 수 없고, **단일 SSOT(`*/agents/*.md`, dual-block frontmatter) → 각 툴 네이티브로 생성**한다. 스킬(`SKILL.md`)은 양쪽 포맷이 같아 심링크로 공유된다.

## Env

| 변수 | 용도 |
|---|---|
| `PLUGIFY_HOME` | 정본 레포 경로 강제 (기본: 기존 클론 자동탐지 → 없으면 `~/.plugify`) |
| `CLAUDE_CONFIG_DIR` | Claude 설정 디렉터리 (기본 `~/.claude`) |
| `CODEX_HOME` | Codex 설정 디렉터리 (기본 `~/.codex`) |

## 요구사항

`git`, `bash`, `python3`, Node.js 18+. (macOS/Linux 또는 Windows WSL;
네이티브 Windows hook command는 현재 생성하지 않는다.)

## License

MIT
