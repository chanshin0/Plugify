# case-02 — SessionStart askpass helper가 새 checkout에서도 실행 가능하다

## 사고

macOS 새 기기에서 workspace migration dry-run·apply·strict verify는 모두 통과했지만,
실제 `workspace-session-start.py`는 Git 요청 전에 `workspace:unexpected-error`를 냈다.
원인은 Git이 직접 실행하는 `scripts/no-askpass.py`가 저장소에 mode `100644`로
기록되어 새 checkout에서 실행 권한을 잃은 것이었다. 기존 migration 검증은 누락된
저장소를 clone할 때만 helper를 검사해 이미 세 저장소가 있는 기기에서는 이 결함을
통과시켰다.

## 무엇을 시험하나

1. `scripts/no-askpass.py`의 Git index mode가 정확히 `100755`다.
2. 현재 checkout의 helper가 regular non-symlink 파일이며 실제 실행 가능하다.
3. migration dry-run의 production `preflight()`가 비실행 helper를 PLAN 출력 전에 거부한다.
4. production `strict_verify()`도 저장소 검사보다 먼저 같은 결함을 거부한다.
5. 실제 SessionStart main 경로는 비실행 helper에서 fetch 등 askpass가 필요한 Git 경로와
   사용자 자산 재생성을 시작하지 않고, 경로나 예외를 노출하지 않는
   `workspace-validation` 주의 신호로 fail-closed한다. 저장소 identity를 확인하는 로컬
   read-only Git 명령은 askpass가 필요 없으므로 이 경계보다 먼저 실행해도 된다.

## 실행

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp \
  python3 evals/install/case-02-session-start-askpass-executable/check-boundary.py
```

네트워크, 사용자 설정 변경, 실제 workspace checkout 변경 없이 `/tmp`에 세 형제 Git
저장소·router·manifest를 갖춘 managed workspace fixture를 만들고 production 모듈 경계를
실행한다.

## 합격선

- 고정된 5개 검사가 모두 `ok`이고 마지막 줄이
  `5/5 askpass executable boundary checks PASS`이며 exit code가 0이다.
- Git index mode와 현재 filesystem 실행 가능성 중 하나만 맞으면 실패다.
- migration preflight·strict verify·SessionStart 실경로 중 하나라도 helper 결함을 늦게
  발견하거나 `unexpected-error`로 뭉개면 실패다.
- 테스트 수·기대 신호·검사 경로 완화는 사용자 승인 없이는 금지한다.
