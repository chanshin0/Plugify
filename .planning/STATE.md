# Plugify 작업 상태

## 최근 완료 — 2026-08-20 SessionStart 작업공간 최신화

### 결과

기기별 최초 1회 설치 후 Codex와 Claude Code의 SessionStart에서 `Plugify`, `second_brain`, `godowon-office`를 안전하게 최신화하고, 갱신된 Plugify 정본으로 에이전트 자산을 재생성한다.

구현 출하 커밋 `73565fd`를 `origin/main`에 push했고, 이 노트북의 WSL Claude 설정과 활성 Codex `CODEX_HOME`에 실제 설치했다.

### 완료 증거

- `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp python3 scripts/test-workspace-session-start.py`: 21/21 PASS.
- fresh reviewer가 처음 발견한 동시 시작 대기시간 불안정을 수정한 뒤 해당 프로세스 회귀를 독립 재실행해 1/1 PASS.
- `node scripts/test-install-contracts.mjs`: 6/6 PASS.
- `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp python3 scripts/test-workspace-migration.py`: 30/30 PASS.
- 구문 검사와 `git diff --check`: PASS.
- 실제 Claude·Codex 설정은 각각 `startup|resume` updater 1개와 `clear|compact` agent sync 1개만 보유하고 legacy `.plugify` 관리 훅은 0개다. 무관한 JSON 구조, 0600 권한, Codex trust/config 해시는 보존됐다.
- 실제 updater 실행은 경고·출력 없이 성공했다. 세 저장소 모두 `HEAD...origin/main = 0/0`, tracked clean이다. `godowon-office`의 기존 untracked `nul`·`output/`은 그대로 보존됐다.
- 실제 workspace의 strict migration `--verify`는 위 두 untracked 항목 때문에 의도대로 dirty 경고를 낸다. SessionStart updater는 incoming path와 충돌하지 않는 untracked 산출물을 허용하는 별도 안전 계약을 사용한다.

### 승인된 비가역 표면

- Plugify `main` 커밋·push: 이번 사용자 요청이 지속 설정 구현과 모든 기기 재사용을 명시했으므로 승인됨.
- 이 기기의 Codex·Claude 사용자 설정 갱신: 이번 사용자 요청 범위로 승인됨. Codex 훅 신뢰 승인은 도구가 위조하지 않고 사용자 UI 경계를 보존한다.

### 닫힌 범위

- 포함: 공용 SessionStart updater, 동시 실행 잠금, 비대화형 Git 검증·fetch·fast-forward, 훅 설치·중복 정리, 회귀 테스트, 다중 기기 bootstrap/운영 기록, 이 기기 적용.
- 제외: 네이티브 Windows 지원(현재 WSL 사용), 계정 로그인만으로 dotfile 배포, OS 로그인/AppStart 스케줄러, 자동 reset/rebase/stash/push, 충돌 자동 해결, Claude cloud의 로컬 사용자 설정 복제.

### 첫 실전 관찰 / 재계획 조건

- 다음 실제 Codex·Claude 새 세션에서 훅 실행 결과와 중복 부재를 관찰하고, 다음 새 기기 bootstrap에서 로컬 Git 인증·Codex hook trust 경계를 재검증한다.
- 기존 저장소의 tracked 변경·detached/feature branch·ahead/diverged 상태에서 자동 갱신이 필요하다는 새 요구가 생김.
- Codex 또는 Claude의 공식 훅 계약이 현재 SessionStart matcher·동시 실행 동작과 다름이 실증됨.
- 기존 install/eval 계약을 보존하면서 managed-hook 분리가 불가능함.

## 다음 task — 2026-08-20 macOS askpass 실행권한 회귀

### 목표

새 checkout에서도 `scripts/no-askpass.py`가 실제로 실행 가능하고, workspace 검증이 이 배포 불변식을 사전에 잡으며, 이 Mac의 실제 SessionStart가 주의 신호 없이 완료된다.

### 게이트

- auto: 동결된 install 회귀 케이스가 수정 전 실패하고 수정 후 exit 0과 고정 PASS 신호를 낸다.
- auto: `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp python3 scripts/test-workspace-session-start.py`가 전부 통과한다.
- auto: `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp python3 scripts/test-workspace-migration.py`가 전부 통과한다.
- auto: `node scripts/test-install-contracts.mjs`가 전부 통과한다.
- auto: `python3 scripts/workspace-migrate.py --root /Users/admin/Projects --verify`가 exit 0이다.
- auto: `python3 scripts/workspace-session-start.py`가 exit 0이며 `attention`을 출력하지 않는다.
- auto: `git status --short`가 비어 있다.

### 비가역 표면

- Plugify `main` commit/push는 사용자가 명시 승인했다.
- Codex 훅 신뢰 승인은 사용자가 직접 수행하며 자동 승인하지 않는다.

### 첫 실전 관찰

- 수정·push 후 이 Mac의 실제 `workspace-session-start.py` 실행을 첫 실전으로 관찰하고, 세 저장소가 clean·`main`·`origin/main` 일치인지 재검증한다.
