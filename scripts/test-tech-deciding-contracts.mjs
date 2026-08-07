#!/usr/bin/env node

import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = fs.readFileSync(path.join(root, 'skills/tech-deciding/workflow.mjs'), 'utf8')
const marker = '// ── 입력'
const start = source.indexOf(marker)
assert.notEqual(start, -1)
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const runWorkflow = new AsyncFunction('args', 'agent', 'parallel', 'log', 'phase', source.slice(start))
const sha256 = value => createHash('sha256').update(value).digest('hex')

function fileDigest(file) {
  return fs.existsSync(file) && fs.statSync(file).isFile() ? sha256(fs.readFileSync(file)) : ''
}

function decisionSnapshot(finalPath, proposedPath, proposalRunId) {
  const dir = path.dirname(finalPath)
  const canonicalDecisionDir = fs.realpathSync(dir)
  const canonicalFinalPath = path.join(canonicalDecisionDir, path.basename(finalPath))
  const canonicalProposedPath = path.join(canonicalDecisionDir, path.basename(proposedPath))
  const rows = fs.existsSync(dir)
    ? fs.readdirSync(dir, { recursive: true, withFileTypes: true })
      .filter(entry => entry.isFile())
      .map(entry => path.join(entry.parentPath, entry.name))
      .filter(file => file !== proposedPath)
      .map(file => `${path.relative(dir, file)}\t${fileDigest(file)}`)
      .sort()
    : []
  const proposalText = fs.existsSync(proposedPath) ? fs.readFileSync(proposedPath, 'utf8') : ''
  const statusValues = proposalText.split('\n').map(line => line.match(/^상태:\s*(.*?)\s*$/)?.[1]).filter(value => value !== undefined)
  const proposalRunIds = proposalText.split('\n').map(line => line.match(/^proposal_run_id:\s*(.*?)\s*$/)?.[1]).filter(value => value !== undefined)
  return {
    finalExists: fs.existsSync(finalPath), finalDigest: fileDigest(finalPath),
    proposedExists: fs.existsSync(proposedPath), proposedDigest: fileDigest(proposedPath),
    otherDecisionDigest: sha256(rows.join('\n')),
    canonicalDecisionDir, canonicalFinalPath, canonicalProposedPath,
    proposalStatus: statusValues.length === 1 ? statusValues[0] : '',
    proposalRunIds,
  }
}

async function runCase(writer, setup = null) {
  const fixtureRoot = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'plugify-tech-contract-')))
  const decisions = path.join(fixtureRoot, '.planning', 'decisions')
  fs.mkdirSync(decisions, { recursive: true })
  const finalPath = path.join(decisions, '001-db.md')
  const proposedPath = `${finalPath}.proposed`
  const proposalRunId = 'tech-contract-current-run'
  fs.writeFileSync(finalPath, '# Existing ADR\n\nstatus: accepted\n')
  if (setup) await setup({ fixtureRoot, finalPath, proposedPath, proposalRunId })
  const calls = []
  const agent = async (prompt, options = {}) => {
    calls.push({ prompt, options })
    if (options.label === '타깃 해석') return { resolvedRoot: fixtureRoot, planningPresent: true, pointerQuestion: '', pointerAdrPath: '' }
    if (options.label === 'ADR canonical 경로') {
      const canonicalDecisionDir = fs.realpathSync(decisions)
      return { canonicalDecisionDir, canonicalFinalPath: path.join(canonicalDecisionDir, path.basename(finalPath)), canonicalProposedPath: path.join(canonicalDecisionDir, path.basename(proposedPath)) }
    }
    if (options.phase === 'Define') return { constraints: 'small project', axes: [{ key: 'db', title: 'database', questions: 'which database?' }] }
    if (options.label === 'research:db') return 'finding https://example.invalid/primary'
    if (options.label === 'run 기록') return { runDir: path.join(fixtureRoot, '.planning', 'runs', 'test'), written: 3, gitExcluded: true }
    if (options.phase === 'Synthesize') return 'recommendation https://example.invalid/primary'
    if (options.phase === 'Critique') return 'risk: lock-in'
    if (options.label === 'ADR 경로 기준선') {
      const { proposalStatus: _status, proposalRunIds: _runs, ...snapshot } = decisionSnapshot(finalPath, proposedPath, proposalRunId)
      return snapshot
    }
    if (options.phase === 'ADR Draft' && !options.label) { await writer({ fixtureRoot, finalPath, proposedPath, proposalRunId }); return {} }
    if (options.label === 'ADR 제안 증거') return decisionSnapshot(finalPath, proposedPath, proposalRunId)
    throw new Error(`unexpected call: ${options.label || options.phase}`)
  }
  try {
    const result = await runWorkflow(
      { question: 'which database?', projectRoot: fixtureRoot, adrPath: finalPath, runId: proposalRunId },
      agent, async jobs => Promise.all(jobs.map(job => job())), () => {}, () => {},
    )
    return { result, calls, fixtureRoot, finalPath, proposedPath, proposalRunId }
  } catch (error) {
    fs.rmSync(fixtureRoot, { recursive: true, force: true })
    throw error
  }
}

async function testVerifiedProposalStopsPendingHuman() {
  const run = await runCase(async ({ proposedPath, proposalRunId }) => {
    fs.writeFileSync(proposedPath, `# ADR Proposal\n\n상태: 제안 — 사용자 승인 전\nproposal_run_id: ${proposalRunId}\n`)
  })
  try {
    const writerCall = run.calls.find(c => c.options.phase === 'ADR Draft' && !c.options.label)
    assert.ok(writerCall?.prompt.includes(run.proposedPath))
    assert.ok(writerCall.prompt.includes('제안 — 사용자 승인 전'))
    assert.equal(run.result.proposedAdrPath, run.proposedPath)
    assert.equal(run.result.terminalState, 'pending-human')
    assert.equal(run.result.approval.required, true)
    assert.equal(run.result.proposalEvidence.verified, true)
    assert.equal(fs.readFileSync(run.finalPath, 'utf8'), '# Existing ADR\n\nstatus: accepted\n')
  } finally { fs.rmSync(run.fixtureRoot, { recursive: true, force: true }) }
}

async function testCanonicalAdrOverwriteCannotReachApproval() {
  const run = await runCase(async ({ finalPath, proposedPath, proposalRunId }) => {
    fs.writeFileSync(proposedPath, `# ADR Proposal\n\n상태: 제안 — 사용자 승인 전\nproposal_run_id: ${proposalRunId}\n`)
    fs.writeFileSync(finalPath, '# Illegally accepted\n')
  })
  try {
    assert.equal(run.result.terminalState, 'proposal-failed')
    assert.equal(run.result.approval.required, false)
    assert.equal(run.result.proposalEvidence.verified, false)
    assert.equal(run.result.proposalEvidence.proof.proposedExists, true)
    assert.deepEqual(run.result.proposalEvidence.proof.proposalRunIds, [run.proposalRunId])
    assert.notEqual(run.result.proposalEvidence.proof.finalDigest, run.result.proposalEvidence.baseline.finalDigest)
  } finally { fs.rmSync(run.fixtureRoot, { recursive: true, force: true }) }
}

async function testSiblingDecisionMutationCannotReachApproval() {
  const run = await runCase(async ({ proposedPath, finalPath, proposalRunId }) => {
    fs.writeFileSync(proposedPath, `# ADR Proposal\n\n상태: 제안 — 사용자 승인 전\nproposal_run_id: ${proposalRunId}\n`)
    fs.writeFileSync(path.join(path.dirname(finalPath), '999-injected.md'), 'injected\n')
  })
  try {
    assert.equal(run.result.terminalState, 'proposal-failed')
    assert.equal(run.result.proposalEvidence.verified, false)
    assert.deepEqual(run.result.proposalEvidence.proof.proposalRunIds, [run.proposalRunId])
    assert.notEqual(run.result.proposalEvidence.proof.otherDecisionDigest, run.result.proposalEvidence.baseline.otherDecisionDigest)
  } finally { fs.rmSync(run.fixtureRoot, { recursive: true, force: true }) }
}

async function testAdrPathEscapeIsRejected() {
  const fixtureRoot = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'plugify-tech-escape-')))
  const outsidePath = path.resolve(fixtureRoot, '../outside.md')
  const agent = async (_prompt, options = {}) => {
    if (options.label === '타깃 해석') return { resolvedRoot: fixtureRoot, planningPresent: false, pointerQuestion: '', pointerAdrPath: '' }
    if (options.label === 'ADR canonical 경로') return { canonicalDecisionDir: path.dirname(outsidePath), canonicalFinalPath: outsidePath, canonicalProposedPath: `${outsidePath}.proposed` }
    throw new Error('workflow should reject before research')
  }
  try {
    await assert.rejects(
      runWorkflow({ question: 'escape?', projectRoot: fixtureRoot, adrPath: '../outside.md' }, agent, async jobs => Promise.all(jobs.map(job => job())), () => {}, () => {}),
      /프로젝트 루트 밖/,
    )
  } finally { fs.rmSync(fixtureRoot, { recursive: true, force: true }) }
}

async function testStaleProposalCannotReachApproval() {
  const run = await runCase(
    async () => {},
    async ({ proposedPath, proposalRunId }) => {
      fs.writeFileSync(proposedPath, `# Stale ADR Proposal\n\n상태: 제안 — 사용자 승인 전\nproposal_run_id: ${proposalRunId}-old\n`)
    },
  )
  try {
    assert.equal(run.result.terminalState, 'proposal-failed')
    assert.equal(run.result.approval.required, false)
    assert.equal(run.result.proposalEvidence.verified, false)
    assert.deepEqual(run.result.proposalEvidence.proof.proposalRunIds, [`${run.proposalRunId}-old`])
  } finally { fs.rmSync(run.fixtureRoot, { recursive: true, force: true }) }
}

async function testSymlinkedDecisionDirIsRejectedBeforeResearch() {
  const fixtureRoot = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'plugify-tech-symlink-')))
  const projectRoot = path.join(fixtureRoot, 'project')
  const outside = path.join(fixtureRoot, 'outside')
  fs.mkdirSync(path.join(projectRoot, '.planning'), { recursive: true })
  fs.mkdirSync(outside, { recursive: true })
  const decisions = path.join(projectRoot, '.planning', 'decisions')
  fs.symlinkSync(outside, decisions, 'dir')
  const finalPath = path.join(decisions, '001-db.md')
  const calls = []
  const agent = async (_prompt, options = {}) => {
    calls.push(options.label || options.phase)
    if (options.label === '타깃 해석') return { resolvedRoot: fs.realpathSync(projectRoot), planningPresent: false, pointerQuestion: '', pointerAdrPath: '' }
    if (options.label === 'ADR canonical 경로') {
      const canonicalDecisionDir = fs.realpathSync(decisions)
      return { canonicalDecisionDir, canonicalFinalPath: path.join(canonicalDecisionDir, '001-db.md'), canonicalProposedPath: path.join(canonicalDecisionDir, '001-db.md.proposed') }
    }
    throw new Error('workflow should reject before research')
  }
  try {
    await assert.rejects(
      runWorkflow({ question: 'symlink escape?', projectRoot, adrPath: finalPath }, agent, async jobs => Promise.all(jobs.map(job => job())), () => {}, () => {}),
      /canonical 경로가 프로젝트 루트 밖/,
    )
    assert.equal(calls.includes('Define'), false)
  } finally { fs.rmSync(fixtureRoot, { recursive: true, force: true }) }
}

const tests = [
  testVerifiedProposalStopsPendingHuman,
  testCanonicalAdrOverwriteCannotReachApproval,
  testSiblingDecisionMutationCannotReachApproval,
  testAdrPathEscapeIsRejected,
  testStaleProposalCannotReachApproval,
  testSymlinkedDecisionDirIsRejectedBeforeResearch,
]
const EXPECTED_CONTRACT_COUNT = 6
assert.equal(tests.length, EXPECTED_CONTRACT_COUNT, 'contract manifest count changed — draft CASE/ANSWER와 fresh/blind review 필요')
assert.equal(new Set(tests.map(test => test.name)).size, EXPECTED_CONTRACT_COUNT, 'contract manifest has duplicate test names')
for (const test of tests) {
  await test()
  process.stdout.write(`ok - ${test.name}\n`)
}
process.stdout.write(`${EXPECTED_CONTRACT_COUNT} tech-deciding draft contract checks green (not a confirmed eval pass)\n`)
