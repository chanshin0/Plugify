#!/usr/bin/env node

import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const sha = c => c.repeat(40)
const digest = c => c.repeat(64)

function loadWorkflow(relativePath, marker, parameters) {
  const source = fs.readFileSync(path.join(root, relativePath), 'utf8')
  const start = source.indexOf(marker)
  assert.notEqual(start, -1, `${relativePath}: workflow body marker missing`)
  return new AsyncFunction(...parameters, source.slice(start))
}

const runSingleBody = loadWorkflow('skills/spec-building/workflow.mjs', '// ── 입력', ['args', 'agent', 'log'])
const runGraphBodyRaw = loadWorkflow('skills/spec-building/graph-workflow.mjs', '// ═', ['args', 'agent', 'parallel', 'log'])
// Existing fixtures intentionally exercise the old graph through the explicit migration-only switch.
// Production/default calls use runGraphBodyRaw and fail closed when contractVersion is absent.
const runGraphBody = (args, ...rest) => runGraphBodyRaw({ allowLegacyGraph: true, ...args }, ...rest)

function scriptedAgent(handlers) {
  const calls = []
  const agent = async (prompt, options = {}) => {
    const label = options.label ?? ''
    calls.push({ label, prompt, options })
    assertEvidenceAcquisitionPrompt(label, prompt)
    const handler = handlers.find(h => typeof h.match === 'string' ? h.match === label : h.match.test(label))
    assert.ok(handler, `unexpected agent call: ${label}`)
    handler.count = (handler.count ?? 0) + 1
    const rawResult = typeof handler.value === 'function' ? handler.value({ prompt, options, count: handler.count }) : handler.value
    return structuredClone(rawResult)
  }
  return { agent, calls }
}

function assertEvidenceAcquisitionPrompt(label, prompt) {
  const requireAll = commands => {
    for (const command of commands) assert.ok(prompt.includes(command), `${label}: evidence prompt missing ${command}`)
  }
  if (/^(검토 전 changeset|리뷰 changeset|종결 검토 전 changeset|종결 changeset|(?:pre|post)-review:|int-pre-review:|int-changeset:)/.test(label)) {
    requireAll(['git branch --show-current', 'git rev-parse HEAD', 'git diff --name-only', 'git ls-files --others', 'reviewedDigest', 'git status --porcelain'])
  } else if (label === '커밋 증거' || label === '종결 증거' || /^commit-proof:|^int-commit-proof:/.test(label)) {
    requireAll(['git branch --show-current', 'git rev-list --count', 'git diff --name-only', 'committedDigest', 'git status --porcelain'])
  } else if (label.startsWith('merge-proof:')) {
    requireAll(['git branch --show-current', 'git rev-list --first-parent --reverse', "--format='%P'", '--remerge-diff', 'git status --porcelain'])
  } else if (/^(merge-snapshot:|integration-snapshot:|integration-proof:|regen-snapshot:|regen-proof:)/.test(label)) {
    requireAll(['git branch --show-current', 'git rev-parse HEAD', 'git status --porcelain'])
  } else if (label.startsWith('프리뷰 SHA 증거')) {
    requireAll(['git rev-parse HEAD', 'git ls-remote', 'DEPLOYED_SHA=<40hex>'])
  } else if (label === 'finalize-snapshot' || label === 'finalize-proof') {
    requireAll(['git branch --show-current', 'git rev-parse HEAD', 'git status --porcelain'])
  }
}

const target = { match: '타깃 해석', value: { resolvedRoot: '/tmp/spec-contract-fixture', statePresent: true } }
const cleanBaseline = { match: '작업트리 기준선', value: { branch: 'work/test', head: sha('a'), statusPorcelain: '' } }
const done = {
  status: 'DONE', filesChanged: ['src/a.js'], decisions: 'SECRET_DECISION_SENTINEL',
  selfCheck: 'SECRET_SELFCHECK_SENTINEL', concerns: [], missing: '',
}
const blindPass = {
  pass: true, issues: [], advisories: [], concernDispositions: [], summary: 'pass',
  evidenceResults: [{ id: 'E1', run: 'npm test -- a', exit: '0', output: 'pass', passed: true }],
}
const exitZeroExpectation = { exit: '0', outputIncludes: [], outputExcludes: [] }

function singleReviewPair(value) {
  return [
    { match: '검토 전 changeset', value },
    { match: '리뷰 changeset', value },
  ]
}

function graphReviewPair(id, value) {
  return [
    { match: new RegExp(`^pre-review:${id}\\(`), value },
    { match: new RegExp(`^post-review:${id}\\(`), value },
  ]
}

function integrationReviewPair(wave, value) {
  return [
    { match: `int-pre-review:w${wave}`, value },
    { match: `int-changeset:w${wave}`, value },
  ]
}

function mockMergeProof({ beforeHead, taskHead, mergeHead = sha('e'), revCount = '2', firstParentCount = '1', ancExit = '0', statusPorcelain = '', remergeDiff = '' }) {
  return {
    branch: 'work/test', afterHead: mergeHead, revCount, firstParentCount, statusPorcelain,
    checks: [{ id: 'T1', ancExit }],
    mergeCommits: revCount === '2' && firstParentCount === '1'
      ? [{ id: 'T1', mergeHead, parents: `${beforeHead} ${taskHead}`, remergeDiff }]
      : [],
  }
}

function git(cwd, ...gitArgs) {
  return execFileSync('git', gitArgs, { cwd, encoding: 'utf8' }).trimEnd()
}

function makeGitFixture(withRemote = false) {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'plugify-git-evidence-'))
  const repo = path.join(fixtureRoot, 'repo')
  fs.mkdirSync(path.join(repo, '.planning'), { recursive: true })
  fs.mkdirSync(path.join(repo, 'src'), { recursive: true })
  git(fixtureRoot, 'init', '-b', 'work/test', repo)
  git(repo, 'config', 'user.name', 'Plugify Contract Test')
  git(repo, 'config', 'user.email', 'contract@example.invalid')
  fs.writeFileSync(path.join(repo, '.planning', 'STATE.md'), '## 다음 task\n\n### 목표\ntest\n')
  fs.writeFileSync(path.join(repo, 'src', 'a.js'), 'export const a = 1\n')
  git(repo, 'add', '.planning/STATE.md', 'src/a.js')
  git(repo, 'commit', '-m', 'initial')
  let remote = null
  if (withRemote) {
    remote = path.join(fixtureRoot, 'remote.git')
    git(fixtureRoot, 'init', '--bare', remote)
    git(repo, 'remote', 'add', 'origin', remote)
    git(repo, 'push', '-u', 'origin', 'work/test')
  }
  return { fixtureRoot, repo, remote }
}

function actualSnapshot(repo) {
  const tracked = git(repo, 'diff', '--name-only', 'HEAD')
  const untracked = git(repo, 'ls-files', '--others', '--exclude-standard')
  const reviewedFiles = [tracked, untracked].filter(Boolean).join('\n').split('\n').filter(Boolean).sort().join('\n')
  return {
    branch: git(repo, 'branch', '--show-current'),
    beforeHead: git(repo, 'rev-parse', 'HEAD'),
    statusPorcelain: git(repo, 'status', '--porcelain'),
    reviewedFiles,
    reviewedDigest: contentDigest(repo, reviewedFiles),
  }
}

function contentDigest(repo, filesRaw) {
  const lines = filesRaw.split('\n').map(s => s.trim()).filter(Boolean).sort().map(file => {
    const absolute = path.join(repo, file)
    const blob = fs.existsSync(absolute) && fs.statSync(absolute).isFile() ? git(repo, 'hash-object', '--', file) : 'DELETE'
    return `${file}\t${blob}`
  })
  return createHash('sha256').update(lines.join('\n')).digest('hex')
}

function actualCommitProof(repo, beforeHead) {
  const committedFiles = git(repo, 'diff', '--name-only', `${beforeHead}..HEAD`)
  return {
    branch: git(repo, 'branch', '--show-current'),
    afterHead: git(repo, 'rev-parse', 'HEAD'),
    headLog: git(repo, 'log', '-1', '--format=%H %s'),
    revCount: git(repo, 'rev-list', '--count', `${beforeHead}..HEAD`),
    statusPorcelain: git(repo, 'status', '--porcelain'),
    committedFiles,
    committedDigest: contentDigest(repo, committedFiles),
  }
}

function actualGraphMergeProof(repo, beforeHead, taskHead) {
  const afterHead = git(repo, 'rev-parse', 'HEAD')
  const mergeHeads = git(repo, 'rev-list', '--first-parent', '--reverse', `${beforeHead}..HEAD`).split('\n').filter(Boolean)
  return {
    branch: git(repo, 'branch', '--show-current'),
    afterHead,
    revCount: git(repo, 'rev-list', '--count', `${beforeHead}..HEAD`),
    firstParentCount: git(repo, 'rev-list', '--first-parent', '--count', `${beforeHead}..HEAD`),
    statusPorcelain: git(repo, 'status', '--porcelain'),
    checks: [{ id: 'T1', ancExit: (() => { try { git(repo, 'merge-base', '--is-ancestor', taskHead, 'work/test'); return '0' } catch { return '1' } })() }],
    mergeCommits: mergeHeads.map(head => ({
      id: 'T1', mergeHead: head, parents: git(repo, 'show', '-s', '--format=%P', head),
      remergeDiff: git(repo, 'show', '--remerge-diff', '--format=', head),
    })),
  }
}

async function runActualGraphMerge(mode) {
  const { fixtureRoot, repo } = makeGitFixture()
  git(repo, 'checkout', '-b', 'graph-T1')
  fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const graphChange = true\n')
  git(repo, 'add', 'src/a.js')
  git(repo, 'commit', '-m', '그래프 작업')
  const taskHead = git(repo, 'rev-parse', 'HEAD')
  git(repo, 'checkout', 'work/test')
  const before = git(repo, 'rev-parse', 'HEAD')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'true' })
  const handlers = [
    { match: '타깃 해석', value: { resolvedRoot: repo, statePresent: true } },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: `${repo}/.planning/worktrees/T1`, head: before, output: 'fixture' }] } },
    { match: 'impl:T1', value: done },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'blind-review:T1', value: blindPass },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 그래프 작업`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 그래프 작업`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: () => ({ branch: git(repo, 'branch', '--show-current'), beforeHead: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: git(repo, 'status', '--porcelain') }) },
    { match: 'merge:w1', value: () => {
      if (mode === 'ours') git(repo, 'merge', '--no-ff', '-s', 'ours', '--no-edit', 'graph-T1')
      else {
        git(repo, 'merge', '--no-ff', '--no-edit', 'graph-T1')
        if (mode === 'amended') {
          git(repo, 'read-tree', '--reset', '-u', before)
          git(repo, 'commit', '--amend', '--no-edit')
        }
      }
      const head = git(repo, 'rev-parse', 'HEAD')
      return { merges: [{ id: 'T1', exit: '0', headLog: git(repo, 'log', '-1', '--format=%H %s'), conflict: false }], head }
    } },
    { match: 'merge-proof:w1', value: () => actualGraphMergeProof(repo, before, taskHead) },
    { match: 'integration-snapshot:w1#1', value: () => ({ branch: git(repo, 'branch', '--show-current'), beforeHead: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: git(repo, 'status', '--porcelain') }) },
    { match: 'integration:w1', value: { exit: '0', output: 'pass' } },
    { match: 'integration-proof:w1#1', value: () => ({ branch: git(repo, 'branch', '--show-current'), afterHead: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: git(repo, 'status', '--porcelain') }) },
    { match: 'finalize-snapshot', value: () => ({ branch: git(repo, 'branch', '--show-current'), beforeHead: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: git(repo, 'status', '--porcelain') }) },
    { match: 'ancestor 확인', value: { checks: [{ id: 'T1', ancExit: '0' }] } },
    { match: 'worktree 제거', value: { removed: ['T1'] } },
    { match: 'finalize-proof', value: () => ({ branch: git(repo, 'branch', '--show-current'), afterHead: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: git(repo, 'status', '--porcelain') }) },
  ]
  const scripted = scriptedAgent(handlers)
  try {
    const result = await runGraphBody({ projectRoot: repo, maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
    return { result, calls: scripted.calls }
  } finally { fs.rmSync(fixtureRoot, { recursive: true, force: true }) }
}

async function runSingle(handlers, args = {}) {
  const scripted = scriptedAgent(handlers)
  const result = await runSingleBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1, ...args }, scripted.agent, () => {})
  return { result, calls: scripted.calls }
}

async function testHumanOnlyStopsBeforeImplementation() {
  const { result, calls } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 0, humanCount: 1, irreversiblePresent: false, liveItems: [] } },
  ])
  assert.equal(result.terminalState, 'pending-human')
  assert.equal(result.attempts, 0)
  assert.equal(result.runSummary.autonomousPathClosed, false)
  assert.equal(result.runSummary.metrics.eligibleTransitions, 2)
  assert.equal(result.runSummary.metrics.workflowAutonomousTransitionRatio, 1)
  assert.equal(result.runSummary.metrics.autonomousCompletion, false)
  assert.deepEqual(calls.map(c => c.label), ['타깃 해석', '작업트리 기준선', '게이트 점검'])
}

async function testLiveGateNeedsExplicitPreviewPushAuthorization() {
  const liveItem = 'auto: curl {PREVIEW_URL}/health → 200'
  const { result, calls } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [liveItem], nextTaskRaw: '## 다음 task\npreview-push: unauthorized', previewPushAuthorized: true } },
  ])
  assert.equal(result.terminalState, 'pending-human')
  assert.equal(result.attempts, 0)
  assert.ok(result.pendingHuman.reason.includes('명시 승인'))
  assert.equal(calls.some(call => call.label === '구현'), false)
  assert.equal(calls.some(call => call.label === 'push+프리뷰'), false)
}

async function testDirtyWorktreeStopsBeforeImplementation() {
  const { result, calls } = await runSingle([
    { ...target },
    { match: '작업트리 기준선', value: { branch: 'work/test', head: sha('a'), statusPorcelain: ' M user-change.md' } },
  ])
  assert.equal(result.terminalState, 'pending-human')
  assert.equal(result.pendingHuman.statusPorcelain, ' M user-change.md')
  assert.deepEqual(calls.map(c => c.label), ['타깃 해석', '작업트리 기준선'])
}

async function testBlindReviewInputContract() {
  const { result, calls } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
    { match: '구현', value: done },
    ...singleReviewPair({ branch: 'work/test', beforeHead: sha('a'), statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') }),
    { match: '블라인드 리뷰', value: blindPass },
  ], { commit: false })
  const reviewCall = calls.find(c => c.label === '블라인드 리뷰')
  assert.ok(reviewCall)
  assert.equal(reviewCall.prompt.includes('SECRET_DECISION_SENTINEL'), false)
  assert.equal(reviewCall.prompt.includes('SECRET_SELFCHECK_SENTINEL'), false)
  assert.equal(reviewCall.prompt.includes('구현 보고(JSON)'), false)
  assert.equal(result.terminalState, 'reviewed-uncommitted')
  assert.equal(result.runSummary.reviewerBlind, true)
  assert.equal(result.runSummary.humanReintervention, 'not_observable')
  assert.equal(Object.hasOwn(result.runSummary, 'score'), false)
  assert.equal(JSON.stringify(result.runSummary).includes('SECRET_'), false)
}

async function testStaleHeadCannotCountAsCommit() {
  const oldHead = sha('a')
  const { result } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: oldHead, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: '.planning/STATE.md\nsrc/a.js', reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: oldHead, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: '.planning/STATE.md\nsrc/a.js', reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: oldHead, afterHead: oldHead, headLog: `${oldHead} 기존 커밋`, statusPorcelain: '', committedFiles: '.planning/STATE.md\nsrc/a.js' } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: oldHead, headLog: `${oldHead} 기존 커밋`, revCount: '0', statusPorcelain: '', committedFiles: '.planning/STATE.md\nsrc/a.js', committedDigest: digest('d') } },
  ])
  assert.equal(result.committed, false)
  assert.equal(result.terminalState, 'commit-failed')
  assert.equal(result.commit.beforeHead, result.commit.afterHead)
}

async function testMixedHumanGateNeverReturnsVerified() {
  const before = sha('a')
  const after = sha('b')
  const { result, calls } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 1, irreversiblePresent: false, liveItems: [] } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: after, headLog: `${after} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: after, headLog: `${after} 변경`, revCount: '1', statusPorcelain: '', committedFiles: 'src/a.js', committedDigest: digest('d') } },
  ])
  assert.equal(result.terminalState, 'pending-human')
  assert.equal(result.committed, true)
  const commitCall = calls.find(c => c.label === '커밋')
  assert.ok(commitCall.prompt.includes('.planning/STATE.md'))
  assert.ok(commitCall.prompt.includes('일절 수정하지 말고'))
  assert.equal(commitCall.prompt.includes('이 task 완료로'), false)
}

async function testTwoCommitsCannotSatisfyAtomicContract() {
  const before = sha('a')
  const after = sha('b')
  const { result } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: '.planning/STATE.md\nsrc/a.js', reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: '.planning/STATE.md\nsrc/a.js', reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: after, headLog: `${after} 변경`, statusPorcelain: '', committedFiles: '.planning/STATE.md\nsrc/a.js' } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: after, headLog: `${after} 변경`, revCount: '2', statusPorcelain: '', committedFiles: '.planning/STATE.md\nsrc/a.js', committedDigest: digest('d') } },
  ])
  assert.equal(result.committed, false)
  assert.equal(result.terminalState, 'commit-failed')
  assert.equal(result.commit.revCount, '2')
}

async function testCommitCannotAddUnreviewedFile() {
  const before = sha('a')
  const after = sha('b')
  const { result } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: '.planning/STATE.md\nsrc/a.js', reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: '.planning/STATE.md\nsrc/a.js', reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: after, headLog: `${after} 변경`, statusPorcelain: '', committedFiles: '.planning/STATE.md\nsrc/a.js\nsrc/evil.js' } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: after, headLog: `${after} 변경`, revCount: '1', statusPorcelain: '', committedFiles: '.planning/STATE.md\nsrc/a.js\nsrc/evil.js', committedDigest: digest('d') } },
  ])
  assert.equal(result.committed, false)
  assert.equal(result.commit.evidenceMatched, false)
}

async function testAutoOnlyCommitIncludesReviewedStateAndVerifies() {
  const before = sha('a')
  const after = sha('b')
  const files = '.planning/STATE.md\nsrc/a.js'
  const { result, calls } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
    { match: '구현', value: { ...done, filesChanged: ['src/a.js', '.planning/STATE.md'] } },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: files, reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: files, reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: after, headLog: `${after} 변경`, statusPorcelain: '', committedFiles: files } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: after, headLog: `${after} 변경`, revCount: '1', statusPorcelain: '', committedFiles: files, committedDigest: digest('d') } },
  ])
  assert.equal(result.terminalState, 'verified')
  assert.equal(result.committed, true)
  assert.ok(result.runSummary.metrics.agentSelfTurns > 0)
  assert.equal(result.runSummary.metrics.workflowAutonomousTransitionRatio, 1)
  assert.equal(result.runSummary.metrics.autonomousCompletion, true)
  assert.equal(result.runSummary.metrics.reviewCatchRate, 'not_observable')
  const implCall = calls.find(c => c.label === '구현')
  const commitCall = calls.find(c => c.label === '커밋')
  assert.ok(implCall.prompt.includes('STATE 변경도 코드와 함께 reviewer가 검증'))
  assert.ok(commitCall.prompt.includes('여기서 내용을 다시 수정하지 마라'))
}

async function testUntrackedResidueFailsCleanContract() {
  const before = sha('a')
  const after = sha('b')
  const files = '.planning/STATE.md\nsrc/a.js'
  const { result } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
    { match: '구현', value: { ...done, filesChanged: ['src/a.js', '.planning/STATE.md'] } },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: files, reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M .planning/STATE.md\n M src/a.js', reviewedFiles: files, reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: after, headLog: `${after} 변경`, statusPorcelain: '?? unreviewed.txt', committedFiles: files } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: after, headLog: `${after} 변경`, revCount: '1', statusPorcelain: '?? unreviewed.txt', committedFiles: files, committedDigest: digest('d') } },
  ])
  assert.equal(result.committed, false)
  assert.equal(result.terminalState, 'commit-failed')
}

async function testConcernDispositionIdentityMismatchEscalates() {
  const impl = { ...done, status: 'DONE_WITH_CONCERNS', concerns: ['data loss', 'missing auth'] }
  const { result } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
    { match: '구현', value: impl },
    ...singleReviewPair({ branch: 'work/test', beforeHead: sha('a'), statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') }),
    { match: '블라인드 리뷰', value: blindPass },
    { match: '우려 대조 1', value: { issues: [], advisories: [], summary: 'wrong identity', concernDispositions: [
      { concern: 'missing auth', disposition: 'accepted', note: 'a' },
      { concern: 'missing auth', disposition: 'accepted', note: 'b' },
    ] } },
  ], { commit: false })
  assert.equal(result.terminalState, 'escalated')
  assert.ok(result.escalation.reason.includes('reviewer 프로토콜 실패'))
}

async function testSingleReviewerBranchSwitchIsRejectedBeforeCommit() {
  const before = sha('a')
  const frozen = { beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') }
  const { result, calls } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', ...frozen } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'reviewer-switched', ...frozen } },
  ])
  assert.equal(result.terminalState, 'escalated')
  assert.ok(result.escalation.blockers.some(blocker => blocker.includes('branch work/test->reviewer-switched')))
  assert.equal(calls.some(call => call.label === '커밋'), false)
}

async function testLiveMixedHumanGateSkipsStateClosure() {
  const before = sha('a')
  const after = sha('b')
  const liveItem = 'auto: curl {PREVIEW_URL}/health → 200'
  const { result, calls } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 1, irreversiblePresent: false, liveItems: [liveItem], nextTaskRaw: '## 다음 task\npreview-push: authorized' } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: after, headLog: `${after} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: after, headLog: `${after} 변경`, revCount: '1', statusPorcelain: '', committedFiles: 'src/a.js', committedDigest: digest('d') } },
    { match: 'push+프리뷰', value: { branch: 'work/test', isMain: false, pushed: true, previewUrl: 'https://preview.invalid', reason: '' } },
    { match: '프리뷰 SHA 증거', value: { localHead: after, remoteHead: after, deployedHead: after, proofPreviewUrl: 'https://preview.invalid', evidence: 'explicit bound fixture' } },
    { match: '라이브 프로브', value: { pass: true, results: [{ item: liveItem, pass: true, output: '200' }], failures: [], evidence: '200' } },
  ])
  assert.equal(result.terminalState, 'pending-human')
  assert.equal(result.liveGate.closure.status, 'pending-human')
  assert.equal(calls.some(c => c.label === '종결 커밋'), false)
}

async function testClosureEvidenceMismatchIsFailure() {
  const before = sha('a')
  const implementationHead = sha('b')
  const closureHead = sha('c')
  const wrongRemote = sha('d')
  const liveItem = 'auto: curl {PREVIEW_URL}/health → 200'
  const { result } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [liveItem], nextTaskRaw: '## 다음 task\npreview-push: authorized' } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: implementationHead, headLog: `${implementationHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: implementationHead, headLog: `${implementationHead} 변경`, revCount: '1', statusPorcelain: '', committedFiles: 'src/a.js', committedDigest: digest('d') } },
    { match: 'push+프리뷰', value: { branch: 'work/test', isMain: false, pushed: true, previewUrl: 'https://preview.invalid', reason: '' } },
    { match: '프리뷰 SHA 증거', value: { localHead: implementationHead, remoteHead: implementationHead, deployedHead: implementationHead, proofPreviewUrl: 'https://preview.invalid', evidence: 'explicit bound fixture' } },
    { match: '라이브 프로브', value: { pass: true, results: [{ item: liveItem, pass: true, output: '200' }], failures: [], evidence: '200' } },
    { match: '종결 STATE 제안', value: { changed: true } },
    { match: '종결 검토 전 changeset', value: { branch: 'work/test', beforeHead: implementationHead, reviewedFiles: '.planning/STATE.md', reviewedDigest: digest('s'), statusPorcelain: ' M .planning/STATE.md' } },
    { match: '종결 STATE 리뷰', value: { pass: true, issues: [], stateOnlyChanged: true, targetTaskClosed: true, previewUrlRecorded: true, prodMergePendingRecorded: true, noOtherTaskRewritten: true } },
    { match: '종결 changeset', value: { branch: 'work/test', beforeHead: implementationHead, reviewedFiles: '.planning/STATE.md', reviewedDigest: digest('s'), statusPorcelain: ' M .planning/STATE.md' } },
    { match: '종결 커밋', value: { beforeHead: implementationHead, afterHead: closureHead, headLog: `${closureHead} 종결`, remoteHead: wrongRemote, statusPorcelain: '' } },
    { match: '종결 증거', value: { branch: 'work/test', afterHead: closureHead, headLog: `${closureHead} 종결`, remoteHead: wrongRemote, revCount: '1', committedFiles: '.planning/STATE.md', committedDigest: digest('s'), statusPorcelain: '' } },
  ])
  assert.equal(result.liveGate.status, 'closure-failed')
  assert.equal(result.liveGate.closure.verified, false)
  assert.ok(result.escalation)
  assert.equal(result.terminalState, 'closure-failed')
}

async function testClosureReviewerMutationIsRejectedBeforeCommit() {
  const before = sha('a')
  const implementationHead = sha('b')
  const liveItem = 'auto: curl {PREVIEW_URL}/health → 200'
  const { result, calls } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [liveItem], nextTaskRaw: '## 다음 task\npreview-push: authorized' } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: implementationHead, headLog: `${implementationHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: implementationHead, headLog: `${implementationHead} 변경`, revCount: '1', statusPorcelain: '', committedFiles: 'src/a.js', committedDigest: digest('d') } },
    { match: 'push+프리뷰', value: { branch: 'work/test', isMain: false, pushed: true, previewUrl: 'https://preview.invalid', reason: '' } },
    { match: '프리뷰 SHA 증거', value: { localHead: implementationHead, remoteHead: implementationHead, deployedHead: implementationHead, proofPreviewUrl: 'https://preview.invalid', evidence: 'explicit bound fixture' } },
    { match: '라이브 프로브', value: { pass: true, results: [{ item: liveItem, pass: true, output: '200' }], failures: [], evidence: '200' } },
    { match: '종결 STATE 제안', value: { changed: true } },
    { match: '종결 검토 전 changeset', value: { branch: 'work/test', beforeHead: implementationHead, reviewedFiles: '.planning/STATE.md', reviewedDigest: digest('s'), statusPorcelain: ' M .planning/STATE.md' } },
    { match: '종결 STATE 리뷰', value: { pass: true, issues: [], stateOnlyChanged: true, targetTaskClosed: true, previewUrlRecorded: true, prodMergePendingRecorded: true, noOtherTaskRewritten: true } },
    { match: '종결 changeset', value: { branch: 'work/test', beforeHead: implementationHead, reviewedFiles: '.planning/STATE.md', reviewedDigest: digest('x'), statusPorcelain: ' M .planning/STATE.md' } },
  ])
  assert.equal(result.liveGate.status, 'closure-failed')
  assert.ok(result.liveGate.reason.includes('reviewer'))
  assert.equal(calls.some(call => call.label === '종결 커밋'), false)
  assert.equal(result.terminalState, 'closure-failed')
}

async function testGraphReviewFailureCannotCommit() {
  const before = sha('a')
  const taskHead = sha('b')
  const graph = JSON.stringify({
    tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }],
    verify: 'npm test',
  })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: mockMergeProof({ beforeHead: before, taskHead }) },
    { match: 'integration-snapshot:w1#1', value: { branch: 'work/test', beforeHead: sha('e'), statusPorcelain: '' } },
    { match: 'integration:w1', value: { exit: '1', output: 'failing integration' } },
    { match: 'integration-proof:w1#1', value: { branch: 'work/test', afterHead: sha('e'), statusPorcelain: '' } },
    { match: 'int-fix:w1', value: done },
    { match: 'int-pre-review:w1', value: { branch: 'work/test', beforeHead: sha('e'), reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'int-blind-review:w1', value: { pass: false, issues: ['still broken'], advisories: [], concernDispositions: [], summary: 'fail' } },
  ])
  const result = await runGraphBody(
    { projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 },
    scripted.agent,
    async jobs => Promise.all(jobs.map(job => job())),
    () => {},
  )
  assert.equal(scripted.calls.some(c => c.label === 'int-commit:w1'), false)
  assert.equal(result.integration[0].reason, 'integration-review-failed')
  assert.equal(result.terminalState, 'escalated')
}

async function testGraphHumanOnlyStopsBeforeWorktree() {
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: sha('a'), graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 0, humanCount: 1, statusPorcelain: '' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture' }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.terminalState, 'pending-human')
  assert.equal(scripted.calls.some(c => c.label.startsWith('worktree:')), false)
}

async function testGraphSpecialOnlyTargetsAreRejectedBeforeWorktree() {
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'external-only', targets: ['external'], depends: [], risk: 'NONE' }], verify: 'true' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: sha('a'), graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
  ])
  await assert.rejects(
    runGraphBody({ projectRoot: '/tmp/spec-contract-fixture' }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {}),
    /최소 1개 파일 target/,
  )
  assert.equal(scripted.calls.some(call => call.label.startsWith('worktree:')), false)
}

async function testGraphV2MissingExecutionContractIsRejectedBeforeWorktree() {
  const completeTask = {
    id: 'T1', goal: 'change a', why: 'contributes to outcome', targets: ['src/a.js'], depends: [],
    evidence: [{ id: 'E1', kind: 'command', run: 'npm test -- a', expect: exitZeroExpectation }], assumptions: [], risk: 'NONE', replanWhen: ['test contract conflicts'],
  }
  const variants = [
    { key: 'why', pattern: /why 가 비어 있음/ },
    { key: 'depends', pattern: /depends 배열 필수/ },
    { key: 'evidence', pattern: /evidence 는/ },
    { key: 'assumptions', pattern: /assumptions 문자열 배열/ },
    { key: 'risk', pattern: /risk 필수/ },
    { key: 'replanWhen', pattern: /replanWhen 은/ },
  ]
  for (const { key, pattern } of variants) {
    const task = { ...completeTask }
    delete task[key]
    const graph = JSON.stringify({ contractVersion: '2.0', tasks: [task], verify: 'npm test' })
    const scripted = scriptedAgent([
      { ...target },
      { match: '정찰', value: { currentBranch: 'work/test', currentHead: sha('a'), graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    ])
    await assert.rejects(
      runGraphBody({ projectRoot: '/tmp/spec-contract-fixture' }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {}),
      pattern,
    )
    assert.equal(scripted.calls.some(call => call.label.startsWith('worktree:')), false)
  }

  const noVerify = JSON.stringify({ contractVersion: '2.0', tasks: [completeTask] })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: sha('a'), graphRaw: noVerify, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
  ])
  await assert.rejects(
    runGraphBody({ projectRoot: '/tmp/spec-contract-fixture' }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {}),
    /graph verify 가 비어 있음/,
  )
  assert.equal(scripted.calls.some(call => call.label.startsWith('worktree:')), false)

  const legacyFreeTextExpect = JSON.stringify({
    contractVersion: '2.0',
    tasks: [{ ...completeTask, evidence: [{ id: 'E1', kind: 'command', run: 'npm test -- a', expect: 'exit 0' }] }],
    verify: 'npm test',
  })
  const malformed = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: sha('a'), graphRaw: legacyFreeTextExpect, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
  ])
  await assert.rejects(
    runGraphBodyRaw({ projectRoot: '/tmp/spec-contract-fixture' }, malformed.agent, async jobs => Promise.all(jobs.map(job => job())), () => {}),
    /expect:\{exit,outputIncludes,outputExcludes\}/,
  )
  assert.equal(malformed.calls.some(call => call.label.startsWith('worktree:')), false)
}

async function testGraphNonStringVersionCannotDowngradeToLegacy() {
  const invalidVersions = [2, true, null, {}, []]
  for (const contractVersion of invalidVersions) {
    const graph = JSON.stringify({
      contractVersion,
      tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }],
      verify: 'npm test',
    })
    const scripted = scriptedAgent([
      { ...target },
      { match: '정찰', value: { currentBranch: 'work/test', currentHead: sha('a'), graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    ])
    await assert.rejects(
      runGraphBody({ projectRoot: '/tmp/spec-contract-fixture' }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {}),
      /정확한 문자열 "2\.0"/,
    )
    assert.equal(scripted.calls.some(call => call.label.startsWith('worktree:')), false)
  }
}

async function testGraphMissingVersionFailsClosedWithoutMigrationMode() {
  const graph = JSON.stringify({
    tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }],
    verify: 'npm test',
  })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: sha('a'), graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
  ])
  await assert.rejects(
    runGraphBodyRaw({ projectRoot: '/tmp/spec-contract-fixture' }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {}),
    /contractVersion.*\(누락\)/,
  )
  assert.equal(scripted.calls.some(call => call.label.startsWith('worktree:')), false)
}

async function testGraphApprovalShapedEvidenceIsRejected() {
  const samples = [
    { id: 'E1', run: 'npm test -- manager-approval' },
    { id: 'E1', run: './scripts/operator-signoff.sh' },
    { id: 'E1', run: 'npm test -- 담당자-승인' },
    { id: 'E1', run: 'npm test -- 관리자-확인' },
    { id: 'E1', run: 'npm test -- manual-QA-sign-off' },
    { id: 'manager_approval', run: 'npm test -- a' },
    { id: 'E1', run: 'npm test -- a', expect: { exit: 'manager approval', outputIncludes: [], outputExcludes: [] } },
    { id: 'managerApproval', run: 'npm test -- a' },
    { id: 'E1', run: 'npm test -- managerApproval' },
    { id: 'E1', run: 'npm test -- a', expect: { exit: '0', outputIncludes: ['managerApproval'], outputExcludes: [] } },
    { id: 'E1', run: 'npm test -- a', expect: { exit: '0', outputIncludes: [], outputExcludes: ['managerApproval'] } },
  ]
  for (const { id, run, expect = exitZeroExpectation } of samples) {
    const graph = JSON.stringify({
      contractVersion: '2.0',
      tasks: [{
        id: 'T1', goal: 'change a', why: 'contributes', targets: ['src/a.js'], depends: [],
        evidence: [{ id, kind: 'command', run, expect }],
        assumptions: [], risk: 'NONE', replanWhen: ['test contract conflicts'],
      }],
      verify: 'npm test',
    })
    const scripted = scriptedAgent([
      { ...target },
      { match: '정찰', value: { currentBranch: 'work/test', currentHead: sha('a'), graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    ])
    await assert.rejects(
      runGraphBodyRaw({ projectRoot: '/tmp/spec-contract-fixture' }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {}),
      /사람 승인·확인을 evidence로 표현할 수 없음/,
    )
    assert.equal(scripted.calls.some(call => call.label.startsWith('worktree:')), false)
  }
}

async function testGraphV2EvidenceResultsMustMatchDeclaredCommands() {
  const before = sha('a')
  const graph = JSON.stringify({
    contractVersion: '2.0',
    tasks: [{
      id: 'T1', goal: 'change a', why: 'contributes', targets: ['src/a.js'], depends: [],
      evidence: [{ id: 'E1', kind: 'command', run: 'npm test -- a', expect: exitZeroExpectation }],
      assumptions: [], risk: 'NONE', replanWhen: ['test contract conflicts'],
    }],
    verify: 'npm test',
  })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'pre-review:T1(1)', value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'blind-review:T1', value: { ...blindPass, evidenceResults: [{ id: 'E1', run: 'npm test -- wrong', exit: '0', output: 'pass', passed: true }] } },
    { match: 'post-review:T1(1)', value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
  ])
  const result = await runGraphBodyRaw({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.taskResults.T1.status, 'review-protocol-failed')
  assert.ok(result.taskResults.T1.review.protocolFailure.includes('evidenceResults 1:1'))
  assert.equal(scripted.calls.some(call => call.label === 'commit:T1'), false)
}

async function testGraphV2EvidenceOutputExpectationIsCodeChecked() {
  const before = sha('a')
  const graph = JSON.stringify({
    contractVersion: '2.0',
    tasks: [{
      id: 'T1', goal: 'change a', why: 'contributes', targets: ['src/a.js'], depends: [],
      evidence: [{ id: 'E1', kind: 'command', run: 'npm test -- a', expect: { exit: '0', outputIncludes: ['EXPECTED_SENTINEL'], outputExcludes: ['FORBIDDEN_SENTINEL'] } }],
      assumptions: [], risk: 'NONE', replanWhen: ['test contract conflicts'],
    }],
    verify: 'npm test',
  })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'pre-review:T1(1)', value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'blind-review:T1', value: { ...blindPass, evidenceResults: [{ id: 'E1', run: 'npm test -- a', exit: '0', output: 'NOPE FORBIDDEN_SENTINEL', passed: true }] } },
    { match: 'post-review:T1(1)', value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'replan:T1(1)', value: { triggered: false, matchedCondition: '', reason: 'same task can be fixed' } },
  ])
  const result = await runGraphBodyRaw({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.taskResults.T1.status, 'review-failed')
  assert.ok(result.taskResults.T1.review.issues.some(issue => issue.includes('EXPECTED_SENTINEL') && issue.includes('FORBIDDEN_SENTINEL')))
  assert.equal(scripted.calls.some(call => call.label === 'commit:T1'), false)
}

async function testGraphV2ReplanConditionStopsSameGraphRetry() {
  const before = sha('a')
  const graph = JSON.stringify({
    contractVersion: '2.0',
    tasks: [{
      id: 'T1', goal: 'change a', why: 'contributes', targets: ['src/a.js'], depends: [],
      evidence: [{ id: 'E1', kind: 'command', run: 'npm test -- a', expect: exitZeroExpectation }],
      assumptions: [], risk: 'NONE', replanWhen: ['existing API contract conflicts'],
    }],
    verify: 'npm test',
  })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'pre-review:T1(1)', value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'blind-review:T1', value: { ...blindPass, pass: false, issues: ['existing API contract conflicts'] } },
    { match: 'post-review:T1(1)', value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'replan:T1(1)', value: { triggered: true, matchedCondition: 'existing API contract conflicts', reason: 'task boundary must change' } },
  ])
  const result = await runGraphBodyRaw({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 3 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.taskResults.T1.status, 'replan-required')
  assert.equal(result.taskResults.T1.replan.matchedCondition, 'existing API contract conflicts')
  assert.equal(scripted.calls.some(call => call.label === 'impl:T1(재시도 2)'), false)
  assert.equal(scripted.calls.some(call => call.label === 'commit:T1'), false)
  assert.equal(result.terminalState, 'escalated')
}

async function testGraphV2IntegrationFailureRequiresGraphReplan() {
  const before = sha('a')
  const taskHead = sha('b')
  const mergeHead = sha('e')
  const graph = JSON.stringify({
    contractVersion: '2.0',
    tasks: [{
      id: 'T1', goal: 'change a', why: 'contributes', targets: ['src/a.js'], depends: [],
      evidence: [{ id: 'E1', kind: 'command', run: 'npm test -- a', expect: exitZeroExpectation }],
      assumptions: [], risk: 'NONE', replanWhen: ['integration contract conflicts'],
    }],
    verify: 'npm test',
  })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: mockMergeProof({ beforeHead: before, taskHead }) },
    { match: 'integration-snapshot:w1#1', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'integration:w1', value: { exit: '1', output: 'integration contract conflicts' } },
    { match: 'integration-proof:w1#1', value: { branch: 'work/test', afterHead: mergeHead, statusPorcelain: '' } },
  ])
  const result = await runGraphBodyRaw({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 3 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.integration[0].reason, 'replan-required')
  assert.deepEqual(result.integration[0].replanWhen, ['T1: integration contract conflicts'])
  assert.equal(scripted.calls.some(call => call.label === 'int-fix:w1'), false)
  assert.equal(result.terminalState, 'escalated')
}

async function testGraphMixedHumanGateCannotReturnVerified() {
  const before = sha('a')
  const taskHead = sha('b')
  const mergeHead = sha('e')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 1, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: mockMergeProof({ beforeHead: before, taskHead }) },
    { match: 'integration-snapshot:w1#1', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'integration:w1', value: { exit: '0', output: 'pass' } },
    { match: 'integration-proof:w1#1', value: { branch: 'work/test', afterHead: mergeHead, statusPorcelain: '' } },
    { match: 'finalize-snapshot', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'ancestor 확인', value: { checks: [{ id: 'T1', ancExit: '0' }] } },
    { match: 'worktree 제거', value: { removed: ['T1'] } },
    { match: 'finalize-proof', value: { branch: 'work/test', afterHead: mergeHead, statusPorcelain: '' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.allMerged, true)
  assert.equal(result.terminalState, 'pending-human')
  assert.equal(result.runSummary.autonomousPathClosed, false)
  assert.equal(result.runSummary.humanReintervention, 'required')
}

async function testGraphFakeIntegrationCommitIsRejected() {
  const base = sha('a')
  const taskHead = sha('b')
  const fakeHead = sha('c')
  const mergeHead = sha('e')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: base, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: base, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: base, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: base, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: base, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: mockMergeProof({ beforeHead: base, taskHead }) },
    { match: 'integration-snapshot:w1#1', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: /^integration:w1/, value: { exit: '1', output: 'failing integration' } },
    { match: 'integration-proof:w1#1', value: { branch: 'work/test', afterHead: mergeHead, statusPorcelain: '' } },
    { match: 'int-fix:w1', value: done },
    { match: 'int-blind-review:w1', value: blindPass },
    { match: /^int-(?:pre-review|changeset):w1$/, value: { branch: 'work/test', beforeHead: mergeHead, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'int-commit:w1', value: { beforeHead: mergeHead, afterHead: fakeHead, headLog: `${fakeHead} 조작`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'int-commit-proof:w1', value: { branch: 'work/test', afterHead: mergeHead, headLog: `${mergeHead} 실제`, revCount: '0', committedFiles: '', committedDigest: '', statusPorcelain: ' M src/a.js' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.integration[0].reason, 'integration-commit-failed')
  assert.equal(result.terminalState, 'escalated')
}

async function testGraphRegenCannotCommitOutsideDeclaredTargets() {
  const before = sha('a')
  const taskHead = sha('b')
  const regenHead = sha('c')
  const mergeHead = sha('e')
  const graph = JSON.stringify({
    tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }],
    regenBarriers: [{ after: ['T1'], run: 'npm run generate', targets: ['generated'] }],
    verify: 'npm test',
  })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: mockMergeProof({ beforeHead: before, taskHead }) },
    { match: 'regen-snapshot:w1#0', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'regen:w1#0', value: { exit: '0', output: 'generated', headLog: `${regenHead} regen` } },
    { match: 'regen-proof:w1#0', value: { branch: 'work/test', afterHead: regenHead, headLog: `${regenHead} regen`, revCount: '1', committedFiles: '.planning/STATE.md', statusPorcelain: '' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.terminalState, 'escalated')
  assert.ok(result.escalation.reason.includes('regen barrier'))
  assert.equal(scripted.calls.some(c => c.label === 'integration:w1'), false)
}

async function testGraphCommitCannotAddUnreviewedFile() {
  const before = sha('a')
  const after = sha('b')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change src', targets: ['src'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: after, headLog: `${after} 변경`, statusPorcelain: '', committedFiles: 'src/a.js\nsrc/evil.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: after, headLog: `${after} 변경`, revCount: '1', committedFiles: 'src/a.js\nsrc/evil.js', committedDigest: digest('d'), statusPorcelain: '' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.taskResults.T1.status, 'commit-failed')
  assert.equal(result.terminalState, 'escalated')
  assert.equal(scripted.calls.some(c => c.label === 'merge-gate:w1'), false)
}

async function testGraphFakeMergeReportCannotReturnVerified() {
  const before = sha('a')
  const taskHead = sha('b')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} 거짓 merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: { branch: 'work/test', afterHead: before, revCount: '0', firstParentCount: '0', statusPorcelain: '', checks: [{ id: 'T1', ancExit: '1' }], mergeCommits: [] } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.allMerged, false)
  assert.equal(result.terminalState, 'escalated')
  assert.equal(scripted.calls.some(c => c.label === 'integration:w1'), false)
}

async function testGraphAutoOnlyHappyPathVerifies() {
  const before = sha('a')
  const taskHead = sha('b')
  const mergeHead = sha('e')
  const graph = JSON.stringify({
    contractVersion: '2.0',
    tasks: [{
      id: 'T1', goal: 'change a', why: '전체 동작을 제공한다', targets: ['src/a.js'], depends: [],
      evidence: [{ id: 'E1', kind: 'command', run: 'npm test -- a', expect: exitZeroExpectation }], assumptions: ['기존 public API 유지'], risk: 'NONE', replanWhen: ['기존 테스트 계약과 충돌'],
    }],
    verify: 'npm test',
  })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: mockMergeProof({ beforeHead: before, taskHead }) },
    { match: 'integration-snapshot:w1#1', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'integration:w1', value: { exit: '0', output: 'pass' } },
    { match: 'integration-proof:w1#1', value: { branch: 'work/test', afterHead: mergeHead, statusPorcelain: '' } },
    { match: 'finalize-snapshot', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'ancestor 확인', value: { checks: [{ id: 'T1', ancExit: '0' }] } },
    { match: 'worktree 제거', value: { removed: ['T1'] } },
    { match: 'finalize-proof', value: { branch: 'work/test', afterHead: mergeHead, statusPorcelain: '' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.allMerged, true)
  assert.equal(result.integration[0].status, 'passed')
  assert.equal(result.terminalState, 'verified')
  const implCall = scripted.calls.find(c => c.label === 'impl:T1')
  assert.ok(implCall.prompt.includes('전체 동작을 제공한다'))
  assert.ok(implCall.prompt.includes('[E1] run=npm test -- a ; expect={"exit":"0","outputIncludes":[],"outputExcludes":[]}'))
  assert.ok(implCall.prompt.includes('기존 public API 유지'))
  assert.ok(implCall.prompt.includes('기존 테스트 계약과 충돌'))
  assert.ok(result.runSummary.metrics.agentSelfTurns > 0)
  assert.equal(result.runSummary.metrics.autonomousCompletion, true)
}

async function testGraphFinalizeMutationCannotReturnVerified() {
  const before = sha('a')
  const taskHead = sha('b')
  const mergeHead = sha('e')
  const mutatedHead = sha('c')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: mockMergeProof({ beforeHead: before, taskHead }) },
    { match: 'integration-snapshot:w1#1', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'integration:w1', value: { exit: '0', output: 'pass' } },
    { match: 'integration-proof:w1#1', value: { branch: 'work/test', afterHead: mergeHead, statusPorcelain: '' } },
    { match: 'finalize-snapshot', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'ancestor 확인', value: { checks: [{ id: 'T1', ancExit: '0' }] } },
    { match: 'worktree 제거', value: { removed: ['T1'] } },
    { match: 'finalize-proof', value: { branch: 'work/test', afterHead: mutatedHead, statusPorcelain: '' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.terminalState, 'escalated')
  assert.ok(result.escalation.reason.includes('Finalize'))
  assert.equal(result.runSummary.autonomousPathClosed, false)
}

async function testGraphExtraBaseCommitIsRejected() {
  const before = sha('a')
  const taskHead = sha('b')
  const injectedHead = sha('c')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: { branch: 'work/test', afterHead: injectedHead, revCount: '3', firstParentCount: '2', statusPorcelain: '', checks: [{ id: 'T1', ancExit: '0' }], mergeCommits: [] } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.allMerged, false)
  assert.equal(result.terminalState, 'escalated')
  assert.equal(scripted.calls.some(c => c.label === 'integration:w1'), false)
}

async function testGraphIntegrationMutationIsRejected() {
  const before = sha('a')
  const taskHead = sha('b')
  const mergeHead = sha('e')
  const mutatedHead = sha('c')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'blind-review:T1', value: blindPass },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${taskHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: mockMergeProof({ beforeHead: before, taskHead }) },
    { match: 'integration-snapshot:w1#1', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'integration:w1', value: { exit: '0', output: 'pass' } },
    { match: 'integration-proof:w1#1', value: { branch: 'work/test', afterHead: mutatedHead, statusPorcelain: '' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.integration[0].reason, 'integration-mutated-repo')
  assert.equal(result.terminalState, 'escalated')
  assert.equal(scripted.calls.some(c => c.label === 'ancestor 확인'), false)
}

async function testGraphCheckoutAwayFromMergeHeadIsRejectedBeforeIntegration() {
  const before = sha('a')
  const taskHead = sha('b')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: before, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: before, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: before, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'blind-review:T1', value: blindPass },
    { match: 'commit:T1', value: { beforeHead: before, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: before, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${sha('e')} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: mockMergeProof({ beforeHead: before, taskHead }) },
    // 과거 happy-path 픽스처가 허용했던 결함: merge HEAD(e)가 아니라 task HEAD(b)로 checkout 된 상태.
    { match: 'integration-snapshot:w1#1', value: { branch: 'work/test', beforeHead: taskHead, statusPorcelain: '' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.integration[0].reason, 'integration-base-mismatch')
  assert.equal(result.terminalState, 'escalated')
  assert.equal(scripted.calls.some(call => call.label === 'integration:w1'), false)
}

async function testWrongClosureStateIsRejectedBeforeCommit() {
  const { fixtureRoot, repo } = makeGitFixture(true)
  try {
    const liveItem = 'auto: curl {PREVIEW_URL}/health → 200'
    let frozenHead = ''
    const scripted = scriptedAgent([
      { match: '타깃 해석', value: { resolvedRoot: repo, statePresent: true } },
      { match: '작업트리 기준선', value: () => ({ branch: 'work/test', head: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: git(repo, 'status', '--porcelain') }) },
      { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [liveItem], nextTaskRaw: '## 다음 task\npreview-push: authorized' } },
      { match: '구현', value: () => { fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const b = 2\n'); return done } },
      { match: '블라인드 리뷰', value: blindPass },
      ...singleReviewPair(() => { const s = actualSnapshot(repo); frozenHead = s.beforeHead; return s }),
      { match: '커밋', value: () => {
        const beforeHead = git(repo, 'rev-parse', 'HEAD')
        git(repo, 'add', 'src/a.js')
        git(repo, 'commit', '-m', '구현 변경')
        const p = actualCommitProof(repo, beforeHead)
        return { beforeHead, afterHead: p.afterHead, headLog: p.headLog, statusPorcelain: p.statusPorcelain, committedFiles: p.committedFiles }
      } },
      { match: '커밋 증거', value: () => actualCommitProof(repo, frozenHead) },
      { match: 'push+프리뷰', value: () => { git(repo, 'push', 'origin', 'work/test'); return { branch: 'work/test', isMain: false, pushed: true, previewUrl: 'https://preview.invalid', reason: '' } } },
      { match: '프리뷰 SHA 증거', value: () => {
        const localHead = git(repo, 'rev-parse', 'HEAD')
        const remoteHead = git(repo, 'ls-remote', 'origin', 'refs/heads/work/test').split(/\s+/)[0]
        return { localHead, remoteHead, deployedHead: remoteHead, proofPreviewUrl: 'https://preview.invalid', evidence: 'actual local/remote fixture plus bound deployment fixture' }
      } },
      { match: '라이브 프로브', value: { pass: true, results: [{ item: liveItem, pass: true, output: '200' }], failures: [], evidence: '200' } },
      { match: '종결 STATE 제안', value: () => { fs.writeFileSync(path.join(repo, '.planning', 'STATE.md'), '## 완료 task\n\n### 목표\nunrelated task\n'); return { changed: true } } },
      { match: '종결 검토 전 changeset', value: () => actualSnapshot(repo) },
      { match: '종결 STATE 리뷰', value: () => {
        const state = fs.readFileSync(path.join(repo, '.planning', 'STATE.md'), 'utf8')
        const valid = state.includes('test') && state.includes('https://preview.invalid') && state.includes('prod 반영은 별도 명시 승인 대기')
        return { pass: valid, issues: valid ? [] : ['현재 task·프리뷰·prod 대기 기록이 아님'], stateOnlyChanged: true, targetTaskClosed: valid, previewUrlRecorded: valid, prodMergePendingRecorded: valid, noOtherTaskRewritten: false }
      } },
      { match: '종결 changeset', value: () => actualSnapshot(repo) },
    ])
    const result = await runSingleBody({ projectRoot: repo, maxAttempts: 1 }, scripted.agent, () => {})
    assert.equal(result.liveGate.status, 'closure-failed')
    assert.equal(result.terminalState, 'closure-failed')
    assert.equal(scripted.calls.some(c => c.label === '종결 커밋'), false)
    assert.equal(git(repo, 'status', '--porcelain').includes('.planning/STATE.md'), true)
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true })
  }
}

async function testRealGitTwoCommitExploitIsRejected() {
  const { fixtureRoot, repo } = makeGitFixture()
  try {
    let frozenHead = ''
    const scripted = scriptedAgent([
      { match: '타깃 해석', value: { resolvedRoot: repo, statePresent: true } },
      { match: '작업트리 기준선', value: () => ({ branch: 'work/test', head: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: git(repo, 'status', '--porcelain') }) },
      { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
      { match: '구현', value: () => { fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const b = 2\n'); fs.appendFileSync(path.join(repo, '.planning', 'STATE.md'), '\n완료\n'); return { ...done, filesChanged: ['src/a.js', '.planning/STATE.md'] } } },
      { match: '블라인드 리뷰', value: blindPass },
      ...singleReviewPair(() => { const s = actualSnapshot(repo); frozenHead = s.beforeHead; return s }),
      { match: '커밋', value: () => {
        const beforeHead = git(repo, 'rev-parse', 'HEAD')
        git(repo, 'add', 'src/a.js', '.planning/STATE.md')
        git(repo, 'commit', '-m', '첫 번째 변경')
        fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const c = 3\n')
        git(repo, 'add', 'src/a.js')
        git(repo, 'commit', '-m', '리뷰 후 두 번째 변경')
        const p = actualCommitProof(repo, beforeHead)
        return { beforeHead, afterHead: p.afterHead, headLog: p.headLog, statusPorcelain: p.statusPorcelain, committedFiles: p.committedFiles }
      } },
      { match: '커밋 증거', value: () => actualCommitProof(repo, frozenHead) },
    ])
    const result = await runSingleBody({ projectRoot: repo, maxAttempts: 1 }, scripted.agent, () => {})
    assert.equal(result.commit.revCount, '2')
    assert.equal(result.committed, false)
    assert.equal(result.terminalState, 'commit-failed')
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true })
  }
}

async function testRealGitUnpushedClosureIsRejected() {
  const { fixtureRoot, repo } = makeGitFixture(true)
  try {
    const liveItem = 'auto: curl {PREVIEW_URL}/health → 200'
    let frozenHead = ''
    const scripted = scriptedAgent([
      { match: '타깃 해석', value: { resolvedRoot: repo, statePresent: true } },
      { match: '작업트리 기준선', value: () => ({ branch: 'work/test', head: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: git(repo, 'status', '--porcelain') }) },
      { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [liveItem], nextTaskRaw: '## 다음 task\npreview-push: authorized' } },
      { match: '구현', value: () => { fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const b = 2\n'); return done } },
      { match: '블라인드 리뷰', value: blindPass },
      ...singleReviewPair(() => { const s = actualSnapshot(repo); frozenHead = s.beforeHead; return s }),
      { match: '커밋', value: () => {
        const beforeHead = git(repo, 'rev-parse', 'HEAD')
        git(repo, 'add', 'src/a.js')
        git(repo, 'commit', '-m', '구현 변경')
        const p = actualCommitProof(repo, beforeHead)
        return { beforeHead, afterHead: p.afterHead, headLog: p.headLog, statusPorcelain: p.statusPorcelain, committedFiles: p.committedFiles }
      } },
      { match: '커밋 증거', value: () => actualCommitProof(repo, frozenHead) },
      { match: 'push+프리뷰', value: () => { git(repo, 'push', 'origin', 'work/test'); return { branch: 'work/test', isMain: false, pushed: true, previewUrl: 'https://preview.invalid', reason: '' } } },
      { match: '프리뷰 SHA 증거', value: () => {
        const localHead = git(repo, 'rev-parse', 'HEAD')
        const remoteHead = git(repo, 'ls-remote', 'origin', 'refs/heads/work/test').split(/\s+/)[0]
        return { localHead, remoteHead, deployedHead: remoteHead, proofPreviewUrl: 'https://preview.invalid', evidence: 'actual local/remote fixture plus bound deployment fixture' }
      } },
      { match: '라이브 프로브', value: { pass: true, results: [{ item: liveItem, pass: true, output: '200' }], failures: [], evidence: '200' } },
      { match: '종결 STATE 제안', value: () => {
        fs.writeFileSync(path.join(repo, '.planning', 'STATE.md'), '## 완료 task\n\n### 목표\ntest\n\n프리뷰 https://preview.invalid 에서 라이브 실증 완료. prod 반영은 별도 명시 승인 대기.\n')
        return { changed: true }
      } },
      { match: '종결 검토 전 changeset', value: () => actualSnapshot(repo) },
      { match: '종결 STATE 리뷰', value: { pass: true, issues: [], stateOnlyChanged: true, targetTaskClosed: true, previewUrlRecorded: true, prodMergePendingRecorded: true, noOtherTaskRewritten: true } },
      { match: '종결 changeset', value: () => actualSnapshot(repo) },
      { match: '종결 커밋', value: () => {
        const beforeHead = git(repo, 'rev-parse', 'HEAD')
        git(repo, 'add', '.planning/STATE.md')
        git(repo, 'commit', '-m', '종결 기록')
        const afterHead = git(repo, 'rev-parse', 'HEAD')
        return { beforeHead, afterHead, headLog: git(repo, 'log', '-1', '--format=%H %s'), remoteHead: afterHead, statusPorcelain: '' }
      } },
      { match: '종결 증거', value: ({ prompt }) => {
        const beforeHead = (prompt.match(/종결 전 HEAD ([0-9a-f]{40})/) || [])[1]
        const remoteLine = git(repo, 'ls-remote', 'origin', 'refs/heads/work/test')
        return { ...actualCommitProof(repo, beforeHead), remoteHead: remoteLine.split(/\s+/)[0] || '' }
      } },
    ])
    const result = await runSingleBody({ projectRoot: repo, maxAttempts: 1 }, scripted.agent, () => {})
    assert.equal(result.liveGate.status, 'closure-failed')
    assert.notEqual(result.liveGate.closure.afterHead, result.liveGate.closure.remoteHead)
    assert.equal(result.terminalState, 'closure-failed')
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true })
  }
}

async function testRealGitReviewedBytesMutationIsRejected() {
  const { fixtureRoot, repo } = makeGitFixture()
  try {
    let frozenHead = ''
    const scripted = scriptedAgent([
      { match: '타깃 해석', value: { resolvedRoot: repo, statePresent: true } },
      { match: '작업트리 기준선', value: () => ({ branch: 'work/test', head: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: git(repo, 'status', '--porcelain') }) },
      { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
      { match: '구현', value: () => { fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const reviewed = true\n'); fs.appendFileSync(path.join(repo, '.planning', 'STATE.md'), '\n완료\n'); return { ...done, filesChanged: ['src/a.js', '.planning/STATE.md'] } } },
      { match: '블라인드 리뷰', value: blindPass },
      ...singleReviewPair(() => { const s = actualSnapshot(repo); frozenHead = s.beforeHead; return s }),
      { match: '커밋', value: () => {
        const beforeHead = git(repo, 'rev-parse', 'HEAD')
        fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const injectedAfterReview = true\n')
        git(repo, 'add', 'src/a.js', '.planning/STATE.md')
        git(repo, 'commit', '-m', '같은 파일 리뷰 후 변조')
        const p = actualCommitProof(repo, beforeHead)
        return { beforeHead, afterHead: p.afterHead, headLog: p.headLog, statusPorcelain: p.statusPorcelain, committedFiles: p.committedFiles }
      } },
      { match: '커밋 증거', value: () => actualCommitProof(repo, frozenHead) },
    ])
    const result = await runSingleBody({ projectRoot: repo, maxAttempts: 1 }, scripted.agent, () => {})
    assert.equal(result.commit.reviewedFiles, result.commit.committedFiles)
    assert.notEqual(result.commit.reviewedDigest, result.commit.committedDigest)
    assert.equal(result.committed, false)
    assert.equal(result.terminalState, 'commit-failed')
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true })
  }
}

async function testRealGitImplementerEarlyCommitIsRejectedBeforeReview() {
  const { fixtureRoot, repo } = makeGitFixture()
  try {
    const scripted = scriptedAgent([
      { match: '타깃 해석', value: { resolvedRoot: repo, statePresent: true } },
      { match: '작업트리 기준선', value: () => ({ branch: 'work/test', head: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: '' }) },
      { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
      { match: '구현', value: () => {
        fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const early = true\n')
        git(repo, 'add', 'src/a.js')
        git(repo, 'commit', '-m', '금지된 조기 커밋')
        fs.appendFileSync(path.join(repo, '.planning', 'STATE.md'), '\n완료\n')
        return { ...done, filesChanged: ['src/a.js', '.planning/STATE.md'] }
      } },
      { match: '검토 전 changeset', value: () => actualSnapshot(repo) },
    ])
    const result = await runSingleBody({ projectRoot: repo, maxAttempts: 1 }, scripted.agent, () => {})
    assert.equal(result.terminalState, 'escalated')
    assert.ok(result.escalation.reason.includes('changeset 프로토콜'))
    assert.equal(scripted.calls.some(c => c.label === '블라인드 리뷰'), false)
  } finally { fs.rmSync(fixtureRoot, { recursive: true, force: true }) }
}

async function testRealGitReviewerMutationIsRejected() {
  const { fixtureRoot, repo } = makeGitFixture()
  try {
    const scripted = scriptedAgent([
      { match: '타깃 해석', value: { resolvedRoot: repo, statePresent: true } },
      { match: '작업트리 기준선', value: () => ({ branch: 'work/test', head: git(repo, 'rev-parse', 'HEAD'), statusPorcelain: '' }) },
      { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 0, irreversiblePresent: false, liveItems: [] } },
      { match: '구현', value: () => {
        fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const reviewed = true\n')
        fs.appendFileSync(path.join(repo, '.planning', 'STATE.md'), '\n완료\n')
        return { ...done, filesChanged: ['src/a.js', '.planning/STATE.md'] }
      } },
      { match: '검토 전 changeset', value: () => actualSnapshot(repo) },
      { match: '블라인드 리뷰', value: () => {
        fs.appendFileSync(path.join(repo, 'src', 'a.js'), 'export const reviewerInjected = true\n')
        return blindPass
      } },
      { match: '리뷰 changeset', value: () => actualSnapshot(repo) },
    ])
    const result = await runSingleBody({ projectRoot: repo, maxAttempts: 1 }, scripted.agent, () => {})
    assert.equal(result.terminalState, 'escalated')
    assert.equal(scripted.calls.some(c => c.label === '커밋'), false)
  } finally { fs.rmSync(fixtureRoot, { recursive: true, force: true }) }
}

async function testStalePreviewShaIsRejectedBeforeProbe() {
  const before = sha('a'), implementationHead = sha('b'), stale = sha('c')
  const liveItem = 'auto: curl {PREVIEW_URL}/health → 200'
  const { result, calls } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 1, humanCount: 1, irreversiblePresent: false, liveItems: [liveItem], nextTaskRaw: '## 다음 task\npreview-push: authorized' } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: implementationHead, headLog: `${implementationHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: implementationHead, headLog: `${implementationHead} 변경`, revCount: '1', statusPorcelain: '', committedFiles: 'src/a.js', committedDigest: digest('d') } },
    { match: 'push+프리뷰', value: { branch: 'work/test', isMain: false, pushed: true, previewUrl: 'https://preview.invalid', reason: '' } },
    { match: '프리뷰 SHA 증거', value: { localHead: implementationHead, remoteHead: implementationHead, deployedHead: stale, proofPreviewUrl: 'https://preview.invalid', evidence: 'stale fixture' } },
  ])
  assert.ok(result.liveGate)
  assert.equal(result.liveGate.status, 'preview-failed')
  assert.equal(calls.some(c => c.label === '라이브 프로브'), false)
}

async function testDuplicateLiveGateItemsCannotPass() {
  const before = sha('a'), implementationHead = sha('b')
  const liveItems = ['auto: check alpha at {PREVIEW_URL}', 'auto: check beta at {PREVIEW_URL}']
  const { result } = await runSingle([
    { ...target },
    { ...cleanBaseline },
    { match: '게이트 점검', value: { gatePresent: true, autoCount: 2, humanCount: 1, irreversiblePresent: false, liveItems, nextTaskRaw: '## 다음 task\npreview-push: authorized' } },
    { match: '구현', value: done },
    { match: '검토 전 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '블라인드 리뷰', value: blindPass },
    { match: '리뷰 changeset', value: { branch: 'work/test', beforeHead: before, statusPorcelain: ' M src/a.js', reviewedFiles: 'src/a.js', reviewedDigest: digest('d') } },
    { match: '커밋', value: { beforeHead: before, afterHead: implementationHead, headLog: `${implementationHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: '커밋 증거', value: { branch: 'work/test', afterHead: implementationHead, headLog: `${implementationHead} 변경`, revCount: '1', statusPorcelain: '', committedFiles: 'src/a.js', committedDigest: digest('d') } },
    { match: 'push+프리뷰', value: { branch: 'work/test', isMain: false, pushed: true, previewUrl: 'https://preview.invalid', reason: '' } },
    { match: '프리뷰 SHA 증거', value: { localHead: implementationHead, remoteHead: implementationHead, deployedHead: implementationHead, proofPreviewUrl: 'https://preview.invalid', evidence: 'bound fixture' } },
    { match: '라이브 프로브', value: { pass: true, results: [
      { item: liveItems[0], pass: true, output: 'ok' }, { item: liveItems[0], pass: true, output: 'ok again' },
    ], failures: [], evidence: 'duplicate fixture' } },
  ])
  assert.equal(result.liveGate.status, 'failed')
  assert.ok(result.liveGate.failures[0].includes('멀티셋'))
}

async function testGraphIntegrationFixEarlyCommitIsRejected() {
  const base = sha('a'), taskHead = sha('b'), mergeHead = sha('e'), earlyHead = sha('c')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: base, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: base, output: 'ok' }] } },
    { match: 'impl:T1', value: done }, { match: /^(?:pre|post)-review:T1\(/, value: { branch: 'graph-T1', beforeHead: base, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'blind-review:T1', value: blindPass },
    { match: 'commit:T1', value: { beforeHead: base, afterHead: taskHead, headLog: `${taskHead} 변경`, statusPorcelain: '', committedFiles: 'src/a.js' } },
    { match: 'commit-proof:T1', value: { branch: 'graph-T1', afterHead: taskHead, headLog: `${taskHead} 변경`, revCount: '1', committedFiles: 'src/a.js', committedDigest: digest('d'), statusPorcelain: '' } },
    { match: 'merge-gate:w1', value: { gates: [{ id: 'T1', revCount: '1', diffFiles: 'src/a.js' }] } },
    { match: 'merge-snapshot:w1', value: { branch: 'work/test', beforeHead: base, statusPorcelain: '' } },
    { match: 'merge:w1', value: { merges: [{ id: 'T1', exit: '0', headLog: `${mergeHead} merge`, conflict: false }] } },
    { match: 'merge-proof:w1', value: { branch: 'work/test', afterHead: mergeHead, revCount: '2', firstParentCount: '1', statusPorcelain: '', checks: [{ id: 'T1', ancExit: '0' }], mergeCommits: [{ id: 'T1', mergeHead, parents: `${base} ${taskHead}`, remergeDiff: '' }] } },
    { match: 'integration-snapshot:w1#1', value: { branch: 'work/test', beforeHead: mergeHead, statusPorcelain: '' } },
    { match: 'integration:w1', value: { exit: '1', output: 'fail' } },
    { match: 'integration-proof:w1#1', value: { branch: 'work/test', afterHead: mergeHead, statusPorcelain: '' } },
    { match: 'int-fix:w1', value: done },
    { match: 'int-pre-review:w1', value: { branch: 'work/test', beforeHead: earlyHead, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.integration[0].reason, 'integration-fix-early-commit')
  assert.equal(scripted.calls.some(c => c.label === 'int-blind-review:w1'), false)
}

async function testGraphTaskEarlyCommitIsRejectedBeforeReview() {
  const base = sha('a'), earlyHead = sha('b')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: base, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: base, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'pre-review:T1(1)', value: { branch: 'graph-T1', beforeHead: earlyHead, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.taskResults.T1.status, 'changeset-protocol-failed')
  assert.equal(scripted.calls.some(c => c.label === 'blind-review:T1'), false)
}

async function testGraphTaskReviewerMutationIsRejected() {
  const base = sha('a')
  const graph = JSON.stringify({ tasks: [{ id: 'T1', goal: 'change a', targets: ['src/a.js'], depends: [], risk: 'NONE' }], verify: 'npm test' })
  const scripted = scriptedAgent([
    { ...target },
    { match: '정찰', value: { currentBranch: 'work/test', currentHead: base, graphRaw: graph, hasPreviewUrl: false, overallGoal: 'test', gatePresent: true, autoCount: 1, humanCount: 0, statusPorcelain: '' } },
    { match: 'worktree:w1', value: { worktrees: [{ id: 'T1', addExit: '0', toplevel: '/tmp/spec-contract-fixture/.planning/worktrees/T1', head: base, output: 'ok' }] } },
    { match: 'impl:T1', value: done },
    { match: 'pre-review:T1(1)', value: { branch: 'graph-T1', beforeHead: base, reviewedFiles: 'src/a.js', reviewedDigest: digest('d'), statusPorcelain: ' M src/a.js' } },
    { match: 'blind-review:T1', value: blindPass },
    { match: 'post-review:T1(1)', value: { branch: 'graph-T1', beforeHead: base, reviewedFiles: 'src/a.js', reviewedDigest: digest('e'), statusPorcelain: ' M src/a.js' } },
  ])
  const result = await runGraphBody({ projectRoot: '/tmp/spec-contract-fixture', maxAttempts: 1 }, scripted.agent, async jobs => Promise.all(jobs.map(job => job())), () => {})
  assert.equal(result.taskResults.T1.status, 'changeset-protocol-failed')
  assert.equal(result.taskResults.T1.reason, 'reviewer-mutated-changeset')
  assert.equal(scripted.calls.some(c => c.label === 'commit:T1'), false)
}

async function testRealGitOursMergeIsRejected() {
  const { result } = await runActualGraphMerge('ours')
  assert.equal(result.terminalState, 'escalated')
  assert.ok(result.escalation.reason.includes('merge 사후 증거'))
}

async function testRealGitAmendedMergeTreeIsRejected() {
  const { result } = await runActualGraphMerge('amended')
  assert.equal(result.terminalState, 'escalated')
  assert.ok(result.escalation.reason.includes('merge 사후 증거'))
}

async function testRealGitNormalMergeVerifies() {
  const { result } = await runActualGraphMerge('normal')
  assert.equal(result.terminalState, 'verified')
  assert.equal(result.allMerged, true)
}

const tests = [
  testHumanOnlyStopsBeforeImplementation,
  testLiveGateNeedsExplicitPreviewPushAuthorization,
  testDirtyWorktreeStopsBeforeImplementation,
  testBlindReviewInputContract,
  testStaleHeadCannotCountAsCommit,
  testMixedHumanGateNeverReturnsVerified,
  testTwoCommitsCannotSatisfyAtomicContract,
  testCommitCannotAddUnreviewedFile,
  testAutoOnlyCommitIncludesReviewedStateAndVerifies,
  testUntrackedResidueFailsCleanContract,
  testConcernDispositionIdentityMismatchEscalates,
  testSingleReviewerBranchSwitchIsRejectedBeforeCommit,
  testLiveMixedHumanGateSkipsStateClosure,
  testClosureEvidenceMismatchIsFailure,
  testClosureReviewerMutationIsRejectedBeforeCommit,
  testGraphReviewFailureCannotCommit,
  testGraphHumanOnlyStopsBeforeWorktree,
  testGraphSpecialOnlyTargetsAreRejectedBeforeWorktree,
  testGraphV2MissingExecutionContractIsRejectedBeforeWorktree,
  testGraphNonStringVersionCannotDowngradeToLegacy,
  testGraphMissingVersionFailsClosedWithoutMigrationMode,
  testGraphApprovalShapedEvidenceIsRejected,
  testGraphV2EvidenceResultsMustMatchDeclaredCommands,
  testGraphV2EvidenceOutputExpectationIsCodeChecked,
  testGraphV2ReplanConditionStopsSameGraphRetry,
  testGraphV2IntegrationFailureRequiresGraphReplan,
  testGraphMixedHumanGateCannotReturnVerified,
  testGraphFakeIntegrationCommitIsRejected,
  testGraphRegenCannotCommitOutsideDeclaredTargets,
  testGraphCommitCannotAddUnreviewedFile,
  testGraphFakeMergeReportCannotReturnVerified,
  testGraphAutoOnlyHappyPathVerifies,
  testGraphFinalizeMutationCannotReturnVerified,
  testGraphExtraBaseCommitIsRejected,
  testGraphIntegrationMutationIsRejected,
  testGraphCheckoutAwayFromMergeHeadIsRejectedBeforeIntegration,
  testWrongClosureStateIsRejectedBeforeCommit,
  testRealGitTwoCommitExploitIsRejected,
  testRealGitUnpushedClosureIsRejected,
  testRealGitReviewedBytesMutationIsRejected,
  testRealGitImplementerEarlyCommitIsRejectedBeforeReview,
  testRealGitReviewerMutationIsRejected,
  testStalePreviewShaIsRejectedBeforeProbe,
  testDuplicateLiveGateItemsCannotPass,
  testGraphIntegrationFixEarlyCommitIsRejected,
  testGraphTaskEarlyCommitIsRejectedBeforeReview,
  testGraphTaskReviewerMutationIsRejected,
  testRealGitOursMergeIsRejected,
  testRealGitAmendedMergeTreeIsRejected,
  testRealGitNormalMergeVerifies,
]
const EXPECTED_CONTRACT_COUNT = 50
assert.equal(tests.length, EXPECTED_CONTRACT_COUNT, 'contract manifest count changed — draft CASE/ANSWER와 fresh/blind review 필요')
assert.equal(new Set(tests.map(test => test.name)).size, EXPECTED_CONTRACT_COUNT, 'contract manifest has duplicate test names')

for (const test of tests) {
  await test()
  process.stdout.write(`ok - ${test.name}\n`)
}
process.stdout.write(`${EXPECTED_CONTRACT_COUNT} draft contract checks green (not a confirmed eval pass)\n`)
