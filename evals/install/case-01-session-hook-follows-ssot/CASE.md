# case-01 — SessionStart 에이전트 동기화가 현재 Plugify 정본을 따른다

## 무엇을 시험하나

Plugify 스킬은 현재 정본 레포를 심링크로 읽지만, Claude·Codex의 기존 `SessionStart` 훅이 오래된 marketplace clone의 `sync-agents.py`를 실행해 최신 `plan-writer`·`reviewer` 정의를 구버전으로 되돌리는 사고가 발생했다.

설치 공정은 실행된 **현재 Plugify 레포**를 에이전트 SSOT로 고정해야 한다.

1. Claude `settings.json`과 Codex `hooks.json`의 기존 Plugify `sync-agents.py --ensure` 훅을 현재 레포의 절대경로를 실제 실행하는 단일 고정 명령으로 교체한다. 주석·선행 no-op 같은 비실행 문자열 포함으로 통과할 수 없다.
2. 두 설정의 Plugify와 무관한 키·훅은 보존한다.
3. Plugify 훅이 없으면 `SessionStart`에 정확히 하나 추가한다.
4. 반복 실행해도 파일 바이트와 훅 개수가 변하지 않는다.
5. `--dry-run`은 구경로→현재 정본 경로의 필요한 변경을 보고하되 파일을 쓰지 않는다.
6. `scripts/install.sh`의 정상 실행이 Claude·Codex 양쪽 에이전트 생성과 훅 갱신을 함께 수행한다.
7. Codex의 hook trust hash를 코드가 위조·자동 승인하지 않는다. 변경된 훅의 신뢰는 Codex `/hooks` 검토 경계를 유지한다.

## 실행 절차

```bash
node scripts/test-install-contracts.mjs
```

테스트는 `HOME`·`CLAUDE_CONFIG_DIR`·`CODEX_HOME`을 모두 임시 디렉터리로 격리하고, 실제 사용자 설정을 수정하지 않는다. 고정된 테스트 이름·개수 manifest와 실행 목록이 일치해야 한다.

## 합격선

- 6개 테스트가 모두 `ok`이고 프로세스 종료 코드가 0이다.
- 기존 설정 보존, 정확히 1개인 Plugify 훅, 현재 정본 결속, dry-run 무변경, 반복 멱등 중 하나라도 빠지면 실패다.
- 테스트 수·assertion 완화는 사람 승인 없이는 금지한다.
