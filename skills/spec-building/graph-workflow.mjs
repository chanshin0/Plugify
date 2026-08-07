export const meta = {
  name: 'spec-building-graph',
  description: '에이전트가 만든 evidence-bearing 멀티 task 그래프를 wave(위상정렬·동시 상한 4)로 실행한다: task별 why·evidence·가정·재계획 조건 → 격리 implementer → blind reviewer → 커밋 → merge-gate → base merge → 통합 게이트. 속으면 안 되는 판정은 코드가 맡는다. push 금지(로컬 커밋만)·main 직접작업 금지.',
  whenToUse: '한 STATE task가 여러 하위 task로 갈리고 서로 의존관계가 있을 때. 새 그래프는 contractVersion 2.0과 task별 id·goal·why·targets·depends·evidence·assumptions·risk·replanWhen을 사용한다. 단일 task는 workflow.mjs를 쓴다.',
  phases: [
    { title: 'Resolve', detail: '타깃 해석 + 그래프 추출(haiku 사실 반환) → 결정적 파싱·검증(코드) — 무효 그래프/라이브게이트/main 은 구현 진입 전 반려' },
    { title: 'Wave', detail: 'wave별: worktree 직렬 생성 → implementer→reviewer→커밋 병렬(≤4) → merge-gate 코드 판정 → base merge 직렬 → regen barrier → 통합 게이트' },
    { title: 'Finalize', detail: '전 wave 통과 후 worktree 정리(ancestor 확인 후 remove, 실패 worktree 보존)' },
  ],
}

// ══════════════════════════════════════════════════════════════════════════
// 판정 이원화(Plugify 원칙 "속으면 안 되는 판정은 코드"):
//   - 에이전트(haiku)는 git/명령을 실행하고 **출력 원문 그대로**만 반환한다(사실).
//   - 그래프 유효성(targets 필수 포함) / merge-gate(STATE 불가침·strictly-ahead·diff·target 교집합) /
//     통합 게이트(exit0) / main 차단 / 라이브 게이트 반려 / implementer 상태 분기·concernDispositions
//     1:1 대조 = **전부 아래 순수 JS 가 판정**한다. 조용한 폴백 금지·fail-fast.
//   - risk 생략 = "미분류"(≠ MECHANICAL). 미분류·RISKY 는 검증을 강한 쪽으로 편향(Codex 수행·리뷰 강조),
//     MECHANICAL/NONE 만 약화(Codex 생략). 명시된 잘못된 risk 값은 반려한다.
//   - 신뢰 경계: push 없음(로컬 커밋만) · main/master 직접작업 금지(시작 시 fail-fast) · merge/push는 명시 승인 경계.
//     라이브 게이트({PREVIEW_URL})는 v1 범위 밖 → 시작 시 반려(단일 task 경로 workflow.mjs 로 안내).
// ══════════════════════════════════════════════════════════════════════════

const CONCURRENCY = 4          // wave 내 동시 dispatch 상한
const INTEGRATION_FIX_CAP = 1  // 통합 게이트 실패 시 원인 수정 재투입 상한(초과 = 에스컬레이션)

// ── 입력 ──────────────────────────────────────────────
// 하니스가 args 를 JSON "문자열"로 전달한다(2026-06-11 첫 실전 관찰 실증) → 객체로 정규화.
const A = (typeof args === 'string') ? (() => { try { return JSON.parse(args) } catch { return null } })() : (args ?? null)
const MAX_TASK_ATTEMPTS = A?.maxAttempts ?? 3
const runStartedAt = new Date().toISOString()
const runId = (typeof A?.runId === 'string' && A.runId.trim())
  ? A.runId.trim()
  : `spec-graph-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
log(`args 수신(정규화 후): ${JSON.stringify(A)}`)

function graphEvent(phase, transition, outcome, reasonCode = '', attempt = 0, details = {}) {
  return {
    at: new Date().toISOString(), phase, transition, outcome, reasonCode, attempt,
    actorType: details.actorType ?? 'orchestrator',
    triggerSource: details.triggerSource ?? 'workflow',
    meaningful: details.meaningful !== false,
    plannedHumanGate: details.plannedHumanGate === true,
    ...(details.taskId ? { taskId: details.taskId } : {}),
    ...(details.wave ? { wave: details.wave } : {}),
  }
}

function graphRunSummary(terminalState, reviewerBlind, humanReintervention, autonomousPathClosed, events, evidence) {
  const eligible = events.filter(e => e.meaningful && !e.plannedHumanGate)
  const autonomous = eligible.filter(e => e.actorType !== 'human' && e.triggerSource !== 'user')
  return {
    schemaVersion: '1.0', runId, workflow: 'spec-building-graph',
    startedAt: runStartedAt, endedAt: new Date().toISOString(), terminalState,
    reviewerBlind, humanReintervention, autonomousPathClosed, events, evidence,
    metrics: {
      agentSelfTurns: autonomous.length,
      eligibleTransitions: eligible.length,
      workflowAutonomousTransitionRatio: eligible.length ? autonomous.length / eligible.length : 'not_observable',
      autonomousCompletion: terminalState === 'verified',
      humanReintervention,
      reviewCatchRate: 'not_observable',
      postCompletionEscapeRate: 'not_observable',
      wasteRate: 'not_observable',
    },
  }
}

// ── 순수 JS 검증기 (구현 진입 전, 실패 시 구체 에러로 throw) ─────────────
const RISK_ENUM = ['RISKY', 'MECHANICAL', 'NONE']
const AUTOMATION_COMMAND_PREFIX = /^(?:\.{1,2}\/\S+|\/\S+|npm|pnpm|yarn|bun|node|npx|deno|python3?|pytest|uv|poetry|ruby|bundle|rake|go|cargo|make|cmake|ctest|gradle|mvn|dotnet|swift|xcodebuild|git|rg|grep|bash|sh|zsh|curl|wget|docker|podman|kubectl|terraform|ansible|playwright|vitest|jest|eslint|tsc|biome|env)(?:\s|$)/
const ENGLISH_HUMAN_ROLE = /\b(?:human|user|manager|operator|reviewer|owner|admin(?:istrator)?|supervisor|stakeholder|approver)\b/
const ENGLISH_APPROVAL_ACTION = /\b(?:approv(?:e|al|ed)|confirm(?:ation|ed)?|authoriz(?:e|ation|ed)|consent(?:ed)?|sign ?off|manual (?:qa|review)|visual check)\b/
const ENGLISH_HUMAN_ROLE_COMPACT = /(?:human|user|manager|operator|reviewer|owner|admin(?:istrator)?|supervisor|stakeholder|approver)/
const ENGLISH_APPROVAL_ACTION_COMPACT = /(?:approv(?:e|al|ed)|confirm(?:ation|ed)?|authoriz(?:e|ation|ed)|consent(?:ed)?|signoff|manual(?:qa|review)|visualcheck)/
const KOREAN_HUMAN_ROLE = /(?:사용자|사람|담당자|관리자|운영자|검토자|책임자|승인자)/
const KOREAN_APPROVAL_ACTION = /(?:승인|확인|검토|서명|동의|허가)/

function containsHumanApprovalSignal(...parts) {
  const normalized = parts.join('\n').normalize('NFKC')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2').toLowerCase()
    .replace(/[\p{P}\p{S}_]+/gu, ' ').replace(/\s+/g, ' ').trim()
  const compact = normalized.replace(/\s+/g, '')
  return (ENGLISH_HUMAN_ROLE.test(normalized) && ENGLISH_APPROVAL_ACTION.test(normalized)) ||
    (ENGLISH_HUMAN_ROLE_COMPACT.test(compact) && ENGLISH_APPROVAL_ACTION_COMPACT.test(compact)) ||
    (KOREAN_HUMAN_ROLE.test(normalized) && KOREAN_APPROVAL_ACTION.test(normalized)) ||
    /\bmanual (?:qa|review)(?: sign off)?\b/.test(normalized)
}

function validStringArray(value) {
  return Array.isArray(value) && value.every(x => typeof x === 'string' && x.length > 0)
}

function validateGraph(raw) {
  let g
  try { g = JSON.parse(raw) }
  catch (e) { throw new Error(`그래프 JSON 파싱 실패: ${e.message}. STATE "### 그래프" 의 fenced json 블록이 유효한 JSON 이어야 한다(YAML 아님 — 스크립트가 JSON.parse 로 결정적 검증).`) }
  if (!g || typeof g !== 'object' || Array.isArray(g)) throw new Error('그래프 최상위가 객체가 아님')
  const tasks = g.tasks
  if (!Array.isArray(tasks) || tasks.length === 0) throw new Error('그래프에 tasks 배열이 없거나 비어 있음')
  const hasContractVersion = Object.hasOwn(g, 'contractVersion')
  const contractVersion = hasContractVersion && typeof g.contractVersion === 'string' ? g.contractVersion.trim() : ''
  const shapedContract = contractVersion === '2.0'
  const legacyMigration = !hasContractVersion && A?.allowLegacyGraph === true
  if (!shapedContract && !legacyMigration) {
    throw new Error(`지원하지 않는 graph contractVersion: ${hasContractVersion ? JSON.stringify(g.contractVersion) : '(누락)'} (지원: 정확한 문자열 "2.0"; 버전 없는 legacy는 명시적 allowLegacyGraph migration에서만 허용)`)
  }

  const ids = new Set()
  for (const t of tasks) {
    if (!t || typeof t !== 'object') throw new Error('task 항목이 객체가 아님')
    if (typeof t.id !== 'string' || !t.id.trim()) throw new Error('task.id 가 비어 있음(문자열 필수)')
    if (ids.has(t.id)) throw new Error(`task id 중복: ${t.id} (id 유일성 위반)`)
    ids.add(t.id)
    if (typeof t.goal !== 'string' || !t.goal.trim()) throw new Error(`task ${t.id}: goal 이 비어 있음(각 task goal 필수)`)
    if (shapedContract && (typeof t.why !== 'string' || !t.why.trim())) throw new Error(`task ${t.id}: why 가 비어 있음(contractVersion 2.0은 전체 outcome 기여 이유 필수)`)
    if (t.depends !== undefined && !Array.isArray(t.depends)) throw new Error(`task ${t.id}: depends 는 배열이어야 함`)
    if (shapedContract && !Array.isArray(t.depends)) throw new Error(`task ${t.id}: depends 배열 필수(contractVersion 2.0, 선행 없음은 [])`)
    if (shapedContract && (!Array.isArray(t.evidence) || t.evidence.length === 0)) {
      throw new Error(`task ${t.id}: evidence 는 비어있지 않은 구조화 배열 필수(contractVersion 2.0)`)
    }
    if (shapedContract) {
      const evidenceIds = new Set()
      for (const evidence of t.evidence) {
        const expect = evidence?.expect
        const expectKeys = expect && typeof expect === 'object' && !Array.isArray(expect) ? Object.keys(expect).sort() : []
        const valid = evidence && typeof evidence === 'object' && !Array.isArray(evidence) &&
          typeof evidence.id === 'string' && evidence.id.trim() && evidence.kind === 'command' &&
          typeof evidence.run === 'string' && evidence.run.trim() && expect && typeof expect === 'object' && !Array.isArray(expect) &&
          expectKeys.join(',') === 'exit,outputExcludes,outputIncludes' && typeof expect.exit === 'string' && expect.exit.trim() &&
          validStringArray(expect.outputIncludes) && validStringArray(expect.outputExcludes)
        if (!valid) throw new Error(`task ${t.id}: evidence 항목은 {id,kind:"command",run,expect:{exit,outputIncludes,outputExcludes}} 정확한 구조 필수`)
        if (evidenceIds.has(evidence.id)) throw new Error(`task ${t.id}: evidence id 중복 ${JSON.stringify(evidence.id)}`)
        evidenceIds.add(evidence.id)
        if (!AUTOMATION_COMMAND_PREFIX.test(evidence.run.trim())) {
          throw new Error(`task ${t.id}: evidence.run 은 허용된 비대화형 도구 또는 명시적 스크립트 경로로 시작해야 함(${evidence.id}) — 사람 판정 문장 대신 자동 실행 가능한 명령을 사용`)
        }
        if (containsHumanApprovalSignal(evidence.id, evidence.run, expect.exit, ...expect.outputIncludes, ...expect.outputExcludes)) {
          throw new Error(`task ${t.id}: 사람 승인·확인을 evidence로 표현할 수 없음(${evidence.id}) — approval ledger/human 게이트로 분리`)
        }
        if (!/^(?:0|[1-9]\d*)$/.test(expect.exit.trim())) {
          throw new Error(`task ${t.id}: evidence.expect.exit 은 0 이상의 정수 문자열이어야 함(${evidence.id})`)
        }
      }
    }
    if (shapedContract && (!Array.isArray(t.assumptions) || t.assumptions.some(x => typeof x !== 'string' || !x.trim()))) {
      throw new Error(`task ${t.id}: assumptions 문자열 배열 필수(contractVersion 2.0, 없으면 [])`)
    }
    if (shapedContract && (!Array.isArray(t.replanWhen) || t.replanWhen.length === 0 || t.replanWhen.some(x => typeof x !== 'string' || !x.trim()))) {
      throw new Error(`task ${t.id}: replanWhen 은 비어있지 않은 문자열 배열 필수(contractVersion 2.0)`)
    }
    // targets 필수(2026-07-06 적대 리뷰 A4): 선언이 아예 없으면 merge-gate 의 diff∩targets 검사가
    // 통째로 우회된다 → 비어있지 않은 문자열 배열 강제. 이 그래프 경로는 task마다 리뷰된 파일
    // 커밋 1개를 요구하므로 state/external 표지만 있는 task는 표현할 수 없다. 파일 target 없이
    // 허용하면 임의 파일 diff가 target 검사를 우회한다(2026-08-06 적대 검토 재현).
    if (!Array.isArray(t.targets) || t.targets.length === 0 || t.targets.some(x => typeof x !== 'string' || !x.trim())) {
      throw new Error(`task ${t.id}: targets 는 비어있지 않은 문자열 배열 필수(파일 경로 | "state" | "external") — 선언 없는 task 는 merge-gate(diff∩targets)를 우회하므로 반려한다.`)
    }
    if (!t.targets.some(target => target !== 'state' && target !== 'external')) {
      throw new Error(`task ${t.id}: 그래프 task 는 최소 1개 파일 target 이 필요함 — state/external 표지만 두면 임의 파일 커밋이 merge-gate 를 우회하므로 단일 task/사람 게이트로 분리하라.`)
    }
    // risk 생략 = 미분류(허용). 명시됐다면 enum 3값만 — 그 외는 반려(미분류로 관대 처리하지 않는다).
    if (shapedContract && t.risk === undefined) throw new Error(`task ${t.id}: risk 필수(contractVersion 2.0)`)
    if (t.risk !== undefined && !RISK_ENUM.includes(t.risk)) {
      throw new Error(`task ${t.id}: risk 는 ${RISK_ENUM.join('|')} 중 하나여야 함(받은 값: ${JSON.stringify(t.risk)}). risk 생략은 "미분류"로 허용되지만 명시된 잘못된 값은 반려한다.`)
    }
  }
  // depends 가 실재 id 만 참조(dangling 금지)
  for (const t of tasks) for (const d of (t.depends || [])) {
    if (typeof d !== 'string' || !ids.has(d)) throw new Error(`task ${t.id}: depends 가 실재하지 않는 id 참조(dangling): ${JSON.stringify(d)}`)
  }
  // regen barriers 검증
  const barriers = g.regenBarriers ?? []
  if (!Array.isArray(barriers)) throw new Error('regenBarriers 는 배열이어야 함')
  barriers.forEach((b, i) => {
    if (!b || typeof b !== 'object') throw new Error(`regenBarriers[${i}] 가 객체가 아님`)
    if (!Array.isArray(b.after) || b.after.length === 0) throw new Error(`regenBarriers[${i}].after 는 비어있지 않은 배열이어야 함`)
    for (const a of b.after) if (!ids.has(a)) throw new Error(`regenBarriers[${i}].after dangling id: ${JSON.stringify(a)}`)
    if (typeof b.run !== 'string' || !b.run.trim()) throw new Error(`regenBarriers[${i}].run 명령이 비어 있음`)
    if (!Array.isArray(b.targets) || b.targets.length === 0 || b.targets.some(x => typeof x !== 'string' || !x.trim() || x === 'state' || x === 'external')) {
      throw new Error(`regenBarriers[${i}].targets 는 생성 명령이 바꿀 수 있는 파일/디렉토리 경로의 비어있지 않은 문자열 배열이어야 함(state/external 금지)`)
    }
  })
  // 비순환 — 위상정렬 성공 여부로 판정(실패=순환)
  const waves = topoWaves(tasks)
  const verify = (typeof g.verify === 'string' && g.verify.trim()) ? g.verify.trim() : null
  if (shapedContract && !verify) throw new Error('graph verify 가 비어 있음(contractVersion 2.0은 전체 통합검증 명령 필수)')
  return { contractVersion: shapedContract ? '2.0' : 'legacy-migration', tasks, byId: new Map(tasks.map(t => [t.id, t])), barriers, waves, verify }
}

// 위상정렬 → wave(각 wave = depends 가 전부 충족된 ready set). 순환이면 throw.
function topoWaves(tasks) {
  const byId = new Map(tasks.map(t => [t.id, t]))
  const idx = new Map(tasks.map((t, i) => [t.id, i]))
  const remaining = new Set(tasks.map(t => t.id))
  const done = new Set()
  const waves = []
  while (remaining.size) {
    const ready = [...remaining].filter(id => (byId.get(id).depends || []).every(d => done.has(d)))
    if (ready.length === 0) {
      throw new Error(`그래프에 순환 존재 — 위상정렬 불가(비순환 위반). 남은 task: ${[...remaining].join(', ')}`)
    }
    ready.sort((a, b) => idx.get(a) - idx.get(b))
    waves.push(ready)
    for (const id of ready) { remaining.delete(id); done.add(id) }
  }
  return waves
}

function chunk(arr, n) {
  const out = []
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n))
  return out
}

// 계측 배열에서 task 레코드 조인 — 에이전트가 id 를 task id("T1")로 주든 브랜치명("graph-T1")으로 주든
// 코드가 양쪽을 수용한다(2026-07-06 case-04 ② 첫 시험: merge-gate·merge 판정이 조인 miss 로 오판한 실결함).
// 프롬프트 지시에만 기대지 않는다 — 판정 이원화.
function findByTaskId(arr, id, branch) {
  return (arr || []).find(x => x?.id === id || (branch && x?.id === branch))
}

function normalizeFileSet(raw) {
  return [...new Set((raw ?? '').split('\n').map(s => s.trim()).filter(Boolean))].sort()
}

function judgeIndependentCommit(snapshot, reported, proof, expectedBranch = null) {
  const snapshotBranch = (snapshot?.branch ?? '').trim()
  const proofBranch = (proof?.branch ?? '').trim()
  const branchOk = expectedBranch ? snapshotBranch === expectedBranch && proofBranch === expectedBranch : true
  const beforeHead = (snapshot?.beforeHead ?? '').trim()
  const reportedBefore = (reported?.beforeHead ?? '').trim()
  const reportedAfter = (reported?.afterHead ?? '').trim()
  const proofAfter = (proof?.afterHead ?? '').trim()
  const logHead = ((proof?.headLog ?? '').match(/^([0-9a-f]{7,40})\s/) || [])[1] ?? ''
  const reviewedFiles = normalizeFileSet(snapshot?.reviewedFiles)
  const committedFiles = normalizeFileSet(proof?.committedFiles)
  const reviewedDigest = (snapshot?.reviewedDigest ?? '').trim()
  const committedDigest = (proof?.committedDigest ?? '').trim()
  const dirty = (proof?.statusPorcelain ?? 'UNKNOWN').split('\n').map(l => l.trim()).filter(Boolean)
  const sameFiles = reviewedFiles.length === committedFiles.length && reviewedFiles.every((f, i) => f === committedFiles[i])
  const sameContent = /^[0-9a-f]{64}$/.test(reviewedDigest) && committedDigest === reviewedDigest
  const ok = branchOk && /^[0-9a-f]{7,40}$/.test(beforeHead) && reportedBefore === beforeHead && reportedAfter !== beforeHead &&
    reportedAfter === proofAfter && proofAfter === logHead && (proof?.revCount ?? '').trim() === '1' &&
    reviewedFiles.length > 0 && sameFiles && sameContent && dirty.length === 0
  return { ok, branchOk, snapshotBranch, proofBranch, beforeHead, afterHead: proofAfter, reviewedFiles, committedFiles, reviewedDigest, committedDigest, dirty, sameFiles, sameContent, revCount: (proof?.revCount ?? '').trim() }
}

// merge-gate 판정(결정적, dryforge 이식 핵심): ⓪ STATE 불가침 ① strictly ahead ② diff 비어있지 않음
// ③ diff 파일이 선언 file target 과 교집합(파일 target 있는 task 만). 대상 밖 파일 = 경고.
function judgeMergeGate(task, revCount, diffFilesRaw) {
  const ahead = Number.parseInt((revCount || '').trim(), 10) === 1
  const files = (diffFilesRaw || '').split('\n').map(s => s.trim()).filter(Boolean)
  const nonEmpty = files.length > 0
  const fileTargets = (task.targets || []).filter(t => t !== 'state' && t !== 'external')
  const hasFileTarget = fileTargets.length > 0
  const matches = f => fileTargets.some(t => { const n = t.replace(/\/+$/, ''); return f === n || f.startsWith(n + '/') })
  // ⓪ STATE 불가침(2026-07-06 적대 리뷰 A5, 코드 판정): 그래프 task 커밋이 .planning/STATE.md 를
  // 건드렸으면 경고가 아니라 **게이트 실패** — 종결 기록은 그래프 완주 후 메인 몫(case-03 계열
  // "검증 전 STATE 완료 기록" 실사고의 병렬 경로 방지책). target 유형과 무관하게 적용.
  if (files.includes('.planning/STATE.md')) {
    return { pass: false, reason: 'diff 에 .planning/STATE.md 포함 — STATE 불가침 위반(종결 기록은 그래프 완주 후 메인 몫). merge 거부', warnings: [], noFileDiff: !hasFileTarget, stateViolation: true }
  }
  if (!hasFileTarget) return { pass: false, reason: '파일 target 없음 — 임의 파일 diff 우회 방지', warnings: [], noFileDiff: true }
  const intersect = files.some(matches)
  const extra = files.filter(f => !matches(f))
  const reasons = []
  if (!ahead) reasons.push('rev-list 가 정확히 1이 아님(atomic commit 계약 위반)')
  if (!nonEmpty) reasons.push('diff 비어 있음')
  if (!intersect) reasons.push(`diff 파일이 선언 targets(${fileTargets.join(', ')})와 교집합 없음`)
  if (extra.length) reasons.push(`선언 targets 밖 파일 포함: ${extra.join(', ')}`)
  return {
    pass: ahead && nonEmpty && intersect && extra.length === 0,
    reason: reasons.join('; '),
    warnings: [],
    noFileDiff: false,
  }
}

// ── 에이전트 계약 스키마 — **skills/spec-building/workflow.mjs 의 IMPL_SCHEMA/REVIEW_SCHEMA 복제**
// (2026-07-06 적대 리뷰 B1: 워크플로우 스크립트는 파일 간 import 불가 → 복제. 정본이 바뀌면 여기도 동기화.)
// implementer 상태값 프로토콜(dryforge 이식): 사실(status)은 에이전트가, 분기(리뷰 생략/재투입/실패 처리)는 코드가.
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
    // 조용한 기각 금지: 비차단 지적은 버리지 않고 advisories 로 반환.
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
const TASK_REVIEW_SCHEMA = {
  ...REVIEW_SCHEMA,
  properties: {
    ...REVIEW_SCHEMA.properties,
    evidenceResults: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          id: { type: 'string' },
          run: { type: 'string' },
          exit: { type: 'string', description: '실행한 명령의 exit code 원문' },
          output: { type: 'string', description: '통과/실패를 판단할 최소 출력 원문' },
          passed: { type: 'boolean' },
        },
        required: ['id', 'run', 'exit', 'output', 'passed'],
      },
      description: 'task evidence 각 항목을 reviewer가 직접 실행한 1:1 결과. 순서·id·run·통과를 코드가 대조한다.',
    },
  },
  required: [...REVIEW_SCHEMA.required, 'evidenceResults'],
}
const CONCERN_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    issues: { type: 'array', items: { type: 'string' } },
    advisories: { type: 'array', items: { type: 'string' } },
    concernDispositions: REVIEW_SCHEMA.properties.concernDispositions,
    summary: { type: 'string' },
  },
  required: ['issues', 'advisories', 'concernDispositions', 'summary'],
}

// 조용한 기각 금지 가드(코드 판정 — workflow.mjs 동일 로직 이식): DONE_WITH_CONCERNS 면
// concernDispositions 가 concerns 와 1:1 이어야 하고, disposition 'blocker' 는 issues 로 승격.
function applyConcernGuard(impl, review) {
  if (impl?.status !== 'DONE_WITH_CONCERNS' || !review) return review
  const concernCount = impl.concerns?.length ?? 0
  const dispositions = Array.isArray(review.concernDispositions) ? review.concernDispositions : []
  if (concernCount === 0) {
    review.pass = false
    review.issues = [...(review.issues ?? []), 'DONE_WITH_CONCERNS 인데 concerns 가 비어 있음 — 상태 계약 위반']
  } else if (dispositions.length !== concernCount) {
    review.pass = false
    review.protocolFailure = `concernDispositions 개수 불일치(concerns=${concernCount}, dispositions=${dispositions.length}) — reviewer 우려 판정 누락`
    review.issues = [...(review.issues ?? []), review.protocolFailure]
  } else {
    const expectedConcerns = [...(impl.concerns ?? [])].map(String).sort()
    const disposedConcerns = dispositions.map(d => String(d?.concern ?? '')).sort()
    const concernIdentityMatched = expectedConcerns.every((c, i) => c === disposedConcerns[i])
    if (!concernIdentityMatched) {
      review.pass = false
      review.protocolFailure = 'concernDispositions 원문 1:1 불일치 — concern 중복·누락·치환 감지'
      review.issues = [...(review.issues ?? []), review.protocolFailure]
    }
    const promoted = dispositions.filter(d => d?.disposition === 'blocker')
    if (concernIdentityMatched && promoted.length) {
      review.pass = false
      review.issues = [...(review.issues ?? []), ...promoted.map(d => `[concern→blocker 승격] ${d.concern}: ${d.note}`)]
    }
  }
  return review
}
async function reconcileAfterBlind(impl, review, context, label) {
  if (!review?.pass || impl?.status !== 'DONE_WITH_CONCERNS') return review
  const reconciliation = await agent(
    `블라인드 최초 리뷰는 이미 pass 로 동결됐다. 이제 구현자가 신고한 concerns 만 실제 diff와 대조해 처분하라. ${context}\n` +
    `concerns(${impl.concerns?.length ?? 0}개):\n${(impl.concerns ?? []).map((c, i) => `  ${i + 1}. ${c}`).join('\n')}\n` +
    `각 concern 을 resolved/accepted/blocker 로 1:1 판정하라. 구현자의 decisions·selfCheck·이전 리뷰 전문은 보지 않는다.`,
    { agentType: 'reviewer', schema: CONCERN_SCHEMA, phase: 'Wave', label }
  )
  review.concernDispositions = reconciliation?.concernDispositions ?? []
  review.advisories = [...(review.advisories ?? []), ...(reconciliation?.advisories ?? [])]
  review.issues = [...(review.issues ?? []), ...(reconciliation?.issues ?? [])]
  if ((reconciliation?.issues?.length ?? 0) > 0) review.pass = false
  return applyConcernGuard(impl, review)
}
function applyEvidenceGuard(task, review) {
  if (graph?.contractVersion !== '2.0' || !review) return review
  const expected = task.evidence ?? []
  const results = Array.isArray(review.evidenceResults) ? review.evidenceResults : []
  const expectedIds = expected.map(e => e.id)
  const resultIds = results.map(r => r?.id)
  const uniqueResults = new Set(resultIds).size === resultIds.length
  const identityMatched = expected.length === results.length && uniqueResults &&
    expected.every((e, i) => resultIds[i] === e.id && results[i]?.run === e.run)
  const judgments = identityMatched ? expected.map((e, i) => {
    const result = results[i]
    const output = String(result?.output ?? '')
    const actualExit = String(result?.exit ?? '').trim()
    const expectedExit = e.expect.exit.trim()
    const missing = e.expect.outputIncludes.filter(marker => !output.includes(marker))
    const forbidden = e.expect.outputExcludes.filter(marker => output.includes(marker))
    const mechanicallyPassed = actualExit === expectedExit && missing.length === 0 && forbidden.length === 0
    return { id: e.id, mechanicallyPassed, reviewerPassed: result?.passed === true, actualExit, expectedExit, missing, forbidden }
  }) : []
  const allPassed = identityMatched && judgments.every(j => j.mechanicallyPassed && j.reviewerPassed)
  if (!allPassed) {
    review.pass = false
    const issue = !identityMatched
      ? `evidenceResults 1:1 불일치(expected=${expectedIds.join(',')}, actual=${resultIds.join(',')})`
      : `task evidence 미통과: ${judgments.filter(j => !j.mechanicallyPassed || !j.reviewerPassed).map(j => `${j.id}(exit=${j.actualExit}/${j.expectedExit},missing=${JSON.stringify(j.missing)},forbidden=${JSON.stringify(j.forbidden)},reviewerPassed=${j.reviewerPassed})`).join('; ')}`
    if (!identityMatched) review.protocolFailure = issue
    review.issues = [...(review.issues ?? []), issue]
  }
  return review
}
const REPLAN_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    triggered: { type: 'boolean' },
    matchedCondition: { type: 'string' },
    reason: { type: 'string' },
  },
  required: ['triggered', 'matchedCondition', 'reason'],
}
async function assessReplan(task, failureEvidence, label) {
  if (graph?.contractVersion !== '2.0') return { triggered: false, matchedCondition: '', reason: 'legacy migration' }
  return agent(
    `재계획 조건 대조 — 구현·수정·커밋 금지. task ${task.id}.\n` +
    `사전 replanWhen:\n${task.replanWhen.map((x, i) => `${i + 1}. ${x}`).join('\n')}\n\n` +
    `새 실패 증거:\n${failureEvidence}\n\n` +
    `실패 증거가 사전 조건 중 하나를 실제로 충족하면 triggered=true와 원문 조건을 matchedCondition에 반환하라. 단순 구현 실수로 같은 접근 안에서 고칠 수 있으면 false. 추측 금지.`,
    { phase: 'Wave', label, model: 'haiku', schema: REPLAN_SCHEMA }
  )
}
const COMMIT_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    beforeHead: { type: 'string', description: 'commit 직전 git rev-parse HEAD 원문' },
    afterHead: { type: 'string', description: 'commit 직후 git rev-parse HEAD 원문' },
    headLog: { type: 'string', description: "git log -1 --format='%H %s' 원문" },
    statusPorcelain: { type: 'string', description: 'git status --porcelain 원문(클린이면 빈 문자열)' },
    committedFiles: { type: 'string', description: "git show HEAD --stat --format='' 원문" },
  },
  required: ['beforeHead', 'afterHead', 'headLog', 'statusPorcelain', 'committedFiles'],
}

// ── 타깃 해석 — 조용한 기본값 금지(workflow.mjs 와 동일 패턴) ──────────────
const argRoot = (typeof A?.projectRoot === 'string' && A.projectRoot.trim()) ? A.projectRoot.trim() : null
const probe = await agent(
  `타깃 디렉토리 해석 — 아래 절차만 수행하고 결과를 반환하라(구현 작업 아님).\n` +
  (argRoot
    ? `1) 후보 경로: ${argRoot}\n`
    : `1) 후보 경로를 \`cat /tmp/spec-building.target\` 으로 읽어라(1줄 절대경로). 파일이 없으면 resolvedRoot 를 빈 문자열로.\n`) +
  `2) 후보 디렉토리가 존재하고 그 안에 .planning/STATE.md 가 실재하는지 ls 로 확인.\n` +
  `3) resolvedRoot(절대경로)·statePresent 만 반환. **추측·대체 경로 탐색 금지** — 후보가 무효면 무효라고 반환하라.`,
  {
    phase: 'Resolve', label: '타깃 해석', model: 'haiku',
    schema: {
      type: 'object', additionalProperties: false,
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
const cdBase = `작업 디렉토리 base = ${projectRoot} 다. Bash 사용 시 항상 먼저 cd ${projectRoot}. 이 디렉토리 밖 레포를 건드리지 마라.`
log(`타깃 확정: ${projectRoot}`)

// ── 정찰: 현재 브랜치 + 그래프 원문 + 라이브게이트 유무 + 전체 목표 (haiku 사실 반환) ──
const recon = await agent(
  `그래프 실행 정찰 — 아래만 수행하고 사실을 반환하라(구현·수정·보정 금지). ${cdBase}\n` +
  `1) 현재 브랜치: git branch --show-current 결과를 currentBranch 로, git rev-parse HEAD 결과를 currentHead 로.\n` +
  `2) ${projectRoot}/.planning/STATE.md 를 읽어라. "## 다음 task" 섹션만 본다(다음 "## " 헤더 또는 "---" 전까지).\n` +
  `3) 그 안 "### 그래프" 하위의 \`\`\`json ... \`\`\` fenced 블록 **내용을 fence 제외 원문 그대로** graphRaw 로. 블록이 없으면 빈 문자열.\n` +
  `4) "## 다음 task" 섹션 어디든 문자열 "{PREVIEW_URL}" 이 등장하면 hasPreviewUrl=true(라이브 게이트 표시), 없으면 false.\n` +
  `5) "### 목표" 하위 텍스트(전체 목표)를 overallGoal 로(없으면 빈 문자열).\n` +
  `6) "### 게이트" 하위 섹션 존재 여부를 gatePresent 로, 글머리 항목 중 "auto:" 개수를 autoCount, "human:" 개수를 humanCount 로. 앞쪽 글머리표·체크박스·공백은 무시하고 마커만 센다.\n` +
  `7) git status --porcelain 원문을 statusPorcelain 로.\n` +
  `**친절한 추론·보정 금지** — 있는 그대로 반환하라.`,
  {
    phase: 'Resolve', label: '정찰', model: 'haiku',
    schema: {
      type: 'object', additionalProperties: false,
      properties: {
        currentBranch: { type: 'string', description: 'git branch --show-current 결과' },
        currentHead: { type: 'string', description: 'git rev-parse HEAD 결과' },
        graphRaw: { type: 'string', description: '### 그래프 의 json fenced 블록 원문(없으면 빈 문자열)' },
        hasPreviewUrl: { type: 'boolean', description: '"## 다음 task" 에 "{PREVIEW_URL}" 등장 여부' },
        overallGoal: { type: 'string', description: '### 목표 텍스트(없으면 빈 문자열)' },
        gatePresent: { type: 'boolean', description: '### 게이트 섹션 존재 여부' },
        autoCount: { type: 'integer', description: 'auto: 게이트 개수' },
        humanCount: { type: 'integer', description: 'human: 게이트 개수' },
        statusPorcelain: { type: 'string', description: 'base 작업트리 git status --porcelain 원문' },
      },
      required: ['currentBranch', 'currentHead', 'graphRaw', 'hasPreviewUrl', 'overallGoal', 'gatePresent', 'autoCount', 'humanCount', 'statusPorcelain'],
    },
  }
)

// ── fail-fast 게이트 (코드 판정 — 구현 진입 전) ───────────────────────────
const baseBranch = (recon?.currentBranch || '').trim()
let expectedBaseHead = (recon?.currentHead || '').trim()
if (baseBranch === 'main' || baseBranch === 'master' || baseBranch === '') {
  throw new Error(`그래프 실행은 작업 브랜치에서 — 현재 브랜치 "${baseBranch || '(불명)'}". main/master 직접 그래프 실행은 신뢰 경계 위반(prod 반영·merge는 별도 명시 승인 경계). 작업 브랜치를 만들고(git checkout -b <branch>) 재실행하라.`)
}
if (!/^[0-9a-f]{7,40}$/.test(expectedBaseHead)) {
  throw new Error(`그래프 실행 base HEAD 확인 실패 — currentHead=${expectedBaseHead || '(불명)'}`)
}
if ((recon?.statusPorcelain ?? 'UNKNOWN').trim()) {
  throw new Error(`그래프 실행 전 base 작업트리가 더러움 — 기존 변경과 wave merge 를 안전하게 구분할 수 없어 구현 진입 전 반려. 먼저 별도 커밋·stash·브랜치로 정리하라. status: ${recon.statusPorcelain}`)
}
if (recon?.hasPreviewUrl) {
  throw new Error(`라이브 게이트({PREVIEW_URL})는 그래프 실행 v1 범위 밖이다 — 반려. 라이브로 닫는 task 는 단일 task 경로(workflow.mjs, Phase C)로 실행하라(그래프는 로컬 검증·merge-gate·통합 게이트까지만 자율, 프리뷰/push 는 다루지 않는다).`)
}
if (!recon?.gatePresent || ((recon?.autoCount ?? 0) === 0 && (recon?.humanCount ?? 0) === 0)) {
  throw new Error(`그래프 task 게이트가 없거나 비어 있음(gatePresent=${recon?.gatePresent}, auto=${recon?.autoCount}, human=${recon?.humanCount}) — 구현 전 통과의 정의를 명시하라.`)
}
if (!recon?.graphRaw?.trim()) {
  throw new Error('그래프 없음 — "## 다음 task" 에 "### 그래프" + fenced json 블록이 없다. 그래프 실행은 멀티 task 그래프를 요구한다(단일 task 는 workflow.mjs).')
}

// ── 그래프 결정적 파싱·검증 (무효면 여기서 throw — 구현 0) ──────────────
const graph = validateGraph(recon.graphRaw.trim())
const overallGoal = (recon.overallGoal || '').trim()
const hasPendingHuman = (recon.humanCount ?? 0) > 0
if ((recon.autoCount ?? 0) === 0) {
  const terminalState = 'pending-human'
  const pendingHuman = { reason: `human-only 그래프 게이트(auto=0, human=${recon.humanCount}) — 구현에 진입하지 않음`, nextAction: '실제 approval 경계면 필요한 승인·권한·비공개 맥락만 요청하고, 증거 설계 누락이면 메인 에이전트가 auto/evidence를 보강해 재실행' }
  return {
    projectRoot, baseBranch, waves: [], taskResults: {}, integration: [], allMerged: false,
    escalation: null, terminalState, pendingHuman,
    runSummary: graphRunSummary(
      terminalState, false, 'required', false,
      [graphEvent('Resolve', 'human-gate', 'pending', 'human-only', 0, { plannedHumanGate: true, triggerSource: 'gate' })],
      { allMerged: false, integrationPassed: false },
    ),
  }
}
log(`그래프 검증 통과 — contract ${graph.contractVersion} · task ${graph.tasks.length}개 · wave ${graph.waves.length}개(${graph.waves.map((w, i) => `w${i + 1}[${w.join(',')}]`).join(' ')}) · regenBarriers ${graph.barriers.length}개 · verify ${graph.verify ? `"${graph.verify}"` : '(미지정 — STATE/pkg 에서 발견 시도)'}`)

// verify 명령 확정: graph.verify 우선(결정적, STATE 그래프 블록 내). 없으면 발견 에이전트(원문 반환).
let verifyCmd = graph.verify
if (!verifyCmd) {
  const vd = await agent(
    `통합 검증 명령 발견 — 아래만 수행하고 사실을 반환하라(실행·수정 금지). ${cdBase}\n` +
    `1) .planning/STATE.md 와 package.json(있으면) 을 읽어 프로젝트 verify(테스트/빌드) 명령을 찾아라.\n` +
    `2) 가장 대표적인 1개를 verifyCmd 로 원문 반환(예: "node --test test/*.test.js", "npm test"). 없으면 빈 문자열.\n` +
    `**명령을 지어내지 마라** — 근거가 없으면 빈 문자열.`,
    { phase: 'Resolve', label: 'verify 발견', model: 'haiku',
      schema: { type: 'object', additionalProperties: false, properties: { verifyCmd: { type: 'string' } }, required: ['verifyCmd'] } }
  )
  verifyCmd = (vd?.verifyCmd || '').trim() || null
  log(`verify 발견: ${verifyCmd ? `"${verifyCmd}"` : '없음(통합 게이트는 기록된 생략 — 침묵 아님)'}`)
}

// risk → 검증 지시(미분류·RISKY = 강, MECHANICAL/NONE = 약)
function riskDirectives(task) {
  const r = task.risk // undefined = 미분류
  const strong = (r === 'RISKY' || r === undefined)
  const implNote = strong
    ? `이 task 는 ${r === undefined ? '미분류(risk 생략 — 강한 쪽으로 편향)' : 'RISKY'} 다 — 엣지케이스·불변식·상태조율·검증 규칙을 특히 꼼꼼히 구현·자기검증하라.`
    : `이 task 는 ${r} 로 분류됐다 — 그래도 자기검증(게이트 재실행)은 생략하지 마라.`
  const codex = strong
    ? 'Codex 교차검증: 수행 — RISKY/미분류(에이전트 정의 §외부 모델 교차검증대로 병렬 실행).'
    : 'Codex 교차검증: 생략 — MECHANICAL/NONE(reviewer 단독 판정, summary 에 생략 명시).'
  return { implNote, codex }
}

// ══════════════════════════════════════════════════════════════════════════
// wave 실행
// ══════════════════════════════════════════════════════════════════════════
const wtPath = id => `${projectRoot}/.planning/worktrees/${id}`
const branchOf = id => `graph-${id}`

const taskResults = {}      // id -> { status, review?, commit?, mergeGate?, merged? }
const completed = new Set() // base 로 merge 성공한 id
const ranBarriers = new Set()
const waveSummaries = []
const integration = []      // wave별 통합 게이트 결과
let escalation = null

function escalate(reason, blockers, nextOptions) {
  escalation = { reason, blockers: blockers ?? [], nextOptions: nextOptions ?? [] }
  log(`⚠ 에스컬레이션: ${reason}`)
}

// 한 task 파이프라인: implementer → reviewer → 커밋(worktree 안). 병렬 dispatch 단위.
async function runTask(task, expectedHead) {
  const wt = wtPath(task.id)
  const branch = branchOf(task.id)
  const cdWt = `작업 디렉토리는 이 task 의 worktree = ${wt} 다. Bash 사용 시 항상 먼저 cd ${wt}. base(${projectRoot}) 나 다른 worktree 를 건드리지 마라. 시작 시 git rev-parse --show-toplevel 로 위치를 확인하라.`
  const { implNote, codex } = riskDirectives(task)
  const targetsStr = task.targets.join(', ') // validateGraph 가 비어있지 않음을 보장(A4)
  const evidenceStr = (task.evidence ?? []).map((x, i) => typeof x === 'string'
    ? `${i + 1}. ${x}`
    : `${i + 1}. [${x.id}] run=${x.run} ; expect=${JSON.stringify(x.expect)}`).join('\n') || '(legacy migration — task별 evidence 미기재, 전체 게이트를 사용)'
  const assumptionsStr = (task.assumptions ?? []).map((x, i) => `${i + 1}. ${x}`).join('\n') || '(없음)'
  const replanStr = (task.replanWhen ?? []).map((x, i) => `${i + 1}. ${x}`).join('\n') || '(legacy graph — 상한 뒤 메인 판단)'
  const specSlice =
    (overallGoal ? `전체 목표(맥락):\n${overallGoal}\n\n` : '') +
    `이 task(${task.id}) 목표:\n${task.goal}\n` +
    `전체 목표 기여 이유:\n${task.why || '(legacy graph — 미기재)'}\n\n` +
    `선언 targets(이 범위만 변경): ${targetsStr}\n` +
    `완료 evidence(직접 실행·관찰):\n${evidenceStr}\n` +
    `가정:\n${assumptionsStr}\n` +
    `재계획 조건:\n${replanStr}\n${implNote}\n`

  let impl, review = null, feedback = '', attempt = 0, frozenReviewSnapshot = null
  while (true) {
    attempt++
    impl = await agent(
      `그래프 하위 task 구현 — 이 task 하나만 끝까지 구현·자기검증하라. ${cdWt}\n\n${specSlice}\n` +
      (feedback ? `\n⚠ 이전 시도가 막혔다. 아래 블로커를 반드시 해결하라:\n${feedback}\n` : '') +
      `\n선언 targets 밖 파일은 건드리지 마라(merge-gate 가 target 교집합을 코드로 판정한다). .planning/STATE.md 는 수정 금지(그래프 계약 — merge-gate 가 코드로 거부한다). ` +
      `커밋·push 하지 마라(상위 워크플로우가 커밋·merge 한다).\n(역할·읽을 SSOT·자기검증·상태값 규칙은 너의 에이전트 정의에 있다 — 따르라.) 반환은 스키마(status·filesChanged·decisions·selfCheck·concerns·missing) 그대로.`,
      { agentType: 'implementer', phase: 'Wave', label: attempt > 1 ? `impl:${task.id}(재시도 ${attempt})` : `impl:${task.id}`, schema: IMPL_SCHEMA }
    )

    // NEEDS_CONTEXT/BLOCKED: 리뷰로는 판정할 게 없다(구현 자체가 성립 안 함) — 리뷰 건너뛰고
    // missing 을 피드백으로 재투입(workflow.mjs 이식, 분기는 코드). 상한 도달 = task 실패(worktree 보존).
    if (impl?.status === 'NEEDS_CONTEXT' || impl?.status === 'BLOCKED') {
      log(`[${task.id}] implementer ${impl.status} — 리뷰 생략. 부족분: ${impl.missing || '(미기재)'}`)
      const replan = await assessReplan(task, `implementer ${impl.status}: ${impl.missing || '(missing 미기재)'}`, `replan:${task.id}(${attempt})`)
      if (replan?.triggered) {
        return { id: task.id, status: 'replan-required', implStatus: impl.status, missing: impl.missing || '(missing 미기재)', replan, attempts: attempt }
      }
      if (attempt >= MAX_TASK_ATTEMPTS) {
        return { id: task.id, status: 'blocked', implStatus: impl.status, missing: impl.missing || '(missing 미기재)', attempts: attempt }
      }
      feedback = `implementer 가 ${impl.status} 상태를 반환했다 — 아래 부족분을 반드시 보강하라:\n${impl.missing || '(미기재)'}`
      continue
    }

    const preReviewSnapshot = await agent(
      `그래프 task implementer 반환 직후·리뷰 전 changeset 동결 — 수정·스테이징·커밋 금지. ${cdWt}\n` +
      `기대 브랜치 ${branch}, HEAD ${expectedHead}. branch=git branch --show-current, beforeHead=git rev-parse HEAD, reviewedFiles=(git diff --name-only HEAD; git ls-files --others --exclude-standard | sort -u), ` +
      `reviewedDigest=정렬된 경로+현재 blob hash(삭제는 DELETE)의 SHA-256, statusPorcelain=git status --porcelain 원문. 지어내지 마라.`,
      { phase: 'Wave', label: `pre-review:${task.id}(${attempt})`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, reviewedFiles: { type: 'string' }, reviewedDigest: { type: 'string' }, statusPorcelain: { type: 'string' } },
          required: ['branch', 'beforeHead', 'reviewedFiles', 'reviewedDigest', 'statusPorcelain'] } }
    )
    const preFiles = normalizeFileSet(preReviewSnapshot?.reviewedFiles)
    if ((preReviewSnapshot?.branch ?? '').trim() !== branch || (preReviewSnapshot?.beforeHead ?? '').trim() !== expectedHead || preFiles.length === 0 || !/^[0-9a-f]{64}$/.test((preReviewSnapshot?.reviewedDigest ?? '').trim())) {
      return { id: task.id, status: 'changeset-protocol-failed', reason: 'implementer-early-commit-or-empty-changeset', attempts: attempt }
    }

    review = await agent(
      `그래프 하위 task 블라인드 리뷰 — 실제 diff·게이트 재실행으로 검증하라. ${cdWt}\n\n${specSlice}\n${codex}\n` +
      `이 task 범위(선언 targets)만 변경됐는지, 목표를 만족하는지 판정하라. 라이브/프리뷰 항목은 이 그래프 범위 밖 — 판정 대상 아님. ` +
      `contract 2.0이면 evidence를 각자 worktree에서 직접 실행하고 evidenceResults에 같은 순서·id·run, 실제 exit/output, passed를 1:1 반환하라. exit·outputIncludes·outputExcludes는 코드가 실제 결과와 다시 대조한다. 하나라도 실행 불능·기대 불충족이면 pass=false다.\n` +
      `블라인드 입력 계약: 구현 보고·결정·selfCheck·concerns·이전 리뷰는 제공되지 않는다. 실제 파일과 diff 를 직접 읽어라. concernDispositions 는 빈 배열로 반환하라.\n` +
      `(검증·교차검증·판정 규칙은 너의 에이전트 정의에 있다 — 위 Codex 지시와 함께 따르라.)`,
      { agentType: 'reviewer', schema: graph.contractVersion === '2.0' ? TASK_REVIEW_SCHEMA : REVIEW_SCHEMA, phase: 'Wave', label: attempt > 1 ? `blind-review:${task.id}(${attempt})` : `blind-review:${task.id}` }
    )
    review = await reconcileAfterBlind(impl, review, `${cdWt}\ntask(${task.id}): ${task.goal}`, `concern:${task.id}(${attempt})`)
    review = applyEvidenceGuard(task, review)

    const postReviewSnapshot = await agent(
      `그래프 task reviewer 직후 changeset 재동결 — 수정·스테이징·커밋 금지. ${cdWt}\n` +
      `branch=git branch --show-current, beforeHead=git rev-parse HEAD, reviewedFiles=(git diff --name-only HEAD; git ls-files --others --exclude-standard | sort -u), ` +
      `reviewedDigest=정렬된 경로+현재 blob hash(삭제는 DELETE)의 SHA-256, statusPorcelain=git status --porcelain 원문. 지어내지 마라.`,
      { phase: 'Wave', label: `post-review:${task.id}(${attempt})`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, reviewedFiles: { type: 'string' }, reviewedDigest: { type: 'string' }, statusPorcelain: { type: 'string' } },
          required: ['branch', 'beforeHead', 'reviewedFiles', 'reviewedDigest', 'statusPorcelain'] } }
    )
    const postFiles = normalizeFileSet(postReviewSnapshot?.reviewedFiles)
    const reviewerKeptChangeset = (preReviewSnapshot?.branch ?? '').trim() === branch && (postReviewSnapshot?.branch ?? '').trim() === branch &&
      (postReviewSnapshot?.beforeHead ?? '').trim() === expectedHead &&
      postFiles.length === preFiles.length && postFiles.every((f, i) => f === preFiles[i]) &&
      (postReviewSnapshot?.reviewedDigest ?? '').trim() === (preReviewSnapshot?.reviewedDigest ?? '').trim() &&
      (postReviewSnapshot?.statusPorcelain ?? '').trim() === (preReviewSnapshot?.statusPorcelain ?? '').trim()
    if (!reviewerKeptChangeset) {
      return { id: task.id, status: 'changeset-protocol-failed', reason: 'reviewer-mutated-changeset', review, attempts: attempt }
    }

    if (review.pass) { frozenReviewSnapshot = postReviewSnapshot; break }
    if (review.protocolFailure) {
      return { id: task.id, status: 'review-protocol-failed', review, attempts: attempt }
    }
    const replan = await assessReplan(task, (review.issues ?? []).join('\n') || 'review failed without issue text', `replan:${task.id}(${attempt})`)
    if (replan?.triggered) {
      return { id: task.id, status: 'replan-required', review, replan, attempts: attempt }
    }
    if (attempt >= MAX_TASK_ATTEMPTS) {
      return { id: task.id, status: 'review-failed', review, advisories: review?.advisories ?? [], concernDispositions: review?.concernDispositions ?? [], attempts: attempt }
    }
    feedback = review.issues.join('\n')
    log(`[${task.id}] 리뷰 블로커 ${review.issues.length}개 → 재시도 ${attempt + 1}/${MAX_TASK_ATTEMPTS}`)
  }

  const reviewedSnapshot = frozenReviewSnapshot

  // 커밋 — worktree 안에서. STATE 수정 금지·새 파일 발명 금지(리뷰 통과 상태 그대로).
  const commit = await agent(
    `리뷰를 통과한 이 worktree 의 변경을 atomic commit 하라(커밋만 — 코드 재작성·새 파일 발명·STATE 수정 금지). ${cdWt}\n` +
    `task(${task.id}): ${task.goal}\n` +
    `1) git add -A 로 리뷰-통과 변경을 스테이징(무관 파일만 제외, **.planning/STATE.md 수정·새 파일 발명 금지**).\n` +
    `2) 한국어 커밋 메시지로 commit 정확히 1개(--no-verify·--force 금지). 메시지에 '완료'·'검증됨'·'merge' 주장 금지 — 변경 내용만 서술(merge·통합검증은 상위가 한다). 메시지 끝: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>\n` +
    `3) commit 직전 git rev-parse HEAD 를 beforeHead 에 보존하라. 커밋 후 **실행한 명령의 출력 원문 그대로** 반환: beforeHead, afterHead=git rev-parse HEAD, headLog=git log -1 --format='%H %s', statusPorcelain=git status --porcelain(클린이면 빈 문자열), committedFiles=git show HEAD --stat --format='' 원문. 실패하면 beforeHead=afterHead 로 사실대로 반환하라. 지어내지 마라.`,
    { phase: 'Wave', label: `commit:${task.id}`, model: 'haiku', schema: COMMIT_SCHEMA }
  )
  const commitProof = await agent(
    `그래프 task 커밋 사후 증거 — 수정·스테이징·커밋·amend 금지. ${cdWt}\n` +
    `기준 브랜치 ${branch}, HEAD ${(reviewedSnapshot?.beforeHead ?? '').trim()}. branch=git branch --show-current, afterHead=git rev-parse HEAD, headLog=git log -1 --format='%H %s', ` +
    `revCount=git rev-list --count ${(reviewedSnapshot?.beforeHead ?? '').trim()}..HEAD, committedFiles=git diff --name-only ${(reviewedSnapshot?.beforeHead ?? '').trim()}..HEAD, ` +
    `committedDigest=committedFiles의 정렬된 각 경로와 현재 blob hash(삭제는 DELETE)를 reviewedDigest와 같은 방식으로 SHA-256, statusPorcelain=git status --porcelain 원문을 반환하라. 지어내지 마라.`,
    { phase: 'Wave', label: `commit-proof:${task.id}`, model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: { branch: { type: 'string' }, afterHead: { type: 'string' }, headLog: { type: 'string' }, revCount: { type: 'string' }, committedFiles: { type: 'string' }, committedDigest: { type: 'string' }, statusPorcelain: { type: 'string' } },
        required: ['branch', 'afterHead', 'headLog', 'revCount', 'committedFiles', 'committedDigest', 'statusPorcelain'] } }
  )
  const jc = judgeIndependentCommit(reviewedSnapshot, commit, commitProof, branch)
  return {
    id: task.id, status: jc.ok ? 'committed' : 'commit-failed', review,
    advisories: review?.advisories ?? [], concernDispositions: review?.concernDispositions ?? [],
    commit, commitProof, dirty: jc.dirty, attempts: attempt,
  }
}

for (let w = 0; w < graph.waves.length; w++) {
  if (escalation) break
  const waveIds = graph.waves[w]
  const waveTasks = waveIds.map(id => graph.byId.get(id))
  log(`── wave ${w + 1}/${graph.waves.length}: [${waveIds.join(', ')}] ──`)

  // shared-write 사전 경고(순수 코드, 진단용 — 실제 방어는 직렬 merge 의 충돌-abort backstop).
  const targetOwners = new Map()
  for (const t of waveTasks) for (const tg of (t.targets || [])) {
    if (tg === 'state' || tg === 'external') continue
    if (!targetOwners.has(tg)) targetOwners.set(tg, [])
    targetOwners.get(tg).push(t.id)
  }
  const shared = [...targetOwners.entries()].filter(([, o]) => o.length > 1)
  if (shared.length) log(`⚠ shared-write 경고(wave ${w + 1}): ${shared.map(([f, o]) => `${f}←{${o.join(',')}}`).join('; ')} — 직렬 merge 충돌 시 abort·에스컬레이션(무결성 우선).`)

  // 1) worktree 직렬 생성(단일 haiku 에이전트가 순차 실행 — .git/config.lock 경합 방지).
  const wtRes = await agent(
    `그래프 wave worktree 생성 — 아래를 **직렬로** 수행하고 사실을 반환하라(구현·커밋 금지). ${cdBase}\n` +
    `0) base 상태 오염 방지: grep -q '^.planning/worktrees/$' .git/info/exclude 2>/dev/null || echo '.planning/worktrees/' >> .git/info/exclude (worktree 디렉토리를 base git 추적에서 제외).\n` +
    `1) 아래 각 task 에 대해 **하나씩 순차로**(동시 금지 — .git/config.lock 경합):\n` +
    waveIds.map(id => `   - git worktree add ${wtPath(id)} -b ${branchOf(id)} ${baseBranch} ; echo "ADD_EXIT=$?" ; git -C ${wtPath(id)} rev-parse --show-toplevel ; git -C ${wtPath(id)} rev-parse HEAD`).join('\n') + '\n' +
    `2) worktrees 배열에 task 마다 {id, addExit(ADD_EXIT 값 문자열), toplevel(rev-parse 출력), head(git rev-parse HEAD), output(그 task 명령들의 출력 원문)} 을 담아라. **지어내지 마라** — 실패하면 실패 원문 그대로.`,
    {
      phase: 'Wave', label: `worktree:w${w + 1}`, model: 'haiku',
      schema: {
        type: 'object', additionalProperties: false,
        properties: {
          worktrees: {
            type: 'array',
            items: {
              type: 'object', additionalProperties: false,
              properties: { id: { type: 'string' }, addExit: { type: 'string' }, toplevel: { type: 'string' }, head: { type: 'string' }, output: { type: 'string' } },
              required: ['id', 'addExit', 'toplevel', 'head', 'output'],
            },
          },
        },
        required: ['worktrees'],
      },
    }
  )
  // worktree 생성 코드 판정: addExit==0 AND toplevel 이 기대 경로로 끝나야 성공.
  const wtByIdOk = new Map()
  for (const id of waveIds) {
    const rec = findByTaskId(wtRes?.worktrees, id, branchOf(id))
    const addOk = (rec?.addExit || '').trim() === '0'
    const topOk = typeof rec?.toplevel === 'string' && rec.toplevel.trim().endsWith(`/.planning/worktrees/${id}`)
    const headOk = (rec?.head ?? '').trim() === expectedBaseHead
    wtByIdOk.set(id, addOk && topOk && headOk)
    if (!(addOk && topOk && headOk)) log(`✗ [${id}] worktree 생성 실패 — addExit=${rec?.addExit ?? '?'}, toplevel=${(rec?.toplevel || '').trim() || '(없음)'}, head=${(rec?.head || '').trim() || '(없음)'}`)
  }
  const wtFailed = waveIds.filter(id => !wtByIdOk.get(id))
  if (wtFailed.length) {
    for (const id of wtFailed) taskResults[id] = { status: 'worktree-failed' }
    escalate(`wave ${w + 1} worktree 생성 실패: ${wtFailed.join(', ')} — 구조적 문제(브랜치 중복·git 상태). 원인 확인 후 재실행.`,
      wtFailed.map(id => `${id}: git worktree add 실패`),
      ['기존 graph-<id> 브랜치/worktree 잔재가 있는지 확인(git worktree list·git branch) 후 정리', '작업 브랜치 상태 점검 후 재실행'])
    break
  }

  // 2) implementer→reviewer→커밋 병렬(≤CONCURRENCY), 사전 생성된 worktree 에 pin.
  for (const batch of chunk(waveTasks, CONCURRENCY)) {
    const res = await parallel(batch.map(t => () => {
      const rec = findByTaskId(wtRes?.worktrees, t.id, branchOf(t.id))
      return runTask(t, (rec?.head ?? '').trim())
    }))
    for (const r of res) taskResults[r.id] = r
  }
  const notCommitted = waveIds.filter(id => taskResults[id]?.status !== 'committed')
  if (notCommitted.length) {
    const blockers = notCommitted.map(id => {
      const r = taskResults[id]
      if (r?.status === 'replan-required') return `${id}: 사전 replanWhen 발화(${r.replan?.matchedCondition || '?'}) — ${r.replan?.reason || '그래프 수정 필요'}`
      if (r?.status === 'blocked') return `${id}: implementer ${r.implStatus}(${MAX_TASK_ATTEMPTS}회, 리뷰 미도달) — 부족분: ${r.missing}`
      if (r?.status === 'review-failed') return `${id}: ${MAX_TASK_ATTEMPTS}회 리뷰 미통과 — ${(r.review?.issues || []).join(' / ')}`
      if (r?.status === 'review-protocol-failed') return `${id}: reviewer 프로토콜 실패 — ${r.review?.protocolFailure || '우려 대조 누락'}`
      if (r?.status === 'changeset-protocol-failed') return `${id}: changeset 프로토콜 실패 — ${r.reason}`
      if (r?.status === 'commit-failed') return `${id}: 커밋 미확인 — status 잔여 ${(r.dirty || []).join(' | ') || '(headLog 불일치)'}`
      return `${id}: 미완(${r?.status})`
    })
    escalate(`wave ${w + 1}: ${notCommitted.length}개 task 가 커밋에 도달 못함(${notCommitted.join(', ')}) — 커밋된 것은 merge 안 하고 멈춘다(실패 worktree 진단용 보존).`,
      blockers,
      ['replan-required면 메인 오케스트레이터가 실패 증거·matchedCondition으로 v2 graph의 가정·task·의존성을 수정하고 사용자 재승인 없이 재투입', 'blocked(NEEDS_CONTEXT/BLOCKED)면 missing 의 부족 정보(스키마·ADR·환경)를 그래프 goal/STATE 에 보강 후 재투입', 'review-protocol-failed 면 implementer 를 재실행하지 말고 reviewer 입력·스키마만 점검', '리뷰 블로커면 수용 기준/task 분해 재검토 후 재투입', 'commit-failed 면 해당 worktree git 상태 확인(부당 커밋 공존 여부)', 'task 가 크면 그래프를 더 작은 단위로 재작성'])
    break
  }
  log(`✓ wave ${w + 1}: ${waveIds.length}개 task 전부 커밋됨`)

  // 3) merge-gate(코드 판정) — 커밋된 task 별 rev-list·diff 원문을 받아 판정.
  const gateRecon = await agent(
    `merge-gate 계측 — 아래를 수행하고 **출력 원문 그대로** 반환하라(merge·수정 금지, 판정은 상위 코드가 한다). ${cdBase}\n` +
    waveIds.map(id => `- git rev-list ${baseBranch}..${branchOf(id)} | wc -l  (→ revCount)\n  git diff ${baseBranch}...${branchOf(id)} --name-only  (→ diffFiles, 세 점 diff)`).join('\n') + '\n' +
    `gates 배열에 task 마다 {id, revCount(wc -l 출력 숫자 문자열), diffFiles(--name-only 출력 원문, 파일당 한 줄)} 을 담아라. **id 는 task id 원문**(예: "T1" — 브랜치명 "graph-T1" 이 아니다). 지어내지 마라.`,
    {
      phase: 'Wave', label: `merge-gate:w${w + 1}`, model: 'haiku',
      schema: {
        type: 'object', additionalProperties: false,
        properties: {
          gates: { type: 'array', items: { type: 'object', additionalProperties: false,
            properties: { id: { type: 'string' }, revCount: { type: 'string' }, diffFiles: { type: 'string' } },
            required: ['id', 'revCount', 'diffFiles'] } },
        },
        required: ['gates'],
      },
    }
  )
  const mergeOrder = []
  const gateFailed = []
  for (const id of waveIds) {
    const gr = findByTaskId(gateRecon?.gates, id, branchOf(id))
    const verdict = judgeMergeGate(graph.byId.get(id), gr?.revCount, gr?.diffFiles)
    taskResults[id].mergeGate = verdict
    if (verdict.warnings.length) log(`⚠ [${id}] merge-gate 경고: ${verdict.warnings.join('; ')}`)
    if (verdict.pass) { mergeOrder.push(id); log(`✓ [${id}] merge-gate 통과 (ahead+diff+target 교집합)`) }
    else { gateFailed.push(id); log(`✗ [${id}] merge-gate 실패: ${verdict.reason}`) }
  }
  if (gateFailed.length) {
    escalate(`wave ${w + 1}: merge-gate 실패 ${gateFailed.join(', ')} — STATE 불가침 위반 또는 선언 targets 와 실제 diff 불일치(빈 diff·대상 밖만 변경 등). base 미오염(merge 안 함), 실패 worktree 보존.`,
      gateFailed.map(id => `${id}: ${taskResults[id].mergeGate.reason}`),
      ['STATE 불가침 위반이면 해당 worktree 커밋에서 .planning/STATE.md 변경을 걷어낸 뒤 재투입(종결 기록은 완주 후 메인)', 'task 가 targets 밖을 건드렸는지/아무 것도 안 바꿨는지 worktree diff 확인', '선언 targets 가 실제 산출물과 맞는지 그래프 재작성', 'task 재투입'])
    break
  }

  // 4) base merge 직렬(gate 통과분만). 충돌 시 abort → 에스컬레이션.
  const mergeSnapshot = await agent(
    `base merge 전 기준선 — 수정·checkout·merge 금지. ${cdBase}\n` +
    `branch=git branch --show-current, beforeHead=git rev-parse HEAD, statusPorcelain=git status --porcelain 원문을 반환하라. 지어내지 마라.`,
    { phase: 'Wave', label: `merge-snapshot:w${w + 1}`, model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, statusPorcelain: { type: 'string' } }, required: ['branch', 'beforeHead', 'statusPorcelain'] } }
  )
  if ((mergeSnapshot?.branch ?? '').trim() !== baseBranch || (mergeSnapshot?.beforeHead ?? '').trim() !== expectedBaseHead || (mergeSnapshot?.statusPorcelain ?? 'UNKNOWN').trim()) {
    escalate(`wave ${w + 1}: merge 전 base 브랜치/HEAD/작업트리 불일치 — merge 시작 금지.`, [`branch=${mergeSnapshot?.branch || '?'}`, `head=${mergeSnapshot?.beforeHead || '?'} expected=${expectedBaseHead}`, `status=${mergeSnapshot?.statusPorcelain || '(clean)'}`], ['base 변경을 별도 처리한 뒤 그래프 재실행'])
    break
  }
  const mergeRes = await agent(
    `base 브랜치(${baseBranch}) 로 merge — 아래 순서대로 **직렬** 실행하고 사실을 반환하라(코드 수정·push 금지). ${cdBase}\n` +
    `1) 현재 base(${baseBranch}) 체크아웃 상태 확인(git branch --show-current). 아니면 git checkout ${baseBranch}.\n` +
    `2) 다음 브랜치를 **하나씩 순서대로** 반드시 --no-ff merge 하라(충돌이면 즉시 git merge --abort 하고 그 task 부터 중단 — 뒤 task 는 시도하지 마라). 다른 커밋 생성 금지:\n` +
    mergeOrder.map(id => `   - git merge --no-ff --no-edit ${branchOf(id)} ; echo "${id}:MERGE_EXIT=$?"`).join('\n') + '\n' +
    `3) merges 배열에 merge 시도한 task 마다 {id, exit(git merge exit code 문자열), headLog(merge 후 git log -1 --format='%H %s' 원문), conflict(충돌이면 true)} 을 담아라. 지어내지 마라 — abort 했으면 conflict=true.`,
    {
      phase: 'Wave', label: `merge:w${w + 1}`, model: 'haiku',
      schema: {
        type: 'object', additionalProperties: false,
        properties: {
          merges: { type: 'array', items: { type: 'object', additionalProperties: false,
            properties: { id: { type: 'string' }, exit: { type: 'string' }, headLog: { type: 'string' }, conflict: { type: 'boolean' } },
            required: ['id', 'exit', 'headLog', 'conflict'] } },
        },
        required: ['merges'],
      },
    }
  )
  let mergeConflict = null
  for (const id of mergeOrder) {
    const m = findByTaskId(mergeRes?.merges, id, branchOf(id))
    const ok = m && m.conflict !== true && (m.exit || '').trim() === '0' && /^[0-9a-f]{7,40} /.test(m.headLog || '')
    if (!ok) { taskResults[id].merged = false; mergeConflict = mergeConflict || id; log(`✗ [${id}] merge 실패/충돌 — exit=${m?.exit ?? '?'} conflict=${m?.conflict}`) }
  }
  if (mergeConflict) {
    escalate(`wave ${w + 1}: base merge 충돌(${mergeConflict}) — abort 됨(base 무결). 성공 merge 는 base 에 남아 있다. 충돌은 자동 해소하지 않는다(무결성 우선).`,
      [`${mergeConflict}: git merge 충돌 → abort`],
      ['충돌 파일이 shared-write 인지 확인 — 그래프에서 단일 writer 로 재구성', '수동 충돌 해소 후 이어가기', '사용자 에스컬레이션'])
    break
  }
  const mergeProof = await agent(
    `base merge 사후 독립 증거 — 수정·checkout·merge·commit 금지. ${cdBase}\n` +
    `기준 브랜치 ${baseBranch}, HEAD ${(mergeSnapshot?.beforeHead ?? '').trim()}. branch=git branch --show-current, afterHead=git rev-parse HEAD, ` +
    `revCount=git rev-list --count ${(mergeSnapshot?.beforeHead ?? '').trim()}..HEAD, ` +
    `firstParentCount=git rev-list --first-parent --count ${(mergeSnapshot?.beforeHead ?? '').trim()}..HEAD, ` +
    `statusPorcelain=git status --porcelain 을 반환하고, 각 브랜치에 대해 git merge-base --is-ancestor <branch> ${baseBranch}; echo ANC=$? 를 실행하라:\n` +
    mergeOrder.map(id => `- ${id}: ${branchOf(id)}`).join('\n') + '\n' +
    `git rev-list --first-parent --reverse ${(mergeSnapshot?.beforeHead ?? '').trim()}..HEAD 로 merge commit을 순서대로 열거하고, 각 task 순서에 맞춰 ` +
    `mergeCommits 배열에 {id, mergeHead, parents(git show -s --format='%P' <mergeHead>), remergeDiff(git show --remerge-diff --format= <mergeHead> 원문)}를 담아라. ` +
    `checks 배열은 {id, ancExit} 원문. 지어내지 마라.`,
    { phase: 'Wave', label: `merge-proof:w${w + 1}`, model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: {
          branch: { type: 'string' }, afterHead: { type: 'string' }, revCount: { type: 'string' }, firstParentCount: { type: 'string' }, statusPorcelain: { type: 'string' },
          checks: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { id: { type: 'string' }, ancExit: { type: 'string' } }, required: ['id', 'ancExit'] } },
          mergeCommits: { type: 'array', items: { type: 'object', additionalProperties: false,
            properties: { id: { type: 'string' }, mergeHead: { type: 'string' }, parents: { type: 'string' }, remergeDiff: { type: 'string' } },
            required: ['id', 'mergeHead', 'parents', 'remergeDiff'] } },
        },
        required: ['branch', 'afterHead', 'revCount', 'firstParentCount', 'statusPorcelain', 'checks', 'mergeCommits'] } }
  )
  const mergeBeforeHead = (mergeSnapshot?.beforeHead ?? '').trim()
  const mergeAfterHead = (mergeProof?.afterHead ?? '').trim()
  const mergeProofFailed = mergeOrder.filter(id => {
    const c = findByTaskId(mergeProof?.checks, id, branchOf(id))
    return (c?.ancExit ?? '').trim() !== '0'
  })
  let previousMergeHead = mergeBeforeHead
  const mergeTreeFailures = []
  if (!Array.isArray(mergeProof?.mergeCommits) || mergeProof.mergeCommits.length !== mergeOrder.length) {
    mergeTreeFailures.push(`merge commit 개수 불일치(${mergeProof?.mergeCommits?.length ?? 0}/${mergeOrder.length})`)
  } else {
    for (let i = 0; i < mergeOrder.length; i++) {
      const id = mergeOrder[i]
      const rec = mergeProof.mergeCommits[i]
      const mergeHead = (rec?.mergeHead ?? '').trim()
      const parents = (rec?.parents ?? '').trim().split(/\s+/).filter(Boolean)
      const expectedTaskHead = (taskResults[id]?.commitProof?.afterHead ?? '').trim()
      const valid = rec?.id === id && /^[0-9a-f]{7,40}$/.test(mergeHead) && mergeHead !== previousMergeHead && mergeHead !== expectedTaskHead &&
        parents.length === 2 && parents[0] === previousMergeHead && parents[1] === expectedTaskHead && (rec?.remergeDiff ?? '').trim() === ''
      if (!valid) mergeTreeFailures.push(`${id}: parent/order/remerge 불일치`)
      previousMergeHead = mergeHead
    }
    if (previousMergeHead !== mergeAfterHead) mergeTreeFailures.push('마지막 merge commit != afterHead')
  }
  const mergeEvidenceOk = /^[0-9a-f]{7,40}$/.test(mergeBeforeHead) && /^[0-9a-f]{7,40}$/.test(mergeAfterHead) &&
    mergeBeforeHead !== mergeAfterHead && (mergeProof?.revCount ?? '').trim() === String(mergeOrder.length * 2) &&
    (mergeProof?.firstParentCount ?? '').trim() === String(mergeOrder.length) &&
    (mergeProof?.branch ?? '').trim() === baseBranch && (mergeProof?.statusPorcelain ?? 'UNKNOWN').trim() === '' && mergeProofFailed.length === 0 && mergeTreeFailures.length === 0
  if (!mergeEvidenceOk) {
    for (const id of mergeOrder) taskResults[id].merged = false
    escalate(`wave ${w + 1}: merge 사후 증거 불일치 — 자기보고만으로 완료 처리하지 않음.`,
      [`before=${mergeBeforeHead || '?'}`, `after=${mergeAfterHead || '?'}`, `rev=${mergeProof?.revCount ?? '?'}(기대 ${mergeOrder.length * 2})`, `first-parent=${mergeProof?.firstParentCount ?? '?'}(기대 ${mergeOrder.length})`, `ancestor 실패=${mergeProofFailed.join(',') || '(없음)'}`, `merge tree 실패=${mergeTreeFailures.join(' | ') || '(없음)'}`, `status=${mergeProof?.statusPorcelain || '(clean)'}`],
      ['base git log --graph·status·merge-base를 직접 확인', '부분 merge 또는 여분 커밋이면 그래프를 재구성하고 복구 전략을 사람에게 에스컬레이션'])
    break
  }
  for (const id of mergeOrder) {
    completed.add(id)
    taskResults[id].merged = true
    taskResults[id].status = 'merged'
    log(`✓ [${id}] base merge 독립 증거 확인`)
  }
  expectedBaseHead = mergeAfterHead

  // 5) regen barriers — after 충족분 실행(base). 비0 = 에스컬레이션.
  const dueBarriers = graph.barriers.filter((b, i) => !ranBarriers.has(i) && b.after.every(a => completed.has(a)))
  let barrierFail = null
  for (let bi = 0; bi < graph.barriers.length && !barrierFail; bi++) {
    const b = graph.barriers[bi]
    if (ranBarriers.has(bi) || !b.after.every(a => completed.has(a))) continue
    const barrierSnapshot = await agent(
      `regen barrier 실행 전 기준선 — 수정·스테이징·커밋 금지. ${cdBase}\n` +
      `branch=git branch --show-current, beforeHead=git rev-parse HEAD, statusPorcelain=git status --porcelain 원문을 반환하라. 작업트리가 clean이 아니면 숨기지 마라.`,
      { phase: 'Wave', label: `regen-snapshot:w${w + 1}#${bi}`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, statusPorcelain: { type: 'string' } }, required: ['branch', 'beforeHead', 'statusPorcelain'] } }
    )
    if ((barrierSnapshot?.branch ?? '').trim() !== baseBranch || (barrierSnapshot?.beforeHead ?? '').trim() !== expectedBaseHead || (barrierSnapshot?.statusPorcelain ?? 'UNKNOWN').trim()) {
      barrierFail = { bi, run: b.run, output: `regen 전 base 불일치: branch=${barrierSnapshot?.branch || '?'}, head=${barrierSnapshot?.beforeHead || '?'} expected=${expectedBaseHead}, status=${barrierSnapshot?.statusPorcelain || '(clean)'}` }
      break
    }
    const br = await agent(
      `regen barrier 실행 — 아래 명령을 base 에서 실행하고 사실을 반환하라(명령 외 수정 금지). ${cdBase}\n` +
      `git checkout ${baseBranch} 후: ${b.run} ; echo "EXIT=$?"\n` +
      `허용 산출물 경로: ${b.targets.join(', ')}. 명령이 이 경로 안 파일을 바꿨으면 그 경로만 명시적으로 git add 하고 한국어로 commit 정확히 1개(--no-verify 금지, 메시지 끝 Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>). git add -A 금지. 바뀐 게 없으면 커밋하지 마라. STATE·허용 경로 밖 변경은 커밋하지 말고 그대로 남겨라(사후 판정이 실패시킨다).\n` +
      `반환: exit(EXIT 값 문자열)·output(명령 출력 원문)·headLog(커밋했으면 git log -1 --format='%H %s' 원문, 아니면 빈 문자열). 지어내지 마라.`,
      { phase: 'Wave', label: `regen:w${w + 1}#${bi}`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { exit: { type: 'string' }, output: { type: 'string' }, headLog: { type: 'string' } },
          required: ['exit', 'output', 'headLog'] } }
    )
    const barrierProof = await agent(
      `regen barrier 사후 증거 — 수정·스테이징·커밋·amend 금지. ${cdBase}\n` +
      `기준 브랜치 ${baseBranch}, HEAD ${(barrierSnapshot?.beforeHead ?? '').trim()}. branch=git branch --show-current, afterHead=git rev-parse HEAD, headLog=git log -1 --format='%H %s', ` +
      `revCount=git rev-list --count ${(barrierSnapshot?.beforeHead ?? '').trim()}..HEAD, committedFiles=git diff --name-only ${(barrierSnapshot?.beforeHead ?? '').trim()}..HEAD, statusPorcelain=git status --porcelain 원문을 반환하라. 지어내지 마라.`,
      { phase: 'Wave', label: `regen-proof:w${w + 1}#${bi}`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { branch: { type: 'string' }, afterHead: { type: 'string' }, headLog: { type: 'string' }, revCount: { type: 'string' }, committedFiles: { type: 'string' }, statusPorcelain: { type: 'string' } },
          required: ['branch', 'afterHead', 'headLog', 'revCount', 'committedFiles', 'statusPorcelain'] } }
    )
    ranBarriers.add(bi)
    const barrierBefore = (barrierSnapshot?.beforeHead ?? '').trim()
    const barrierAfter = (barrierProof?.afterHead ?? '').trim()
    const barrierRevCount = (barrierProof?.revCount ?? '').trim()
    const barrierFiles = normalizeFileSet(barrierProof?.committedFiles)
    const barrierDirty = (barrierProof?.statusPorcelain ?? 'UNKNOWN').trim()
    const barrierLogHead = ((barrierProof?.headLog ?? '').match(/^([0-9a-f]{7,40})\s/) || [])[1] ?? ''
    const barrierMatchesTarget = f => b.targets.some(t => { const n = t.replace(/\/+$/, ''); return f === n || f.startsWith(n + '/') })
    const barrierBranchOk = (barrierProof?.branch ?? '').trim() === baseBranch
    const barrierNoChange = barrierBranchOk && barrierRevCount === '0' && barrierAfter === barrierBefore && barrierFiles.length === 0 && barrierDirty === ''
    const barrierOneCommit = barrierRevCount === '1' && barrierAfter !== barrierBefore && barrierAfter === barrierLogHead &&
      barrierBranchOk && barrierFiles.length > 0 && barrierFiles.every(barrierMatchesTarget) && !barrierFiles.includes('.planning/STATE.md') && barrierDirty === ''
    if ((br?.exit || '').trim() !== '0' || (!barrierNoChange && !barrierOneCommit)) {
      barrierFail = { bi, run: b.run, output: (br?.output || '') + `\n증거 불일치(revCount=${barrierRevCount}, files=${barrierFiles.join(',') || '(없음)'}, dirty=${barrierDirty || '(clean)'})` }
      break
    }
    expectedBaseHead = barrierAfter
    log(`✓ regen barrier #${bi} (after ${b.after.join(',')}) 실행: exit 0${barrierOneCommit ? ` · ${barrierProof.headLog}` : ' · 변경 없음'}`)
  }
  if (barrierFail) {
    escalate(`wave ${w + 1}: regen barrier 비0 종료(#${barrierFail.bi}: ${barrierFail.run}) — 선행 merge 가 전제를 깼는지 확인.`,
      [`regen 명령 실패: ${barrierFail.run}\n${(barrierFail.output || '').slice(0, 600)}`],
      ['regen 명령이 merge 된 파일을 덮어쓰려는지 확인', '명령/그래프 after 정합 재검토', '사용자 에스컬레이션'])
    break
  }
  if (dueBarriers.length) log(`regen barriers ${dueBarriers.length}개 처리 완료`)

  // 6) wave 통합 게이트 — verify 명령 exit0(코드 판정).
  // v2 실패는 같은 그래프의 임의 수정으로 덮지 않고 실패 증거를 메인에 돌려 graph를 재계획한다.
  const ig = await integrationGate(w + 1, waveIds)
  integration.push({ wave: w + 1, ...ig })
  waveSummaries.push({ wave: w + 1, tasks: waveIds, merged: waveIds.filter(id => completed.has(id)), integration: ig.status })
  if (ig.status === 'failed') {
    const replanRequired = ig.reason === 'replan-required'
    escalate(replanRequired
      ? `wave ${w + 1}: v2 통합 증거가 실패해 graph 재계획이 필요하다. merge 는 base 에 남아 있으나(push 없음) 같은 graph로 임의 수정하지 않는다.`
      : `wave ${w + 1}: 통합 게이트 미통과(${INTEGRATION_FIX_CAP + 1}회 상한). merge 는 base 에 남아 있으나(push 없음) 교차작용 결함이 있다.`,
      [`통합 게이트 exit≠0:\n${(ig.output || '').slice(0, 800)}`],
      replanRequired
        ? ['메인 오케스트레이터가 실패 출력과 wave task의 replanWhen을 근거로 가정·task·의존성·evidence를 수정한 v2 graph를 만들고 사용자 재승인 없이 재투입', 'verify 명령 자체가 잘못됐다는 증거가 있으면 graph verify도 함께 수정']
        : ['실패 출력으로 원인 task 확정(debugger) 후 재투입', 'verify 명령이 wave 산출물과 맞는지 확인', '그래프 의존/순서 재검토'])
    break
  }
  if (ig.status === 'skipped') log(`⚠ wave ${w + 1} 통합 게이트 생략(기록됨): ${ig.reason}`)
}

// 통합 게이트 헬퍼 — verify 를 base 에서 실행, exit0 판정(코드).
// v2 실패는 graph 재계획 신호, 명시적 legacy migration만 기존 원인 수정 루프를 사용한다.
async function integrationGate(waveNo, waveIds) {
  if (!verifyCmd) return { status: 'skipped', reason: 'verify 명령 없음(그래프·STATE·package.json 미발견) — 기록된 생략' }
  let attempt = 0
  let lastOut = ''
  while (true) {
    attempt++
    const integrationSnapshot = await agent(
      `wave 통합 게이트 실행 전 불변 기준선 — 수정·checkout·검증 실행·커밋 금지. ${cdBase}\n` +
      `branch=git branch --show-current, beforeHead=git rev-parse HEAD, statusPorcelain=git status --porcelain 원문을 반환하라. 지어내지 마라.`,
      { phase: 'Wave', label: `integration-snapshot:w${waveNo}#${attempt}`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, statusPorcelain: { type: 'string' } }, required: ['branch', 'beforeHead', 'statusPorcelain'] } }
    )
    const integrationBefore = (integrationSnapshot?.beforeHead ?? '').trim()
    if ((integrationSnapshot?.branch ?? '').trim() !== baseBranch || integrationBefore !== expectedBaseHead || !/^[0-9a-f]{7,40}$/.test(integrationBefore) || (integrationSnapshot?.statusPorcelain ?? 'UNKNOWN').trim()) {
      return { status: 'failed', reason: 'integration-base-mismatch', attempts: attempt, output: `branch=${integrationSnapshot?.branch || '?'} head=${integrationBefore || '?'} expected=${expectedBaseHead} status=${integrationSnapshot?.statusPorcelain || '(clean)'}` }
    }
    const r = await agent(
      `wave 통합 게이트 — base 에서 verify 명령을 실행하고 **exit code 와 출력 원문 그대로** 반환하라(수정·커밋 금지). ${cdBase}\n` +
      `git checkout ${baseBranch} 후: ${verifyCmd} ; echo "EXIT=$?"\n` +
      `반환: exit(EXIT 값 문자열)·output(명령 출력 원문, 실패 시 실패 로그 포함). 지어내지 마라 — 통과 신호를 제조하지 마라.`,
      { phase: 'Wave', label: `integration:w${waveNo}${attempt > 1 ? `(재${attempt})` : ''}`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false, properties: { exit: { type: 'string' }, output: { type: 'string' } }, required: ['exit', 'output'] } }
    )
    lastOut = r?.output || ''
    const integrationProof = await agent(
      `wave 통합 게이트 실행 후 불변 증거 — 수정·checkout·검증 실행·커밋 금지. ${cdBase}\n` +
      `branch=git branch --show-current, afterHead=git rev-parse HEAD, statusPorcelain=git status --porcelain 원문을 반환하라. 실행 전 HEAD ${integrationBefore} 와 비교하되 사실만 반환하라.`,
      { phase: 'Wave', label: `integration-proof:w${waveNo}#${attempt}`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { branch: { type: 'string' }, afterHead: { type: 'string' }, statusPorcelain: { type: 'string' } }, required: ['branch', 'afterHead', 'statusPorcelain'] } }
    )
    const integrationAfter = (integrationProof?.afterHead ?? '').trim()
    const integrationMutated = (integrationProof?.branch ?? '').trim() !== baseBranch || !/^[0-9a-f]{7,40}$/.test(integrationAfter) || integrationAfter !== integrationBefore ||
      (integrationProof?.statusPorcelain ?? 'UNKNOWN').trim() !== ''
    if (integrationMutated) {
      log(`✗ wave ${waveNo} 통합 게이트가 저장소를 변조함 — 성공 주장 무효`)
      return { status: 'failed', reason: 'integration-mutated-repo', attempts: attempt, output: lastOut,
        beforeHead: integrationBefore, afterHead: integrationAfter, statusPorcelain: integrationProof?.statusPorcelain ?? 'UNKNOWN' }
    }
    if ((r?.exit || '').trim() === '0') { log(`✓ wave ${waveNo} 통합 게이트 통과 (exit 0, 시도 ${attempt})`); return { status: 'passed', attempts: attempt, output: lastOut } }
    log(`✗ wave ${waveNo} 통합 게이트 실패 (exit≠0, 시도 ${attempt})`)
    if (graph.contractVersion === '2.0') {
      const replanWhen = waveIds.flatMap(id => (graph.byId.get(id)?.replanWhen ?? []).map(condition => `${id}: ${condition}`))
      return { status: 'failed', reason: 'replan-required', attempts: attempt, output: lastOut, replanWhen }
    }
    if (attempt > INTEGRATION_FIX_CAP) return { status: 'failed', attempts: attempt, output: lastOut }
    // 원인 수정 재투입: base 에서 implementer 로 고치고 reviewer 통과 후 커밋(피드백 인라인).
    log(`통합 게이트 실패 → 원인 수정 재투입 ${attempt}/${INTEGRATION_FIX_CAP + 1}`)
    const fix = await agent(
      `wave ${waveNo} 통합 검증이 실패했다 — base(${projectRoot}) 에서 원인을 찾아 고쳐라(이 wave 의 merge 된 task: ${waveIds.join(', ')}). ${cdBase}\n` +
      `git checkout ${baseBranch} 상태에서 작업하라. 실패 로그:\n${lastOut.slice(0, 1200)}\n` +
      `수정은 최소 범위로, .planning/STATE.md 는 건드리지 마라. 커밋·push 하지 마라(상위가 커밋).\n(자기검증·상태값 규칙은 너의 에이전트 정의에 있다.) 반환은 스키마(status·filesChanged·decisions·selfCheck·concerns·missing) 그대로.`,
      { agentType: 'implementer', phase: 'Wave', label: `int-fix:w${waveNo}`, schema: IMPL_SCHEMA }
    )
    if (fix?.status === 'NEEDS_CONTEXT' || fix?.status === 'BLOCKED') {
      // 수정 자체가 성립 안 함 — 리뷰·커밋 생략, 게이트 재실행이 실판정(실패 → 상한 초과 → 에스컬레이션에 원문 포함).
      log(`통합 수정 implementer ${fix.status} — 부족분: ${fix.missing || '(미기재)'}. 리뷰·커밋 생략, 게이트 재실행으로 판정.`)
    } else {
      const integrationPreReview = await agent(
        `통합 수정 reviewer 직전 changeset 동결 — 수정·스테이징·커밋 금지. ${cdBase}\n` +
        `기대 브랜치 ${baseBranch}, HEAD ${integrationBefore}. branch=git branch --show-current, beforeHead=git rev-parse HEAD, reviewedFiles=(git diff --name-only HEAD; git ls-files --others --exclude-standard | sort -u), ` +
        `reviewedDigest=정렬된 경로+현재 blob hash(삭제는 DELETE)의 SHA-256, statusPorcelain=git status --porcelain 원문. 지어내지 마라.`,
        { phase: 'Wave', label: `int-pre-review:w${waveNo}`, model: 'haiku',
          schema: { type: 'object', additionalProperties: false,
            properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, reviewedFiles: { type: 'string' }, reviewedDigest: { type: 'string' }, statusPorcelain: { type: 'string' } },
            required: ['branch', 'beforeHead', 'reviewedFiles', 'reviewedDigest', 'statusPorcelain'] } }
      )
      const intPreFiles = normalizeFileSet(integrationPreReview?.reviewedFiles)
      if ((integrationPreReview?.branch ?? '').trim() !== baseBranch || (integrationPreReview?.beforeHead ?? '').trim() !== integrationBefore || intPreFiles.length === 0 || !/^[0-9a-f]{64}$/.test((integrationPreReview?.reviewedDigest ?? '').trim())) {
        return { status: 'failed', reason: 'integration-fix-early-commit', attempts: attempt, output: lastOut }
      }
      let rev = await agent(
        `wave ${waveNo} 통합 수정 블라인드 리뷰 — 실제 diff·게이트 재실행으로 원인이 고쳐졌는지 검증하라. ${cdBase}\nCodex 교차검증: 생략 — 통합 수정(단독 판정).\n` +
        `실패 로그(수정 전):\n${lastOut.slice(0, 1200)}\n` +
        `블라인드 입력 계약: 수정 보고·결정·selfCheck·concerns 는 제공되지 않는다. 실제 파일과 diff 를 직접 읽어라. concernDispositions 는 빈 배열로 반환하라.`,
        { agentType: 'reviewer', schema: REVIEW_SCHEMA, phase: 'Wave', label: `int-blind-review:w${waveNo}` }
      )
      rev = await reconcileAfterBlind(fix, rev, `${cdBase}\nwave ${waveNo} 통합 수정`, `int-concern:w${waveNo}`)
      if (rev.protocolFailure) {
        log(`통합 수정 reviewer 프로토콜 실패 — 구현자 재시도·커밋 금지: ${rev.protocolFailure}`)
        return { status: 'failed', reason: 'integration-review-protocol-failed', attempts: attempt, output: lastOut, review: rev }
      }
      if (!rev.pass) {
        log(`통합 수정 리뷰 미통과(${(rev.issues || []).join(' / ')}) — 커밋 금지·통합 실패로 종료`)
        return { status: 'failed', reason: 'integration-review-failed', attempts: attempt, output: lastOut, review: rev }
      }
      const integrationSnapshot = await agent(
        `통합 수정 리뷰 통과 changeset 동결 — 수정·스테이징·커밋 금지. ${cdBase}\n` +
        `branch=git branch --show-current, beforeHead=git rev-parse HEAD, reviewedFiles=(git diff --name-only HEAD; git ls-files --others --exclude-standard | sort -u), statusPorcelain=git status --porcelain 원문을 반환하라. ` +
        `reviewedFiles 는 경로만 한 줄씩 중복 없이 정렬. reviewedDigest는 정렬된 각 경로와 현재 blob hash(삭제는 DELETE)를 묶어 SHA-256 한 값이다. 지어내지 마라.`,
        { phase: 'Wave', label: `int-changeset:w${waveNo}`, model: 'haiku',
          schema: { type: 'object', additionalProperties: false,
            properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, reviewedFiles: { type: 'string' }, reviewedDigest: { type: 'string' }, statusPorcelain: { type: 'string' } },
            required: ['branch', 'beforeHead', 'reviewedFiles', 'reviewedDigest', 'statusPorcelain'] } }
      )
      const intPostFiles = normalizeFileSet(integrationSnapshot?.reviewedFiles)
      const integrationReviewUnchanged = (integrationPreReview?.branch ?? '').trim() === baseBranch && (integrationSnapshot?.branch ?? '').trim() === baseBranch &&
        (integrationSnapshot?.beforeHead ?? '').trim() === integrationBefore &&
        intPostFiles.length === intPreFiles.length && intPostFiles.every((f, i) => f === intPreFiles[i]) &&
        (integrationSnapshot?.reviewedDigest ?? '').trim() === (integrationPreReview?.reviewedDigest ?? '').trim() &&
        (integrationSnapshot?.statusPorcelain ?? '').trim() === (integrationPreReview?.statusPorcelain ?? '').trim()
      if (!integrationReviewUnchanged) {
        return { status: 'failed', reason: 'integration-review-mutated-changeset', attempts: attempt, output: lastOut }
      }
      const integrationCommit = await agent(
        `통합 수정 커밋 — base 의 변경을 atomic commit 하라(커밋만·STATE 수정 금지·새 파일 발명 금지). ${cdBase}\n` +
        `git checkout ${baseBranch} 후 commit 직전 git rev-parse HEAD 를 beforeHead 에 보존 → git add -A(무관 파일 제외) → 한국어 commit 1개(--no-verify·--force 금지, 메시지 끝 Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>). 반환 원문: beforeHead·afterHead(git rev-parse HEAD)·headLog·statusPorcelain·committedFiles. 실패하면 beforeHead=afterHead 로 사실대로 반환.`,
        { phase: 'Wave', label: `int-commit:w${waveNo}`, model: 'haiku', schema: COMMIT_SCHEMA }
      )
      const integrationProof = await agent(
        `통합 수정 커밋 사후 증거 — 수정·스테이징·커밋·amend 금지. ${cdBase}\n` +
        `기준 브랜치 ${baseBranch}, HEAD ${(integrationSnapshot?.beforeHead ?? '').trim()}. branch=git branch --show-current, afterHead=git rev-parse HEAD, headLog=git log -1 --format='%H %s', ` +
        `revCount=git rev-list --count ${(integrationSnapshot?.beforeHead ?? '').trim()}..HEAD, committedFiles=git diff --name-only ${(integrationSnapshot?.beforeHead ?? '').trim()}..HEAD, ` +
        `committedDigest=committedFiles의 정렬된 각 경로와 현재 blob hash(삭제는 DELETE)를 reviewedDigest와 같은 방식으로 SHA-256, statusPorcelain=git status --porcelain 원문을 반환하라. 지어내지 마라.`,
        { phase: 'Wave', label: `int-commit-proof:w${waveNo}`, model: 'haiku',
          schema: { type: 'object', additionalProperties: false,
            properties: { branch: { type: 'string' }, afterHead: { type: 'string' }, headLog: { type: 'string' }, revCount: { type: 'string' }, committedFiles: { type: 'string' }, committedDigest: { type: 'string' }, statusPorcelain: { type: 'string' } },
            required: ['branch', 'afterHead', 'headLog', 'revCount', 'committedFiles', 'committedDigest', 'statusPorcelain'] } }
      )
      const integrationCommitVerdict = judgeIndependentCommit(integrationSnapshot, integrationCommit, integrationProof, baseBranch)
      if (!integrationCommitVerdict.ok) {
        log(`통합 수정 커밋 미확인 — 커밋 증거 불충분 또는 작업트리 잔여(${integrationCommitVerdict.dirty.join(' | ') || 'HEAD 미전진/파일목록 없음'})`)
        return { status: 'failed', reason: 'integration-commit-failed', attempts: attempt, output: lastOut, commit: integrationCommit, commitProof: integrationProof }
      }
      expectedBaseHead = integrationCommitVerdict.afterHead
    }
    // 루프 재진입 → 게이트 재실행으로 실판정.
  }
}

// ══════════════════════════════════════════════════════════════════════════
// 종결 — 전 wave 통과 시 worktree 정리(ancestor 코드 판정 후 remove, 실패 worktree 보존)
// ══════════════════════════════════════════════════════════════════════════
if (!escalation && completed.size) {
  const finalizeSnapshot = await agent(
    `Finalize 전 base 증거 — 수정·checkout·remove·prune 금지. ${cdBase}\n` +
    `branch=git branch --show-current, beforeHead=git rev-parse HEAD, statusPorcelain=git status --porcelain 원문을 반환하라. 지어내지 마라.`,
    { phase: 'Finalize', label: 'finalize-snapshot', model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: { branch: { type: 'string' }, beforeHead: { type: 'string' }, statusPorcelain: { type: 'string' } }, required: ['branch', 'beforeHead', 'statusPorcelain'] } }
  )
  const finalizeBefore = (finalizeSnapshot?.beforeHead ?? '').trim()
  if ((finalizeSnapshot?.branch ?? '').trim() !== baseBranch || finalizeBefore !== expectedBaseHead || !/^[0-9a-f]{7,40}$/.test(finalizeBefore) || (finalizeSnapshot?.statusPorcelain ?? 'UNKNOWN').trim()) {
    escalate('Finalize 시작 전 base 증거 불일치 — worktree 정리 시작 금지.',
      [`branch=${finalizeSnapshot?.branch || '?'}`, `head=${finalizeBefore || '?'} expected=${expectedBaseHead}`, `status=${finalizeSnapshot?.statusPorcelain || '(unknown)'}`],
      ['base git log·status를 확인하고 검증된 통합 HEAD로 복구'])
  }
  if (!escalation) {
    const mergedIds = [...completed]
    const anc = await agent(
      `worktree 정리 전 ancestor 확인 — 아래만 수행하고 사실을 반환하라(remove·수정 금지, 제거는 상위 코드 판정 후). ${cdBase}\n` +
      mergedIds.map(id => `- git merge-base --is-ancestor ${branchOf(id)} ${baseBranch} ; echo "${id}:ANC=$?"`).join('\n') + '\n' +
      `checks 배열에 {id, ancExit(ANC 값 문자열, 0=ancestor)} 을 담아 반환. 지어내지 마라.`,
      { phase: 'Finalize', label: 'ancestor 확인', model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { checks: { type: 'array', items: { type: 'object', additionalProperties: false,
            properties: { id: { type: 'string' }, ancExit: { type: 'string' } }, required: ['id', 'ancExit'] } } },
          required: ['checks'] } }
    )
    const removable = mergedIds.filter(id => {
      const c = findByTaskId(anc?.checks, id, branchOf(id))
      const ok = (c?.ancExit || '').trim() === '0'
      if (!ok) log(`⚠ [${id}] merge 가 base 의 ancestor 아님 — worktree 보존(정리 안 함)`)
      return ok
    })
    if (removable.length) {
      await agent(
        `worktree 안전 제거 — 아래 task 의 worktree 만 제거하라(--force 금지, 실패해도 다른 것 계속). ${cdBase}\n` +
        removable.map(id => `- git worktree remove ${wtPath(id)}`).join('\n') + '\n' +
        `그 후 git worktree prune. 남은 게 없으면 .planning/worktrees 빈 디렉토리도 정리(rmdir, 실패 무시). removed 배열에 실제 제거된 id 를 담아라. 지어내지 마라.`,
        { phase: 'Finalize', label: 'worktree 제거', model: 'haiku',
          schema: { type: 'object', additionalProperties: false, properties: { removed: { type: 'array', items: { type: 'string' } } }, required: ['removed'] } }
      )
      log(`worktree 정리: ${removable.length}개(ancestor 확인분). 실패/미merge worktree 는 진단용 보존.`)
    }
    const finalizeProof = await agent(
      `Finalize 사후 base 증거 — 수정·checkout·remove·prune 금지. ${cdBase}\n` +
      `branch=git branch --show-current, afterHead=git rev-parse HEAD, statusPorcelain=git status --porcelain 원문을 반환하라. 지어내지 마라.`,
      { phase: 'Finalize', label: 'finalize-proof', model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { branch: { type: 'string' }, afterHead: { type: 'string' }, statusPorcelain: { type: 'string' } }, required: ['branch', 'afterHead', 'statusPorcelain'] } }
    )
    const finalizeAfter = (finalizeProof?.afterHead ?? '').trim()
    if ((finalizeProof?.branch ?? '').trim() !== baseBranch || finalizeAfter !== finalizeBefore || (finalizeProof?.statusPorcelain ?? 'UNKNOWN').trim()) {
      escalate('Finalize 중 base 저장소 변조 감지 — cached 통합 결과로 verified 처리하지 않음.',
        [`before=${finalizeBefore}`, `after=${finalizeAfter || '?'}`, `status=${finalizeProof?.statusPorcelain || '(unknown)'}`],
        ['worktree 정리 단계가 만든 HEAD/파일 변경을 확인하고 검증된 통합 HEAD로 복구', '해당 경로 회귀 평가 재실행'])
    }
  }
}

// ── 반환 ──────────────────────────────────────────────
const allMerged = graph.tasks.every(t => completed.has(t.id))
const allIntegrationPassed = integration.length > 0 && integration.every(i => i.status === 'passed')
const terminalState = escalation ? 'escalated' : hasPendingHuman && allMerged && allIntegrationPassed ? 'pending-human' : allMerged && allIntegrationPassed ? 'verified' : allMerged ? 'completed-unverified' : 'incomplete'
log(escalation
  ? `그래프 실행 중단 — 에스컬레이션(merge 완료 ${completed.size}/${graph.tasks.length}, push 없음이라 base 로컬만)`
  : `그래프 실행 완료 — ${completed.size}/${graph.tasks.length} merge, 통합 게이트 ${integration.filter(i => i.status === 'passed').length}/${integration.length} 통과. 원격 push/prod 반영은 명시적으로 승인된 범위에서만 수행.`)

return {
  projectRoot,
  baseBranch,
  waves: waveSummaries,
  taskResults,
  integration,
  allMerged,
  escalation,
  terminalState,
  pendingHuman: terminalState === 'pending-human'
    ? { reason: `human 게이트 ${recon.humanCount}개가 남아 STATE 종결·verified 선언을 하지 않음`, nextAction: '해당 approval에 필요한 사람 답·권한을 받으면 에이전트가 증거를 기록하고 종결' }
    : null,
  runSummary: graphRunSummary(
    terminalState, true, hasPendingHuman ? 'required' : 'not_observable', terminalState === 'verified',
    [
      graphEvent('Resolve', 'graph-validated', 'passed'),
      ...Object.values(taskResults).map(r => graphEvent('Wave', 'task-terminal', r.status, r.status, r.attempts ?? 0, { taskId: r.id ?? '' })),
      ...integration.map(i => graphEvent('Wave', 'integration-gate', i.status, i.reason ?? '', i.attempts ?? 0, { actorType: 'probe', wave: i.wave })),
      graphEvent('Finalize', 'terminal-state', terminalState, terminalState),
    ],
    { allMerged, integrationPassed: allIntegrationPassed },
  ),
}
