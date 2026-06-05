export const meta = {
  name: 'spec-building',
  description: '구현 task 1개를 격리 implementer 가 작성+자기검증 → reviewer(+Codex 교차검증) 리뷰 → 통과까지 재시도 → 통과 시 atomic commit. 3회 미통과 시 메인 에스컬레이션 신호 반환. 스택·도메인 비종속(규칙은 프로젝트 ADR/STATE/기존코드에서).',
  whenToUse: '확정된 task 를 격리해서 구현할 때. args: { task?, acceptance?, projectRoot, isolation?, commit?, maxAttempts? }. task/acceptance 생략 시 STATE.md "다음 task" 를 읽는다.',
  phases: [
    { title: 'Implement', detail: '격리 implementer(sonnet) — 작성 + 자기검증' },
    { title: 'Review', detail: '격리 reviewer(opus) + Codex 병렬 교차검증' },
    { title: 'Commit', detail: '통과 시 atomic commit(haiku) + STATE 갱신 / 미통과 시 에스컬레이션' },
  ],
}

// ── 입력 ──────────────────────────────────────────────
const task        = args?.task ?? '.planning/STATE.md 의 "## 다음 task" 최상단 미완료 항목을 거기 적힌 수용 기준대로 구현하라.'
const acceptance  = args?.acceptance ?? '수용 기준은 .planning/STATE.md 의 해당 task 항목(하위 글머리)에 인라인으로 적혀 있다 — 그것을 SSOT 로 따르라.'
const projectRoot = args?.projectRoot ?? '.'
const isolation   = args?.isolation === 'worktree' ? { isolation: 'worktree' } : {}
const doCommit    = args?.commit !== false
const MAX         = args?.maxAttempts ?? 3
const cdNote      = `작업 디렉토리는 ${projectRoot} 다. Bash 사용 시 항상 먼저 cd ${projectRoot}.`

const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    pass:    { type: 'boolean' },
    issues:  { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['pass', 'issues', 'summary'],
}

// ── 구현 ↔ 리뷰 재시도 루프 ────────────────────────────
let impl, review, feedback = '', attempt = 0
while (true) {
  attempt++
  // implementer: 규칙·SSOT·자기검증은 에이전트 정의(agents/implementer.md)에 있다 → 프롬프트엔 입력만.
  impl = await agent(
    `구현 task: ${task}\n${cdNote}\n` +
    (acceptance ? `\n수용 기준(전부 만족해야 함):\n${acceptance}\n` : '') +
    (feedback ? `\n⚠ 이전 시도가 리뷰에서 막혔다. 아래 블로커를 반드시 해결하라:\n${feedback}\n` : '') +
    `\n(역할·읽을 SSOT·자기검증 규칙은 너의 에이전트 정의에 있다 — 따르라.) 반환: 변경 파일 목록 · 핵심 결정(추정 표시) · 자기검증 결과.`,
    { agentType: 'implementer', phase: 'Implement', label: attempt > 1 ? `구현(재시도 ${attempt}/${MAX})` : '구현', ...isolation }
  )

  // reviewer: 검증·Codex 교차검증·판정 규칙은 에이전트 정의(agents/reviewer.md)에 있다 → 프롬프트엔 입력만.
  review = await agent(
    `task: ${task}\n${cdNote}\n` +
    (acceptance ? `수용 기준(이 기준으로 pass 판정):\n${acceptance}\n` : '') +
    `구현 보고:\n${impl}\n\n(검증·Codex 병렬 교차검증·판정 규칙은 너의 에이전트 정의에 있다 — 따르라.)`,
    { agentType: 'reviewer', schema: REVIEW_SCHEMA, phase: 'Review', label: attempt > 1 ? `리뷰 ${attempt}` : '리뷰' }
  )

  if (review.pass) { log(`✓ 통과 (시도 ${attempt}/${MAX})`); break }
  if (attempt >= MAX) { log(`✗ ${MAX}회 미통과 — 메인 에스컬레이션 필요`); break }
  feedback = review.issues.join('\n')
  log(`리뷰 블로커 ${review.issues.length}개 → 재시도 ${attempt + 1}/${MAX}: ${review.issues.join(' / ')}`)
}

// ── 커밋(통과) 또는 에스컬레이션(미통과) ──────────────
let committed = false
let escalation = null
if (review.pass) {
  if (doCommit) {
    await agent(
      `리뷰를 통과한 변경을 atomic commit 하라. ${cdNote}\n` +
      `task: ${task}\n` +
      `1) git add -A 로 관련 변경만 스테이징(무관 파일 제외). 2) .planning/STATE.md 갱신(이 task 완료로, 다음 task 명시). **라이브 검증을 실제로 했으면 정확히 반영 — '미수행'으로 추측 기입 금지.** 3) 한국어 커밋 메시지로 commit(--no-verify·--force 금지). 메시지 끝: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`,
      { phase: 'Commit', label: '커밋', model: 'haiku' }
    )
    committed = true
    log(`커밋 완료: ${task}`)
  }
} else {
  // 3회 미통과 → 메인이 전략을 바꿔 재투입해야 한다. 무한 자동 루프는 위험하므로 여기서 멈추고 신호만 올린다.
  escalation = {
    reason: `${MAX}회 시도 후에도 reviewer 미통과(커밋 보류)`,
    blockers: review.issues,
    nextOptions: [
      '수용 기준이 과하거나 모순인가 → STATE 의 수용 기준 조정 후 재투입',
      'task 가 너무 큰가 → 더 작은 단위로 분해 후 각각 재투입',
      'implementer 모델이 약한가 → maxAttempts 와 함께 implementer 를 opus 로 격상해 1~2회 추가',
      '구조적으로 막혔나(외부 의존·환경) → 사용자에게 에스컬레이션',
    ],
  }
  log(`⚠ 에스컬레이션: ${escalation.reason}. 메인이 위 nextOptions 중 택해 재투입할 것.`)
}

return { task, attempts: attempt, impl, review, committed, escalation }
