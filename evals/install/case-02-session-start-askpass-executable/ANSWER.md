# 정답지 — install case-02

## 기대 출력

```text
ok - testGitIndexModeIsExecutable
ok - testFilesystemHelperIsExecutable
ok - testPreflightRejectsUnsafeHelperBeforePlan
ok - testStrictVerifyRejectsUnsafeHelperBeforeRepositoryChecks
ok - testSessionStartSanitizesUnsafeHelperBeforeGit
5/5 askpass executable boundary checks PASS
```

## 채점표

| # | 불변식 | 실패 시 의미 |
|---|---|---|
| 1 | Git index가 helper를 `100755`로 추적 | 현재 기기 chmod만으로 거짓 green, 다음 clone에서 재발 |
| 2 | checkout 파일이 symlink가 아닌 regular executable | Git metadata와 실제 실행 상태 불일치 |
| 3 | `preflight()`가 비실행 helper를 PLAN 전에 거부 | dry-run이 설치 불가능한 workspace를 안전하다고 보고 |
| 4 | `strict_verify()`가 비실행 helper를 repo 검사 전에 거부 | verify green 뒤 SessionStart 실패 재발 |
| 5 | SessionStart main이 fetch·자산 재생성 전 `workspace-validation`으로 sanitized fail-closed | 네트워크/사용자 설정 변경 선행 또는 `unexpected-error`로 원인 은폐 |

단순 source 문자열 검색, 테스트 전용 validator, 현재 파일에만 적용한 로컬 chmod는 합격으로
보지 않는다. production 함수와 실제 Git index/filesystem 상태를 실행해 판정한다.
