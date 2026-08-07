export const meta = {
  name: 'tech-deciding',
  description: '되돌리기 비싼 기술/아키텍처 결정: 기능→난제 정의 → 축별 격리 조사(researcher 병렬·web·cited) → 종합 선정 → 적대 검증 → ADR 산출. 스택·도메인 비종속.',
  whenToUse: '스택/프레임워크/라이브러리/인프라 등 되돌리기 비싼 기술 결정 시. 정본 채널 = /tmp/tech-deciding.target (JSON 1줄: {"question","projectRoot","adrPath"?}). args: { question, projectRoot, adrPath?, planningDir?, runId? } 는 보조 채널.',
  phases: [
    { title: 'Define', detail: '기획에서 기능→기술난제 매핑, 조사 축 도출(sonnet)' },
    { title: 'Research', detail: '난제 축별 격리 researcher 병렬(web·cited)' },
    { title: 'Archive', detail: 'run 디렉토리에 조사 프롬프트·산출물 정착 — 증거(haiku)' },
    { title: 'Synthesize', detail: '후보 비교 + 선정 초안(opus)' },
    { title: 'Critique', detail: '적대 검증 — 빠진 축·과투자·되돌리기비용(opus)' },
    { title: 'ADR Draft', detail: 'decisions/NNN-*.md.proposed 제안 기록(haiku) — 사용자 승인 전 정본 금지' },
  ],
}

// ── 입력 ──────────────────────────────────────────────
// 하니스가 args 를 JSON "문자열"로 전달한다(2026-06-11 spec-building 첫 실전 관찰 실증) → 객체로 정규화.
const A = (typeof args === 'string') ? (() => { try { return JSON.parse(args) } catch { return null } })() : (args ?? null)
const proposalRunId = (typeof A?.runId === 'string' && A.runId.trim())
  ? A.runId.trim()
  : `tech-proposal-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
log(`args 수신(정규화 후): ${JSON.stringify(A)}`)

// ── 타깃·질문 해석 — 조용한 기본값 금지 ─────────────────
// args 는 하니스에 따라 미전달(2026-06-11 spec-building 첫 실전 관찰 사고) → 정본 채널 = 포인터 파일
// /tmp/tech-deciding.target (메인이 Workflow 호출 직전 JSON 1줄 기록: {"question","projectRoot","adrPath"?}).
// args 는 보조 채널. placeholder question·'.' 폴백으로 비싼 조사(researcher 병렬 위임)를 낭비하지 않는다.
const argQuestion = (typeof A?.question === 'string' && A.question.trim()) ? A.question.trim() : null
const argRoot     = (typeof A?.projectRoot === 'string' && A.projectRoot.trim()) ? A.projectRoot.trim() : null
const probe = await agent(
  `타깃·입력 해석 — 아래 절차만 수행하고 결과를 반환하라(조사·구현 작업 아님).\n` +
  `1) \`cat /tmp/tech-deciding.target\` 시도 — JSON 1줄({"question","projectRoot","adrPath"?})이면 필드를 읽어라. 파일이 없거나 JSON 파싱 불가면 포인터 필드(pointerQuestion·pointerAdrPath)는 빈 문자열로.\n` +
  (argRoot
    ? `2) 후보 루트 경로: ${argRoot}\n`
    : `2) 후보 루트 경로 = 1)에서 읽은 projectRoot (포인터가 없으면 후보 없음 → resolvedRoot 빈 문자열).\n`) +
  `3) 후보 루트 디렉토리가 실재하는지 ls 로 확인 — 실재하면 \`cd <후보> && pwd -P\`가 반환한 canonical 절대경로를 resolvedRoot 에, 아니면 빈 문자열. **추측·대체 경로 탐색 금지** — 후보가 무효면 무효라고 반환하라(다른 레포를 찾아내지 마라).\n` +
  `4) <resolvedRoot>/.planning/planning 디렉토리 실재 여부를 planningPresent 로.`,
  {
    phase: 'Define', label: '타깃 해석', model: 'haiku',
    schema: {
      type: 'object',
      properties: {
        resolvedRoot:    { type: 'string', description: 'ls 로 검증 후 pwd -P 로 정규화한 canonical 절대경로(무효면 빈 문자열)' },
        planningPresent: { type: 'boolean', description: '<resolvedRoot>/.planning/planning 실재 여부' },
        pointerQuestion: { type: 'string', description: '포인터 파일의 question(없으면 빈 문자열)' },
        pointerAdrPath:  { type: 'string', description: '포인터 파일의 adrPath(없으면 빈 문자열)' },
      },
      required: ['resolvedRoot', 'planningPresent', 'pointerQuestion', 'pointerAdrPath'],
    },
  }
)
const question = argQuestion ?? ((typeof probe?.pointerQuestion === 'string' && probe.pointerQuestion.trim()) ? probe.pointerQuestion.trim() : null)
if (!probe?.resolvedRoot || !question) {
  throw new Error('타깃/질문 해석 실패 — args 와 /tmp/tech-deciding.target 어디에도 유효한 projectRoot·question 이 없음. 조용한 기본값으로 진행하지 않는다(메인: 포인터 파일(JSON 1줄)을 쓰고 재실행).')
}
function normalizeAbsolutePath(value) {
  if (typeof value !== 'string' || !value.startsWith('/')) return null
  const parts = []
  for (const part of value.split('/')) {
    if (!part || part === '.') continue
    if (part === '..') parts.pop()
    else parts.push(part)
  }
  return `/${parts.join('/')}`
}
const projectRoot = normalizeAbsolutePath(probe.resolvedRoot)
if (!projectRoot || projectRoot === '/') throw new Error('타깃 canonical 경로가 유효한 절대 프로젝트 루트가 아님')

// adrPath 는 projectRoot 기준 절대경로로 정규화한다(2026-06-05 M2: 상대경로 Write + cd 보호 부재로
// ADR 이 엉뚱한 디렉토리에 생성될 위험). 없으면 ADR 단계 스킵.
const rawAdr  = (typeof A?.adrPath === 'string' && A.adrPath.trim()) ? A.adrPath.trim()
              : ((typeof probe?.pointerAdrPath === 'string' && probe.pointerAdrPath.trim()) ? probe.pointerAdrPath.trim() : null)
const adrCandidate = rawAdr ? (rawAdr.startsWith('/') ? rawAdr : `${projectRoot}/${rawAdr}`) : null
const adrPath = adrCandidate ? normalizeAbsolutePath(adrCandidate) : null
const proposedAdrPath = adrPath ? `${adrPath}.proposed` : null
let adrCanonical = null
if (adrPath) {
  const adrDir = adrPath.slice(0, adrPath.lastIndexOf('/'))
  adrCanonical = await agent(
    `ADR canonical 경로 사전검사 — Read 전용, 파일 내용 읽기·생성·수정·삭제 금지. 프로젝트 루트 ${projectRoot}.\n` +
    `python3 os.path.realpath 또는 동등한 canonical 해석으로 decisionDir=${adrDir}, final=${adrPath}, proposed=${proposedAdrPath} 의 symlink 해소 절대경로를 각각 canonicalDecisionDir·canonicalFinalPath·canonicalProposedPath로 반환하라. 경로가 아직 없어도 실재하는 상위 symlink를 해소하라.`,
    { phase: 'Define', label: 'ADR canonical 경로', model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: { canonicalDecisionDir: { type: 'string' }, canonicalFinalPath: { type: 'string' }, canonicalProposedPath: { type: 'string' } },
        required: ['canonicalDecisionDir', 'canonicalFinalPath', 'canonicalProposedPath'] } }
  )
  const insideProject = value => typeof value === 'string' && value.startsWith(`${projectRoot}/`)
  if (!insideProject(adrCanonical?.canonicalDecisionDir) || !insideProject(adrCanonical?.canonicalFinalPath) || !insideProject(adrCanonical?.canonicalProposedPath)) {
    throw new Error(`ADR canonical 경로가 프로젝트 루트 밖을 가리킴 — decisionDir=${adrCanonical?.canonicalDecisionDir || '?'}, final=${adrCanonical?.canonicalFinalPath || '?'}, proposed=${adrCanonical?.canonicalProposedPath || '?'}`)
  }
}
const rawPlanning = (typeof A?.planningDir === 'string' && A.planningDir.trim()) ? A.planningDir.trim() : '.planning/planning'
const planningDir = rawPlanning.startsWith('/') ? rawPlanning : `${projectRoot}/${rawPlanning}`
log(`타깃 확정: ${projectRoot} (planning ${probe.planningPresent ? '있음' : '없음'}) · question: ${question} · adr: ${adrPath ?? '(스킵)'}`)

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

// ── P2 조사 (축별 격리 병렬 위임, researcher 에이전트) ──
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

// ── P2.5 기록 — run 디렉토리에 인스턴스 프롬프트·조사 산출물 정착 ──
// 증거·레인 재실행·프롬프트 개선의 기반(scaffold 규약과 동형). 기록 실패는
// 파이프라인을 멈추지 않는다 — 증거 계층이지 게이트가 아니다.
phase('Archive')
const archivePayload = research.filter(Boolean).map(r => {
  const axis = define.axes.find(a => a.key === r.key)
  const prompt = `결정 축 조사: ${r.title}\n\n조사 질문:\n${axis?.questions ?? '(원문 미보존)'}\n\n프로젝트 제약:\n${define.constraints}`
  return `===AXIS ${r.key}===\n---PROMPT---\n${prompt}\n---OUTPUT---\n${r.findings}`
}).join('\n\n')
const archived = await agent(
  `기록 작업만 수행하라(조사·코드 수정 아님). 대상 레포: ${projectRoot}\n` +
  `run 디렉토리를 만들어라: <ROOT>/.planning/ 이 실재하면 <ROOT>/.planning/runs/<오늘 YYYY-MM-DD>-tech-deciding/, 없으면 <ROOT>/runs/<오늘 YYYY-MM-DD>-tech-deciding/ (이하 <RUN>).\n` +
  `대상이 git 레포면 파일을 만들기 **전에** run 상위 상대경로(.planning/runs/ 또는 runs/)를 \`git -C <ROOT> rev-parse --git-path info/exclude\`가 가리키는 exclude 파일에 멱등 추가하고, \`git -C <ROOT> check-ignore -q <RUN>\`으로 추적 제외를 확인하라. .gitignore 제품 규칙은 수정하지 마라.\n` +
  `아래 페이로드를 마커(===AXIS <key>=== / ---PROMPT--- / ---OUTPUT---)로 분해해 Write 하라:\n` +
  `1) <RUN>/BRIEF.md — 결정 질문("${question}")과 축 목록·제약 요약\n` +
  `2) 축마다 <RUN>/prompts/<key>.md — PROMPT 원문 그대로\n` +
  `3) 축마다 <RUN>/outputs/<key>.md — OUTPUT 원문 그대로(요약·수정 금지)\n` +
  `이 파일들 외 어떤 파일도 만들지·수정하지 마라.\n\n페이로드:\n${archivePayload}`,
  {
    phase: 'Archive', label: 'run 기록', model: 'haiku',
    schema: {
      type: 'object',
      properties: {
        runDir:  { type: 'string', description: '생성한 run 디렉토리 절대경로' },
        written: { type: 'number', description: 'Write 한 파일 수' },
        gitExcluded: { type: 'boolean', description: 'git 레포면 run 경로 check-ignore 성공, git 아님이면 true' },
      },
      required: ['runDir', 'written', 'gitExcluded'],
    },
  }
).catch(() => null)
if (archived?.runDir && archived.gitExcluded) log(`run 기록: ${archived.runDir} (${archived.written}개 파일, git 추적 제외 확인)`)
else if (archived?.runDir) log(`경고: run 기록은 생겼으나 git 추적 제외 미확인 — 자율 커밋 전에 반드시 정리`)
else log('경고: run 기록 실패 — 증거 미정착(파이프라인은 계속)')

// ── P3 종합 ───────────────────────────────────────────
phase('Synthesize')
const synthesis = await agent(
  `다음은 "${question}" 결정을 위한 축별 웹조사 결과다. 이를 종합해 단일 스택/결정을 선정하라.\n` +
  `요구: (1) 기능→난제→선정 매핑표, (2) 각 축 추천+근거, (3) 탈락안과 이유, (4) 비용, (5) 뒤집을 조건.\n` +
  `출처 보존 의무: 추천·주장·탈락 사유의 근거가 되는 조사 결과의 **출처 URL 을 본문에 그대로 보존**하라 — 요약하면서 URL 을 유실하지 마라. 하류(ADR)가 이 문서에서 출처를 승계한다(2026-07-22 eval: 종합이 URL 을 떨궈 ADR 출처가 1개로 붕괴한 실결함).\n\n` +
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

// ── P5 ADR 제안 기록 (사용자 승인 전 정본 금지) ──
// load-bearing 결정을 같은 파이프라인이 조사→선정→비평→확정까지 자기완결하면 승인 게이트가
// 문서에만 남는다. 워크플로우는 .proposed 만 쓰고 pending-human 으로 멈춘다. 최종 ADR 승격은
// 메인이 선정안·critique·제안 파일을 사용자에게 보여 승인받은 뒤 별도로 수행한다.
let proposalEvidence = null
if (proposedAdrPath) {
  phase('ADR Draft')
  const adrDir = adrPath.slice(0, adrPath.lastIndexOf('/'))
  const baseline = await agent(
    `ADR 제안 작성 전 파일 기준선 — Read 전용, 파일 생성·수정·삭제 금지. 프로젝트 루트 ${projectRoot}.\n` +
    `final=${adrPath}, proposed=${proposedAdrPath}, decisionDir=${adrDir}. canonicalDecisionDir/canonicalFinalPath/canonicalProposedPath는 os.path.realpath로 symlink를 해소한 절대경로다. ` +
    `finalExists/proposedExists는 파일 실재 여부, 각 digest는 실재 파일의 SHA-256(없으면 빈 문자열). ` +
    `otherDecisionDigest는 decisionDir 아래 모든 일반 파일 중 proposed만 제외하고, 정렬된 \"상대경로<TAB>SHA-256\" 전체의 SHA-256이다(디렉토리 없거나 파일 0개면 빈 입력 SHA-256). 사실만 반환하라.`,
    { phase: 'ADR Draft', label: 'ADR 경로 기준선', model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: {
          finalExists: { type: 'boolean' }, finalDigest: { type: 'string' },
          proposedExists: { type: 'boolean' }, proposedDigest: { type: 'string' }, otherDecisionDigest: { type: 'string' },
          canonicalDecisionDir: { type: 'string' }, canonicalFinalPath: { type: 'string' }, canonicalProposedPath: { type: 'string' },
        },
        required: ['finalExists', 'finalDigest', 'proposedExists', 'proposedDigest', 'otherDecisionDigest', 'canonicalDecisionDir', 'canonicalFinalPath', 'canonicalProposedPath'] } }
  )
  const baselineCanonicalMatched = baseline?.canonicalDecisionDir === adrCanonical?.canonicalDecisionDir &&
    baseline?.canonicalFinalPath === adrCanonical?.canonicalFinalPath && baseline?.canonicalProposedPath === adrCanonical?.canonicalProposedPath
  if (!baselineCanonicalMatched) throw new Error('ADR 기준선 canonical 경로가 사전검사와 달라짐 — 제안 작성 전 중단')
  await agent(
    `다음 결정을 ADR **제안** 형식으로 정확히 이 절대경로에 Write 하라: ${proposedAdrPath}\n` +
    `(상대경로·현재 디렉토리 기준 Write 금지 — 위 절대경로 외 다른 위치에 파일을 만들지 마라. 이미 있으면 덮어쓰기 전 Read.)\n` +
    `상태는 반드시 "제안 — 사용자 승인 전"으로 기록하고, 정확한 실행 결속 표식 \`proposal_run_id: ${proposalRunId}\`를 기록하라. 확정·채택·approved 표현은 금지한다. 형식 섹션: 상태/날짜/방법 · 컨텍스트(기능→난제) · 제안 결정 · 근거(+출처) · 대안(왜 탈락) · 뒤집을 조건.\n` +
    `근거의 출처는 아래 선정안·적대 검증에 있는 **URL 을 그대로 보존**해 기록하라(요약하면서 URL 유실 금지 — ADR 은 다음 단계의 SSOT 라 출처가 끊기면 검증 불가). 출처가 정말 없는 주장만 '출처 없음'으로 표기.\n` +
    (archived?.runDir
      ? `선정안·적대 검증에 남은 URL 이 3개 미만이면 조사 원문에서 회수하라: ${archived.runDir}/outputs/ 의 파일들을 Read 해 결정 근거에 해당하는 출처 URL 을 ADR 근거·출처 섹션에 기록한다(상류 유실 백스톱).\n\n`
      : `\n`) +
    `결정 질문: ${question}\n\n선정안:\n${synthesis}\n\n적대적 검증(반영할 것):\n${critique}`,
    { phase: 'ADR Draft', model: 'haiku' }
  )
  const proof = await agent(
    `ADR 제안 작성 사후 독립 증거 — Read 전용, 파일 생성·수정·삭제 금지. 프로젝트 루트 ${projectRoot}.\n` +
    `final=${adrPath}, proposed=${proposedAdrPath}, decisionDir=${adrDir}. canonicalDecisionDir/canonicalFinalPath/canonicalProposedPath는 os.path.realpath로 symlink를 해소한 절대경로다. ` +
    `finalExists/proposedExists와 각 SHA-256, proposed 본문의 \"상태:\" 값 원문을 proposalStatus로, 줄 전체가 proposal_run_id: 로 시작하는 모든 값 원문을 proposalRunIds 배열로 반환하라. ` +
    `otherDecisionDigest는 decisionDir 아래 모든 일반 파일 중 proposed만 제외한 정렬된 \"상대경로<TAB>SHA-256\" 전체의 SHA-256(0개면 빈 입력 SHA-256). 사실만 반환하라.`,
    { phase: 'ADR Draft', label: 'ADR 제안 증거', model: 'haiku',
      schema: { type: 'object', additionalProperties: false,
        properties: {
          finalExists: { type: 'boolean' }, finalDigest: { type: 'string' },
          proposedExists: { type: 'boolean' }, proposedDigest: { type: 'string' }, otherDecisionDigest: { type: 'string' },
          canonicalDecisionDir: { type: 'string' }, canonicalFinalPath: { type: 'string' }, canonicalProposedPath: { type: 'string' },
          proposalStatus: { type: 'string' }, proposalRunIds: { type: 'array', items: { type: 'string' } },
        },
        required: ['finalExists', 'finalDigest', 'proposedExists', 'proposedDigest', 'otherDecisionDigest', 'canonicalDecisionDir', 'canonicalFinalPath', 'canonicalProposedPath', 'proposalStatus', 'proposalRunIds'] } }
  )
  const validDigest = value => /^[0-9a-f]{64}$/.test((value ?? '').trim())
  const finalUnchanged = proof?.finalExists === baseline?.finalExists &&
    (proof?.finalExists ? validDigest(proof?.finalDigest) && proof.finalDigest === baseline?.finalDigest : (proof?.finalDigest ?? '') === (baseline?.finalDigest ?? ''))
  // 같은 runId 재실행은 멱등이지만, 다른 실행의 stale .proposed 는 현재 run 표식이 없어 통과하지 못한다.
  const proposedWritten = proof?.proposedExists === true && validDigest(proof?.proposedDigest)
  const otherDecisionsUnchanged = validDigest(baseline?.otherDecisionDigest) && proof?.otherDecisionDigest === baseline.otherDecisionDigest
  const canonicalUnchanged = proof?.canonicalDecisionDir === baseline?.canonicalDecisionDir && proof?.canonicalFinalPath === baseline?.canonicalFinalPath && proof?.canonicalProposedPath === baseline?.canonicalProposedPath
  const runIds = Array.isArray(proof?.proposalRunIds) ? proof.proposalRunIds.map(String) : []
  const verified = finalUnchanged && proposedWritten && otherDecisionsUnchanged && canonicalUnchanged &&
    proof?.proposalStatus === '제안 — 사용자 승인 전' && runIds.length === 1 && runIds[0] === proposalRunId
  proposalEvidence = { verified, proposalRunId, baseline, proof }
  if (verified) log(`ADR 제안 증거 확인: ${proposedAdrPath} — 사용자 승인 전 정본 아님`)
  else log(`ADR 제안 증거 실패: 제안 파일·상태·정본 불변 중 하나 이상 미확인 — pending-human 으로 넘기지 않음`)
}

const proposalVerified = !proposedAdrPath || proposalEvidence?.verified === true
return {
  question, projectRoot, axes: define.axes.map(a => a.key), synthesis, critique, proposalRunId,
  adrPath, proposedAdrPath, runDir: archived?.runDir ?? null, runGitExcluded: archived?.gitExcluded ?? false,
  proposalEvidence,
  terminalState: proposalVerified ? 'pending-human' : 'proposal-failed',
  approval: {
    required: proposalVerified,
    reason: proposalVerified
      ? 'load-bearing 기술 결정 — 사용자 승인 전 최종 ADR 확정 금지'
      : 'ADR 제안 파일의 독립 증거가 실패해 사용자 승인 대상으로 승격할 수 없음',
    nextAction: !proposalVerified
      ? '제안 파일·정본 불변 증거를 확인하고 ADR Draft 단계를 재실행'
      : proposedAdrPath
      ? `선정안·critique·${proposedAdrPath} 를 사용자에게 제시하고 승인 후 ${adrPath} 로 승격`
      : '선정안·critique 를 사용자에게 제시하고 승인 후 최종 ADR 경로에 기록',
  },
}
