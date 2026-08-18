# 확정 실패 증거 — 2026-08-15 visualize 포워드 테스트

이 문서는 실제 크래시를 재현하지 않고 회귀 조건을 보존하기 위한 최소 증거 요약이다.

## 실행 사실

- 시각: 2026-08-15 10:15:58 KST
- 실행 주체: 이 Codex 태스크의 `/root/forward_test_visualize`
- 위험 패턴: 기본 sandbox 내부에서 `Promise.all`로 macOS 앱 바이너리 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless=new`을 데스크톱/모바일 2개 동시 실행
- 결과: 두 프로세스 모두 exit 134, 사용자-visible “Google Chrome이 예기치 않게 종료됨” 경고

## 원본 crash reports

| 파일 | SHA-256 | PID |
|---|---|---:|
| `Google Chrome-2026-08-15-101558.ips` | `ec3bd27bb166c99fccf8e4d4b749d5aa38dc4864255c169cf4622bc28fe2b4e9` | 51087 |
| `Google Chrome-2026-08-15-101558.000.ips` | `9147f4fbc1eb0761ba85c659224fd740a8c148c694ab8c3ae46a0142010abf01` | 51086 |

두 보고서에서 직접 확인된 공통 필드:

```text
parentProc: codex
coalitionName: com.openai.codex
responsibleProc: ChatGPT
exception: EXC_CRASH / SIGABRT
termination: Abort trap: 6
stack: abort → _RegisterApplication → TransformProcessType → ChromeMain
```

통합 로그의 LaunchServices·WindowServer·TCC 조회는 `Sandbox restriction`으로 거부됐다.

## 반복성

- `Google Chrome-2026-08-12-191223.ips`
- `Google Chrome-2026-08-12-204346.ips`
- `Google Chrome-2026-08-13-120317.ips`

위 보고서도 `coalitionName=com.openai.codex`, `responsibleProc=ChatGPT`, `EXC_CRASH/SIGABRT`, `_RegisterApplication → TransformProcessType → ChromeMain`을 공유한다.

## 경계

실패한 두 headless PID는 사용자의 평상시 Chrome PID와 별개였다. 따라서 사용자 프로필 손상은 이 증거에서 결론 내리지 않는다.
