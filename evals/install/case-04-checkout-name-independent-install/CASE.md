# case-04 — 폴더명이 `Plugify` 가 아닌 checkout 에서도 SessionStart 훅 설치가 되고 멱등하다

## 사고

2026-09-01, 형제 worktree `Plugify-model-tier/` 에서 `scripts/install.sh`·`test-install-contracts.mjs` 가
`internal error: desired managed hook command is invalid` 로 전부 실패했다. `install-session-hooks.py` 가
"이 훅 명령이 Plugify 것인가" 를 **경로에 `plugify`/`.plugify` 폴더명이 있는지** 로만 판별했기 때문이다.
이 판별은 재실행 멱등성(자기 훅을 알아봐야 중복 설치가 안 됨)의 근거라서, 설치기가 자기 명령을 못 알아보면
설치를 거부한다. 기존 worktree `Plugify-hymn-pair-flow/` 에서도 같은 6/6 실패를 재현했다. 다기기
migration 은 항상 `Plugify` 폴더명을 쓰므로 실제 기기 설치는 안 걸렸고, 에러 문구가 원인을 말해 주지 않았다.

## 무엇을 시험하나

1. 경로 어디에도 `plugify`/`.plugify` 가 없는 checkout 을 `--repo-root` 로 주면 설치가 exit 0 으로 성공하고,
   Claude `settings.json`·Codex `hooks.json` 각각에 목적별 훅이 **정확히 하나씩**(현재 checkout 절대경로) 생긴다.
   같은 파일에 있던 옛 `…/plugins/marketplaces/plugify/…`·`~/.plugify/…` 훅은 제거되고, Plugify 와 무관한
   사용자 훅(파일명이 같은 `/opt/other-tool/scripts/sync-agents.py --ensure` 포함)과 다른 키는 보존된다.
2. 같은 checkout 으로 두 번째 실행하면 두 파일 바이트가 그대로이고 둘 다 `already bound` 로 보고한다
   (사고의 진짜 위험 = 매 실행마다 훅이 하나씩 늘어나는 것).
3. `--dry-run` 은 `DRY-RUN update` 와 새 경로를 보고하되 파일을 쓰지 않는다.
4. 폴더명이 `Plugify` 인 정상 경로는 이전과 같이 설치·멱등이다(회귀 방지).

## 실행

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp \
  python3 evals/install/case-04-checkout-name-independent-install/check-install-path.py
```

production `scripts/install-session-hooks.py` 를 임시 HOME·임시 checkout 으로 실행한다(사용자 설정·네트워크 무관).
수정 전 재현: `PLUGIFY_EVAL_REPO_ROOT=<수정 전 checkout>` (`pre-fix-result.txt` = origin/main `76af626` archive, 1/4).
3레포 최신화 훅 자체(`workspace-session-start.py`)의 동작은 이 케이스가 바꾸지 않는다 — 그 계약은
`scripts/test-workspace-session-start.py` 와 confirmed `install/case-01`·`case-02` 가 그대로 지킨다.

## 합격선

- 4개 검사 모두 `ok`, 마지막 줄 `4/4 checkout-name-independent install checks PASS`, exit 0.
- 폴더명 규칙을 그냥 없애서 통과시키는 구현(옛 `plugify/.plugify` 경로를 못 알아보거나, 파일명만 같은 사용자 훅을
  건드리는 것)은 1번에서 실패해야 하며 합격이 아니다.
- confirmed `install/case-01`(6/6)·`case-02`(5/5)·`scripts/test-workspace-session-start.py` 가 함께 green 이어야 출하.
- 주의: confirmed `case-01` 의 runner(`scripts/test-install-contracts.mjs`)는 자기 판별 정규식에 옛 폴더명 규칙을 내장하고 있어
  **폴더명이 `Plugify` 인 경로에서 실행해야 6/6** 이다(이름 바뀐 worktree 에선 설치는 성공하지만 runner 가 자기 훅을 못 알아봐 3/6).
  confirmed 자산이라 구현 주체가 고치지 않는다 — 필요하면 fresh reviewer 의 별도 판정으로.
