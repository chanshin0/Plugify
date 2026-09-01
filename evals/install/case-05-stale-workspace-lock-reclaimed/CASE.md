# case-05 — 죽은 리더가 남긴 SessionStart 잠금이 3레포 최신화를 영구히 막지 않는다

## 사고

2026-09-01 확인: `~/Projects/.plugify-session-sync.lock` 이 **08-29 11:45** 에 만들어진 채 남아 있었다
(`owner.json` 토큰만 있고 살아있는 프로세스 없음 — 그때 리더가 중간에 죽은 것). 잠금 코드는 "만든 쪽만
자기 토큰을 확인하고 지운다" 규칙뿐이어서 죽은 주인의 잠금은 아무도 치우지 않았고, 그 뒤 **3일간 모든
Claude·Codex 세션 시작이 120초를 기다리다 `workspace:lock-timeout`** 으로 세 저장소 fast-forward 와
agent sync 를 건너뛰었다. 세션 시작도 매번 2분씩 느려졌다. 다기기 "항상 최신화" 계약이 조용히 멈춘 것이다.

## 무엇을 시험하나

1. `STALE_LOCK_SECONDS`(600초)를 넘긴 잠금은 production `WorkspaceLock.acquire()` 가 이어받아 리더가 되고
   (`reclaimed_stale = True`, `owner.json` 이 새 토큰), `release()` 뒤 잠금과 `*.stale-*` 잔재가 남지 않는다.
2. 방금 생긴(살아있는) 남의 잠금은 가로채지 않는다 — timeout 까지 기다리다 `wait_timed_out` 으로 물러나고 잠금 내용은 그대로다.
3. 이어받은 잠금은 새 리더의 살아있는 잠금이다 — 뒤따르는 프로세스가 다시 가로채지 않는다(두 번째 리더 금지 불변식 유지).
4. production 훅 실경로: 오래된 잠금이 있어도 세 저장소 fast-forward·agent sync 가 실행되고
   `workspace:stale-lock-reclaimed` 를 한 번 알리며, 살아있는 잠금은 `workspace:lock-timeout` 으로 물러난다
   (`scripts/test-workspace-session-start.py` 의 두 테스트).

## 실행

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp \
  python3 evals/install/case-05-stale-workspace-lock-reclaimed/check-stale-lock.py
```

임시 디렉터리에서 production 모듈을 직접 실행하고, 4번은 격리 workspace fixture(세 형제 Git + manifest)를 쓰는
기존 훅 테스트를 호출한다. 네트워크·사용자 설정·실제 workspace 무관.
수정 전 재현: `PLUGIFY_EVAL_REPO_ROOT=<수정 전 checkout>` (`pre-fix-result.txt` = origin/main `c3293ac` archive, 1/4).

## 합격선

- 4개 검사 모두 `ok`, 마지막 줄 `4/4 stale workspace lock checks PASS`, exit 0.
- "잠금이 있으면 무조건 지우고 진행" 같은 구현은 2·3번에서 실패해야 하며 합격이 아니다 — 동시 세션이 같은
  최신화를 두 번 돌리지 않는다는 기존 불변식(`test_concurrent_*`)이 함께 green 이어야 한다.
- 합격선 완화·검사 수 변경은 사람 승인 없이는 금지한다.
