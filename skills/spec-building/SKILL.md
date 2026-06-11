---
name: spec-building
description: 확정된 구현 task 를 격리 에이전트로 구현·자기검증·적대리뷰(+Codex 교차검증)·커밋까지 자동으로 민다. "구현해", "이 task 구현", "다음 task 진행", "STATE 다음 거 만들어", "스펙대로 구현", "implement" 등에 트리거. 기획(service-planning)·결정(tech-deciding) 다음 단계. lean-agent-design — 메인은 task 분해·게이트·에스컬레이션만, 구현 잡음은 격리 서브에이전트에 가둔다.
---

# spec-building — task → 격리 구현 → 검증 → 커밋

기획·결정이 끝난 프로젝트에서 **확정된 구현 task** 를 격리 워크플로우로 끝까지 민다. 메인 컨텍스트 신선도 1순위 — 빌드 로그·구현 디테일은 서브에이전트에 가두고 메인은 조율·게이트·에스컬레이션만 들고 가볍게 유지한다.

## 선행 조건
- 프로젝트에 `.planning/` 이 있어야 한다 (`STATE.md` · `decisions/`(ADR) · `planning/`). 없으면 §부트스트랩 먼저, 또는 service-planning(기획)→tech-deciding(결정) 을 선행.
- **task·수용 기준은 `.planning/STATE.md` 의 "## 다음 task" 에 인라인**으로 적는다 — 이게 워크플로우로 task 를 넘기는 안정 인터페이스다(워크플로우 args.task 가 전달 안 되는 환경에서도 동작).

## 실행
메인은 **① 타깃 포인터 파일을 먼저 쓰고** ② Workflow 도구로 이 스킬 디렉토리의 `workflow.mjs` 를 절대경로로 실행한다:
```
echo "<레포 절대경로>" > /tmp/spec-building.target   # 정본 채널 — args 는 하니스에 따라 미전달(2026-06-11 실증)
Workflow({ scriptPath: "<이 스킬 디렉토리 절대경로>/workflow.mjs", args: { projectRoot: "<레포 절대경로>" } })
```
- 워크플로우는 타깃을 해석·검증(.planning/STATE.md 실재)하고, 무효면 **조용한 폴백 없이 즉시 실패**한다 — 엉뚱한 레포 실행 차단.
- `task`/`acceptance` 를 args 로 줄 수도 있으나, **생략 시 워크플로우가 STATE "다음 task" 를 읽는다**(권장 — args 전달 불안정성 회피).
- 진행: implementer(sonnet) 작성+자기검증 → reviewer(opus) + Codex(gpt-5.5/xhigh) **병렬** 교차검증 → 통과까지 최대 `maxAttempts`(기본 3)회 재시도 → 통과 시 atomic commit + STATE 갱신.
- **메인은 반환 `committed` 를 신뢰하지 말고 push 전에 `git log -1`·`git status --short` 로 커밋 실재를 직접 확인**한다(2026-06-11: commit 에이전트가 커밋 없이 완료 응답 → 오보고 사고. 워크플로우도 git 상태 기반 판정으로 보강됐지만 마지막 게이트는 메인). `committed=false` 면 작업트리(=리뷰 통과 상태)를 메인이 검증 후 직접 커밋한다.
- 에이전트(`agents/implementer.md`·`reviewer.md`)는 plugify 전역등록되어 `agentType` 으로 호출된다(모델·규칙은 각 `.md` 가 SSOT).

## 수용 기준 작성 룰 (메인 — STATE 인라인 전에 자가점검)
버그픽스 검증 설계 실수의 재발 방지 (niche-market Bug-9→10 교훈, 2026-06-11):
- **실증 기준은 실코드 경로**: 재현/실증 수용 기준은 실제 프로덕션 코드 경로(실모듈 import 또는 동일 구조 *전체* 경유)를 통과해야 한다. **진단에 쓴 최소 재현을 수용 기준으로 복사 금지** — 최소 재현은 원인 격리용이지 픽스 검증용이 아니다. 직렬 마스킹(앞 버그가 뒷 버그를 가림) 구조에서는 픽스 후 실경로 재실행 없이는 가려진 버그가 그대로 출하된다.
- **게이트 통과 ≠ 동작**: 프로젝트 테스트가 순수로직만 커버하면(네트워크·DB·외부 IO 경로 공백) 그 공백을 수용 기준의 실증 항목으로 명시해 메운다. 4게이트 전부 초록이어도 IO 경로 버그는 통과한다.
- **사용자-가시 버그는 라이브로 닫는다**: 커밋·배포 후 증상이 보고된 환경에서 증상 경로를 재실행해 확인하는 단계까지가 픽스다. 이 확인은 메인이 한다(워크플로우 범위 밖) — 확인 전에 "해결됨"이라고 보고하지 않는다. **표준 절차 = `live-verify` 스킬** (push 확인→배포 폴링→경로 재실행→실패 시 표준 버그 블록으로 재투입).

## 에스컬레이션 (메인이 처리 — 무한루프 방지)
워크플로우 반환의 **`escalation !== null`** 이면 3회 미통과로 멈춘 것이다(커밋 안 됨). 메인이 `escalation.blockers`·`nextOptions` 를 보고 **전략을 바꿔 재투입**한다:
- 수용 기준이 과하거나 모순 → STATE 수용 기준 조정 후 재실행
- task 가 너무 큼 → 더 작게 분해해 각각 재실행
- 모델이 약함 → `maxAttempts` 늘리고 implementer 를 opus 로(필요 시 워크플로우 일시 수정) 재실행
- 구조적으로 막힘(외부 의존·환경) → 사용자에게 에스컬레이션
- **무한 자동 재시도 금지**(통과 불가 task 에 토큰 폭발). 상한 도달 시 반드시 메인 판단.

## 부트스트랩 (.planning 없을 때)
메인이 `.planning/` 뼈대를 만든다 — `decisions/`(빈)·`planning/`(service-planning 산출물 있으면 복사)·`STATE.md`(아래 뼈대). git clone 으로 다른 환경에서 이어갈 수 있게 in-repo SSOT 로 둔다.
`STATE.md` 최소 뼈대 섹션: `## 현재 위치`(단계·다음) / `## 완료`(상세는 git log 위임) / `## 다음 task`(제목 + 수용 기준 인라인) / `## 열린 결정` / `## 다음 명령`.

## 금지
- 메인이 구현 디테일을 직접 떠안기(컨텍스트 오염) · 에이전트 함대화(task 1개당 implementer 1개) · 미통과를 통과로 위장 · `--no-verify`·`--force`.
