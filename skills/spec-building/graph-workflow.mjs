export const meta = {
  name: 'spec-building-graph',
  description: '멀티 task 그래프를 wave(위상정렬·동시 상한 4)로 병렬 실행한다: task별 격리 worktree → implementer(sonnet) → reviewer(opus) → 커밋 → merge-gate(결정적) → base merge(직렬) → regen barrier → wave 통합 게이트(exit0). "속으면 안 되는 판정(그래프 유효성·merge-gate·통합 게이트·main 차단·라이브 게이트 반려)은 전부 코드", 에이전트는 사실만 원문 반환. push 금지(로컬 커밋만)·main 직접작업 금지(사람 merge). 스택·도메인 비종속.',
  whenToUse: '한 STATE task 가 여러 하위 task 로 갈라지고 서로 의존관계가 있어 병렬 탐색이 이득일 때. 단일 task 는 workflow.mjs 를 쓴다. 입력: STATE "## 다음 task" 의 "### 그래프" fenced json 블록. 정본 채널 = /tmp/spec-building.target(절대경로 1줄), args:{projectRoot} 는 보조. 라이브 게이트({PREVIEW_URL})·main 브랜치는 시작 시 fail-fast.',
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
//   - 신뢰 경계: push 없음(로컬 커밋만) · main/master 직접작업 금지(시작 시 fail-fast) · 사람이 merge/push.
//     라이브 게이트({PREVIEW_URL})는 v1 범위 밖 → 시작 시 반려(단일 task 경로 workflow.mjs 로 안내).
// ══════════════════════════════════════════════════════════════════════════

const CONCURRENCY = 4          // wave 내 동시 dispatch 상한
const INTEGRATION_FIX_CAP = 1  // 통합 게이트 실패 시 원인 수정 재투입 상한(초과 = 에스컬레이션)

// ── 입력 ──────────────────────────────────────────────
// 하니스가 args 를 JSON "문자열"로 전달한다(2026-06-11 첫 실전 관찰 실증) → 객체로 정규화.
const A = (typeof args === 'string') ? (() => { try { return JSON.parse(args) } catch { return null } })() : (args ?? null)
const MAX_TASK_ATTEMPTS = A?.maxAttempts ?? 3
log(`args 수신(정규화 후): ${JSON.stringify(A)}`)

// ── 순수 JS 검증기 (구현 진입 전, 실패 시 구체 에러로 throw) ─────────────
const RISK_ENUM = ['RISKY', 'MECHANICAL', 'NONE']

function validateGraph(raw) {
  let g
  try { g = JSON.parse(raw) }
  catch (e) { throw new Error(`그래프 JSON 파싱 실패: ${e.message}. STATE "### 그래프" 의 fenced json 블록이 유효한 JSON 이어야 한다(YAML 아님 — 스크립트가 JSON.parse 로 결정적 검증).`) }
  if (!g || typeof g !== 'object' || Array.isArray(g)) throw new Error('그래프 최상위가 객체가 아님')
  const tasks = g.tasks
  if (!Array.isArray(tasks) || tasks.length === 0) throw new Error('그래프에 tasks 배열이 없거나 비어 있음')

  const ids = new Set()
  for (const t of tasks) {
    if (!t || typeof t !== 'object') throw new Error('task 항목이 객체가 아님')
    if (typeof t.id !== 'string' || !t.id.trim()) throw new Error('task.id 가 비어 있음(문자열 필수)')
    if (ids.has(t.id)) throw new Error(`task id 중복: ${t.id} (id 유일성 위반)`)
    ids.add(t.id)
    if (typeof t.goal !== 'string' || !t.goal.trim()) throw new Error(`task ${t.id}: goal 이 비어 있음(각 task goal 필수)`)
    if (t.depends !== undefined && !Array.isArray(t.depends)) throw new Error(`task ${t.id}: depends 는 배열이어야 함`)
    // targets 필수(2026-07-06 적대 리뷰 A4): 선언이 아예 없으면 merge-gate 의 diff∩targets 검사가
    // 통째로 우회된다 → 비어있지 않은 문자열 배열 강제. 'state'/'external' 멤버는 허용 —
    // 파일 target 0개 task 는 merge-gate 에서 strictly-ahead+커밋 실재만 보되(기존 동작),
    // "무선언 우회"는 여기서 차단한다.
    if (!Array.isArray(t.targets) || t.targets.length === 0 || t.targets.some(x => typeof x !== 'string' || !x.trim())) {
      throw new Error(`task ${t.id}: targets 는 비어있지 않은 문자열 배열 필수(파일 경로 | "state" | "external") — 선언 없는 task 는 merge-gate(diff∩targets)를 우회하므로 반려한다.`)
    }
    // risk 생략 = 미분류(허용). 명시됐다면 enum 3값만 — 그 외는 반려(미분류로 관대 처리하지 않는다).
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
  })
  // 비순환 — 위상정렬 성공 여부로 판정(실패=순환)
  const waves = topoWaves(tasks)
  const verify = (typeof g.verify === 'string' && g.verify.trim()) ? g.verify.trim() : null
  return { tasks, byId: new Map(tasks.map(t => [t.id, t])), barriers, waves, verify }
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

function judgeCommit(c) {
  const dirty = (c?.statusPorcelain ?? 'UNKNOWN').split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('??'))
  const ok = dirty.length === 0 && /^[0-9a-f]{7,40} /.test(c?.headLog ?? '')
  return { ok, dirty }
}

// merge-gate 판정(결정적, dryforge 이식 핵심): ⓪ STATE 불가침 ① strictly ahead ② diff 비어있지 않음
// ③ diff 파일이 선언 file target 과 교집합(파일 target 있는 task 만). 대상 밖 파일 = 경고.
function judgeMergeGate(task, revCount, diffFilesRaw) {
  const ahead = Number.parseInt((revCount || '').trim(), 10) >= 1
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
  if (!hasFileTarget) {
    // state/external 전용 task(no-file-diff): 커밋 실재(strictly ahead)만으로 판정.
    return { pass: ahead, reason: ahead ? '' : 'rev-list 0(커밋이 base 보다 앞서지 않음)', warnings: [], noFileDiff: true }
  }
  const intersect = files.some(matches)
  const extra = files.filter(f => !matches(f))
  const reasons = []
  if (!ahead) reasons.push('rev-list 0(base 보다 앞서지 않음)')
  if (!nonEmpty) reasons.push('diff 비어 있음')
  if (!intersect) reasons.push(`diff 파일이 선언 targets(${fileTargets.join(', ')})와 교집합 없음`)
  return {
    pass: ahead && nonEmpty && intersect,
    reason: reasons.join('; '),
    warnings: extra.length ? [`대상 밖 파일 섞임(경고): ${extra.join(', ')}`] : [],
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

// 조용한 기각 금지 가드(코드 판정 — workflow.mjs 동일 로직 이식): DONE_WITH_CONCERNS 면
// concernDispositions 가 concerns 와 1:1 이어야 하고, disposition 'blocker' 는 issues 로 승격.
function applyConcernGuard(impl, review) {
  if (impl?.status !== 'DONE_WITH_CONCERNS' || !review) return review
  const concernCount = impl.concerns?.length ?? 0
  const dispositions = Array.isArray(review.concernDispositions) ? review.concernDispositions : []
  if (dispositions.length !== concernCount) {
    review.pass = false
    review.issues = [...(review.issues ?? []), `concernDispositions 개수 불일치(concerns=${concernCount}, dispositions=${dispositions.length}) — 우려 판정 누락(조용한 기각 금지 가드)`]
  } else {
    const promoted = dispositions.filter(d => d?.disposition === 'blocker')
    if (promoted.length) {
      review.pass = false
      review.issues = [...(review.issues ?? []), ...promoted.map(d => `[concern→blocker 승격] ${d.concern}: ${d.note}`)]
    }
  }
  return review
}
// DONE_WITH_CONCERNS 의 concerns 를 reviewer 프롬프트에 명시 전달하는 블록(workflow.mjs 와 동일 문구).
function concernsBlock(impl) {
  return (impl?.status === 'DONE_WITH_CONCERNS' && impl.concerns?.length)
    ? `⚠ implementer 가 DONE_WITH_CONCERNS 로 보고했다 — 아래 concerns 를 하나도 빠짐없이 concernDispositions(resolved/accepted/blocker)로 판정하라:\n${impl.concerns.map((c, i) => `  ${i + 1}. ${c}`).join('\n')}\n`
    : ''
}
const COMMIT_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    headLog: { type: 'string', description: "git log -1 --format='%H %s' 원문" },
    statusPorcelain: { type: 'string', description: 'git status --porcelain 원문(클린이면 빈 문자열)' },
    committedFiles: { type: 'string', description: "git show HEAD --stat --format='' 원문" },
  },
  required: ['headLog', 'statusPorcelain', 'committedFiles'],
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
  `1) 현재 브랜치: git branch --show-current 결과를 currentBranch 로.\n` +
  `2) ${projectRoot}/.planning/STATE.md 를 읽어라. "## 다음 task" 섹션만 본다(다음 "## " 헤더 또는 "---" 전까지).\n` +
  `3) 그 안 "### 그래프" 하위의 \`\`\`json ... \`\`\` fenced 블록 **내용을 fence 제외 원문 그대로** graphRaw 로. 블록이 없으면 빈 문자열.\n` +
  `4) "## 다음 task" 섹션 어디든 문자열 "{PREVIEW_URL}" 이 등장하면 hasPreviewUrl=true(라이브 게이트 표시), 없으면 false.\n` +
  `5) "### 목표" 하위 텍스트(전체 목표)를 overallGoal 로(없으면 빈 문자열).\n` +
  `**친절한 추론·보정 금지** — 있는 그대로 반환하라.`,
  {
    phase: 'Resolve', label: '정찰', model: 'haiku',
    schema: {
      type: 'object', additionalProperties: false,
      properties: {
        currentBranch: { type: 'string', description: 'git branch --show-current 결과' },
        graphRaw: { type: 'string', description: '### 그래프 의 json fenced 블록 원문(없으면 빈 문자열)' },
        hasPreviewUrl: { type: 'boolean', description: '"## 다음 task" 에 "{PREVIEW_URL}" 등장 여부' },
        overallGoal: { type: 'string', description: '### 목표 텍스트(없으면 빈 문자열)' },
      },
      required: ['currentBranch', 'graphRaw', 'hasPreviewUrl', 'overallGoal'],
    },
  }
)

// ── fail-fast 게이트 (코드 판정 — 구현 진입 전) ───────────────────────────
const baseBranch = (recon?.currentBranch || '').trim()
if (baseBranch === 'main' || baseBranch === 'master' || baseBranch === '') {
  throw new Error(`그래프 실행은 작업 브랜치에서 — 현재 브랜치 "${baseBranch || '(불명)'}". main/master 직접 그래프 실행은 신뢰 경계 위반(prod 반영·merge=사람). 작업 브랜치를 만들고(git checkout -b <branch>) 재실행하라.`)
}
if (recon?.hasPreviewUrl) {
  throw new Error(`라이브 게이트({PREVIEW_URL})는 그래프 실행 v1 범위 밖이다 — 반려. 라이브로 닫는 task 는 단일 task 경로(workflow.mjs, Phase C)로 실행하라(그래프는 로컬 검증·merge-gate·통합 게이트까지만 자율, 프리뷰/push 는 다루지 않는다).`)
}
if (!recon?.graphRaw?.trim()) {
  throw new Error('그래프 없음 — "## 다음 task" 에 "### 그래프" + fenced json 블록이 없다. 그래프 실행은 멀티 task 그래프를 요구한다(단일 task 는 workflow.mjs).')
}

// ── 그래프 결정적 파싱·검증 (무효면 여기서 throw — 구현 0) ──────────────
const graph = validateGraph(recon.graphRaw.trim())
const overallGoal = (recon.overallGoal || '').trim()
log(`그래프 검증 통과 — task ${graph.tasks.length}개 · wave ${graph.waves.length}개(${graph.waves.map((w, i) => `w${i + 1}[${w.join(',')}]`).join(' ')}) · regenBarriers ${graph.barriers.length}개 · verify ${graph.verify ? `"${graph.verify}"` : '(미지정 — STATE/pkg 에서 발견 시도)'}`)

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
async function runTask(task) {
  const wt = wtPath(task.id)
  const cdWt = `작업 디렉토리는 이 task 의 worktree = ${wt} 다. Bash 사용 시 항상 먼저 cd ${wt}. base(${projectRoot}) 나 다른 worktree 를 건드리지 마라. 시작 시 git rev-parse --show-toplevel 로 위치를 확인하라.`
  const { implNote, codex } = riskDirectives(task)
  const targetsStr = task.targets.join(', ') // validateGraph 가 비어있지 않음을 보장(A4)
  const specSlice =
    (overallGoal ? `전체 목표(맥락):\n${overallGoal}\n\n` : '') +
    `이 task(${task.id}) 목표:\n${task.goal}\n\n선언 targets(이 범위만 변경): ${targetsStr}\n${implNote}\n`

  let impl, review = null, feedback = '', attempt = 0
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
      if (attempt >= MAX_TASK_ATTEMPTS) {
        return { id: task.id, status: 'blocked', implStatus: impl.status, missing: impl.missing || '(missing 미기재)', attempts: attempt }
      }
      feedback = `implementer 가 ${impl.status} 상태를 반환했다 — 아래 부족분을 반드시 보강하라:\n${impl.missing || '(미기재)'}`
      continue
    }

    review = await agent(
      `그래프 하위 task 리뷰 — implementer 보고를 믿지 말고 실제(diff·게이트 재실행)로 검증하라. ${cdWt}\n\n${specSlice}\n${codex}\n` +
      `이 task 범위(선언 targets)만 변경됐는지, 목표를 만족하는지 판정하라. 라이브/프리뷰 항목은 이 그래프 범위 밖 — 판정 대상 아님.\n` +
      concernsBlock(impl) +
      `구현 보고(JSON):\n${JSON.stringify(impl)}\n\n(검증·교차검증·판정 규칙은 너의 에이전트 정의에 있다 — 위 Codex 지시와 함께 따르라.)`,
      { agentType: 'reviewer', schema: REVIEW_SCHEMA, phase: 'Wave', label: attempt > 1 ? `review:${task.id}(${attempt})` : `review:${task.id}` }
    )
    review = applyConcernGuard(impl, review) // 코드 판정: dispositions 1:1 + blocker 승격

    if (review.pass) break
    if (attempt >= MAX_TASK_ATTEMPTS) {
      return { id: task.id, status: 'review-failed', review, advisories: review?.advisories ?? [], concernDispositions: review?.concernDispositions ?? [], attempts: attempt }
    }
    feedback = review.issues.join('\n')
    log(`[${task.id}] 리뷰 블로커 ${review.issues.length}개 → 재시도 ${attempt + 1}/${MAX_TASK_ATTEMPTS}`)
  }

  // 커밋 — worktree 안에서. STATE 수정 금지·새 파일 발명 금지(리뷰 통과 상태 그대로).
  const commit = await agent(
    `리뷰를 통과한 이 worktree 의 변경을 atomic commit 하라(커밋만 — 코드 재작성·새 파일 발명·STATE 수정 금지). ${cdWt}\n` +
    `task(${task.id}): ${task.goal}\n` +
    `1) git add -A 로 리뷰-통과 변경을 스테이징(무관 파일만 제외, **.planning/STATE.md 수정·새 파일 발명 금지**).\n` +
    `2) 한국어 커밋 메시지로 commit 정확히 1개(--no-verify·--force 금지). 메시지에 '완료'·'검증됨'·'merge' 주장 금지 — 변경 내용만 서술(merge·통합검증은 상위가 한다). 메시지 끝: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>\n` +
    `3) 커밋 후 **실행한 명령의 출력 원문 그대로** 반환: headLog=git log -1 --format='%H %s', statusPorcelain=git status --porcelain(클린이면 빈 문자열), committedFiles=git show HEAD --stat --format='' 원문. 지어내지 마라.`,
    { phase: 'Wave', label: `commit:${task.id}`, model: 'haiku', schema: COMMIT_SCHEMA }
  )
  const jc = judgeCommit(commit)
  return {
    id: task.id, status: jc.ok ? 'committed' : 'commit-failed', review,
    advisories: review?.advisories ?? [], concernDispositions: review?.concernDispositions ?? [],
    commit, dirty: jc.dirty, attempts: attempt,
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
    waveIds.map(id => `   - git worktree add ${wtPath(id)} -b ${branchOf(id)} ${baseBranch} ; echo "ADD_EXIT=$?" ; git -C ${wtPath(id)} rev-parse --show-toplevel`).join('\n') + '\n' +
    `2) worktrees 배열에 task 마다 {id, addExit(ADD_EXIT 값 문자열), toplevel(rev-parse 출력 마지막 줄), output(그 task 명령들의 출력 원문)} 을 담아라. **지어내지 마라** — 실패하면 실패 원문 그대로.`,
    {
      phase: 'Wave', label: `worktree:w${w + 1}`, model: 'haiku',
      schema: {
        type: 'object', additionalProperties: false,
        properties: {
          worktrees: {
            type: 'array',
            items: {
              type: 'object', additionalProperties: false,
              properties: { id: { type: 'string' }, addExit: { type: 'string' }, toplevel: { type: 'string' }, output: { type: 'string' } },
              required: ['id', 'addExit', 'toplevel', 'output'],
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
    wtByIdOk.set(id, addOk && topOk)
    if (!(addOk && topOk)) log(`✗ [${id}] worktree 생성 실패 — addExit=${rec?.addExit ?? '?'}, toplevel=${(rec?.toplevel || '').trim() || '(없음)'}`)
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
    const res = await parallel(batch.map(t => () => runTask(t)))
    for (const r of res) taskResults[r.id] = r
  }
  const notCommitted = waveIds.filter(id => taskResults[id]?.status !== 'committed')
  if (notCommitted.length) {
    const blockers = notCommitted.map(id => {
      const r = taskResults[id]
      if (r?.status === 'blocked') return `${id}: implementer ${r.implStatus}(${MAX_TASK_ATTEMPTS}회, 리뷰 미도달) — 부족분: ${r.missing}`
      if (r?.status === 'review-failed') return `${id}: ${MAX_TASK_ATTEMPTS}회 리뷰 미통과 — ${(r.review?.issues || []).join(' / ')}`
      if (r?.status === 'commit-failed') return `${id}: 커밋 미확인 — status 잔여 ${(r.dirty || []).join(' | ') || '(headLog 불일치)'}`
      return `${id}: 미완(${r?.status})`
    })
    escalate(`wave ${w + 1}: ${notCommitted.length}개 task 가 커밋에 도달 못함(${notCommitted.join(', ')}) — 커밋된 것은 merge 안 하고 멈춘다(실패 worktree 진단용 보존).`,
      blockers,
      ['blocked(NEEDS_CONTEXT/BLOCKED)면 missing 의 부족 정보(스키마·ADR·환경)를 그래프 goal/STATE 에 보강 후 재투입', '리뷰 블로커면 수용 기준/task 분해 재검토 후 재투입', 'commit-failed 면 해당 worktree git 상태 확인(부당 커밋 공존 여부)', 'task 가 크면 그래프를 더 작은 단위로 재작성'])
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
    if (verdict.pass) { mergeOrder.push(id); log(`✓ [${id}] merge-gate 통과 (ahead+diff+target 교집합${verdict.noFileDiff ? '(no-file-diff: 커밋실재)' : ''})`) }
    else { gateFailed.push(id); log(`✗ [${id}] merge-gate 실패: ${verdict.reason}`) }
  }
  if (gateFailed.length) {
    escalate(`wave ${w + 1}: merge-gate 실패 ${gateFailed.join(', ')} — STATE 불가침 위반 또는 선언 targets 와 실제 diff 불일치(빈 diff·대상 밖만 변경 등). base 미오염(merge 안 함), 실패 worktree 보존.`,
      gateFailed.map(id => `${id}: ${taskResults[id].mergeGate.reason}`),
      ['STATE 불가침 위반이면 해당 worktree 커밋에서 .planning/STATE.md 변경을 걷어낸 뒤 재투입(종결 기록은 완주 후 메인)', 'task 가 targets 밖을 건드렸는지/아무 것도 안 바꿨는지 worktree diff 확인', '선언 targets 가 실제 산출물과 맞는지 그래프 재작성', 'task 재투입'])
    break
  }

  // 4) base merge 직렬(gate 통과분만). 충돌 시 abort → 에스컬레이션.
  const mergeRes = await agent(
    `base 브랜치(${baseBranch}) 로 merge — 아래 순서대로 **직렬** 실행하고 사실을 반환하라(코드 수정·push 금지). ${cdBase}\n` +
    `1) 현재 base(${baseBranch}) 체크아웃 상태 확인(git branch --show-current). 아니면 git checkout ${baseBranch}.\n` +
    `2) 다음 브랜치를 **하나씩 순서대로** merge 하라(충돌이면 즉시 git merge --abort 하고 그 task 부터 중단 — 뒤 task 는 시도하지 마라):\n` +
    mergeOrder.map(id => `   - git merge ${branchOf(id)} ; echo "${id}:MERGE_EXIT=$?"`).join('\n') + '\n' +
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
    if (ok) { completed.add(id); taskResults[id].merged = true; taskResults[id].status = 'merged'; log(`✓ [${id}] base merge 완료: ${m.headLog}`) }
    else { taskResults[id].merged = false; mergeConflict = mergeConflict || id; log(`✗ [${id}] merge 실패/충돌 — exit=${m?.exit ?? '?'} conflict=${m?.conflict}`) }
  }
  if (mergeConflict) {
    escalate(`wave ${w + 1}: base merge 충돌(${mergeConflict}) — abort 됨(base 무결). 성공 merge 는 base 에 남아 있다. 충돌은 자동 해소하지 않는다(무결성 우선).`,
      [`${mergeConflict}: git merge 충돌 → abort`],
      ['충돌 파일이 shared-write 인지 확인 — 그래프에서 단일 writer 로 재구성', '수동 충돌 해소 후 이어가기', '사용자 에스컬레이션'])
    break
  }

  // 5) regen barriers — after 충족분 실행(base). 비0 = 에스컬레이션.
  const dueBarriers = graph.barriers.filter((b, i) => !ranBarriers.has(i) && b.after.every(a => completed.has(a)))
  let barrierFail = null
  for (let bi = 0; bi < graph.barriers.length && !barrierFail; bi++) {
    const b = graph.barriers[bi]
    if (ranBarriers.has(bi) || !b.after.every(a => completed.has(a))) continue
    const br = await agent(
      `regen barrier 실행 — 아래 명령을 base 에서 실행하고 사실을 반환하라(명령 외 수정 금지). ${cdBase}\n` +
      `git checkout ${baseBranch} 후: ${b.run} ; echo "EXIT=$?"\n` +
      `명령이 파일을 바꿨으면(후속 wave worktree 가 base 에서 갈라지므로) git add -A && 한국어로 commit 1개(--no-verify 금지, 메시지 끝 Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>). 바뀐 게 없으면 커밋하지 마라.\n` +
      `반환: exit(EXIT 값 문자열)·output(명령 출력 원문)·headLog(커밋했으면 git log -1 --format='%H %s' 원문, 아니면 빈 문자열). 지어내지 마라.`,
      { phase: 'Wave', label: `regen:w${w + 1}#${bi}`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false,
          properties: { exit: { type: 'string' }, output: { type: 'string' }, headLog: { type: 'string' } },
          required: ['exit', 'output', 'headLog'] } }
    )
    ranBarriers.add(bi)
    if ((br?.exit || '').trim() !== '0') { barrierFail = { bi, run: b.run, output: br?.output || '' }; break }
    log(`✓ regen barrier #${bi} (after ${b.after.join(',')}) 실행: exit 0${br.headLog ? ` · ${br.headLog}` : ''}`)
  }
  if (barrierFail) {
    escalate(`wave ${w + 1}: regen barrier 비0 종료(#${barrierFail.bi}: ${barrierFail.run}) — 선행 merge 가 전제를 깼는지 확인.`,
      [`regen 명령 실패: ${barrierFail.run}\n${(barrierFail.output || '').slice(0, 600)}`],
      ['regen 명령이 merge 된 파일을 덮어쓰려는지 확인', '명령/그래프 after 정합 재검토', '사용자 에스컬레이션'])
    break
  }
  if (dueBarriers.length) log(`regen barriers ${dueBarriers.length}개 처리 완료`)

  // 6) wave 통합 게이트 — verify 명령 exit0(코드 판정). 실패 시 상한 내 원인 수정 재투입.
  const ig = await integrationGate(w + 1, waveIds)
  integration.push({ wave: w + 1, ...ig })
  waveSummaries.push({ wave: w + 1, tasks: waveIds, merged: waveIds.filter(id => completed.has(id)), integration: ig.status })
  if (ig.status === 'failed') {
    escalate(`wave ${w + 1}: 통합 게이트 미통과(${INTEGRATION_FIX_CAP + 1}회 상한). merge 는 base 에 남아 있으나(push 없음) 교차작용 결함이 있다.`,
      [`통합 게이트 exit≠0:\n${(ig.output || '').slice(0, 800)}`],
      ['실패 출력으로 원인 task 확정(debugger) 후 재투입', 'verify 명령이 wave 산출물과 맞는지 확인', '그래프 의존/순서 재검토'])
    break
  }
  if (ig.status === 'skipped') log(`⚠ wave ${w + 1} 통합 게이트 생략(기록됨): ${ig.reason}`)
}

// 통합 게이트 헬퍼 — verify 를 base 에서 실행, exit0 판정(코드). 실패 시 원인 수정 재투입(상한).
async function integrationGate(waveNo, waveIds) {
  if (!verifyCmd) return { status: 'skipped', reason: 'verify 명령 없음(그래프·STATE·package.json 미발견) — 기록된 생략' }
  let attempt = 0
  let lastOut = ''
  while (true) {
    attempt++
    const r = await agent(
      `wave 통합 게이트 — base 에서 verify 명령을 실행하고 **exit code 와 출력 원문 그대로** 반환하라(수정·커밋 금지). ${cdBase}\n` +
      `git checkout ${baseBranch} 후: ${verifyCmd} ; echo "EXIT=$?"\n` +
      `반환: exit(EXIT 값 문자열)·output(명령 출력 원문, 실패 시 실패 로그 포함). 지어내지 마라 — 통과 신호를 제조하지 마라.`,
      { phase: 'Wave', label: `integration:w${waveNo}${attempt > 1 ? `(재${attempt})` : ''}`, model: 'haiku',
        schema: { type: 'object', additionalProperties: false, properties: { exit: { type: 'string' }, output: { type: 'string' } }, required: ['exit', 'output'] } }
    )
    lastOut = r?.output || ''
    if ((r?.exit || '').trim() === '0') { log(`✓ wave ${waveNo} 통합 게이트 통과 (exit 0, 시도 ${attempt})`); return { status: 'passed', attempts: attempt, output: lastOut } }
    log(`✗ wave ${waveNo} 통합 게이트 실패 (exit≠0, 시도 ${attempt})`)
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
      let rev = await agent(
        `wave ${waveNo} 통합 수정 리뷰 — 실제로 원인을 고쳤는지 diff·게이트 재실행으로 검증하라. ${cdBase}\nCodex 교차검증: 생략 — 통합 수정(단독 판정).\n` +
        concernsBlock(fix) +
        `수정 보고(JSON):\n${JSON.stringify(fix)}`,
        { agentType: 'reviewer', schema: REVIEW_SCHEMA, phase: 'Wave', label: `int-review:w${waveNo}` }
      )
      rev = applyConcernGuard(fix, rev) // 코드 판정: dispositions 1:1 + blocker 승격
      if (!rev.pass) { log(`통합 수정 리뷰 미통과(${(rev.issues || []).join(' / ')}) — 다음 게이트 재실행에서 실판정`) }
      await agent(
        `통합 수정 커밋 — base 의 변경을 atomic commit 하라(커밋만·STATE 수정 금지·새 파일 발명 금지). ${cdBase}\n` +
        `git checkout ${baseBranch} 후 git add -A(무관 파일 제외) → 한국어 commit 1개(--no-verify·--force 금지, 메시지 끝 Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>). 반환 원문: headLog·statusPorcelain·committedFiles.`,
        { phase: 'Wave', label: `int-commit:w${waveNo}`, model: 'haiku', schema: COMMIT_SCHEMA }
      )
    }
    // 루프 재진입 → 게이트 재실행으로 실판정.
  }
}

// ══════════════════════════════════════════════════════════════════════════
// 종결 — 전 wave 통과 시 worktree 정리(ancestor 코드 판정 후 remove, 실패 worktree 보존)
// ══════════════════════════════════════════════════════════════════════════
if (!escalation && completed.size) {
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
}

// ── 반환 ──────────────────────────────────────────────
const allMerged = graph.tasks.every(t => completed.has(t.id))
log(escalation
  ? `그래프 실행 중단 — 에스컬레이션(merge 완료 ${completed.size}/${graph.tasks.length}, push 없음이라 base 로컬만)`
  : `그래프 실행 완료 — ${completed.size}/${graph.tasks.length} merge, 통합 게이트 ${integration.filter(i => i.status === 'passed').length}/${integration.length} 통과. prod 반영(merge/push)=사람.`)

return {
  projectRoot,
  baseBranch,
  waves: waveSummaries,
  taskResults,
  integration,
  allMerged,
  escalation,
}
