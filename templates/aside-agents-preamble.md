# Aside 세션 공통 규칙

이 파일은 Aside 가 모든 세션(사이드패널·CLI·Project)의 시스템 프롬프트에 자동 주입한다. Claude Code(`~/.claude/CLAUDE.md`)·Codex(`~/.codex/AGENTS.md`)와 같은 맥락을 유지하기 위한 어댑터다.

## 작업 폴더와 루트 지시문

- 워크스페이스 루트는 `/Users/admin/Projects` 다 — 독립 Git 레포들의 컨테이너(`Plugify/`·`second_brain/`·`godowon-office/`). 루트 라우터 `/Users/admin/Projects/AGENTS.md` 가 레포 라우팅·NAS 조회 계약·경로 계약의 정본이다.
- Project 없이 시작한 세션(사이드패널·`aside` CLI)의 작업 폴더는 `/Users/admin/.aside/u/0` 이고, 그 밖의 경로는 세션 샌드박스가 막는다. 파일 읽기의 "Operation not permitted" 는 macOS 권한 문제가 아니라 **세션 워크스페이스 밖**이라는 뜻이다.
- 레포 파일을 읽거나 써야 하는 작업은 **Aside Project "Workspace"(작업 폴더 `/Users/admin/Projects`)에서 세션을 시작**한다. 그 Project 는 `/Users/admin/Projects/AGENTS.md` 를 자동 로드하고 `/Users/admin/Projects` 전체를 워크스페이스로 준다. 접근이 막히면 같은 명령을 반복하지 말고, 사용자에게 Project "Workspace" 로 전환을 **한 번만** 요청한다.
- 셸에서 `~` 는 `/Users/admin` 이 아니라 샌드박스 홈으로 풀린다 — 항상 절대 경로 `/Users/admin/...` 를 쓴다.
- 워크스페이스에 `/Users/admin/Projects/AGENTS.md` 가 있으면 먼저 읽고, 하위 레포에 들어갈 때 그 레포의 `AGENTS.md`·`POLICY.md` 를 읽는다. 개인 브레인과 업무 브레인의 본문을 미리 통째로 읽지 않는다.

## 브라우저 작업 경계 (다른 실행기와 동일)

- 결제·로그인/계정 변경·메시지/메일 전송·삭제·게시·비가역 콘솔 변경은 실행하지 말고, 직전 상태와 필요한 동작을 보고하고 멈춘다(사용자 승인 경계). 유튜브 업로드는 브라우저로 하지 않는다(공식 Data API 전용).
- 내가 연 탭은 마치면 닫고, 사용자가 원래 열어둔 탭은 건드리지 않는다.

아래는 `~/.codex/AGENTS.md`(개인/업무 브레인 라우터)의 사본이다. 여기서 고치지 말고 원본을 고친 뒤 `python3 /Users/admin/Projects/Plugify/scripts/sync-aside-context.py` 로 재생성한다.
