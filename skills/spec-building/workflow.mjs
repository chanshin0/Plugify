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
// 하니스가 args 를 JSON "문자열"로 전달한다(2026-06-11 canary 실증: args 수신 로그가 "{\"projectRoot\"...}" 문자열) → 객체로 정규화.
const A = (typeof args === 'string') ? (() => { try { return JSON.parse(args) } catch { return null } })() : (args ?? null)
const task        = A?.task ?? '.planning/STATE.md 의 "## 다음 task" 의 ### 목표 를, 같은 task 의 ### 게이트 항목이 전부 통과하도록 구현하라.'
const acceptance  = A?.acceptance ?? '수용 기준 = .planning/STATE.md 해당 task 의 "### 게이트" 항목 전부 — auto: 는 명시된 명령/테스트/라이브 프로브로 실증, human: 은 사람이 닫는다. 이것을 SSOT 로 따르라.'
const isolation   = A?.isolation === 'worktree' ? { isolation: 'worktree' } : {}
const doCommit    = A?.commit !== false
const MAX         = A?.maxAttempts ?? 3

// ── 타깃 해석 — 조용한 기본값 금지 ─────────────────────
// 2026-06-11 canary 사고: 이 하니스에서 args 가 전달되지 않는데 `?? '.'` 폴백이
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
const cdNote      = `작업 디렉토리는 ${projectRoot} 다. Bash 사용 시 항상 먼저 cd ${projectRoot}. 이 디렉토리 밖의 레포를 건드리지 마라.`

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
      },
      required: ['gatePresent', 'autoCount', 'humanCount', 'irreversiblePresent', 'liveItems'],
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
  log(`⚠ human-only 게이트(auto=0, human=${gate.humanCount}) — 자동 검증 불가, 사람이 닫는 task 로 진행. 가능하면 auto 신호 1개 이상 추가 권장.`)
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
if (hasLive) log(`라이브 게이트 ${liveItems.length}개 캡처 — 커밋 후 push→프리뷰 프로브로 닫는다 (Phase C)`)

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

// ── 구현 ↔ 리뷰 ↔ (커밋 → 라이브 게이트) 루프 ──────────
// Phase C: 라이브 게이트 task 는 커밋 후 push→프리뷰 프로브까지 이 루프 안에서 닫는다
// (사람 재트리거 없는 자율 반복 — 상한 MAX 공유). 라이브 게이트 없으면 기존 모양 그대로.
let impl, review, feedback = '', attempt = 0
let committed = false, commitInfo = null, escalation = null, liveGate = null
while (true) {
  attempt++
  // implementer: 규칙·SSOT·자기검증은 에이전트 정의(agents/implementer.md)에 있다 → 프롬프트엔 입력만.
  impl = await agent(
    `구현 task: ${task}\n${cdNote}\n` +
    (acceptance ? `\n수용 기준(전부 만족해야 함):\n${acceptance}\n` : '') +
    (hasLive ? `\n참고: 게이트의 {PREVIEW_URL} 항목(라이브 게이트)은 네 범위 밖이다 — 커밋 후 워크플로우가 push→프리뷰에서 닫는다. 로컬 판정 가능한 게이트만 자기검증하라.\n` : '') +
    (feedback ? `\n⚠ 이전 시도가 막혔다. 아래 블로커를 반드시 해결하라:\n${feedback}\n` : '') +
    `\n(역할·읽을 SSOT·자기검증 규칙은 너의 에이전트 정의에 있다 — 따르라.) 반환: 변경 파일 목록 · 핵심 결정(추정 표시) · 자기검증 결과.`,
    { agentType: 'implementer', phase: 'Implement', label: attempt > 1 ? `구현(재시도 ${attempt}/${MAX})` : '구현', ...isolation }
  )

  // reviewer: 검증·Codex 교차검증·판정 규칙은 에이전트 정의(agents/reviewer.md)에 있다 → 프롬프트엔 입력만.
  review = await agent(
    `task: ${task}\n${cdNote}\n` +
    (acceptance ? `수용 기준(이 기준으로 pass 판정):\n${acceptance}\n` : '') +
    `${codexDirective}\n` +
    (hasLive ? `라이브 게이트({PREVIEW_URL} 항목)는 리뷰 범위 밖 — 커밋 후 워크플로우 Live 단계가 프리뷰에서 닫는다. 로컬 판정 가능한 게이트만 재실행해 판정하고, 라이브 항목 미실행을 블로커로 삼지 마라.\n` : '') +
    `구현 보고:\n${impl}\n\n(검증·교차검증·판정 규칙은 너의 에이전트 정의에 있다 — 위 Codex 지시와 함께 따르라.)`,
    { agentType: 'reviewer', schema: REVIEW_SCHEMA, phase: 'Review', label: attempt > 1 ? `리뷰 ${attempt}` : '리뷰' }
  )

  if (!review.pass) {
    if (attempt >= MAX) { log(`✗ ${MAX}회 미통과 — 메인 에스컬레이션 필요`); break }
    feedback = review.issues.join('\n')
    log(`리뷰 블로커 ${review.issues.length}개 → 재시도 ${attempt + 1}/${MAX}: ${review.issues.join(' / ')}`)
    continue
  }
  log(`✓ 리뷰 통과 (시도 ${attempt}/${MAX})`)
  if (!doCommit) break // 커밋 미요청 — 리뷰 통과로 종료(기존 동작)

  // ── 커밋 — 실재는 에이전트 자기보고가 아니라 git 상태로 판정(2026-06-11: haiku 가
  // 커밋 없이 완료 응답 → committed:true 오보고로 메인이 픽스 미포함 push 할 뻔한 사고).
  const commitResult = await agent(
    `리뷰를 통과한 변경을 atomic commit 하라. ${cdNote}\n` +
    `task: ${task}\n` +
    `**중요(2026-06-23 사고 방지): 너는 커밋만 한다 — 새 파일을 만들거나 구현 코드를 수정하지 마라.** implementer/reviewer 가 남긴 작업트리(=리뷰 통과 상태)를 *그대로* 스테이징·커밋만 하라. 코드를 다시 짜거나 새 스크립트/파일을 발명하면 미검증 코드 출하다(실제 사고: commit 에이전트가 reviewer 미검증 파일을 발명·커밋하고 검증본을 작업트리에 방치).\n` +
    (hasLive
      ? `**이 task 는 라이브 게이트가 남아 있다 — 아직 미검증이다(커밋 후 워크플로우가 프리뷰에서 검증).** 따라서: ⓐ .planning/STATE.md 를 **일절 수정하지 마라** — 특히 "## 다음 task" 의 목표/게이트/비가역 표면 정의는 라이브 검증의 계약이다(지우면 검증이 무력화된다 — 실사고). 종결 기록은 라이브 통과 후 워크플로우가 별도로 한다. ⓑ 커밋 메시지에 '완료'·'검증됨' 주장 금지 — 변경 내용만 서술. ⓒ **커밋은 정확히 1개** — 여러 커밋으로 쪼개지 마라.\n` +
        `1) git add -A 로 작업트리의 리뷰-통과 변경을 스테이징(무관 파일만 제외, **새 파일 생성 금지·STATE.md 수정 금지**). 2) 한국어 커밋 메시지로 commit 1개(--no-verify·--force 금지). 메시지 끝: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>\n`
      : `1) git add -A 로 작업트리의 리뷰-통과 변경을 스테이징(무관 파일만 제외, **새 파일 생성 금지**). 2) .planning/STATE.md 갱신(이 task 완료로, 다음 task 명시). **라이브 검증을 실제로 했으면 정확히 반영 — '미수행'으로 추측 기입 금지.** 3) 한국어 커밋 메시지로 **commit 정확히 1개**(코드+STATE 를 한 커밋에 — 2분할 금지, --no-verify·--force 금지). 메시지 끝: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>\n`) +
    `4) 커밋 후 **반드시 실행한 명령의 출력 원문 그대로** 반환하라: (a) headLog = git log -1 --format='%H %s', (b) statusPorcelain = git status --porcelain(빈 출력이면 빈 문자열), (c) committedFiles = git show HEAD --stat --format='' 의 출력(이번 커밋이 담은 파일 목록). 출력을 지어내지 마라 — 커밋에 실패했으면 실패했다고 적고 status 원문을 그대로 줘라.`,
    {
      phase: 'Commit', label: attempt > 1 ? `커밋 ${attempt}` : '커밋', model: 'haiku',
      schema: {
        type: 'object',
        properties: {
          headLog: { type: 'string', description: "git log -1 --format='%H %s' 출력 원문" },
          statusPorcelain: { type: 'string', description: 'git status --porcelain 출력 원문(클린이면 빈 문자열)' },
          committedFiles: { type: 'string', description: "git show HEAD --stat --format='' 출력 원문(이번 커밋이 담은 파일 목록)" },
        },
        required: ['headLog', 'statusPorcelain', 'committedFiles'],
      },
    }
  )
  // 판정: 트래킹 변경이 안 남아 있어야 커밋 성공으로 본다(?? untracked 잔여는 허용).
  const dirty = (commitResult?.statusPorcelain ?? 'UNKNOWN')
    .split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('??'))
  committed = dirty.length === 0 && /^[0-9a-f]{7,40} /.test(commitResult?.headLog ?? '')
  const cFiles = (commitResult?.committedFiles ?? '').trim()
  commitInfo = { headLog: commitResult?.headLog ?? '', committedFiles: cFiles, statusPorcelain: commitResult?.statusPorcelain ?? '' }
  if (committed) log(`커밋 완료: ${commitResult.headLog}\n  담은 파일:\n${cFiles}`)
  else {
    log(`⚠ 커밋 미확인(committed=false) — status 잔여: ${dirty.join(' | ') || '(headLog 불일치)'}. **메인 주의**: committed=false 라도 HEAD 가 이동했을 수 있다(부당/부분 커밋 공존, 2026-06-23 사고). 그냥 작업트리를 덧커밋하지 말고, git log 로 HEAD 이동 여부 + 커밋 파일집합이 리뷰-검증 변경과 일치하는지 먼저 확인하라 — 불일치 시 amend/되돌림으로 수습.`)
    break // 메인 수습 경로(기존 동작) — 라이브 단계 진입 금지(미확인 커밋 push 방지)
  }
  if (!hasLive) break // 라이브 게이트 없는 task — 여기서 완료(기존 모양)

  // ── Phase C: 작업 브랜치 push → 프리뷰 → 라이브 프로브 ──
  // 신뢰 경계: main push(=prod 반영)는 사람 — isMain 이면 push 없이 반환되고 코드가 라이브를 skip 한다.
  const pp = await agent(
    `작업 브랜치 push + 프리뷰 URL 획득 — 아래 절차만 수행하고 사실을 반환하라(코드 수정·커밋·amend 금지). ${cdNote}\n` +
    `1) 현재 브랜치 확인: git branch --show-current. **main 또는 master 면 아무것도 push 하지 말고** isMain=true 로 즉시 반환하라(prod 반영은 사람 — 신뢰 경계).\n` +
    `2) git push -u origin <현재 브랜치> (--force 금지). 실패하면 pushed=false + reason 에 에러 원문.\n` +
    `3) bash .planning/preview.sh <현재 브랜치> 를 실행하고 끝까지 기다려라(내부에서 배포 폴링 — 수 분 걸릴 수 있으니 Bash timeout 을 600000ms 로). rc=0 이면 stdout **마지막 줄**이 프리뷰 URL → previewUrl 에. 파일이 없으면 reason="지점에 .planning/preview.sh 규격 없음", rc≠0 이면 stderr 사유를 reason 에.\n` +
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
    liveGate = { status: 'skipped-main-branch', note: 'main 브랜치 — 에이전트 push 금지(prod 반영=사람). push 후 live-verify 로 닫아라.' }
    log(`⚠ 라이브 게이트 skip: ${liveGate.note}`)
    break
  }
  if (!pp?.pushed || !pp?.previewUrl) {
    liveGate = { status: 'preview-failed', branch: pp?.branch ?? '', reason: pp?.reason || 'push/프리뷰 실패(원인 미상)' }
    log(`✗ 프리뷰 획득 실패: ${liveGate.reason}`)
    break
  }
  const probe = await agent(
    `라이브 게이트 프로브 — 아래 절차만 수행하고 사실을 반환하라(코드 수정·커밋·push 금지). ${cdNote}\n` +
    `프리뷰 URL: ${pp.previewUrl}\n` +
    `검증할 라이브 게이트 항목 ${liveItems.length}개 — **아래 목록이 정본이다(STATE 재독 금지, 항목을 빼거나 더하지 마라)**:\n` +
    liveItems.map((it, i) => `  ${i + 1}. ${it}`).join('\n') + '\n' +
    `1) 레포 루트에 .env.local 이 있으면 셸에서 \`set -a; . ./.env.local; set +a\` 로 로드하라(시크릿 값은 출력·반환에 절대 노출 금지).\n` +
    `2) 각 항목의 {PREVIEW_URL} 을 위 프리뷰 URL 로 치환해 명령을 실행하고, 항목에 적힌 통과 신호와 실제 출력을 대조하라.\n` +
    `3) results 에 항목마다 {item, pass, output} 을 담아라 — **${liveItems.length}개 전부**, output 은 실행 출력 원문(시크릿 마스킹).\n` +
    `4) **통과 신호를 지어내지 마라** — 하나라도 불일치면 pass=false, failures 에 항목+실제 출력.`,
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
  const probedAll = Array.isArray(probe?.results) && probe.results.length === liveItems.length && probe.results.every(r => r?.pass === true)
  if (probe?.pass && probedAll) {
    liveGate = { status: 'passed', branch: pp.branch, previewUrl: pp.previewUrl, results: probe.results, evidence: probe.evidence }
    log(`✓ 라이브 게이트 ${liveItems.length}/${liveItems.length} 통과 — ${pp.previewUrl} (prod 반영 = 사람이 main merge)`)
  } else if (probe?.pass && !probedAll) {
    liveGate = { status: 'failed', branch: pp.branch, previewUrl: pp.previewUrl, failures: [`프로브 무결성 실패 — pass 주장했으나 항목별 결과 불일치(기대 ${liveItems.length}개, 수신 ${probe?.results?.length ?? 0}개 / 전항목 pass 아님). 공허 통과 방지 가드.`] }
  } else {
    liveGate = { status: 'failed', branch: pp.branch, previewUrl: pp.previewUrl, failures: probe?.failures?.length ? probe.failures : ['프로브 결과 없음'] }
  }
  if (liveGate.status === 'passed') break
  if (attempt >= MAX) { log(`✗ 라이브 게이트 ${MAX}회 미통과 — 메인 에스컬레이션 필요`); break }
  feedback = `라이브 게이트 실패 — 코드가 프리뷰(${pp.previewUrl})에서 실제로 이렇게 동작했다. 반드시 해결하라:\n${liveGate.failures.join('\n')}`
  log(`라이브 블로커 ${liveGate.failures.length}개 → 재시도 ${attempt + 1}/${MAX}`)
}

// ── 라이브 통과 시 종결 커밋 — STATE 는 라이브 실증 *후에만* 완료로 적는다 ──
// (첫 case-03 시험 실결함의 형제 방지책: 검증 전 완료 기록 = 거짓 기록)
if (liveGate?.status === 'passed' && doCommit) {
  const closure = await agent(
    `라이브 게이트 통과 종결 커밋 — 아래 절차만 수행하라(코드·다른 파일 수정 금지). ${cdNote}\n` +
    `task: ${task}\n` +
    `라이브 실증: 프리뷰 ${liveGate.previewUrl} 에서 라이브 게이트 ${liveItems.length}개 전부 통과(브랜치 ${liveGate.branch}).\n` +
    `1) .planning/STATE.md 의 "## 다음 task" 해당 task 를 완료로 갱신 — 라이브 게이트가 프리뷰에서 실증됐음을 한 줄로 기록(위 프리뷰 URL 포함), "prod 반영은 사람 merge 대기" 명시. **다른 파일은 일절 변경 금지.**\n` +
    `2) STATE.md 만 스테이징해 한국어 커밋 **정확히 1개**(--no-verify·--force 금지, 메시지 끝: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>) 후 git push origin ${liveGate.branch}.\n` +
    `3) 반환: headLog(git log -1 --format='%H %s' 원문)·statusPorcelain(git status --porcelain 원문). 지어내지 마라.`,
    {
      phase: 'Live', label: '종결 커밋', model: 'haiku',
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          headLog:         { type: 'string', description: "git log -1 --format='%H %s' 출력 원문" },
          statusPorcelain: { type: 'string', description: 'git status --porcelain 출력 원문' },
        },
        required: ['headLog', 'statusPorcelain'],
      },
    }
  )
  liveGate.closure = { headLog: closure?.headLog ?? '', statusPorcelain: closure?.statusPorcelain ?? '' }
  log(`종결 커밋: ${liveGate.closure.headLog || '(미확인 — 메인이 git 으로 확인할 것)'}`)
}

// ── 에스컬레이션 판정 (무한 자동 루프 방지 — 상한 도달 시 멈추고 신호만 올린다) ──
if (!review?.pass) {
  escalation = {
    reason: `${MAX}회 시도 후에도 reviewer 미통과(커밋 보류)`,
    blockers: review?.issues ?? [],
    nextOptions: [
      '수용 기준이 과하거나 모순인가 → STATE 의 수용 기준 조정 후 재투입',
      'task 가 너무 큰가 → 더 작은 단위로 분해 후 각각 재투입',
      'implementer 모델이 약한가 → maxAttempts 와 함께 implementer 를 opus 로 격상해 1~2회 추가',
      '구조적으로 막혔나(외부 의존·환경) → 사용자에게 에스컬레이션',
    ],
  }
  log(`⚠ 에스컬레이션: ${escalation.reason}. 메인이 위 nextOptions 중 택해 재투입할 것.`)
} else if (liveGate && (liveGate.status === 'failed' || liveGate.status === 'preview-failed')) {
  escalation = {
    reason: liveGate.status === 'failed'
      ? `라이브 게이트 미통과(${MAX}회 상한) — 커밋은 작업 브랜치에 실재, prod 미반영이라 안전`
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

return { task, attempts: attempt, impl, review, committed, commit: commitInfo, liveGate, escalation }
