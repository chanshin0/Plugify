export const meta = {
  name: 'spec-building',
  description: '구현 task 1개를 격리 implementer 가 작성+자기검증 → reviewer 리뷰(+Codex 교차검증: 비가역 표면 task 만) → 통과 시 atomic commit → 라이브 게이트({PREVIEW_URL} 항목) 있으면 작업 브랜치 push→프리뷰 프로브까지 통과해야 닫힘(Phase C). 상한 도달 시 메인 에스컬레이션 신호 반환. 스택·도메인 비종속(규칙은 프로젝트 ADR/STATE/기존코드에서).',
  whenToUse: '확정된 task 를 격리해서 구현할 때. args: { task?, acceptance?, projectRoot, isolation?, commit?, maxAttempts? }. task/acceptance 생략 시 STATE.md "다음 task" 를 읽는다.',
  phases: [
    { title: 'Implement', detail: '격리 implementer(sonnet) — 작성 + 자기검증' },
    { title: 'Review', detail: '격리 reviewer(opus) — Codex 병렬 교차검증은 비가역 표면 task 만' },
    { title: 'Commit', detail: '통과 시 atomic commit(haiku) + STATE 갱신 / 미통과 시 에스컬레이션' },
    { title: 'Live', detail: '라이브 게이트 task 만 — 작업 브랜치 push → 지점 preview.sh → 프리뷰 프로브 (main push 금지=사람)' },
  ],
}

// ── 입력 ──────────────────────────────────────────────
// 하니스가 args 를 JSON "문자열"로 전달한다(2026-06-11 첫 실전 관찰 실증: args 수신 로그가 "{\"projectRoot\"...}" 문자열) → 객체로 정규화.
const A = (typeof args === 'string') ? (() => { try { return JSON.parse(args) } catch { return null } })() : (args ?? null)
const task        = A?.task ?? '.planning/STATE.md 의 "## 다음 task" 의 ### 목표 를, 같은 task 의 ### 게이트 항목이 전부 통과하도록 구현하라.'
const acceptance  = A?.acceptance ?? '수용 기준 = .planning/STATE.md 해당 task 의 "### 게이트" 항목 전부 — auto: 는 명시된 명령/테스트/라이브 프로브로 에이전트가 실증하고, human: 은 사람만 제공할 맥락 또는 명시 approval 경계다. 이것을 SSOT 로 따르라.'
const isolation   = A?.isolation === 'worktree' ? { isolation: 'worktree' } : {}
const doCommit    = A?.commit !== false
const MAX         = A?.maxAttempts ?? 3
const runStartedAt = new Date().toISOString()
const runId = (typeof A?.runId === 'string' && A.runId.trim())
  ? A.runId.trim()
  : `spec-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
const transitionEvents = []
function recordEvent(phase, transition, outcome, reasonCode = '', eventAttempt = 0, details = {}) {
  transitionEvents.push({
    at: new Date().toISOString(), phase, transition, outcome, reasonCode, attempt: eventAttempt,
    actorType: details.actorType ?? 'orchestrator',
    triggerSource: details.triggerSource ?? 'workflow',
    meaningful: details.meaningful !== false,
    plannedHumanGate: details.plannedHumanGate === true,
  })
}
function finishRun(terminalState, runAttempts, reviewerBlind, extra = {}) {
  const summary = {
    schemaVersion: '1.0', runId, workflow: 'spec-building',
    startedAt: runStartedAt, endedAt: new Date().toISOString(), terminalState,
    attempts: runAttempts, reviewerBlind,
    humanReintervention: 'not_observable',
    events: transitionEvents.slice(),
    ...extra,
  }
  const eligible = summary.events.filter(e => e.meaningful && !e.plannedHumanGate)
  const autonomous = eligible.filter(e => e.actorType !== 'human' && e.triggerSource !== 'user')
  summary.metrics = {
    agentSelfTurns: autonomous.length,
    eligibleTransitions: eligible.length,
    workflowAutonomousTransitionRatio: eligible.length ? autonomous.length / eligible.length : 'not_observable',
    autonomousCompletion: terminalState === 'verified',
    humanReintervention: summary.humanReintervention,
    reviewCatchRate: 'not_observable',
    postCompletionEscapeRate: 'not_observable',
    wasteRate: 'not_observable',
  }
  return summary
}
function normalizeFileSet(raw) {
  return [...new Set((raw ?? '').split('\n').map(s => s.trim()).filter(Boolean))].sort()
}

// ── 타깃 해석 — 조용한 기본값 금지 ─────────────────────
// 2026-06-11 첫 실전 관찰 사고: 이 하니스에서 args 가 전달되지 않는데 `?? '.'` 폴백이
// 시험을 엉뚱한 레포에서 실행시킴. 정본 채널 = 포인터 파일 /tmp/spec-building.target
// (메인이 Workflow 호출 직전에 절대경로 1줄 기록). args 는 보조 채널.
log(`args 수신(정규화 후): ${JSON.stringify(A)}`)
const argRoot = (typeof A?.projectRoot === 'string' && A.projectRoot.trim()) ? A.projectRoot.trim() : null
const probe = await agent(
  `타깃 디렉토리 해석 — 아래 절차만 수행하고 결과를 반환하라(구현 작업 아님).\n` +
  (argRoot
    ? `1) 후보 경로: ${argRoot}\n`
    : `1) 후보 경로를 \`cat /tmp/spec-building.target\` 으로 읽어라(1줄 절대경로). 파일이 없으면 resolvedRoot 를 빈 문자열로.\n`) +
  `2) 후보 디렉토리가 존재하고 그 안에 .planning/STATE.md 파일이 실재하는지 ls 로 확인.\n` +
  `3) resolvedRoot(절대경로)·statePresent 만 반환. **추측·대체 경로 탐색 금지** — 후보가 무효면 무효라고 반환하라(다른 레포를 찾아내지 마라).`,
  {
    phase: 'Implement', label: '타깃 해석', model: 'haiku',
    schema: {
      type: 'object',
      properties: {
        resolvedRoot: { type: 'string', description: '검증된 절대경로(무효면 빈 문자열)' },
        statePresent: { type: 'boolean', description: '<resolvedRoot>/.planning/STATE.md 실재 여부' },
      },
      required: ['resolvedRoot', 'statePresent'],
    },
  }
)
if (!probe?.statePresent || !probe.resolvedRoot) {
  throw new Error('projectRoot 해석 실패 — args.projectRoot 와 /tmp/spec-building.target 둘 다 유효한 .planning 레포를 가리키지 않음. 조용한 기본값으로 진행하지 않는다(메인: 포인터 파일을 쓰고 재실행).')
}
const projectRoot = probe.resolvedRoot
log(`타깃 확정: ${projectRoot}`)
recordEvent('Resolve', 'target-resolved', 'passed', '', 0, { actorType: 'probe' })
const cdNote      = `작업 디렉토리는 ${projectRoot} 다. Bash 사용 시 항상 먼저 cd ${projectRoot}. 이 디렉토리 밖의 레포를 건드리지 마라.`

// 자율 커밋의 입력 작업트리는 깨끗해야 한다. 기존 사용자 변경·다른 workflow run 증거가 있으면
// git add -A 가 리뷰 대상과 섞을 수 있으므로 구현 전에 pending-human 으로 멈춘다.
const baseline = await agent(
  `작업트리 기준선 확인 — 수정·스테이징·커밋 금지. ${cdNote}\n` +
  `git branch --show-current, git rev-parse HEAD, git status --porcelain 을 실행해 branch·head·statusPorcelain 원문만 반환하라.`,
  {
    phase: 'Resolve', label: '작업트리 기준선', model: 'haiku',
    schema: {
      type: 'object', additionalProperties: false,
      properties: { branch: { type: 'string' }, head: { type: 'string' }, statusPorcelain: { type: 'string' } },
      required: ['branch', 'head', 'statusPorcelain'],
    },
  }
)
if (doCommit && (baseline?.statusPorcelain ?? 'UNKNOWN').trim()) {
  const pendingHuman = {
    reason: '자율 커밋 시작 전 작업트리가 더러움 — 기존 변경과 이번 리뷰 대상을 안전하게 구분할 수 없음',
    nextAction: '기존 변경을 별도 커밋·stash·작업 브랜치로 정리하거나 commit=false로 검토만 수행',
    statusPorcelain: baseline.statusPorcelain,
  }
  recordEvent('Resolve', 'worktree-baseline', 'pending', 'dirty-worktree', 0, { actorType: 'probe' })
  return {
    task, attempts: 0, impl: null, review: null,
    advisories: [], concernDispositions: [], committed: false, commit: null,
    liveGate: null, escalation: null, terminalState: 'pending-human', pendingHuman,
    runSummary: finishRun('pending-human', 0, false, { humanReintervention: 'required', autonomousPathClosed: false, evidence: { baselineHead: baseline?.head ?? '', baselineClean: false } }),
  }
}
recordEvent('Resolve', 'worktree-baseline', 'passed', '', 0, { actorType: 'probe' })

// ── 게이트 검증 — 구현 전에 "통과의 정의"가 있는가 (결정적 반려) ──────────
// Phase A (2026-06-22, SYSTEM.md §6 ★1): STATE "## 다음 task" 는 목표+게이트 형식이어야 한다.
// 게이트(통과 기준)가 없으면 구현하지 않는다 — 검증을 끝으로 미루는 폭포수 차단.
// "게이트 존재/auto 개수"는 속으면 안 되는 판정 → 에이전트는 사실만 읽고, 반려는 코드가 결정한다(타깃 해석과 동일 패턴).
const gate = await agent(
  `STATE 게이트 점검 — 아래만 수행하고 사실을 반환하라(구현·수정·보정 금지).\n` +
  `1) ${projectRoot}/.planning/STATE.md 를 읽어라.\n` +
  `2) "## 다음 task" 섹션만 본다(다음 "## " 헤더 또는 "---" 구분선 전까지).\n` +
  `3) 그 안에 "### 게이트" 하위 섹션이 있는가 → gatePresent.\n` +
  `4) 게이트 항목 글머리 중 "auto:" 로 시작하는 개수 → autoCount, "human:" 으로 시작하는 개수 → humanCount. ` +
  `앞쪽 글머리표(- · *)·체크박스(- [ ])·공백은 무시하고 마커만 센다.\n` +
  `5) 같은 task 안에 "### 비가역 표면" 하위 섹션이 있고 **실질 내용**이 있는가 → irreversiblePresent. ` +
  `섹션이 없거나, 내용이 비었거나, "없음"·"N/A"·"-" 뿐이면 false. 스키마·인증·배포설정 등 실제 표면이 명시돼 있으면 true.\n` +
  `6) "auto:" 항목 중 문자열 "{PREVIEW_URL}" 을 포함하는 것들 → liveItems 에 **항목 원문 그대로**(글머리표 제외) 배열로.\n` +
  `7) "## 다음 task" 섹션 전체를 헤더부터 끝까지 nextTaskRaw 에 **바이트를 보정하지 말고 원문 그대로** 반환하라. preview push 승인 여부를 네가 판정하지 마라.\n` +
  `**친절한 추론 금지** — 형식이 구식(게이트 섹션 없이 "수용 기준:" 산문만)이면 gatePresent=false 로 사실대로 반환하라. 비어 있으면 비었다고 답하라.`,
  {
    phase: 'Implement', label: '게이트 점검', model: 'haiku',
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        gatePresent: { type: 'boolean', description: '"## 다음 task" 안에 "### 게이트" 섹션 실재 여부' },
        autoCount:   { type: 'integer', description: '게이트의 "auto:" 항목 개수' },
        humanCount:  { type: 'integer', description: '게이트의 "human:" 항목 개수' },
        irreversiblePresent: { type: 'boolean', description: '"### 비가역 표면" 섹션이 실질 내용으로 존재("없음"·빈 내용이면 false)' },
        liveItems:   { type: 'array', items: { type: 'string' }, description: '{PREVIEW_URL} 포함 auto: 항목 원문 배열(없으면 빈 배열)' },
        nextTaskRaw: { type: 'string', description: '"## 다음 task" 섹션 헤더부터 끝까지 원문' },
      },
      required: ['gatePresent', 'autoCount', 'humanCount', 'irreversiblePresent', 'liveItems', 'nextTaskRaw'],
    },
  }
)
const gateEmpty = (gate?.autoCount ?? 0) === 0 && (gate?.humanCount ?? 0) === 0
if (!gate?.gatePresent || gateEmpty) {
  throw new Error(
    `게이트 없는 task — 구현 거부. ".planning/STATE.md 의 ## 다음 task" 에 "### 게이트" 가 없거나 비어 있다 ` +
    `(gatePresent=${gate?.gatePresent}, auto=${gate?.autoCount}, human=${gate?.humanCount}). ` +
    `통과의 정의(게이트)를 구현 전에 박아라 — 형식: ### 목표 / ### 게이트(항목마다 "auto:"<명령·테스트·라이브프로브+통과 신호> 또는 "human:"<취향·비가역>, auto≥1 권장) / ### 비가역 표면. ` +
    `(검증을 끝으로 미루는 폭포수 차단 — SYSTEM.md §6 ★1 Phase A)`
  )
}
if ((gate.autoCount ?? 0) === 0) {
  const pendingHuman = {
    reason: `human-only 게이트(auto=0, human=${gate.humanCount}) — 자동으로 증명할 통과 신호가 없어 구현에 진입하지 않음`,
    nextAction: '실제 approval 경계면 필요한 승인·권한·비공개 맥락만 요청하고, 완료 증거 설계 누락이면 메인 에이전트가 auto 신호를 설계해 재실행',
  }
  log(`⏸ ${pendingHuman.reason}`)
  recordEvent('Gate', 'human-gate', 'pending', 'human-only', 0, { plannedHumanGate: true, triggerSource: 'gate' })
  return {
    task, attempts: 0, impl: null, review: null,
    advisories: [], concernDispositions: [],
    committed: false, commit: null, liveGate: null, escalation: null,
    terminalState: 'pending-human', pendingHuman,
    runSummary: finishRun('pending-human', 0, false, { humanReintervention: 'required', autonomousPathClosed: false }),
  }
} else {
  log(`게이트 확인: auto=${gate.autoCount}, human=${gate.humanCount}`)
}
// Codex 교차검증은 비가역 표면 task 만 (2026-07-03 YAGNI 리뷰: 매 task 이중 프런티어 모델의
// 실증된 마진 catch 부재 → 비용 반감. 규칙 정본 = agents/reviewer.md §외부 모델 교차검증).
const codexDirective = gate.irreversiblePresent
  ? 'Codex 교차검증: 수행 — task 에 비가역 표면이 있다(에이전트 정의 §외부 모델 교차검증대로 병렬 실행).'
  : 'Codex 교차검증: 생략 — 비가역 표면 없음(reviewer 단독 판정, summary 에 생략 사실 명시).'
log(gate.irreversiblePresent ? 'Codex 교차검증: 수행(비가역 표면 있음)' : 'Codex 교차검증: 생략(비가역 표면 없음)')
// Phase C (2026-07-03, SYSTEM §6 ★1): {PREVIEW_URL} 게이트 항목 = 라이브 게이트 —
// 커밋 후 작업 브랜치 push → 지점 preview.sh 프리뷰 획득 → 프로브 통과까지가 이 task 의 닫힘.
// 항목 원문을 여기서 캡처해 프로브에 인라인 전달한다 — 이후 STATE 가 어떻게 바뀌든 계약 불변
// (첫 case-03 시험: 커밋 에이전트가 STATE 게이트를 지워 프로브가 0항목 공허 통과한 실결함의 방지책).
const liveItems = Array.isArray(gate.liveItems) ? gate.liveItems.filter(s => typeof s === 'string' && s.includes('{PREVIEW_URL}')) : []
const hasLive = liveItems.length > 0
const hasPendingHuman = (gate.humanCount ?? 0) > 0
const previewPushAuthorized = typeof gate?.nextTaskRaw === 'string' &&
  gate.nextTaskRaw.split(/\r?\n/).some(line => line === 'preview-push: authorized')
if (hasLive && !previewPushAuthorized) {
  const pendingHuman = {
    reason: '프리뷰 생성을 위한 작업 브랜치 push는 외부 전송·원격 변경인데 명시 승인이 기록되지 않음',
    nextAction: '원 요청에 push/preview 배포 승인이 있으면 메인이 STATE에 정확히 "preview-push: authorized"를 기록하고 재실행; 없으면 이 경계에서 승인 요청',
  }
  log(`⏸ ${pendingHuman.reason}`)
  recordEvent('Gate', 'preview-push-approval', 'pending', 'external-write-not-authorized', 0, { plannedHumanGate: true, triggerSource: 'gate' })
  return {
    task, attempts: 0, impl: null, review: null,
    advisories: [], concernDispositions: [], committed: false, commit: null,
    liveGate: null, escalation: null, terminalState: 'pending-human', pendingHuman,
    runSummary: finishRun('pending-human', 0, false, { humanReintervention: 'required', autonomousPathClosed: false }),
  }
}
if (hasLive) log(`라이브 게이트 ${liveItems.length}개 캡처 — 커밋 후 push→프리뷰 프로브로 닫는다 (Phase C)`)

// implementer 상태값 프로토콜(dryforge 이식, 2026-07-06): 판정 이원화 — 사실(상태)은 에이전트,
// 분기(리뷰 생략/진행)는 아래 코드가 결정.
const IMPL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    status:       { type: 'string', enum: ['DONE', 'DONE_WITH_CONCERNS', 'NEEDS_CONTEXT', 'BLOCKED'] },
    filesChanged: { type: 'array', items: { type: 'string' } },
    decisions:    { type: 'string' },
    selfCheck:    { type: 'string' },
    concerns:     { type: 'array', items: { type: 'string' }, description: '비차단 우려(DONE_WITH_CONCERNS 일 때만, 그 외 빈 배열)' },
    missing:      { type: 'string', description: 'NEEDS_CONTEXT/BLOCKED 일 때 부족분 구체 서술(그 외 빈 문자열)' },
  },
  required: ['status', 'filesChanged', 'decisions', 'selfCheck', 'concerns', 'missing'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    pass:    { type: 'boolean' },
    issues:  { type: 'array', items: { type: 'string' } },
    // 조용한 기각 금지(2026-07-06): 비차단 지적은 버리지 않고 advisories 로 반환.
    advisories: { type: 'array', items: { type: 'string' }, description: '비차단 지적(없으면 빈 배열) — 버리지 말고 여기 담는다' },
    concernDispositions: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          concern:     { type: 'string' },
          disposition: { type: 'string', enum: ['resolved', 'accepted', 'blocker'] },
          note:        { type: 'string' },
        },
        required: ['concern', 'disposition', 'note'],
      },
      description: 'implementer 가 DONE_WITH_CONCERNS 로 보고한 concerns 1:1 판정(개수 불일치·미판정 시 코드가 불통과 처리 — 공허 통과 방지 가드)',
    },
    summary: { type: 'string' },
  },
  required: ['pass', 'issues', 'advisories', 'concernDispositions', 'summary'],
}

const CONCERN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    issues: { type: 'array', items: { type: 'string' } },
    advisories: { type: 'array', items: { type: 'string' } },
    concernDispositions: REVIEW_SCHEMA.properties.concernDispositions,
    summary: { type: 'string' },
  },
  required: ['issues', 'advisories', 'concernDispositions', 'summary'],
}

// ── 구현 ↔ 리뷰 ↔ (커밋 → 라이브 게이트) 루프 ──────────
// Phase C: 라이브 게이트 task 는 커밋 후 push→프리뷰 프로브까지 이 루프 안에서 닫는다
// (사람 재트리거 없는 자율 반복 — 상한 MAX 공유). 라이브 게이트 없으면 기존 모양 그대로.
let impl, review = null, feedback = '', attempt = 0, reviewProtocolFailure = null, changesetProtocolFailure = null
let committed = false, commitInfo = null, escalation = null, liveGate = null, blockedInfo = null
let expectedHead = (baseline?.head ?? '').trim()
const expectedBranch = (baseline?.branch ?? '').trim()
while (true) {
  attempt++
  recordEvent('Implement', 'attempt-started', 'started', '', attempt, { triggerSource: attempt > 1 ? 'retry' : 'workflow' })
  // 모델 상향 렁: 마지막 시도만 opus 격상. 단발 실행(maxAttempts=1)은 상향 없음 — 조용한 비용 놀람 방지.
  const lastAttempt = attempt === MAX && MAX > 1
  if (lastAttempt) log(`⚠ 모델 상향(opus) 최종 시도 — implementer 를 opus 로 격상해 투입 (${attempt}/${MAX})`)
  // implementer: 규칙·SSOT·자기검증·상태값 규칙은 에이전트 정의(agents/implementer.md)에 있다 → 프롬프트엔 입력만.
  impl = await agent(
    `구현 task: ${task}\n${cdNote}\n` +
    (acceptance ? `\n수용 기준(전부 만족해야 함):\n${acceptance}\n` : '') +
    (hasLive ? `\n참고: 게이트의 {PREVIEW_URL} 항목(라이브 게이트)은 네 범위 밖이다 — 커밋 후 워크플로우가 push→프리뷰에서 닫는다. 로컬 판정 가능한 게이트만 자기검증하라.\n` : '') +
    (doCommit && !hasLive && !hasPendingHuman ? `\n이 task 는 auto-only 비라이브 경로다. 로컬 auto 게이트를 자기검증한 뒤 .planning/STATE.md 의 해당 task를 완료로 갱신하고 다음 task를 명시하라. 아직 커밋하지 말라 — STATE 변경도 코드와 함께 reviewer가 검증한다.\n` : '') +
    (hasPendingHuman ? `\nhuman 게이트가 남아 있다. .planning/STATE.md 를 완료로 갱신하지 마라. 코드 변경과 자동 검증까지만 수행하라.\n` : '') +
    (feedback ? `\n⚠ 이전 시도가 막혔다. 아래 블로커를 반드시 해결하라:\n${feedback}\n` : '') +
    `\n(역할·읽을 SSOT·자기검증·상태값 규칙은 너의 에이전트 정의에 있다 — 따르라.) 반환은 스키마(status·filesChanged·decisions·selfCheck·concerns·missing) 그대로.`,
    { agentType: 'implementer', phase: 'Implement', label: attempt > 1 ? `구현(재시도 ${attempt}/${MAX})` : '구현', schema: IMPL_SCHEMA, ...isolation, ...(lastAttempt ? { model: 'opus' } : {}) }
  )
  recordEvent('Implement', 'implementation-returned', impl?.status ?? 'unknown', '', attempt, { actorType: 'implementer' })

  // NEEDS_CONTEXT/BLOCKED: 리뷰로는 판정할 게 없다(구현 자체가 성립 안 함) — 리뷰 건너뛰고 missing 을 피드백으로 재투입.
  if (impl?.status === 'NEEDS_CONTEXT' || impl?.status === 'BLOCKED') {
    blockedInfo = impl
    review = null // 이전 시도의 stale 리뷰가 반환(review·advisories·concernDispositions)에 실리는 것 차단 — 이 시도는 리뷰 미도달
    log(`⚠ implementer ${impl.status} — 리뷰 생략. 부족분: ${impl.missing || '(미기재)'}`)
    if (attempt >= MAX) { log(`✗ ${MAX}회 후에도 ${impl.status} — 메인 에스컬레이션 필요`); break }
    feedback = `implementer 가 ${impl.status} 상태를 반환했다 — 아래 부족분을 반드시 보강하라:\n${impl.missing || '(미기재)'}`
    continue
  }
  blockedInfo = null

  // implementer 는 파일만 바꾸고 커밋하지 않는다. attempt 시작의 검증된 HEAD 를 동결해
  // 조기 커밋이 이후 snapshot 기준선으로 흡수되는 것을 막는다.
  const preReviewSnapshot = await agent(
    `implementer 반환 직후·리뷰 전 changeset 동결 — 수정·스테이징·커밋·amend·push 금지. ${cdNote}\n` +
    `기대 브랜치 ${expectedBranch}, 기대 HEAD ${expectedHead}. branch=git branch --show-current, beforeHead=git rev-parse HEAD, statusPorcelain=git status --porcelain, ` +
    `reviewedFiles=(git diff --name-only HEAD; git ls-files --others --exclude-standard | sort -u), ` +
    `reviewedDigest=정렬된 각 경로와 현재 blob hash(삭제는 DELETE)를 묶은 SHA-256 원문을 반환하라. 지어내지 마라.`,
    { phase: 'Review', label: attempt > 1 ? `검토 전 changeset ${attempt}` : '검토 전 changeset', model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, statusPorcelain: { type: 'string' }, reviewedFiles: { type: 'string' }, reviewedDigest: { type: 'string' } },
        required: ['branch', 'beforeHead', 'statusPorcelain', 'reviewedFiles', 'reviewedDigest'] } }
  )
  const preReviewHead = (preReviewSnapshot?.beforeHead ?? '').trim()
  const preReviewFiles = normalizeFileSet(preReviewSnapshot?.reviewedFiles)
  const preReviewDigest = (preReviewSnapshot?.reviewedDigest ?? '').trim()
  if (!expectedBranch || (preReviewSnapshot?.branch ?? '').trim() !== expectedBranch || !/^[0-9a-f]{7,40}$/.test(expectedHead) || preReviewHead !== expectedHead || preReviewFiles.length === 0 || !/^[0-9a-f]{64}$/.test(preReviewDigest)) {
    changesetProtocolFailure = `implementer 브랜치/HEAD 이동 또는 변경 동결 실패(branch=${expectedBranch || '?'}->${(preReviewSnapshot?.branch ?? '').trim() || '?'}, head=${expectedHead || '?'}->${preReviewHead || '?'}, files=${preReviewFiles.length})`
    log(`✗ ${changesetProtocolFailure}`)
    break
  }

  // 최초 reviewer 는 블라인드다. 구현자의 보고·결정·selfCheck·concerns·이전 리뷰를 보지 않고
  // task+수용기준+실제 diff/게이트만으로 먼저 판정을 동결한다(앵커링·자기보고 추종 차단).
  review = await agent(
    `task: ${task}\n${cdNote}\n` +
    (acceptance ? `수용 기준(이 기준으로 pass 판정):\n${acceptance}\n` : '') +
    `${codexDirective}\n` +
    (hasLive ? `라이브 게이트({PREVIEW_URL} 항목)는 리뷰 범위 밖 — 커밋 후 워크플로우 Live 단계가 프리뷰에서 닫는다. 로컬 판정 가능한 게이트만 재실행해 판정하고, 라이브 항목 미실행을 블로커로 삼지 마라.\n` : '') +
    (doCommit && !hasLive && !hasPendingHuman ? `.planning/STATE.md 종결 변경도 리뷰 대상이다. 현재 task 완료 주장이 실제 auto 게이트 결과와 맞고 다음 task가 기존 계획/사용자 지시에 접지됐는지 확인하라. 근거 없는 다음 task 발명·성공 과장이면 fail.\n` : '') +
    (hasPendingHuman ? `human 게이트가 남아 있으므로 .planning/STATE.md가 완료 처리되지 않았는지 확인하라. 완료/verified 표기가 생겼으면 fail.\n` : '') +
    `블라인드 입력 계약: 구현 보고·결정·selfCheck·concerns·이전 리뷰는 제공되지 않는다. 실제 파일과 diff 를 직접 읽고 게이트를 재실행하라. concernDispositions 는 이 단계에서 빈 배열로 반환하라.\n` +
    `(검증·교차검증·판정 규칙은 너의 에이전트 정의에 있다 — 위 Codex 지시와 함께 따르라.)`,
    { agentType: 'reviewer', schema: REVIEW_SCHEMA, phase: 'Review', label: attempt > 1 ? `블라인드 리뷰 ${attempt}` : '블라인드 리뷰' }
  )
  recordEvent('Review', 'blind-verdict', review?.pass ? 'passed' : 'failed', review?.pass ? '' : 'review-blocker', attempt, { actorType: 'reviewer' })

  // 블라인드 verdict 를 먼저 동결한 뒤에만 implementer concerns 를 별도 reviewer 에 공개한다.
  // concern 누락은 구현 재시도가 아니라 이 reconciliation 결과의 실패로 명시된다.
  if (review.pass && impl.status === 'DONE_WITH_CONCERNS') {
    const reconciliation = await agent(
      `블라인드 최초 리뷰는 이미 pass 로 동결됐다. 이제 구현자가 별도로 신고한 concerns 만 실제 diff와 대조해 처분하라. ${cdNote}\n` +
      `task: ${task}\n` +
      `concerns(${impl.concerns?.length ?? 0}개):\n${(impl.concerns ?? []).map((c, i) => `  ${i + 1}. ${c}`).join('\n')}\n` +
      `각 concern 을 resolved/accepted/blocker 로 1:1 판정하라. 구현자의 decisions·selfCheck·이전 리뷰 전문은 보지 않는다.`,
      { agentType: 'reviewer', schema: CONCERN_SCHEMA, phase: 'Review', label: `우려 대조 ${attempt}` }
    )
    recordEvent('Review', 'concerns-reconciled', 'completed', '', attempt, { actorType: 'reviewer' })
    review.concernDispositions = reconciliation?.concernDispositions ?? []
    review.advisories = [...(review.advisories ?? []), ...(reconciliation?.advisories ?? [])]
    review.issues = [...(review.issues ?? []), ...(reconciliation?.issues ?? [])]
    const concernCount = impl.concerns?.length ?? 0
    const dispositions = Array.isArray(review.concernDispositions) ? review.concernDispositions : []
    if (concernCount === 0) {
      review.pass = false
      review.issues = [...(review.issues ?? []), 'DONE_WITH_CONCERNS 인데 concerns 가 비어 있음 — 상태 계약 위반']
    } else if (dispositions.length !== concernCount) {
      review.pass = false
      reviewProtocolFailure = `concernDispositions 개수 불일치(concerns=${concernCount}, dispositions=${dispositions.length}) — reviewer 우려 판정 누락`
      review.issues = [...(review.issues ?? []), reviewProtocolFailure]
    } else {
      const expectedConcerns = [...(impl.concerns ?? [])].map(String).sort()
      const disposedConcerns = dispositions.map(d => String(d?.concern ?? '')).sort()
      const concernIdentityMatched = expectedConcerns.every((c, i) => c === disposedConcerns[i])
      if (!concernIdentityMatched) {
        review.pass = false
        reviewProtocolFailure = 'concernDispositions 원문 1:1 불일치 — concern 중복·누락·치환 감지'
        review.issues = [...(review.issues ?? []), reviewProtocolFailure]
      }
      const promoted = dispositions.filter(d => d?.disposition === 'blocker')
      if (concernIdentityMatched && promoted.length) {
        review.pass = false
        review.issues = [...(review.issues ?? []), ...promoted.map(d => `[concern→blocker 승격] ${d.concern}: ${d.note}`)]
      }
    }
    if ((reconciliation?.issues?.length ?? 0) > 0) review.pass = false
  }

  // pass/fail 어느 쪽이든 reviewer 직후 동일 changeset 을 다시 동결한다. 실패 리뷰가 파일을
  // 바꾼 뒤 다음 implementer 시도에 그 변경을 흡수시키는 경로도 차단한다.
  const reviewedSnapshot = await agent(
    `reviewer 직후 changeset 재동결 — 수정·스테이징·커밋·amend·push 금지. ${cdNote}\n` +
    `branch=git branch --show-current, beforeHead=git rev-parse HEAD, statusPorcelain=git status --porcelain, reviewedFiles=(git diff --name-only HEAD; git ls-files --others --exclude-standard | sort -u) 원문을 반환하라. ` +
    `reviewedFiles 는 파일 경로만 한 줄에 하나씩 중복 없이 정렬해 반환하라. reviewedDigest는 정렬된 각 경로와 현재 blob hash(삭제된 경로는 DELETE)를 묶어 SHA-256 한 값이다. ` +
    `예: 각 reviewedFiles 경로마다 "<경로><TAB><git hash-object 현재파일 또는 DELETE>"를 만들어 전체를 shasum -a 256. 지어내지 마라.`,
    {
      phase: 'Commit', label: attempt > 1 ? `리뷰 changeset ${attempt}` : '리뷰 changeset', model: 'haiku',
      schema: {
        type: 'object', additionalProperties: false,
        properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, statusPorcelain: { type: 'string' }, reviewedFiles: { type: 'string' }, reviewedDigest: { type: 'string' } },
        required: ['branch', 'beforeHead', 'statusPorcelain', 'reviewedFiles', 'reviewedDigest'],
      },
    }
  )
  const reviewedHead = (reviewedSnapshot?.beforeHead ?? '').trim()
  const reviewedFiles = normalizeFileSet(reviewedSnapshot?.reviewedFiles)
  const reviewedDigest = (reviewedSnapshot?.reviewedDigest ?? '').trim()
  const reviewedStatus = (reviewedSnapshot?.statusPorcelain ?? '').trim()
  const preReviewStatus = (preReviewSnapshot?.statusPorcelain ?? '').trim()
  const reviewKeptChangeset = (preReviewSnapshot?.branch ?? '').trim() === expectedBranch && (reviewedSnapshot?.branch ?? '').trim() === expectedBranch &&
    reviewedHead === preReviewHead && reviewedHead === expectedHead &&
    reviewedFiles.length === preReviewFiles.length && reviewedFiles.every((f, i) => f === preReviewFiles[i]) &&
    reviewedDigest === preReviewDigest && reviewedStatus === preReviewStatus
  if (!reviewKeptChangeset) {
    changesetProtocolFailure = `reviewer/게이트가 검토 중 branch·HEAD·파일집합·파일 바이트·status를 변경함(branch ${(preReviewSnapshot?.branch ?? '').trim() || '?'}->${(reviewedSnapshot?.branch ?? '').trim() || '?'}, head ${preReviewHead}->${reviewedHead}, files ${preReviewFiles.length}->${reviewedFiles.length}, digest ${preReviewDigest}->${reviewedDigest}, status ${preReviewStatus || '(clean)'}->${reviewedStatus || '(clean)'})`
    review.pass = false
    review.issues = [...(review.issues ?? []), changesetProtocolFailure]
    recordEvent('Review', 'changeset-unchanged', 'failed', 'review-mutated-changeset', attempt, { actorType: 'probe' })
    log(`✗ ${changesetProtocolFailure}`)
    break
  }
  recordEvent('Review', 'changeset-unchanged', 'passed', '', attempt, { actorType: 'probe' })

  if (!review.pass) {
    if (reviewProtocolFailure) {
      log(`✗ reviewer 프로토콜 실패 — 구현자 재시도 금지: ${reviewProtocolFailure}`)
      break
    }
    if (attempt >= MAX) { log(`✗ ${MAX}회 미통과 — 메인 에스컬레이션 필요`); break }
    feedback = review.issues.join('\n')
    log(`리뷰 블로커 ${review.issues.length}개 → 재시도 ${attempt + 1}/${MAX}: ${review.issues.join(' / ')}`)
    continue
  }
  log(`✓ 리뷰 통과 (시도 ${attempt}/${MAX})`)

  if (!doCommit) break // 커밋 미요청 — 불변 리뷰 통과로 종료
  if (!/^[0-9a-f]{7,40}$/.test(reviewedHead) || reviewedFiles.length === 0 || !/^[0-9a-f]{64}$/.test(reviewedDigest)) {
    commitInfo = { beforeHead: reviewedHead, reviewedFiles, evidenceMatched: false, reason: '리뷰 changeset 동결 실패 또는 변경 파일 없음' }
    recordEvent('Commit', 'reviewed-changeset-captured', 'failed', 'reviewed-changeset-empty', attempt)
    break
  }
  if (!hasLive && !hasPendingHuman && !reviewedFiles.includes('.planning/STATE.md')) {
    recordEvent('Commit', 'reviewed-changeset-captured', 'failed', 'state-not-reviewed', attempt)
    if (attempt >= MAX) {
      commitInfo = { beforeHead: reviewedHead, reviewedFiles: reviewedFiles.join('\n'), evidenceMatched: false, reason: 'auto-only 종결에 필요한 STATE 변경이 reviewer 검증 changeset에 없음' }
      break
    }
    feedback = 'auto-only 비라이브 task의 종결 계약 누락: .planning/STATE.md 해당 task 완료+다음 task 변경을 구현 changeset에 포함하고, auto 게이트와 함께 reviewer가 다시 검증하게 하라.'
    continue
  }
  recordEvent('Commit', 'reviewed-changeset-captured', 'passed', '', attempt)

  // ── 커밋 — 실재는 에이전트 자기보고가 아니라 git 상태로 판정(2026-06-11: haiku 가
  // 커밋 없이 완료 응답 → committed:true 오보고로 메인이 픽스 미포함 push 할 뻔한 사고).
  const commitResult = await agent(
    `리뷰를 통과한 변경을 atomic commit 하라. ${cdNote}\n` +
    `task: ${task}\n` +
    `**중요(2026-06-23 사고 방지): 너는 커밋만 한다 — 새 파일을 만들거나 구현 코드를 수정하지 마라.** implementer/reviewer 가 남긴 작업트리(=리뷰 통과 상태)를 *그대로* 스테이징·커밋만 하라. 코드를 다시 짜거나 새 스크립트/파일을 발명하면 미검증 코드 출하다(실제 사고: commit 에이전트가 reviewer 미검증 파일을 발명·커밋하고 검증본을 작업트리에 방치).\n` +
    (hasLive || hasPendingHuman
      ? `**이 task 는 ${hasLive ? '라이브 게이트' : ''}${hasLive && hasPendingHuman ? '와 ' : ''}${hasPendingHuman ? 'human 게이트' : ''}가 남아 있어 아직 완료가 아니다.** .planning/STATE.md 를 일절 수정하지 말고, 커밋 메시지에 '완료'·'검증됨'을 주장하지 마라.\n`
      : `auto-only 비라이브 task의 STATE 완료 변경은 이미 reviewer가 코드와 함께 검증했다. 그 검증된 STATE를 포함하되 여기서 내용을 다시 수정하지 마라.\n`) +
    `1) git add -A 로 **동결된 리뷰-통과 changeset을 그대로** 스테이징(무관 파일만 제외, 새 파일 생성·코드/STATE 재수정 금지). 2) 한국어 커밋 메시지로 정확히 1개 commit(--no-verify·--force 금지). 메시지 끝: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>\n` +
    `4) commit 직전 git rev-parse HEAD 원문을 beforeHead 에 보존한 뒤 commit 하라. 커밋 후 **반드시 실행한 명령의 출력 원문 그대로** 반환하라: (a) beforeHead, (b) afterHead = git rev-parse HEAD, (c) headLog = git log -1 --format='%H %s', (d) statusPorcelain = git status --porcelain(빈 출력이면 빈 문자열), (e) committedFiles = git show HEAD --stat --format='' 의 출력(이번 커밋이 담은 파일 목록). 출력을 지어내지 마라 — 커밋에 실패했으면 beforeHead=afterHead 로 사실대로 적고 status 원문을 그대로 줘라.`,
    {
      phase: 'Commit', label: attempt > 1 ? `커밋 ${attempt}` : '커밋', model: 'haiku',
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          beforeHead: { type: 'string', description: 'commit 직전 git rev-parse HEAD 출력 원문' },
          afterHead: { type: 'string', description: 'commit 직후 git rev-parse HEAD 출력 원문' },
          headLog: { type: 'string', description: "git log -1 --format='%H %s' 출력 원문" },
          statusPorcelain: { type: 'string', description: 'git status --porcelain 출력 원문(클린이면 빈 문자열)' },
          committedFiles: { type: 'string', description: "git show HEAD --stat --format='' 출력 원문(이번 커밋이 담은 파일 목록)" },
        },
        required: ['beforeHead', 'afterHead', 'headLog', 'statusPorcelain', 'committedFiles'],
      },
    }
  )
  // 커밋 에이전트의 자기보고와 분리된 read-only 증거를 한 번 더 수집한다. 하니스가 직접 shell 을
  // 제공하지 않으므로 완전한 결정적 I/O 는 아니지만, 같은 응답 안의 stale HEAD 재사용·부분 커밋을
  // 코드가 통과시키지 않으며 메인의 최종 git 직접 확인 계약은 그대로 유지한다.
  const commitProof = await agent(
    `커밋 사후 증거 수집 — 수정·스테이징·커밋·amend·push 금지. ${cdNote}\n` +
    `동결 기준 HEAD: ${reviewedHead}\n` +
    `아래 명령을 실행하고 출력 원문만 반환하라: branch=git branch --show-current, afterHead=git rev-parse HEAD, headLog=git log -1 --format='%H %s', ` +
    `revCount=git rev-list --count ${reviewedHead}..HEAD, statusPorcelain=git status --porcelain, ` +
    `committedFiles=git diff --name-only ${reviewedHead}..HEAD. committedFiles 는 파일 경로만 한 줄에 하나씩 반환하라. ` +
    `committedDigest는 committedFiles의 정렬된 각 경로와 현재 blob hash(삭제는 DELETE)를 reviewedDigest와 같은 방식으로 SHA-256 한 값이다. 지어내지 마라.`,
    {
      phase: 'Commit', label: attempt > 1 ? `커밋 증거 ${attempt}` : '커밋 증거', model: 'haiku',
      schema: {
        type: 'object', additionalProperties: false,
        properties: {
          branch: { type: 'string' }, afterHead: { type: 'string' }, headLog: { type: 'string' }, revCount: { type: 'string' },
          statusPorcelain: { type: 'string' }, committedFiles: { type: 'string' }, committedDigest: { type: 'string' },
        },
        required: ['branch', 'afterHead', 'headLog', 'revCount', 'statusPorcelain', 'committedFiles', 'committedDigest'],
      },
    }
  )
  // 판정: HEAD 가 실제로 전진했고, 독립 증거와 일치하며, 트래킹 변경이 남지 않아야 한다.
  // untracked 잔여도 거부하며 committedFiles 공백 역시 실패다.
  const dirty = (commitProof?.statusPorcelain ?? 'UNKNOWN')
    .split('\n').map(l => l.trim()).filter(Boolean)
  const beforeHead = (commitResult?.beforeHead ?? '').trim()
  const afterHead = (commitResult?.afterHead ?? '').trim()
  const proofHead = (commitProof?.afterHead ?? '').trim()
  const logHead = ((commitProof?.headLog ?? '').match(/^([0-9a-f]{7,40})\s/) || [])[1] ?? ''
  const committedFileSet = normalizeFileSet(commitProof?.committedFiles)
  const sameFiles = reviewedFiles.length === committedFileSet.length && reviewedFiles.every((f, i) => f === committedFileSet[i])
  const committedDigest = (commitProof?.committedDigest ?? '').trim()
  const sameContent = committedDigest === reviewedDigest && /^[0-9a-f]{64}$/.test(committedDigest)
  committed = /^[0-9a-f]{7,40}$/.test(beforeHead) && /^[0-9a-f]{7,40}$/.test(afterHead) &&
    beforeHead === reviewedHead && beforeHead !== afterHead && afterHead === proofHead && proofHead === logHead &&
    (commitProof?.branch ?? '').trim() === expectedBranch && (commitProof?.revCount ?? '').trim() === '1' && dirty.length === 0 && committedFileSet.length > 0 && sameFiles && sameContent
  commitInfo = {
    beforeHead, afterHead, headLog: commitProof?.headLog ?? '', committedFiles: committedFileSet.join('\n'),
    reviewedFiles: reviewedFiles.join('\n'), reviewedDigest, committedDigest, revCount: (commitProof?.revCount ?? '').trim(),
    branch: commitProof?.branch ?? '', statusPorcelain: commitProof?.statusPorcelain ?? '', evidenceMatched: afterHead === proofHead && sameFiles && sameContent && (commitProof?.branch ?? '').trim() === expectedBranch,
  }
  recordEvent('Commit', 'commit-evidence-checked', committed ? 'passed' : 'failed', committed ? '' : 'git-evidence-mismatch', attempt, { actorType: 'probe' })
  if (committed) {
    expectedHead = proofHead
    log(`커밋 완료: ${commitProof.headLog}\n  담은 파일:\n${committedFileSet.join('\n')}`)
  }
  else {
    log(`⚠ 커밋 미확인(committed=false) — status 잔여: ${dirty.join(' | ') || '(headLog 불일치)'}. **메인 주의**: committed=false 라도 HEAD 가 이동했을 수 있다(부당/부분 커밋 공존, 2026-06-23 사고). 그냥 작업트리를 덧커밋하지 말고, git log 로 HEAD 이동 여부 + 커밋 파일집합이 리뷰-검증 변경과 일치하는지 먼저 확인하라 — 불일치 시 amend/되돌림으로 수습.`)
    break // 메인 수습 경로(기존 동작) — 라이브 단계 진입 금지(미확인 커밋 push 방지)
  }
  if (!hasLive) break // 라이브 게이트 없는 task — human 게이트가 있으면 종결에서 pending-human

  // ── Phase C: 작업 브랜치 push → 프리뷰 → 라이브 프로브 ──
  // 신뢰 경계: main push(=prod 반영)는 별도 명시 승인 경계 — isMain 이면 push 없이 반환되고 코드가 라이브를 skip 한다.
  const pp = await agent(
    `작업 브랜치 push + 프리뷰 URL 획득 — 아래 절차만 수행하고 사실을 반환하라(코드 수정·커밋·amend 금지). ${cdNote}\n` +
    `1) 현재 브랜치 확인: git branch --show-current. **main 또는 master 면 아무것도 push 하지 말고** isMain=true 로 즉시 반환하라(prod 반영은 별도 명시 승인 경계).\n` +
    `2) git push -u origin <현재 브랜치> (--force 금지). 실패하면 pushed=false + reason 에 에러 원문.\n` +
    `3) bash .planning/preview.sh <현재 브랜치> 를 실행하고 끝까지 기다려라(내부에서 배포 폴링 — 수 분 걸릴 수 있으니 Bash timeout 을 600000ms 로). rc=0 이면 provider 메타데이터로 확인한 DEPLOYED_SHA=<40hex> 줄을 reason의 증거 요약에 포함하고, stdout **마지막 줄**의 프리뷰 URL을 previewUrl 에 넣어라. 파일이 없으면 reason="지점에 .planning/preview.sh 규격 없음", rc≠0 이면 stderr 사유를 reason 에.\n` +
    `4) **출력을 지어내지 마라** — push 실패/URL 미획득이면 그대로 반환하라.`,
    {
      phase: 'Live', label: attempt > 1 ? `push+프리뷰 ${attempt}` : 'push+프리뷰', model: 'haiku',
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          branch:     { type: 'string',  description: 'git branch --show-current 결과' },
          isMain:     { type: 'boolean', description: '현재 브랜치가 main/master 인가(그러면 push 안 함)' },
          pushed:     { type: 'boolean', description: 'origin push 성공 여부' },
          previewUrl: { type: 'string',  description: 'preview.sh 가 반환한 ready 프리뷰 URL(실패 시 빈 문자열)' },
          reason:     { type: 'string',  description: '실패 사유(성공 시 빈 문자열)' },
        },
        required: ['branch', 'isMain', 'pushed', 'previewUrl', 'reason'],
      },
    }
  )
  if (pp?.isMain) {
    liveGate = { status: 'skipped-main-branch', note: 'main 브랜치 — 이 workflow에서 push 금지(prod 반영=별도 명시 승인 경계). 승인된 push 후 live-verify로 닫아라.' }
    log(`⚠ 라이브 게이트 skip: ${liveGate.note}`)
    recordEvent('Live', 'preview-gate', 'pending', 'main-branch', attempt)
    break
  }
  if (!pp?.pushed || !pp?.previewUrl) {
    liveGate = { status: 'preview-failed', branch: pp?.branch ?? '', reason: pp?.reason || 'push/프리뷰 실패(원인 미상)' }
    log(`✗ 프리뷰 획득 실패: ${liveGate.reason}`)
    recordEvent('Live', 'preview-resolve', 'failed', 'preview-failed', attempt, { actorType: 'probe' })
    break
  }
  const previewProof = await agent(
    `프리뷰가 정확한 구현 SHA를 서빙하는지 독립 증거 수집 — 수정·커밋·push 금지. ${cdNote}\n` +
    `기대 구현 SHA ${(commitInfo?.afterHead ?? '').trim()}, 브랜치 ${pp.branch}, 보고 URL ${pp.previewUrl}. ` +
    `localHead=git rev-parse HEAD, remoteHead=git ls-remote origin refs/heads/${pp.branch} SHA를 구하라. ` +
    `bash .planning/preview.sh ${pp.branch} 를 다시 실행해 stdout의 DEPLOYED_SHA=<40hex> 줄을 deployedHead로, 마지막 URL 줄을 proofPreviewUrl로 반환하라. ` +
    `DEPLOYED_SHA가 없거나 provider 배포 메타데이터로 같은 값을 독립 확인할 수 없으면 deployedHead를 빈 문자열로 두어라. evidence에는 시크릿을 마스킹한 명령/출력 요약만.`,
    { phase: 'Live', label: attempt > 1 ? `프리뷰 SHA 증거 ${attempt}` : '프리뷰 SHA 증거', model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: { localHead: { type: 'string' }, remoteHead: { type: 'string' }, deployedHead: { type: 'string' }, proofPreviewUrl: { type: 'string' }, evidence: { type: 'string' } },
        required: ['localHead', 'remoteHead', 'deployedHead', 'proofPreviewUrl', 'evidence'] } }
  )
  const implementationHead = (commitInfo?.afterHead ?? '').trim()
  const previewBound = /^[0-9a-f]{7,40}$/.test(implementationHead) && pp.branch.trim() === expectedBranch &&
    (previewProof?.localHead ?? '').trim() === implementationHead && (previewProof?.remoteHead ?? '').trim() === implementationHead &&
    (previewProof?.deployedHead ?? '').trim() === implementationHead && (previewProof?.proofPreviewUrl ?? '').trim() === pp.previewUrl.trim()
  if (!previewBound) {
    liveGate = { status: 'preview-failed', branch: pp.branch, previewUrl: pp.previewUrl,
      reason: `프리뷰 배포 SHA 미확인/불일치(expected=${implementationHead || '?'}, local=${(previewProof?.localHead ?? '').trim() || '?'}, remote=${(previewProof?.remoteHead ?? '').trim() || '?'}, deployed=${(previewProof?.deployedHead ?? '').trim() || '?'})` }
    log(`✗ ${liveGate.reason}`)
    recordEvent('Live', 'preview-sha-bound', 'failed', 'preview-sha-mismatch', attempt, { actorType: 'probe' })
    break
  }
  recordEvent('Live', 'preview-sha-bound', 'passed', '', attempt, { actorType: 'probe' })
  const probe = await agent(
    `라이브 게이트 프로브 — 아래 절차만 수행하고 사실을 반환하라(코드 수정·커밋·push 금지). ${cdNote}\n` +
    `프리뷰 URL: ${pp.previewUrl}\n` +
    `검증할 라이브 게이트 항목 ${liveItems.length}개 — **아래 목록이 정본이다(STATE 재독 금지, 항목을 빼거나 더하지 마라)**:\n` +
    liveItems.map((it, i) => `  ${i + 1}. ${it}`).join('\n') + '\n' +
    `1) 레포 루트에 .env.local 이 있으면 셸에서 \`set -a; . ./.env.local; set +a\` 로 로드하라(시크릿 값은 출력·반환에 절대 노출 금지).\n` +
    `2) 각 항목의 {PREVIEW_URL} 을 위 프리뷰 URL 로 치환해 명령을 실행하고, 항목에 적힌 통과 신호와 실제 출력을 대조하라.\n` +
    `3) results 에 항목마다 {item, pass, output} 을 담아라 — **${liveItems.length}개 전부**, output 은 실행 출력 원문(시크릿 마스킹).\n` +
    `4) **통과 신호를 지어내지 마라** — 하나라도 불일치면 pass=false, failures 에 항목+실제 출력. **평가 불능 = 실패**: 명령이 대조 전에 죽거나, 출력을 파싱할 수 없거나, 매치 0건이면 그 항목은 pass=false다 — "서버가 로그를 남겼다"·"파일이 생겼다" 같은 부수효과로 pass 를 추론하지 마라.`,
    {
      phase: 'Live', label: attempt > 1 ? `라이브 프로브 ${attempt}` : '라이브 프로브', model: 'haiku',
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          pass:     { type: 'boolean', description: '라이브 게이트 항목 전부 통과 여부' },
          results:  { type: 'array', items: { type: 'object', additionalProperties: false, properties: { item: { type: 'string' }, pass: { type: 'boolean' }, output: { type: 'string' } }, required: ['item', 'pass', 'output'] }, description: '항목별 실행 결과(전 항목 필수)' },
          failures: { type: 'array', items: { type: 'string' }, description: '실패 항목 + 실제 출력(통과면 빈 배열)' },
          evidence: { type: 'string', description: '항목별 실행 명령 + 출력 원문 요약(시크릿 마스킹)' },
        },
        required: ['pass', 'results', 'failures', 'evidence'],
      },
    }
  )
  // 공허 통과 차단(결정적): 캡처된 항목 수만큼 결과가 있고 전부 pass 여야 통과.
  const expectedLiveItems = [...liveItems].map(String).sort()
  const observedLiveItems = Array.isArray(probe?.results) ? probe.results.map(r => String(r?.item ?? '')).sort() : []
  const itemIdentityMatched = expectedLiveItems.length === observedLiveItems.length && expectedLiveItems.every((item, i) => item === observedLiveItems[i])
  const probedAll = Array.isArray(probe?.results) && itemIdentityMatched && probe.results.every(r => r?.pass === true)
  if (probe?.pass && probedAll) {
    liveGate = { status: 'passed', branch: pp.branch, previewUrl: pp.previewUrl, results: probe.results, evidence: probe.evidence }
    log(`✓ 라이브 게이트 ${liveItems.length}/${liveItems.length} 통과 — ${pp.previewUrl} (prod 반영 = 별도 명시 승인 경계)`)
    recordEvent('Live', 'preview-gate', 'passed', '', attempt, { actorType: 'probe' })
  } else if (probe?.pass && !probedAll) {
    liveGate = { status: 'failed', branch: pp.branch, previewUrl: pp.previewUrl, failures: [`프로브 무결성 실패 — pass 주장했으나 항목 원문 멀티셋/결과 불일치(기대 ${liveItems.length}개, 수신 ${probe?.results?.length ?? 0}개 / identity=${itemIdentityMatched}). 공허·중복 통과 방지 가드.`] }
  } else {
    liveGate = { status: 'failed', branch: pp.branch, previewUrl: pp.previewUrl, failures: probe?.failures?.length ? probe.failures : ['프로브 결과 없음'] }
  }
  if (liveGate.status === 'failed') recordEvent('Live', 'preview-gate', 'failed', 'live-gate-failed', attempt, { actorType: 'probe' })
  if (liveGate.status === 'passed') break
  if (attempt >= MAX) { log(`✗ 라이브 게이트 ${MAX}회 미통과 — 메인 에스컬레이션 필요`); break }
  feedback = `라이브 게이트 실패 — 코드가 프리뷰(${pp.previewUrl})에서 실제로 이렇게 동작했다. 반드시 해결하라:\n${liveGate.failures.join('\n')}`
  log(`라이브 블로커 ${liveGate.failures.length}개 → 재시도 ${attempt + 1}/${MAX}`)
}

// ── 라이브 통과 시 종결 커밋 — STATE 는 라이브 실증 *후에만* 완료로 적는다 ──
// (첫 case-03 시험 실결함의 형제 방지책: 검증 전 완료 기록 = 거짓 기록)
if (liveGate?.status === 'passed' && doCommit && !hasPendingHuman) {
  const closureDraft = await agent(
    `라이브 게이트 통과 종결 STATE 제안 — 아래 절차만 수행하라(커밋·push·코드·다른 파일 수정 금지). ${cdNote}\n` +
    `task: ${task}\n` +
    `라이브 실증: 프리뷰 ${liveGate.previewUrl} 에서 라이브 게이트 ${liveItems.length}개 전부 통과(브랜치 ${liveGate.branch}).\n` +
    `.planning/STATE.md 의 "## 다음 task" 에서 **정확히 위 task만** 완료로 갱신하라. 라이브 게이트가 위 프리뷰 URL에서 실증됐음을 기록하고 "prod 반영은 별도 명시 승인 대기"를 명시하라. 다른 task·파일은 손대지 마라. 스테이징·커밋·push 금지. 반환은 changed 사실만.`,
    {
      phase: 'Live', label: '종결 STATE 제안', model: 'haiku',
      schema: {
        type: 'object', additionalProperties: false,
        properties: { changed: { type: 'boolean' } }, required: ['changed'],
      },
    }
  )
  const closurePreReview = await agent(
    `종결 STATE 검토 전 changeset 동결 — 수정·스테이징·커밋·push 금지. ${cdNote}\n` +
    `branch=git branch --show-current, beforeHead=git rev-parse HEAD, reviewedFiles=(git diff --name-only HEAD; git ls-files --others --exclude-standard | sort -u), statusPorcelain=git status --porcelain 원문을 반환하라. ` +
    `reviewedFiles는 경로만 정렬하고, reviewedDigest는 정렬된 각 경로와 현재 blob hash(삭제는 DELETE)를 묶어 SHA-256 한 값이다. 지어내지 마라.`,
    { phase: 'Live', label: '종결 검토 전 changeset', model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, reviewedFiles: { type: 'string' }, reviewedDigest: { type: 'string' }, statusPorcelain: { type: 'string' } },
        required: ['branch', 'beforeHead', 'reviewedFiles', 'reviewedDigest', 'statusPorcelain'] } }
  )
  const closureReview = await agent(
    `라이브 종결 STATE 블라인드 리뷰 — 수정·스테이징·커밋·push 금지. ${cdNote}\n` +
    `현재 task 원문: ${task}\n프리뷰 URL: ${liveGate.previewUrl}\n` +
    `실제 git diff 와 .planning/STATE.md 를 직접 읽어 다음을 검증하라: 변경 파일이 STATE 하나뿐인가, 정확히 현재 task만 완료됐는가, 위 프리뷰 URL과 라이브 실증이 기록됐는가, "prod 반영은 별도 명시 승인 대기"가 명시됐는가, 다른 task를 재작성하지 않았는가. ` +
    `종결 편집자의 자기보고는 입력으로 주어지지 않는다. 하나라도 아니면 pass=false와 issues에 실제 불일치를 적어라.`,
    {
      agentType: 'reviewer', phase: 'Live', label: '종결 STATE 리뷰',
      schema: { type: 'object', additionalProperties: false,
        properties: {
          pass: { type: 'boolean' }, issues: { type: 'array', items: { type: 'string' } },
          stateOnlyChanged: { type: 'boolean' }, targetTaskClosed: { type: 'boolean' }, previewUrlRecorded: { type: 'boolean' },
          prodMergePendingRecorded: { type: 'boolean' }, noOtherTaskRewritten: { type: 'boolean' },
        },
        required: ['pass', 'issues', 'stateOnlyChanged', 'targetTaskClosed', 'previewUrlRecorded', 'prodMergePendingRecorded', 'noOtherTaskRewritten'] },
      }
  )
  const closureSnapshot = await agent(
    `종결 STATE 리뷰 후 changeset 동결 — 수정·스테이징·커밋·push 금지. ${cdNote}\n` +
    `branch=git branch --show-current, beforeHead=git rev-parse HEAD, reviewedFiles=(git diff --name-only HEAD; git ls-files --others --exclude-standard | sort -u), statusPorcelain=git status --porcelain 원문을 반환하라. ` +
    `reviewedFiles는 경로만 정렬하고, reviewedDigest는 정렬된 각 경로와 현재 blob hash(삭제는 DELETE)를 묶어 SHA-256 한 값이다. 지어내지 마라.`,
    { phase: 'Live', label: '종결 changeset', model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, reviewedFiles: { type: 'string' }, reviewedDigest: { type: 'string' }, statusPorcelain: { type: 'string' } },
        required: ['branch', 'beforeHead', 'reviewedFiles', 'reviewedDigest', 'statusPorcelain'] } }
  )
  const closurePreFiles = normalizeFileSet(closurePreReview?.reviewedFiles)
  const closurePostFiles = normalizeFileSet(closureSnapshot?.reviewedFiles)
  const closureReviewUnchanged = (closurePreReview?.branch ?? '').trim() === expectedBranch && (closureSnapshot?.branch ?? '').trim() === expectedBranch &&
    (closurePreReview?.beforeHead ?? '').trim() === (closureSnapshot?.beforeHead ?? '').trim() &&
    closurePreFiles.length === closurePostFiles.length && closurePreFiles.every((file, i) => file === closurePostFiles[i]) &&
    (closurePreReview?.reviewedDigest ?? '').trim() === (closureSnapshot?.reviewedDigest ?? '').trim() &&
    (closurePreReview?.statusPorcelain ?? '').trim() === (closureSnapshot?.statusPorcelain ?? '').trim()
  const closureSemanticsOk = closureDraft?.changed === true && closureReview?.pass === true &&
    closureReview?.stateOnlyChanged === true && closureReview?.targetTaskClosed === true && closureReview?.previewUrlRecorded === true &&
    closureReview?.prodMergePendingRecorded === true && closureReview?.noOtherTaskRewritten === true
  if (!closureReviewUnchanged) {
    liveGate.status = 'closure-failed'
    liveGate.reason = '종결 STATE reviewer가 검토 중 branch·HEAD·파일집합·바이트·status를 변경함'
    liveGate.closure = { verified: false, semanticReview: closureReview, reviewedDigest: closureSnapshot?.reviewedDigest ?? '', reason: liveGate.reason }
    log(`✗ ${liveGate.reason}`)
    recordEvent('Live', 'closure-content-reviewed', 'failed', 'closure-review-mutated-changeset', attempt)
  } else if (!closureSemanticsOk) {
    liveGate.status = 'closure-failed'
    liveGate.reason = `종결 STATE 내용 리뷰 미통과: ${(closureReview?.issues ?? []).join(' / ') || '필수 의미 증거 불충분'}`
    liveGate.closure = { verified: false, semanticReview: closureReview, reason: liveGate.reason }
    log(`✗ ${liveGate.reason}`)
    recordEvent('Live', 'closure-content-reviewed', 'failed', 'closure-content-mismatch', attempt)
  } else {
    recordEvent('Live', 'closure-content-reviewed', 'passed', '', attempt)
    const closureBefore = (closureSnapshot?.beforeHead ?? '').trim()
    const closureReviewedFiles = normalizeFileSet(closureSnapshot?.reviewedFiles)
    const closureStatus = (closureSnapshot?.statusPorcelain ?? 'UNKNOWN').split('\n').map(l => l.trim()).filter(Boolean)
    const closureSnapshotOk = (closureSnapshot?.branch ?? '').trim() === expectedBranch && closureBefore === (commitInfo?.afterHead ?? '') && /^[0-9a-f]{64}$/.test((closureSnapshot?.reviewedDigest ?? '').trim()) &&
      closureReviewedFiles.length === 1 && closureReviewedFiles[0] === '.planning/STATE.md' && closureStatus.length > 0 &&
      closureStatus.every(line => line.endsWith('.planning/STATE.md'))
    if (!closureSnapshotOk) {
      liveGate.status = 'closure-failed'
      liveGate.reason = `종결 STATE changeset 불일치(before=${closureBefore || '?'}, files=${closureReviewedFiles.join(',') || '?'}, status=${closureStatus.join(' | ') || 'clean'})`
      liveGate.closure = { verified: false, semanticReview: closureReview, reviewedDigest: closureSnapshot?.reviewedDigest ?? '', reason: liveGate.reason }
      log(`✗ ${liveGate.reason}`)
      recordEvent('Live', 'closure-evidence-checked', 'failed', 'closure-changeset-mismatch', attempt)
    } else {
      const closure = await agent(
        `리뷰된 종결 STATE 커밋 — 파일을 더 수정하지 말고 현재 .planning/STATE.md 변경만 스테이징·커밋·push 하라. ${cdNote}\n` +
        `git add .planning/STATE.md → 한국어 커밋 정확히 1개(--no-verify·--force 금지, 메시지 끝: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>) → git push origin ${liveGate.branch}. ` +
        `반환 원문: beforeHead(커밋 직전)·afterHead(git rev-parse HEAD)·headLog(git log -1 --format='%H %s')·remoteHead(git ls-remote origin refs/heads/${liveGate.branch} SHA)·statusPorcelain. 지어내지 마라.`,
        { phase: 'Live', label: '종결 커밋', model: 'haiku',
          schema: { type: 'object', additionalProperties: false,
            properties: { beforeHead: { type: 'string' }, afterHead: { type: 'string' }, headLog: { type: 'string' }, remoteHead: { type: 'string' }, statusPorcelain: { type: 'string' } },
            required: ['beforeHead', 'afterHead', 'headLog', 'remoteHead', 'statusPorcelain'] } }
      )
      const closureAfter = (closure?.afterHead ?? '').trim()
      const closureProof = await agent(
        `종결 사후 증거 수집 — 수정·스테이징·커밋·amend·push 금지. ${cdNote}\n` +
        `종결 전 HEAD ${closureBefore}, 브랜치 ${liveGate.branch}. 다음 원문을 반환하라: branch=git branch --show-current, afterHead=git rev-parse HEAD, headLog=git log -1 --format='%H %s', ` +
        `remoteHead=git ls-remote origin refs/heads/${liveGate.branch} SHA, revCount=git rev-list --count ${closureBefore}..HEAD, ` +
        `committedFiles=git diff --name-only ${closureBefore}..HEAD, committedDigest=committedFiles의 정렬된 각 경로와 현재 blob hash(삭제는 DELETE)를 reviewedDigest와 같은 방식으로 SHA-256, statusPorcelain=git status --porcelain. 지어내지 마라.`,
        { phase: 'Live', label: '종결 증거', model: 'haiku',
          schema: { type: 'object', additionalProperties: false,
            properties: { branch: { type: 'string' }, afterHead: { type: 'string' }, headLog: { type: 'string' }, remoteHead: { type: 'string' }, revCount: { type: 'string' }, committedFiles: { type: 'string' }, committedDigest: { type: 'string' }, statusPorcelain: { type: 'string' } },
            required: ['branch', 'afterHead', 'headLog', 'remoteHead', 'revCount', 'committedFiles', 'committedDigest', 'statusPorcelain'] } }
      )
      const proofClosureAfter = (closureProof?.afterHead ?? '').trim()
      const closureRemote = (closureProof?.remoteHead ?? '').trim()
      const closureLogHead = ((closureProof?.headLog ?? '').match(/^([0-9a-f]{7,40})\s/) || [])[1] ?? ''
      const closureDirty = (closureProof?.statusPorcelain ?? 'UNKNOWN').split('\n').map(l => l.trim()).filter(Boolean)
      const closureFiles = normalizeFileSet(closureProof?.committedFiles)
      const closureVerified = (closure?.beforeHead ?? '').trim() === closureBefore && /^[0-9a-f]{7,40}$/.test(closureAfter) &&
        closureBefore !== closureAfter && closureAfter === proofClosureAfter && closureAfter === closureLogHead && closureAfter === closureRemote &&
        (closureProof?.branch ?? '').trim() === expectedBranch && (closureProof?.revCount ?? '').trim() === '1' && closureFiles.length === 1 && closureFiles[0] === '.planning/STATE.md' &&
        (closureProof?.committedDigest ?? '').trim() === (closureSnapshot?.reviewedDigest ?? '').trim() && closureDirty.length === 0
      liveGate.closure = {
        beforeHead: closureBefore, afterHead: proofClosureAfter, headLog: closureProof?.headLog ?? '', remoteHead: closureRemote,
        revCount: (closureProof?.revCount ?? '').trim(), committedFiles: closureFiles.join('\n'), reviewedDigest: closureSnapshot?.reviewedDigest ?? '',
        committedDigest: closureProof?.committedDigest ?? '', statusPorcelain: closureProof?.statusPorcelain ?? '', semanticReview: closureReview, verified: closureVerified,
      }
      if (closureVerified) {
        log(`종결 커밋 검증: ${liveGate.closure.headLog}`)
      } else {
        liveGate.status = 'closure-failed'
        liveGate.reason = `종결 커밋/원격/리뷰 바이트 증거 불일치(before=${closureBefore || '?'}, after=${closureAfter || '?'}, remote=${closureRemote || '?'}, dirty=${closureDirty.length})`
        log(`✗ ${liveGate.reason}`)
      }
      recordEvent('Live', 'closure-evidence-checked', closureVerified ? 'passed' : 'failed', closureVerified ? '' : 'closure-evidence-mismatch', attempt)
    }
  }
} else if (liveGate?.status === 'passed' && hasPendingHuman) {
  liveGate.closure = { verified: false, status: 'pending-human', reason: 'human 게이트가 남아 있어 STATE 종결 커밋을 만들지 않음' }
  recordEvent('Live', 'closure-evidence-checked', 'pending', 'human-gate-open', attempt)
}

// ── 에스컬레이션 판정 (무한 자동 루프 방지 — 상한 도달 시 멈추고 신호만 올린다) ──
if (changesetProtocolFailure) {
  escalation = {
    reason: 'changeset 프로토콜 실패 — 구현/리뷰 단계에서 금지된 HEAD 또는 파일 변조 감지',
    blockers: [changesetProtocolFailure],
    nextOptions: ['git log·status·diff로 조기 커밋/리뷰 변조를 확인하고 검증된 기준선으로 복구', '회귀 평가로 해당 변조 경로를 재현'],
  }
  log(`⚠ 에스컬레이션: ${escalation.reason}`)
} else if (reviewProtocolFailure) {
  escalation = {
    reason: `reviewer 프로토콜 실패 — 구현 변경 문제가 아니므로 implementer 재시도 금지`,
    blockers: [reviewProtocolFailure],
    nextOptions: ['reviewer 입력·스키마·우려 대조 호출을 점검한 뒤 review 단계만 재실행', '반복되면 reviewer 계약 회귀 평가 추가'],
  }
  log(`⚠ 에스컬레이션: ${escalation.reason}`)
} else if (blockedInfo) {
  escalation = {
    reason: `${MAX}회 시도 후에도 implementer ${blockedInfo.status}(리뷰 미도달) — 부족분: ${blockedInfo.missing || '(미기재)'}`,
    blockers: [blockedInfo.missing || '(missing 미기재)'],
    nextOptions: [
      'task/수용 기준에 빠진 정보(스키마·ADR·기존 코드 위치 등)를 STATE·ADR 에 보강한 뒤 재투입',
      MAX > 1 ? '마지막 시도는 이미 opus 였다 — 정보 보강 없는 재시도는 같은 결과일 가능성 높음'
              : '단발 실행(maxAttempts=1)이라 opus 상향이 없었다 — maxAttempts≥2 로 재투입하면 마지막 시도가 opus 로 격상된다',
      '구조적으로 막혔나(외부 의존·권한·환경) → 사용자에게 에스컬레이션',
    ],
  }
  log(`⚠ 에스컬레이션: ${escalation.reason}`)
} else if (!review?.pass) {
  escalation = {
    reason: `${MAX}회 시도 후에도 reviewer 미통과(커밋 보류)`,
    blockers: review?.issues ?? [],
    nextOptions: [
      '수용 기준이 과하거나 모순인가 → STATE 의 수용 기준 조정 후 재투입',
      'task 가 너무 큰가 → 더 작은 단위로 분해 후 각각 재투입',
      MAX > 1 ? '마지막 시도는 이미 opus 로 격상됐다 — 그래도 막히면 maxAttempts 증량보다 task 분해를 우선'
              : '단발 실행(maxAttempts=1)이라 opus 상향이 없었다 — maxAttempts≥2 로 재투입하면 마지막 시도가 opus 로 격상된다',
      '구조적으로 막혔나(외부 의존·환경) → 사용자에게 에스컬레이션',
    ],
  }
  log(`⚠ 에스컬레이션: ${escalation.reason}. 메인이 위 nextOptions 중 택해 재투입할 것.`)
} else if (doCommit && !committed) {
  escalation = {
    reason: '커밋 증거 미확인 — HEAD 전진·사후 증거·커밋 파일집합·작업트리 중 하나 이상 불일치',
    blockers: ['commit-failed'],
    nextOptions: ['메인이 git log -1·git status --short·git show --stat HEAD 로 실제 상태를 확인', '부당 HEAD 이동이면 덧커밋하지 말고 검증된 changeset 으로 복구'],
  }
  log(`⚠ 에스컬레이션: ${escalation.reason}`)
} else if (liveGate && (liveGate.status === 'failed' || liveGate.status === 'preview-failed' || liveGate.status === 'closure-failed')) {
  escalation = {
    reason: liveGate.status === 'failed'
      ? `라이브 게이트 미통과(${MAX}회 상한) — 커밋은 작업 브랜치에 실재, prod 미반영이라 안전`
      : liveGate.status === 'closure-failed'
        ? `라이브 통과 후 종결 실패 — ${liveGate.reason}`
        : `프리뷰 획득 실패 — ${liveGate.reason}`,
    blockers: liveGate.failures ?? [liveGate.reason],
    nextOptions: [
      '프리뷰에서 증상을 재현해 원인 확정(debugger) 후 재투입',
      '그 게이트가 프리뷰에서 판정 불가능한 항목인가 → human: 게이트로 전환 검토',
      'preview-failed 면 지점 .planning/preview.sh·배포 설정부터 수리',
      '구조적으로 막혔나 → 사용자에게 에스컬레이션',
    ],
  }
  log(`⚠ 에스컬레이션: ${escalation.reason}.`)
}

let terminalState = 'incomplete'
if (liveGate?.status === 'closure-failed') terminalState = 'closure-failed'
else if (review?.pass && doCommit && !committed) terminalState = 'commit-failed'
else if (escalation) terminalState = 'escalated'
else if ((gate.humanCount ?? 0) > 0 || liveGate?.status === 'skipped-main-branch') terminalState = 'pending-human'
else if (!doCommit && review?.pass) terminalState = 'reviewed-uncommitted'
else if (review?.pass && committed && (!hasLive || liveGate?.status === 'passed')) terminalState = 'verified'
recordEvent('Finalize', 'terminal-state', terminalState, terminalState)

return {
  task, attempts: attempt, impl, review,
  advisories: review?.advisories ?? [],
  concernDispositions: review?.concernDispositions ?? [],
  committed, commit: commitInfo, liveGate, escalation, terminalState,
  pendingHuman: terminalState === 'pending-human'
    ? { reason: hasPendingHuman ? `human 게이트 ${gate.humanCount}개가 남아 STATE 종결·verified 선언을 하지 않음` : 'main 브랜치 prod 반영은 명시 승인 경계임', nextAction: hasPendingHuman ? '해당 approval에 필요한 사람 답·권한을 받으면 에이전트가 증거를 기록하고 종결' : 'prod 반영이 명시 승인되면 에이전트가 main 반영 후 live-verify 실행' }
    : null,
  runSummary: finishRun(terminalState, attempt, true, {
    humanReintervention: terminalState === 'pending-human' ? 'required' : 'not_observable',
    autonomousPathClosed: terminalState === 'verified',
    evidence: {
      commitVerified: committed,
      liveStatus: liveGate?.status ?? 'not-applicable',
      reviewPassed: review?.pass === true,
    },
  }),
}
