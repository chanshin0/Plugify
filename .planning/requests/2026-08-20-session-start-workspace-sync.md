# 요청 계약 — 세션 시작 작업공간 최신화

- 날짜: 2026-08-20
- 사용자 결과: 개인 자산 세 저장소가 Codex 앱의 세션과 Claude Code 세션 시작 때 최신 상태가 되며, 동일한 설치 절차를 데스크탑·노트북·Mac에서 재사용할 수 있다.

## Discoverable

- Codex와 Claude Code 모두 사용자 로컬 SessionStart 훅을 지원하지만, 계정 로그인은 사용자 훅·Git clone·심링크·Git 인증을 기기 간 배포하지 않는다.
- Codex에는 AppStart 이벤트가 없고 SessionStart의 `startup`, `resume`, `clear`, `compact` source가 있다.
- 같은 이벤트에 매칭되는 명령은 병렬 실행되므로 Git 갱신과 에이전트 생성을 별도 startup 훅으로 설치하면 경합한다.
- 현재 Claude 사용자 설정에는 동일 checkout을 가리키는 `.plugify` legacy 훅과 현재 절대경로 훅이 중복되어 있다.
- 현재 Windows 노트북은 WSL 경로의 Bash/Python 설치기를 사용하며, Mac은 Bash/Python/Git 전제가 충족되면 같은 bootstrap을 쓸 수 있다.

## Assumable

- `startup|resume`에서만 네트워크 갱신하고 `clear|compact`에서는 로컬 에이전트 재생성만 한다.
- 오프라인·인증 실패·tracked dirty·ahead/diverged·feature/detached 상태는 세션을 막지 않고 해당 저장소를 안전하게 skip한다.
- 자동 Git 동작은 검증된 `origin/main` fetch와 fast-forward만 허용한다. reset, rebase, stash, checkout, clean, push는 하지 않는다.
- untracked 파일만 있는 저장소는 incoming path 충돌이 없을 때 갱신할 수 있다. 충돌 가능성이 있으면 파일명을 출력하지 않고 skip한다.
- 기기별 최초 bootstrap과 GitHub 인증, Codex 훅 신뢰 승인은 한 번 필요하다.

## Human context

- 사용자는 세 저장소를 독립 sibling Git으로 유지하고 어디서든 같은 환경을 재구성하기를 원한다.
- 업무 브레인은 로컬 산출물 `output/`을 보유하므로 untracked 파일 존재만으로 영구 skip하면 요구를 충족하지 못한다.

## Approval

- Plugify 코드·문서·테스트 commit/push와 현재 기기의 Codex·Claude 사용자 훅 재설치는 요청에 포함된다.
- 원격 브랜치 강제 변경, 로컬 작업 폐기, 외부 서비스 메시지 전송, Codex 신뢰 승인 위조는 승인되지 않았다.

## 완료 증거

- clean-behind fast-forward, up-to-date no-op, dirty/ahead/diverged/feature/detached skip, untracked 충돌, offline noninteractive, concurrent launch, self-update 후 최신 agent sync를 결정적 테스트로 검증한다.
- `.plugify` legacy 관리 훅을 탐지·정리하고 unrelated 설정 및 trust metadata가 보존됨을 테스트한다.
- 기존 install 및 workspace migration 회귀가 모두 통과한다.
- 현재 기기에 실제 installer를 적용하고 두 도구의 최종 사용자 설정을 구조적으로 검증한다.
