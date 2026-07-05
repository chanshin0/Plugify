---
name: spec-building
description: 확정된 구현 task 를 격리 에이전트로 구현·자기검증·적대리뷰(+Codex 교차검증은 비가역 표면 task 만)·커밋까지 자동으로 민다. "구현해", "이 task 구현", "다음 task 진행", "STATE 다음 거 만들어", "스펙대로 구현", "implement" 등에 트리거. 기획(service-planning)·결정(tech-deciding) 다음 단계. lean-agent-design — 메인은 task 분해·게이트·에스컬레이션만, 구현 잡음은 격리 서브에이전트에 가둔다.
---

# spec-building — task → 격리 구현 → 검증 → 커밋

기획·결정이 끝난 프로젝트에서 **확정된 구현 task** 를 격리 워크플로우로 끝까지 민다. 메인 컨텍스트 신선도 1순위 — 빌드 로그·구현 디테일은 서브에이전트에 가두고 메인은 조율·게이트·에스컬레이션만 들고 가볍게 유지한다.

## 선행 조건
- 프로젝트에 `.planning/` 이 있어야 한다 (`STATE.md` · `decisions/`(ADR) · `planning/`). 없으면 §부트스트랩 먼저, 또는 service-planning(기획)→tech-deciding(결정) 을 선행.
- **task 는 `.planning/STATE.md` 의 "## 다음 task" 에 "목표+게이트" 형식**으로 적는다 — 이게 워크플로우로 task 를 넘기는 안정 인터페이스다(args.task 미전달 환경에서도 동작). 형식(2026-06-22 Phase A):
  - `### 목표` — 무슨 결과를 원하나(한 줄).
  - `### 게이트` — "통과 = 됐다"의 정의. 항목마다 `auto:`<명령·테스트·라이브 프로브 + 통과 신호> 또는 `human:`<취향·비가역, 되도록 적게>. **auto 최소 1개 권장**(에이전트가 대고 반복할 수 있어야).
  - `### 비가역 표면` — 있으면(스키마·인증·배포설정 등).
- **접지 스캔(게이트를 박기 전, 메인이 수행)**: 워크플로우 투입 전 task 가 함의하는 load-bearing 결정(구조·동작·기술·계약)을 열거하고 각각이 기획서/ADR/STATE/사용자 지시 중 하나에 접지되는지 확인한다. 접지 안 된(assumed) 결정은 사용자에게 확정받아 STATE 에 반영한 뒤 투입 — 설정값·관례적 기본값(tuning value)은 접지 대상 아님(과잉 질문 금지).
- **게이트는 구현 *전에* 박는다.** 워크플로우가 STATE 를 읽어 게이트가 없거나 비어 있으면 **구현하지 않고 fail-fast 반려**한다(결정적 코드, 조용한 폴백 금지). human-only 게이트(auto 0)는 경고 후 진행 — 사람이 닫는 task.
- **trivial 우회로(2026-07-03 명문화)**: 게이트를 적을 가치가 없는 변경(오타·주석·문서·설정 1줄 등 제품 동작이 안 바뀌는 것)은 이 스킬을 태우지 않는다 — 사람/메인이 직접 편집+커밋. **우회는 규율 위반이 아니라 설계된 경로다.** 단 제품 동작이 바뀌는 변경은 크기와 무관하게 공정을 태운다(작은 diff ≠ trivial — 경계값 1글자도 동작 변경이다).

## 실행
메인은 **① 타깃 포인터 파일을 먼저 쓰고** ② Workflow 도구로 이 스킬 디렉토리의 `workflow.mjs` 를 절대경로로 실행한다:
```
echo "<레포 절대경로>" > /tmp/spec-building.target   # 정본 채널 — args 는 하니스에 따라 미전달(2026-06-11 실증)
Workflow({ scriptPath: "<이 스킬 디렉토리 절대경로>/workflow.mjs", args: { projectRoot: "<레포 절대경로>" } })
```
- 워크플로우는 타깃을 해석·검증(.planning/STATE.md 실재)하고, 무효면 **조용한 폴백 없이 즉시 실패**한다 — 엉뚱한 레포 실행 차단.
- `task`/`acceptance` 를 args 로 줄 수도 있으나, **생략 시 워크플로우가 STATE "다음 task" 를 읽는다**(권장 — args 전달 불안정성 회피).
- 진행: implementer(sonnet) 작성+자기검증 → reviewer(opus) 적대 검증 → 통과 시 atomic commit + STATE 갱신 → **라이브 게이트 있으면(아래 §라이브 게이트) 작업 브랜치 push→프리뷰 프로브까지** — 전체 상한 `maxAttempts`(기본 3)회 자율 반복. **Codex(gpt-5.5/xhigh) 병렬 교차검증은 task 에 `### 비가역 표면` 이 실질 내용으로 있을 때만**(2026-07-03 YAGNI 리뷰 — 판정은 워크플로우 게이트 점검이 결정, 규칙 정본 = `agents/reviewer.md`).
- **메인은 반환 `committed`·`commit.committedFiles` 를 신뢰하지 말고 push 전에 `git log -1`·`git status --short`·`git show --stat HEAD` 로 커밋 실재 + 커밋 파일집합이 리뷰-검증 변경과 일치하는지 직접 확인**한다(2026-06-11: 커밋 없이 완료 응답 오보고. 2026-06-23: commit 에이전트가 reviewer 미검증 파일을 *발명·커밋*하고 검증본을 작업트리에 방치). 워크플로우 판정은 "트리 클린"만 보지 "검증본을 커밋했나"는 못 본다 — 마지막 게이트는 메인.
- **`committed=false` 가 "커밋이 없다"는 뜻이 아니다** — HEAD 가 부당 이동했는지 먼저 본다. (a) HEAD 미이동 + 작업트리=리뷰 통과 상태 → 메인이 검증 후 직접 커밋. (b) HEAD 가 미검증/부분 커밋으로 이동(부당 커밋 공존) → **그 위에 덧커밋 금지**(미검증 코드가 history 에 남는다) — 검증본으로 `amend` 하거나 부당 커밋을 되돌린 뒤 올바른 changeset 을 커밋한다(2026-06-23 사고: `committed=false` 인데 잘못된 커밋이 HEAD 에 있었고, 메인이 디스크렙시 조사로 잡아 amend).
- **메인은 반환 `advisories` 를 무시 금지** — 리뷰가 비차단으로 짚은 지적이다. 즉시 픽스하거나 STATE `## 열린 결정` 에 근거와 함께 기록한다(조용한 드랍 금지).
- **사이클 종결 시 지점 노트**: 이번 사이클에서 배운 "코드가 말해주지 않는 것"이 있으면 `.planning/notes.md` 에 append 한다(없으면 안 쓴다 — 규약 정본 = live-verify SKILL §지점 노트).
- 에이전트(`agents/implementer.md`·`reviewer.md`)는 plugify 전역등록되어 `agentType` 으로 호출된다(모델·규칙은 각 `.md` 가 SSOT).

## 그래프 실행 (★1 Phase D — 2026-07-06, 큰 task 병렬 탐색)
- **한 STATE task 가 의존관계 있는 여러 하위 task 로 갈라지면** 단일 `workflow.mjs` 대신 `graph-workflow.mjs` 를 쓴다(같은 포인터 채널 `/tmp/spec-building.target`, `Workflow({scriptPath:".../graph-workflow.mjs", args:{projectRoot}})`). 단일 task 는 workflow.mjs 그대로.
- **입력**: "## 다음 task" 에 `### 그래프` + fenced **json**: `{"tasks":[{"id","goal","targets":["경로|state|external"],"depends":[…],"risk?":"RISKY|MECHANICAL|NONE"}],"regenBarriers?":[{"after":[…],"run":"<명령>"}],"verify?":"<통합검증>"}`. JSON 인 이유 = 스크립트가 JSON.parse 로 결정적 검증(YAML 파서 없음). **risk 생략 = 미분류(≠MECHANICAL) → 검증 강한 쪽 편향**.
- **결정적 판정(코드 — 속으면 안 되는 것)**: 그래프 유효성(순환·dangling·id중복·goal빈값·risk enum) → 위상정렬 wave(동시 4) → task별 격리 worktree(`.planning/worktrees/<id>`)·implementer(sonnet)·reviewer(opus)·커밋(haiku) → **merge-gate**(strictly-ahead + diff∩선언targets) → base 직렬 merge → regen barrier → **wave 통합 게이트**(verify exit0). haiku 는 git 출력 원문만 반환, 판정은 전부 순수 JS.
- **신뢰 경계**: push 금지(로컬 커밋만)·main/master 시작 시 fail-fast·라이브 게이트({PREVIEW_URL})는 v1 범위 밖(반려→workflow.mjs)·사람이 merge/push. 반환 `escalation!==null` 이면 메인이 blockers/nextOptions 로 전략 바꿔 재투입(merge-gate 실패·merge 충돌·통합 게이트 미통과·worktree 실패). 회귀 = `evals/spec-building/case-04-graph`.

## 라이브 게이트 (★1 Phase C — 2026-07-03, 프리뷰로 닫는 자율 루프)
- **`auto:` 항목에 `{PREVIEW_URL}` 이 들어가면 라이브 게이트**다. 워크플로우가 커밋 후 ① 작업 브랜치 push(**main/master 면 push 없이 skip** — prod 반영=사람, 코드가 판정) ② 지점 `.planning/preview.sh <branch>` 로 프리뷰 URL 획득 ③ `{PREVIEW_URL}` 치환 후 항목 실행·대조 ④ 실패면 그 실동작을 피드백으로 implementer 재투입 — `maxAttempts` 상한 안에서 사람 재트리거 없이 반복한다.
- **지점 규격 `.planning/preview.sh <branch> [timeout]`**: push 된 브랜치의 프리뷰 배포를 기다려 성공 시 stdout **마지막 줄** = ready URL(rc=0), 실패 시 rc≠0 + stderr 사유. 배포 방식은 지점 소유(예: niche-market 는 Vercel×GitHub Deployments API 폴링 + 프로브에 bypass 헤더 — 그 레포 AGENTS.md 참조). 규격 없는 지점에서 라이브 게이트를 쓰면 `preview-failed` 로 에스컬레이션된다.
- 프로브는 레포 루트 `.env.local` 이 있으면 로드한다(보호 우회 시크릿 등 — 값 노출 금지).
- **신뢰 경계**: 워크플로우의 push 는 작업 브랜치까지만 — **prod 반영(main merge/push)은 사람**. 라이브 게이트 통과 = "프리뷰에서 실증됨"이지 배포 완료가 아니다. 사람이 merge 한 뒤 prod 최종 확인은 `live-verify`(프리뷰에서 이미 닫힌 항목은 스팟체크만).
- 반환 `liveGate.status`: `passed`(프리뷰 실증) / `failed`·`preview-failed`(에스컬레이션 — 커밋은 브랜치에만 있어 안전) / `skipped-main-branch`(main 에서 실행됨 — push 후 live-verify 로).

## 게이트 작성 룰 (`### 게이트` 의 auto 항목을 적을 때 — 이제 형식이 강제)
아래는 게이트의 `auto:` 항목이 *진짜로 동작을 닫는지* 보장하는 룰이다. 버그픽스 검증 설계 실수의 재발 방지 (niche-market Bug-9→10 교훈, 2026-06-11):
- **실증 기준은 실코드 경로**: 재현/실증 수용 기준은 실제 프로덕션 코드 경로(실모듈 import 또는 동일 구조 *전체* 경유)를 통과해야 한다. **진단에 쓴 최소 재현을 수용 기준으로 복사 금지** — 최소 재현은 원인 격리용이지 픽스 검증용이 아니다. 직렬 마스킹(앞 버그가 뒷 버그를 가림) 구조에서는 픽스 후 실경로 재실행 없이는 가려진 버그가 그대로 출하된다.
- **게이트 통과 ≠ 동작**: 프로젝트 테스트가 순수로직만 커버하면(네트워크·DB·외부 IO 경로 공백) 그 공백을 수용 기준의 실증 항목으로 명시해 메운다. 4게이트 전부 초록이어도 IO 경로 버그는 통과한다.
- **사용자-가시 버그는 라이브로 닫는다**: 커밋·배포 후 증상이 보고된 환경에서 증상 경로를 재실행해 확인하는 단계까지가 픽스다. **1순위 = 라이브 게이트**(`{PREVIEW_URL}` 항목 — 워크플로우가 프리뷰에서 자율로 닫음, §라이브 게이트). 프리뷰로 판정 불가한 경로·prod 최종 확인은 사람 merge 후 `live-verify` 스킬(push 확인→배포 폴링→경로 재실행→실패 시 표준 버그 블록으로 재투입). 확인 전에 "해결됨"이라고 보고하지 않는다.
- **평가 불능 체크 = 실패**: auto 항목은 assertion 자체가 성공을 보고해야 통과다. 명령이 assert 전에 죽거나, 출력을 파싱할 수 없거나, 매치 0건이면 실패이지 통과가 아니다 — "서버가 로그를 남김"·"파일이 생김"·"에러 안 남" 같은 부수효과로 pass 를 추론하지 않는다.
- **게이트에서 뺀 항목은 근거를 남긴다**: 검토 중 load-bearing 항목을 게이트에서 제외하기로 했다면 STATE 에 `N/A — <근거>` 로 적는다(grounds-gate 이식) — 기각을 반증 가능한 주장으로 만든다.

## 에스컬레이션 (메인이 처리 — 무한루프 방지)
워크플로우 반환의 **`escalation !== null`** 이면 3회 미통과로 멈춘 것이다(커밋 안 됨). 메인이 `escalation.blockers`·`nextOptions` 를 보고 **전략을 바꿔 재투입**한다:
- 수용 기준이 과하거나 모순 → STATE 수용 기준 조정 후 재실행
- task 가 너무 큼 → 더 작게 분해해 각각 재실행
- 모델이 약함 → **자동 처리됨**: 마지막 시도(attempt==maxAttempts, maxAttempts>1 일 때)엔 워크플로우가 implementer 를 opus 로 자동 격상한다(단발 maxAttempts=1 은 상향 없음 — 비용 놀람 방지, opus 렁이 필요하면 maxAttempts≥2 로 재투입). 그래도 막히면 모델 문제가 아니다 — task 분해나 수용 기준 재검토로 전환
- 구조적으로 막힘(외부 의존·환경) → 사용자에게 에스컬레이션
- **무한 자동 재시도 금지**(통과 불가 task 에 토큰 폭발). 상한 도달 시 반드시 메인 판단.

## 부트스트랩 (.planning 없을 때)
메인이 `.planning/` 뼈대를 만든다 — `decisions/`(빈)·`planning/`(service-planning 산출물 있으면 복사)·`STATE.md`(아래 뼈대). git clone 으로 다른 환경에서 이어갈 수 있게 in-repo SSOT 로 둔다.
`STATE.md` 최소 뼈대 섹션: `## 현재 위치`(단계·다음) / `## 완료`(상세는 git log 위임) / `## 다음 task`(목표+게이트 형식 — `### 목표` / `### 게이트`(auto:·human:) / `### 비가역 표면`) / `## 열린 결정` / `## 다음 명령`.

## 금지
- 메인이 구현 디테일을 직접 떠안기(컨텍스트 오염) · 에이전트 함대화(task 1개당 implementer 1개) · 미통과를 통과로 위장 · `--no-verify`·`--force`.
