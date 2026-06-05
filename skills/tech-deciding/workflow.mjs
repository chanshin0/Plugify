export const meta = {
  name: 'tech-deciding',
  description: '되돌리기 비싼 기술/아키텍처 결정: 기능→난제 정의 → 축별 격리 조사(researcher 병렬·web·cited) → 종합 선정 → 적대 검증 → ADR 산출. 스택·도메인 비종속.',
  whenToUse: '스택/프레임워크/라이브러리/인프라 등 되돌리기 비싼 기술 결정 시. args: { question, projectRoot, adrPath?, planningDir? }',
  phases: [
    { title: 'Define', detail: '기획에서 기능→기술난제 매핑, 조사 축 도출(sonnet)' },
    { title: 'Research', detail: '난제 축별 격리 researcher 병렬(web·cited)' },
    { title: 'Synthesize', detail: '후보 비교 + 선정 초안(opus)' },
    { title: 'Critique', detail: '적대 검증 — 빠진 축·과투자·되돌리기비용(opus)' },
    { title: 'ADR', detail: 'decisions/NNN-*.md 기록(haiku)' },
  ],
}

// ── 입력 ──────────────────────────────────────────────
const question    = args?.question    ?? '(결정할 질문이 args.question 에 없음 — 호출 시 지정하라)'
const projectRoot = args?.projectRoot ?? '.'
const planningDir = args?.planningDir ?? `${projectRoot}/.planning/planning`
const adrPath     = args?.adrPath      // 예: '.planning/decisions/00X-foo.md' (없으면 ADR 단계 스킵)

const DEFINE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    constraints: { type: 'string', description: '프로젝트 핵심 제약 요약(조사 에이전트에 그대로 주입)' },
    axes: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          key:       { type: 'string', description: '짧은 식별자(예: framework, backend, search)' },
          title:     { type: 'string' },
          questions: { type: 'string', description: '이 축에서 웹조사할 구체 질문들' },
        },
        required: ['key', 'title', 'questions'],
      },
    },
  },
  required: ['constraints', 'axes'],
}

// ── P1 정의 ───────────────────────────────────────────
phase('Define')
const define = await agent(
  `너는 결정 분석가다. 기획 산출물(${planningDir}/ 의 기획서·데이터모델·핸드오프 등 있으면)을 Read 로 읽어라.\n` +
  `결정할 질문: "${question}"\n` +
  `이 질문에 답하려면 구현해야 할 기능과, 각 기능이 만드는 진짜 기술 난제를 매핑하라(흔한 CRUD 말고 스택을 가르는 난제만). ` +
  `그 난제들을 독립적으로 웹조사 가능한 "축"으로 묶어라. constraints 에는 조사 에이전트가 알아야 할 제약(규모·예산·확정 결정·타깃)을 요약하라.`,
  { schema: DEFINE_SCHEMA, phase: 'Define', model: 'sonnet' }
)
log(`정의 완료 — 조사 축 ${define.axes.length}개: ${define.axes.map(a => a.key).join(', ')}`)

// ── P2 조사 (축별 격리 fan-out, researcher 에이전트) ──
phase('Research')
const research = await parallel(
  define.axes.map(axis => () =>
    agent(
      `결정 축 조사: ${axis.title}\n\n조사 질문:\n${axis.questions}\n\n프로젝트 제약:\n${define.constraints}\n\n(역할·조사 방법·출력 형식은 너의 에이전트 정의에 있다 — 따르라.)`,
      { agentType: 'researcher', label: `research:${axis.key}`, phase: 'Research' }
    ).then(out => ({ key: axis.key, title: axis.title, findings: out }))
  )
)
const researchBlock = research.filter(Boolean)
  .map(r => `## 축: ${r.title} (${r.key})\n${r.findings}`).join('\n\n---\n\n')

// ── P3 종합 ───────────────────────────────────────────
phase('Synthesize')
const synthesis = await agent(
  `다음은 "${question}" 결정을 위한 축별 웹조사 결과다. 이를 종합해 단일 스택/결정을 선정하라.\n` +
  `요구: (1) 기능→난제→선정 매핑표, (2) 각 축 추천+근거, (3) 탈락안과 이유, (4) 비용, (5) 뒤집을 조건.\n\n` +
  `제약:\n${define.constraints}\n\n조사 결과:\n${researchBlock}`,
  { phase: 'Synthesize', model: 'opus' }
)

// ── P4 적대적 검증 ────────────────────────────────────
phase('Critique')
const critique = await agent(
  `너는 적대적 리뷰어다. 다음 선정안의 약점을 찾아라: 조사 안 된 축, 과투자(YAGNI), 과소투자, 되돌리기 비용을 숨긴 곳, 근거가 출처로 뒷받침 안 된 주장, 프로젝트 제약과의 모순.\n` +
  `제약:\n${define.constraints}\n\n선정안:\n${synthesis}`,
  { phase: 'Critique', model: 'opus' }
)

// ── P5 ADR 기록 (agent 가 Write — 워크플로우는 FS 접근 없음) ──
if (adrPath) {
  phase('ADR')
  await agent(
    `다음 결정을 ADR 형식으로 ${adrPath} 에 Write 하라. 이미 있으면 덮어쓰기 전 Read.\n` +
    `형식 섹션: 상태/날짜/방법 · 컨텍스트(기능→난제) · 결정 · 근거(+출처) · 대안(왜 탈락) · 뒤집을 조건.\n\n` +
    `결정 질문: ${question}\n\n선정안:\n${synthesis}\n\n적대적 검증(반영할 것):\n${critique}`,
    { phase: 'ADR', model: 'haiku' }
  )
  log(`ADR 기록: ${adrPath}`)
}

return { question, axes: define.axes.map(a => a.key), synthesis, critique, adrPath: adrPath ?? null }
