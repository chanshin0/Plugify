---
name: spec-building
description: 구현 요구를 실행 가능한 목표·자동 증거·작업 그래프로 정리한 뒤 격리 에이전트로 구현·자기검증·블라인드 리뷰·재계획·커밋까지 자동으로 민다. 이미 확정된 atomic task는 바로 실행하고, 모호하거나 여러 단계인 요청은 task-orchestrating 계약으로 먼저 조사·인터뷰·분해한다. "구현해", "이 task 구현", "다음 task 진행", "STATE 다음 거 만들어", "스펙대로 구현", "implement" 등에 트리거. 사람에게 routine 완료 체크를 요청하지 않는다.
---

# spec-building — task → 격리 구현 → 검증 → 커밋

구현 요구를 **에이전트가 확인할 증거가 있는 task**로 만든 뒤 격리 워크플로우로 끝까지 민다. 메인 컨텍스트 신선도 1순위 — 빌드 로그·구현 디테일은 서브에이전트에 가두고 메인은 조사·인터뷰·분해·조율·재계획만 들고 가볍게 유지한다.

## 선행 조건
- 프로젝트에 `.planning/` 이 있어야 한다 (`STATE.md` · `decisions/`(ADR) · `planning/`). 없으면 §부트스트랩 먼저, 또는 service-planning(기획)→tech-deciding(결정) 을 선행.
- 사용자에게 이 형식을 작성시키지 마라. raw request면 먼저 `../task-orchestrating/SKILL.md`의 조사·인터뷰·분해 계약을 수행하고, 메인이 `.planning/STATE.md`의 "## 다음 task"를 **목표+게이트(+필요 시 그래프)** 형식으로 컴파일한다. 이미 실행 계약이 있으면 재작성하지 않는다. 이 STATE가 워크플로우로 task를 넘기는 안정 인터페이스다(args.task 미전달 환경에서도 동작).
  - `### 목표` — 무슨 결과를 원하나(한 줄).
  - `### 게이트` — "통과 = 됐다"의 정의. 에이전트가 조사해 `auto:`<명령·테스트·라이브 프로브 + 통과 신호>를 최소 1개 만든다. `human:`은 routine 품질 확인이 아니라 권한·보안·비용·외부 전송·파괴·비가역 승인에만 쓴다.
  - `### 비가역 표면` — 있으면(스키마·인증·배포설정 등).
- **접지 스캔(게이트를 박기 전, 메인이 수행)**: task가 함의하는 load-bearing 결정(구조·동작·기술·계약)을 열거하고 근거를 찾는다. 근거 없는 항목은 `discoverable`이면 조사, 되돌릴 수 있는 저영향 값이면 가정·기록, 사람만 아는 의도면 1~3개 집중 인터뷰, 비가역 행동이면 실행 직전 승인으로 분류한다. "근거 없음"만으로 모두 사용자에게 보내지 마라.
- **게이트는 구현 *전에* 에이전트가 박는다.** 워크플로우가 STATE를 읽어 게이트가 없거나 비어 있으면 구현하지 않고 fail-fast 반려한다. human-only(auto 0)는 완료 증거 설계 실패이거나 실행 전 승인만 남은 상태다. 메인이 먼저 조사해 auto 증거를 설계하고, 실제 승인 경계일 때만 `pending-human`으로 멈춘다.
- **빈 껍데기 먼저(2026-07-21 — 새 산출물 유형/새 지점 한정)**: 프로젝트가 *처음* 내보내는 형태의 산출물(첫 배포, 첫 제출물, 새 전달 형식)이면 내용 구현 전에 골격 task 를 먼저 태운다 — 수용 규격을 역산한 빈 구조가 통과에 치명적인 조건(로드되나·배포되나·로그 남나)을 내용 없이 실증(hello 수준)하고 에이전트가 증거를 확인한 뒤 내용 task 진입. 외부 전송·비용·파괴·비가역 행동이 포함될 때만 실제 경계에서 사람 승인을 받는다. 이후 산출물은 이미 "되는 구조" 안에 떨어진다. 기존 유형의 반복 작업엔 적용하지 않는다(과공정 금지). 원칙 정본 = 본사 AGENTS.md 설계 원칙.
- **trivial 우회로(2026-07-03 명문화)**: 게이트를 적을 가치가 없는 변경(오타·주석·문서·설정 1줄 등 제품 동작이 안 바뀌는 것)은 이 스킬을 태우지 않는다 — 사람/메인이 직접 편집+커밋. **우회는 규율 위반이 아니라 설계된 경로다.** 단 제품 동작이 바뀌는 변경은 크기와 무관하게 공정을 태운다(작은 diff ≠ trivial — 경계값 1글자도 동작 변경이다).

## 실행
메인은 **① 타깃 포인터 파일을 먼저 쓰고** ② Workflow 도구로 이 스킬 디렉토리의 `workflow.mjs` 를 절대경로로 실행한다:
```
echo "<레포 절대경로>" > /tmp/spec-building.target   # 정본 채널 — args 는 하니스에 따라 미전달(2026-06-11 실증)
Workflow({ scriptPath: "<이 스킬 디렉토리 절대경로>/workflow.mjs", args: { projectRoot: "<레포 절대경로>" } })
```
- 워크플로우는 타깃을 해석·검증(.planning/STATE.md 실재)하고, 무효면 **조용한 폴백 없이 즉시 실패**한다 — 엉뚱한 레포 실행 차단.
- 자율 커밋은 시작 시 clean 작업트리를 요구한다. 기존 사용자 변경·다른 workflow run 증거가 있으면 단일 경로는 `pending-human`, 그래프 경로는 구현 전 반려한다. 먼저 별도 커밋·stash·브랜치로 분리하거나 `commit=false` 검토만 수행한다.
- `task`/`acceptance` 를 args 로 줄 수도 있으나, **생략 시 워크플로우가 STATE "다음 task" 를 읽는다**(권장 — args 전달 불안정성 회피).
- 진행: implementer(sonnet) 작성+자기검증 → reviewer(opus) **블라인드 최초 검증**(구현 보고·결정·selfCheck·concerns·이전 리뷰 미제공) → 최초 verdict 동결 후 concerns 별도 대조 → 통과 시 atomic commit. auto-only 비라이브 task는 implementer가 STATE 종결 변경까지 만들고 reviewer가 코드와 함께 검증한 뒤 커밋 에이전트는 그 changeset을 수정 없이 커밋한다. human 게이트가 남으면 코드 변경만 커밋하고 STATE 완료 처리 없이 `pending-human`으로 멈춘다. 라이브 task는 프리뷰 실증 뒤 종결 편집자와 별도 블라인드 reviewer가 현재 task·프리뷰 URL·prod merge 대기·다른 task 불변을 확인하고, reviewer 전후 STATE changeset이 동일할 때만 그 바이트를 별도 커밋한다. 전체 상한은 `maxAttempts`(기본 3)회다. **Codex(gpt-5.5/xhigh) 병렬 교차검증은 task 에 `### 비가역 표면` 이 실질 내용으로 있을 때만**(2026-07-03 YAGNI 리뷰 — 판정은 워크플로우 게이트 점검이 결정, 규칙 정본 = `agents/reviewer.md`).
- 워크플로우는 implementer 직후와 reviewer 직후의 HEAD·파일집합·status·파일별 blob digest를 각각 동결해 서로 같을 때만 진행한다. implementer 조기 커밋이나 reviewer/검증 명령의 파일 변조는 이후 snapshot에 흡수되지 않는다. 사후 read-only 증거의 `revCount==1`·HEAD 전진·동일 파일집합·동일 digest·완전 clean 작업트리(untracked 포함)도 코드로 대조한다. 라이브 종결은 의미 리뷰 뒤 STATE changeset digest를 동결하고 별도 read-only agent가 로컬/원격 SHA·STATE-only 1커밋·동일 digest를 다시 잰다. 그래도 하니스 I/O 자체는 에이전트가 수집하므로, **메인은 반환 `committed`·`commit.committedFiles` 를 최종 진실로 신뢰하지 말고 push 전에 `git log -1`·`git status --short`·`git diff-tree --name-only HEAD` 로 직접 확인**한다. 마지막 게이트는 메인이다.
- **`committed=false` 가 "커밋이 없다"는 뜻이 아니다** — HEAD 가 부당 이동했는지 먼저 본다. (a) HEAD 미이동 + 작업트리=리뷰 통과 상태 → 메인이 검증 후 직접 커밋. (b) HEAD 가 미검증/부분 커밋으로 이동(부당 커밋 공존) → **그 위에 덧커밋 금지**(미검증 코드가 history 에 남는다) — 검증본으로 `amend` 하거나 부당 커밋을 되돌린 뒤 올바른 changeset 을 커밋한다(2026-06-23 사고: `committed=false` 인데 잘못된 커밋이 HEAD 에 있었고, 메인이 디스크렙시 조사로 잡아 amend).
- **메인은 반환 `advisories` 를 무시 금지** — 리뷰가 비차단으로 짚은 지적이다. 즉시 픽스하거나 STATE `## 열린 결정` 에 근거와 함께 기록한다(조용한 드랍 금지).
- 반환 `runSummary` 는 `schemaVersion`·`runId`·시작/종료 시각·의미 있는 phase 전이·attempt·`reviewerBlind`·`terminalState`·최소 증거만 담는다. 메시지/서브에이전트 호출 수를 자율성으로 세지 않는다. human 게이트처럼 재개입이 계약상 필요하면 `humanReintervention=required`, 관측할 수 없으면 `not_observable`로 둔다. 프롬프트 전문·시크릿은 기록하지 않는다. v1은 반환 계약만 제공하며 대상 프로젝트 작업트리에 계측 파일을 쓰지 않는다.
- **사이클 종결 시 지점 노트**: 이번 사이클에서 배운 "코드가 말해주지 않는 것"이 있으면 `.planning/notes.md` 에 append 한다(없으면 안 쓴다 — 규약 정본 = live-verify SKILL §지점 노트).
- 에이전트(`agents/implementer.md`·`reviewer.md`)는 plugify 전역등록되어 `agentType` 으로 호출된다(모델·규칙은 각 `.md` 가 SSOT).

## 그래프 실행 (★1 Phase D — 2026-07-06, 큰 task 병렬 탐색)
- **한 STATE task 가 의존관계 있는 여러 하위 task 로 갈라지면** 단일 `workflow.mjs` 대신 `graph-workflow.mjs` 를 쓴다(같은 포인터 채널 `/tmp/spec-building.target`, `Workflow({scriptPath:".../graph-workflow.mjs", args:{projectRoot}})`). 단일 task 는 workflow.mjs 그대로.
- **입력**: "## 다음 task"에 `### 그래프` + fenced **json**을 둔다. 새 그래프는 `contractVersion:"2.0"`과 task별 `id·goal·why·targets·depends·evidence·assumptions·risk·replanWhen`, 전체 `verify`를 둔다. `evidence`는 `{id,kind:"command",run,expect:{exit,outputIncludes,outputExcludes}}` 배열이며 reviewer의 실제 실행 결과가 `id·run` 1:1로 결속되어야 한다. `run`은 비대화형 도구/명시적 스크립트만 허용하고 승인·육안 판정은 별도 approval ledger로 분리한다. 정확한 형식은 `../task-orchestrating/references/request-contract.md`를 따른다. 버전 누락은 조용한 legacy 강등 없이 fail-closed하며, 기존 fixture 이전은 `allowLegacyGraph:true` 명시 마이그레이션에서만 허용한다. 각 task는 atomic 파일 커밋 계약상 최소 1개 파일 target이 필수다. `state`/`external` 표식만 있는 task는 임의 파일 diff 우회를 막기 위해 구현 전 반려하고 단일 task 또는 승인 단계로 분리한다. JSON 인 이유 = 스크립트가 JSON.parse로 결정적 검증한다. regen barrier는 허용 산출물 `targets`가 필수이며 그 밖 파일·STATE·다중 커밋은 사후 증거에서 거부한다.
- **결정적 판정(코드 — 속으면 안 되는 것)**: STATE 게이트(human-only는 worktree 전 정지, 혼합은 끝에 pending-human) → 그래프 유효성(순환·dangling·id중복·goal빈값·risk enum·파일 target·구조화 evidence 실재) → 위상정렬 wave(동시 4) → task별 격리 worktree(`.planning/worktrees/<id>`)·리뷰 전후 changeset 불변·reviewer 직접 명령 실행·`evidenceResults`의 순서·id·run 결속 및 선언 `expect.exit·outputIncludes·outputExcludes`의 실제 exit/output 코드 대조·커밋(haiku) → **merge-gate**(base 대비 정확히 1커밋 + diff가 선언 targets 안에만 존재) → task당 강제 `--no-ff` 직렬 merge 후 전체 rev `2N`·first-parent `N`·ancestor뿐 아니라 각 merge의 부모가 `(직전 base, 검증된 task tip)` 정확히 2개이고 `--remerge-diff`가 비어 있는지 대조(`-s ours`·merge tree 변조 거부) → regen barrier → **wave 통합 게이트**(verify exit0·실행 전후 HEAD·작업트리 불변; v2 실패는 같은 graph의 임의 수정 대신 재계획 신호) → worktree 정리 전후 base HEAD·status 불변 대조. haiku 는 git 출력 원문만 반환, 판정은 순수 JS가 맡는다.
- **신뢰 경계**: push 금지(로컬 커밋만)·main/master 시작 시 fail-fast·라이브 게이트({PREVIEW_URL})는 v1 범위 밖(반려→workflow.mjs)·prod merge/push는 승인 경계. 반환 `escalation!==null`이면 메인이 먼저 task의 `replanWhen`과 실패 증거로 그래프를 바꿔 재투입한다. 안전한 대안·상한을 소진했거나 승인 경계일 때만 사람에게 에스컬레이션한다. 회귀 = `evals/spec-building/case-04-graph`.

## 라이브 게이트 (★1 Phase C — 2026-07-03, 프리뷰로 닫는 자율 루프)
- **`auto:` 항목에 `{PREVIEW_URL}` 이 들어가면 라이브 게이트**다. 작업 브랜치 push도 외부 전송·원격 변경이므로 원 요청의 명시 승인 또는 실제 경계 승인을 메인이 STATE의 정확한 표식 `preview-push: authorized`로 기록해야 구현에 진입한다. 게이트 판독 에이전트는 승인 boolean을 만들지 않고 `## 다음 task` 원문을 반환하며, workflow 코드가 정확히 일치하는 독립 행의 실재를 판정한다. 표식이 없거나 근사 문구뿐이면 `pending-human`으로 fail-closed한다. 승인됐으면 워크플로우가 커밋 후 ① 작업 브랜치 push(**main/master 면 push 없이 skip**) ② 지점 `.planning/preview.sh <branch>` 로 프리뷰 URL과 배포 SHA 획득 ③ 로컬 HEAD=원격 branch SHA=배포 SHA가 구현 커밋과 모두 같은지 독립 재확인 ④ `{PREVIEW_URL}` 치환 후 캡처된 항목 원문 멀티셋을 1:1 실행·대조 ⑤ 실패면 그 실동작을 피드백으로 implementer 재투입 — `maxAttempts` 상한 안에서 사람 재트리거 없이 반복한다. 예전 배포·항목 중복/치환은 pass가 될 수 없다.
- **지점 규격 `.planning/preview.sh <branch> [timeout]`**: push 된 브랜치의 프리뷰 배포를 기다려 성공 시 stdout에 provider 메타데이터로 확인한 전체 커밋 SHA 한 줄 `DEPLOYED_SHA=<40hex>`를 포함하고, stdout **마지막 줄**은 ready URL이어야 한다(rc=0). SHA를 해당 배포에 결속할 수 없거나 실패하면 rc≠0 + stderr 사유다. 배포 방식은 지점 소유. 규격 없는 지점이나 SHA 불일치는 `preview-failed` 로 에스컬레이션된다.
- 프로브는 레포 루트 `.env.local` 이 있으면 로드한다(보호 우회 시크릿 등 — 값 노출 금지).
- **신뢰 경계**: 워크플로우의 push 는 승인 표식이 있는 작업 브랜치까지만 — prod 반영(main merge/push)은 명시적 권한 경계다. 라이브 게이트 통과 = "프리뷰에서 실증됨"이지 배포 완료가 아니다. prod 반영이 명시 승인된 뒤 최종 확인은 `live-verify`(프리뷰에서 이미 닫힌 항목은 스팟체크만).
- 반환 `liveGate.status`: `passed`(프리뷰 실증; human 게이트가 없으면 종결 커밋/원격 SHA까지 대조) / `failed`·`preview-failed`·`closure-failed`(에스컬레이션 — 성공 선언 금지) / `skipped-main-branch`(main 에서 실행됨 — push 후 live-verify 로). live가 pass여도 human 게이트가 남으면 종결 커밋을 생략하고 전체 `terminalState=pending-human`이다. 전체 종료 상태는 `verified`·`pending-human`·`reviewed-uncommitted`·`commit-failed`·`closure-failed`·`escalated`·`incomplete` 중 하나다.

## 게이트 작성 룰 (`### 게이트` 의 auto 항목을 적을 때 — 이제 형식이 강제)
아래는 게이트의 `auto:` 항목이 *진짜로 동작을 닫는지* 보장하는 룰이다. 버그픽스 검증 설계 실수의 재발 방지 (niche-market Bug-9→10 교훈, 2026-06-11):
- **실증 기준은 실코드 경로**: 재현/실증 수용 기준은 실제 프로덕션 코드 경로(실모듈 import 또는 동일 구조 *전체* 경유)를 통과해야 한다. **진단에 쓴 최소 재현을 수용 기준으로 복사 금지** — 최소 재현은 원인 격리용이지 픽스 검증용이 아니다. 직렬 마스킹(앞 버그가 뒷 버그를 가림) 구조에서는 픽스 후 실경로 재실행 없이는 가려진 버그가 그대로 출하된다.
- **게이트 통과 ≠ 동작**: 프로젝트 테스트가 순수로직만 커버하면(네트워크·DB·외부 IO 경로 공백) 그 공백을 수용 기준의 실증 항목으로 명시해 메운다. 4게이트 전부 초록이어도 IO 경로 버그는 통과한다.
- **사용자-가시 버그는 라이브로 닫는다**: 커밋·배포 후 증상이 보고된 환경에서 증상 경로를 재실행해 확인하는 단계까지가 픽스다. **1순위 = 라이브 게이트**(`{PREVIEW_URL}` 항목 — 워크플로우가 프리뷰에서 자율로 닫음, §라이브 게이트). 프리뷰로 판정 불가한 경로·prod 최종 확인은 명시 승인된 merge/push 후 `live-verify` 스킬(push 확인→배포 폴링→경로 재실행→실패 시 표준 버그 블록으로 재투입). 확인 전에 "해결됨"이라고 보고하지 않는다.
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
`STATE.md` 최소 뼈대 섹션: `## 현재 위치`(단계·다음) / `## 완료`(상세는 git log 위임) / `## 다음 task`(에이전트가 작성하는 `### 목표` / `### 게이트`(auto:·진짜 approval만 human:) / `### 비가역 표면` / 필요 시 `### 그래프`) / `## 열린 결정` / `## 다음 명령`.

## 금지
- 메인이 구현 디테일을 직접 떠안기(컨텍스트 오염) · 에이전트 함대화(task 1개당 implementer 1개) · 미통과를 통과로 위장 · `--no-verify`·`--force`.
