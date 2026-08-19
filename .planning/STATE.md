# Plugify 작업 상태

## 다음 task

### 목표

기기별 최초 1회 설치 후 Codex와 Claude Code의 SessionStart에서 `Plugify`, `second_brain`, `godowon-office`를 안전하게 최신화하고, 갱신된 Plugify 정본으로 에이전트 자산을 재생성한다.

### 게이트

- auto: `TMPDIR=/tmp python3 scripts/test-workspace-session-start.py`
- auto: `node scripts/test-install-contracts.mjs`
- auto: `TMPDIR=/tmp python3 scripts/test-workspace-migration.py`
- auto: `git diff --check`
- auto: 현재 기기 설치 후 Codex·Claude 설정에 `startup|resume` 갱신 훅 1개와 `clear|compact` 자산 훅 1개만 존재하고 legacy `.plugify` 중복 훅이 없다.
- auto: 세 저장소가 `main`에서 원격과 일치하며 출하 커밋이 `origin/main`에 존재한다.

### 비가역 표면

- Plugify `main` 커밋·push: 이번 사용자 요청이 지속 설정 구현과 모든 기기 재사용을 명시했으므로 승인됨.
- 이 기기의 Codex·Claude 사용자 설정 갱신: 이번 사용자 요청 범위로 승인됨. Codex 훅 신뢰 승인은 도구가 위조하지 않고 사용자 UI 경계를 보존한다.

### 범위

- 포함: 공용 SessionStart updater, 동시 실행 잠금, 비대화형 Git 검증·fetch·fast-forward, 훅 설치·중복 정리, 회귀 테스트, 다중 기기 bootstrap/운영 기록, 이 기기 적용.
- 제외: 네이티브 Windows 지원(현재 WSL 사용), 계정 로그인만으로 dotfile 배포, OS 로그인/AppStart 스케줄러, 자동 reset/rebase/stash/push, 충돌 자동 해결, Claude cloud의 로컬 사용자 설정 복제.

### 재계획 조건

- 기존 저장소의 tracked 변경·detached/feature branch·ahead/diverged 상태에서 자동 갱신이 필요하다는 새 요구가 생김.
- Codex 또는 Claude의 공식 훅 계약이 현재 SessionStart matcher·동시 실행 동작과 다름이 실증됨.
- 기존 install/eval 계약을 보존하면서 managed-hook 분리가 불가능함.
