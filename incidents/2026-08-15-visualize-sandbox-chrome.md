# 2026-08-15 visualize 샌드박스 Chrome 크래시

## 증상

`visualize` 포워드 테스트가 데스크톱·모바일 렌더를 확인하려고 macOS Google Chrome 앱 바이너리의 headless 프로세스 두 개를 Codex 기본 샌드박스에서 동시에 실행했다. 두 프로세스가 모두 종료 코드 134에 해당하는 `SIGABRT`로 죽었고, 사용자에게 “Google Chrome이 예기치 않게 종료됨” 경고가 반복 노출됐다.

## 확정 원인

- 실행 시각: 2026-08-15 10:15:58 KST
- 실행 형태: `/root/forward_test_visualize`가 `Promise.all`로 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless=new` 두 개를 병렬 실행
- crash reports: `Google Chrome-2026-08-15-101558.ips`, `Google Chrome-2026-08-15-101558.000.ips`
- 공통 필드: `parentProc=codex`, `coalitionName=com.openai.codex`, `responsibleProc=ChatGPT`, `EXC_CRASH/SIGABRT`, `Abort trap: 6`
- 공통 스택: `abort → _RegisterApplication → TransformProcessType → ChromeMain`
- 통합 로그: LaunchServices·WindowServer·TCC 조회가 `Sandbox restriction`으로 거부됨
- 2026-08-12·13에도 같은 coalition/responsible process와 스택의 보고서가 있어 반복 사고로 판정

핵심 실패는 “sandbox에서 먼저 시험하고 실패하면 escalated로 재시도”한 것이다. 이 환경에서는 첫 sandbox probe 자체가 사용자-visible crash dialog를 만든다. 프로세스 병렬 실행은 같은 경고를 두 번 만들었다.

## 결론 내리지 않은 것

실패한 headless PID 51086·51087은 사용자의 평상시 Chrome PID와 별개였다. 사용자 Chrome 프로필 손상은 이 증거로 확인되지 않았다.

## 보호 자산

- 행동 규칙 정본: `skills/visualize/SKILL.md`의 `plugify.visualize.browser-safety/1` 계약
- 동결 회귀: `evals/visualize/case-02-safe-browser-verification/`
- 첫 실전 관찰: `SYSTEM.md §3.1`의 visualize 항목

회귀 케이스는 실제 Chrome을 다시 실행하지 않고 crash report 요약과 SHA-256을 픽스처로 사용한다. 지원되는 browser automation/agent-browser 도구를 우선하고, CLI headless만 남으면 첫 시도부터 escalated/unsandboxed·격리 프로필·순차 실행을 요구한다.

## 닫힘 조건

다음 실제 `visualize` 실행 1회에서 지원되는 안전 경로로 데스크톱→375px 검증을 순차 수행하고, exit 134·SIGABRT·LaunchServices sandbox 거부·사용자-visible crash dialog가 없음을 실행 로그와 fresh review로 확인한다.
