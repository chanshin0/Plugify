# 정답지 — install case-01

## 기대 출력

```text
ok - testReplacesStaleHooksAndPreservesUnrelatedConfig
ok - testAddsMissingHooksExactlyOnce
ok - testRepeatedRunIsByteIdempotent
ok - testDryRunDoesNotWrite
ok - testInstallScriptWiresCurrentRepo
ok - testDoesNotForgeCodexHookTrust
6 draft contract checks green (not a confirmed eval pass)
```

## 채점표

| # | 불변식 | 실패 시 의미 |
|---|---|---|
| 1 | Claude·Codex의 Plugify 훅 명령이 현재 레포 `scripts/sync-agents.py --ensure`를 실제 실행하는 고정 명령과 정확히 일치 | 새 세션이 구버전 에이전트 정의로 회귀하거나 주석 속 경로로 거짓 통과 |
| 2 | 무관한 설정·훅의 전체 구조와 필드가 의미상 그대로 보존됨 | 설치기가 사용자 설정을 파괴 |
| 3 | 기존 훅 부재 시 추가되고 각 환경에 정확히 1개만 존재 | 자동 self-heal 누락 또는 중복 실행 |
| 4 | 같은 입력으로 두 번 실행한 뒤 파일 바이트가 동일 | 세션/재설치마다 설정 churn |
| 5 | `--dry-run` 전후 파일 바이트가 동일하고 구경로→신경로 변경을 출력 | 미리보기 명령이 실제 설정을 변경하거나 정적 배너로 거짓 보고 |
| 6 | `install.sh`만 실행해도 훅과 Claude·Codex 양쪽 생성 에이전트가 현재 레포에 결속됨 | 수동 별도 조치가 필요하거나 한 도구만 갱신돼 자동 적용 계약 위반 |
| 7 | `~/.codex/config.toml` trust hash를 생성·수정하는 코드가 없음 | 보안 검토 경계를 설치기가 우회 |
| 8 | 실제 `HOME`까지 임시 격리되고 고정 manifest의 6개 시험이 모두 실행됨 | 평가 중 사용자 설정 오염 또는 시험 삭제로 거짓 green |
