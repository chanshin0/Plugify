# 정답지 — install case-03

## 기대 출력

```text
ok - testPreFixShapeIsCaughtByProductionSync
ok - testStrictModelsFailsClosed
ok - testUnsupportedEffortAndUltraAreCaught
ok - testSessionStartSurfacesAttentionOnly
ok - testCurrentSsotIsCleanAgainstTierCatalog
5/5 codex model catalog drift checks PASS
```

## 채점표

| # | 불변식 | 실패 시 의미 |
|---|---|---|
| 1 | 퇴역 슬러그 → `codex-model-stale` + 후속 모델명, exit 0, TOML 생성 유지, 정상 에이전트 무표시 | 사고 재발(조용한 출하) 또는 과잉 차단(세션 중단·오탐) |
| 2 | `--strict-models`: 퇴역/카탈로그 부재 exit 1, 정상 exit 0 | 수동·CI 점검이 거짓 green |
| 3 | 미지원 effort·`ultra` 검출(`ultra` 는 카탈로그 없이도) | 모델이 거부하는 effort 로 런타임 실패, 또는 서브에이전트가 스스로 함대를 띄움 |
| 4 | 훅이 attention 1줄만 출력, stderr 비노출, sync 정상 완료 | 경고가 훅 밖으로 안 나와 사람·에이전트가 못 봄 / 경로·본문 유출 |
| 5 | 현 SSOT 가 티어 표 안, 생성 TOML 에 구세대 슬러그 0 | 이관 누락 파일 존재 |

수정 전 origin/main(`097b20e`)에서는 1~5 전부 실패한다(`pre-fix-result.txt`): 1 은 경고 0 으로 퇴역
슬러그 TOML 을 그대로 생성, 2·5 는 `--strict-models` 옵션 자체가 없음, 3 은 검출 0, 4 는 훅 테스트 부재.
