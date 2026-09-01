# 정답지 — install case-04

## 기대 출력

```text
ok - testInstallFromRenamedCheckoutSucceeds
ok - testSecondRunIsIdempotent
ok - testDryRunFromRenamedCheckoutDoesNotWrite
ok - testPlugifyNamedCheckoutStillWorks
4/4 checkout-name-independent install checks PASS
```

## 채점표

| # | 불변식 | 실패 시 의미 |
|---|---|---|
| 1 | 임의 폴더명 checkout 에서 exit 0, 목적별 훅 정확히 1개(현재 절대경로), 레거시 `plugify/.plugify` 훅 제거, 사용자 훅·다른 키 보존 | 설치 거부(사고 재발) / 훅 중복 / 옛 경로 잔존 / 사용자 훅 훼손 |
| 2 | 재실행 바이트 동일 + `already bound` ×2 | 자기 훅 미인식 → 실행마다 훅 증식 |
| 3 | dry-run 보고만, 파일 불변 | 미리보기가 실제 설치 |
| 4 | `Plugify` 폴더명 경로 설치·멱등 유지 | 정상 경로 회귀 |

수정 전 origin/main(`76af626`)에서는 1·2·3 이 `internal error: desired managed hook command is invalid` 로
실패하고 4 만 통과한다(`pre-fix-result.txt`). 판별 규칙 = 레거시 폴더명 마커 **또는** `--repo-root/scripts/<name>`
와 같은 파일(`resolve()` 비교) — 둘 다 아니면 사용자 훅으로 보존한다.
