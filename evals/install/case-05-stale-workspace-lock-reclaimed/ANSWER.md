# 정답지 — install case-05

## 기대 출력

```text
ok - testStaleLockIsReclaimed
ok - testFreshForeignLockIsRespected
ok - testReclaimedLockIsLiveForOthers
ok - testProductionHookPath
4/4 stale workspace lock checks PASS
```

## 채점표

| # | 불변식 | 실패 시 의미 |
|---|---|---|
| 1 | 600초 넘은 잠금 → 이어받아 리더, 새 토큰, release 후 잔재 0 | 사고 재발(죽은 잠금이 영구히 최신화 차단) 또는 `.stale-*` 쓰레기 누적 |
| 2 | 살아있는 잠금은 timeout 까지 존중, 내용 불변 | 동시 세션이 서로 잠금을 빼앗아 같은 일을 두 번 함 |
| 3 | 이어받은 직후의 잠금도 남이 못 가로챔 | 나이 판정이 아니라 "존재하면 치움" 으로 구현됨 |
| 4 | 실제 훅: 오래된 잠금에서도 fast-forward·agent sync 실행 + `stale-lock-reclaimed` 1회 알림 / 살아있는 잠금은 `lock-timeout` | 단위 로직만 맞고 훅 경로에 연결 안 됨 |

수정 전 origin/main(`c3293ac`)에서는 1·3·4 가 실패하고 2 만 통과한다(`pre-fix-result.txt`). 이어받기는
`os.rename` 경쟁으로 원자화한다 — 같은 죽은 잠금을 본 여러 프로세스 중 rename 에 이긴 하나만 새 리더가 된다.
