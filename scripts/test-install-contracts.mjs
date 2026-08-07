#!/usr/bin/env node

import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const HELPER = join(ROOT, 'scripts', 'install-session-hooks.py')
const INSTALL = join(ROOT, 'scripts', 'install.sh')
const EXPECTED_COMMAND = `/usr/bin/env python3 "${ROOT}/scripts/sync-agents.py" --ensure`

function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`)
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function fixture({ withPlugifyHook = true } = {}) {
  const root = mkdtempSync(join(tmpdir(), 'plugify-install-contract-'))
  const claude = join(root, 'claude')
  const codex = join(root, 'codex')
  const stale = '/tmp/stale-marketplace/plugify/scripts/sync-agents.py'
  const unrelated = {
    matcher: 'startup',
    groupMarker: 'preserve-group-field',
    hooks: [
      {
        type: 'command',
        command: '/usr/bin/python3 /tmp/unrelated.py',
        timeout: 17,
        statusMessage: 'preserve-hook-fields',
      },
      {
        type: 'command',
        command: 'true # /tmp/not-plugify/scripts/sync-agents.py --ensure',
        timeout: 3,
        statusMessage: 'substring-lookalike-must-survive',
      },
    ],
  }
  const session = [structuredClone(unrelated)]
  if (withPlugifyHook) {
    session.push({
      matcher: 'startup',
      plugifyGroupMarker: 'preserve-on-survivor',
      hooks: [{
        type: 'command',
        command: `/usr/bin/python3 "${stale}" --ensure`,
        timeout: 60,
        statusMessage: 'old but preserved',
      }],
    })
    session.push({
      matcher: 'resume',
      hooks: [{
        type: 'command',
        command: `/opt/homebrew/bin/python3 "${stale}" --ensure`,
        timeout: 60,
      }],
    })
  }
  writeJson(join(claude, 'settings.json'), {
    permissions: { defaultMode: 'ask' },
    hooks: { SessionStart: session, PostToolUse: [structuredClone(unrelated)] },
    marker: 'claude-preserved',
  })
  writeJson(join(codex, 'hooks.json'), {
    description: 'preserve me',
    hooks: { SessionStart: structuredClone(session), Stop: [structuredClone(unrelated)] },
    marker: 'codex-preserved',
  })
  writeFileSync(join(codex, 'config.toml'), '[hooks.state."sentinel"]\ntrusted_hash = "preserve-this-exactly"\n')
  return { root, claude, codex }
}

function runHelper(fx, ...args) {
  return execFileSync('python3', [HELPER, '--repo-root', ROOT, ...args], {
    env: {
      ...process.env,
      HOME: fx.root,
      CLAUDE_CONFIG_DIR: fx.claude,
      CODEX_HOME: fx.codex,
      XDG_CONFIG_HOME: join(fx.root, '.config'),
    },
    encoding: 'utf8',
  })
}

function syncHooks(doc) {
  const groups = doc.hooks?.SessionStart ?? []
  return groups.flatMap((group) => group.hooks ?? []).filter((hook) =>
    isManagedSyncCommand(hook.command))
}

function isManagedSyncCommand(command) {
  if (typeof command !== 'string') return false
  return /^(?:(?:\/\S*)?\/python3|python3|\/usr\/bin\/env python3)\s+(?:"[^"]*\/scripts\/sync-agents\.py"|\S*\/scripts\/sync-agents\.py)\s+--ensure$/.test(command)
}

function assertCurrentHook(doc) {
  const hooks = syncHooks(doc)
  assert.equal(hooks.length, 1)
  assert.equal(hooks[0].command, EXPECTED_COMMAND)
}

function expectedUpdated(input) {
  const doc = structuredClone(input)
  const groups = doc.hooks?.SessionStart ?? []
  let survivor = null
  const keptGroups = []
  for (const group of groups) {
    const keptHooks = []
    for (const hook of group.hooks ?? []) {
      const isSync = isManagedSyncCommand(hook.command)
      if (!isSync) {
        keptHooks.push(hook)
      } else if (!survivor) {
        survivor = { ...hook, command: EXPECTED_COMMAND }
        keptHooks.push(survivor)
      }
    }
    if (keptHooks.length) keptGroups.push({ ...group, hooks: keptHooks })
  }
  if (!survivor) {
    keptGroups.push({
      matcher: 'startup|resume|clear|compact',
      hooks: [{
        type: 'command',
        command: EXPECTED_COMMAND,
        timeout: 60,
        statusMessage: 'plugify agent sync',
      }],
    })
  }
  doc.hooks ??= {}
  doc.hooks.SessionStart = keptGroups
  return doc
}

const tests = []
function test(name, fn) { tests.push([name, fn]) }

test('testReplacesStaleHooksAndPreservesUnrelatedConfig', () => {
  const fx = fixture()
  const beforeClaude = readJson(join(fx.claude, 'settings.json'))
  const beforeCodex = readJson(join(fx.codex, 'hooks.json'))
  runHelper(fx)
  const claude = readJson(join(fx.claude, 'settings.json'))
  const codex = readJson(join(fx.codex, 'hooks.json'))
  assertCurrentHook(claude)
  assertCurrentHook(codex)
  assert.deepEqual(claude, expectedUpdated(beforeClaude))
  assert.deepEqual(codex, expectedUpdated(beforeCodex))
})

test('testAddsMissingHooksExactlyOnce', () => {
  const fx = fixture({ withPlugifyHook: false })
  runHelper(fx)
  runHelper(fx)
  assertCurrentHook(readJson(join(fx.claude, 'settings.json')))
  assertCurrentHook(readJson(join(fx.codex, 'hooks.json')))
})

test('testRepeatedRunIsByteIdempotent', () => {
  const fx = fixture()
  runHelper(fx)
  const firstClaude = readFileSync(join(fx.claude, 'settings.json'))
  const firstCodex = readFileSync(join(fx.codex, 'hooks.json'))
  runHelper(fx)
  assert.deepEqual(readFileSync(join(fx.claude, 'settings.json')), firstClaude)
  assert.deepEqual(readFileSync(join(fx.codex, 'hooks.json')), firstCodex)
})

test('testDryRunDoesNotWrite', () => {
  const fx = fixture()
  const beforeClaude = readFileSync(join(fx.claude, 'settings.json'))
  const beforeCodex = readFileSync(join(fx.codex, 'hooks.json'))
  const output = runHelper(fx, '--dry-run')
  assert.deepEqual(readFileSync(join(fx.claude, 'settings.json')), beforeClaude)
  assert.deepEqual(readFileSync(join(fx.codex, 'hooks.json')), beforeCodex)
  assert.match(output, /DRY-RUN/)
  assert.match(output, /settings\.json/)
  assert.match(output, /hooks\.json/)
  assert.match(output, /stale-marketplace/)
  assert.ok(output.includes(`${ROOT}/scripts/sync-agents.py`))
  assert.match(output, /update/)
})

function assertGeneratedAgents(actualDir, expectedDir, extension) {
  const expectedAgents = readdirSync(expectedDir).filter((name) => name.endsWith(extension)).sort()
  const actualAgents = readdirSync(actualDir).filter((name) => name.endsWith(extension)).sort()
  assert.deepEqual(actualAgents, expectedAgents)
  for (const name of expectedAgents) {
    assert.deepEqual(readFileSync(join(actualDir, name)), readFileSync(join(expectedDir, name)))
  }
}

test('testInstallScriptWiresCurrentRepo', () => {
  const fx = fixture()
  const expectedRoot = mkdtempSync(join(tmpdir(), 'plugify-install-expected-'))
  const expectedClaude = join(expectedRoot, 'claude')
  const expectedCodex = join(expectedRoot, 'codex')
  execFileSync('python3', [join(ROOT, 'scripts', 'sync-agents.py')], {
    env: {
      ...process.env,
      HOME: expectedRoot,
      CLAUDE_CONFIG_DIR: expectedClaude,
      CODEX_HOME: expectedCodex,
    },
    stdio: 'pipe',
  })
  execFileSync('bash', [INSTALL], {
    env: {
      ...process.env,
      HOME: fx.root,
      CLAUDE_CONFIG_DIR: fx.claude,
      CODEX_HOME: fx.codex,
      XDG_CONFIG_HOME: join(fx.root, '.config'),
    },
    stdio: 'pipe',
  })
  assertCurrentHook(readJson(join(fx.claude, 'settings.json')))
  assertCurrentHook(readJson(join(fx.codex, 'hooks.json')))
  assertGeneratedAgents(join(fx.claude, 'agents'), join(expectedClaude, 'agents'), '.md')
  assertGeneratedAgents(join(fx.codex, 'agents'), join(expectedCodex, 'agents'), '.toml')
})

test('testDoesNotForgeCodexHookTrust', () => {
  const helperFx = fixture()
  const helperConfig = readFileSync(join(helperFx.codex, 'config.toml'))
  runHelper(helperFx)
  assert.deepEqual(readFileSync(join(helperFx.codex, 'config.toml')), helperConfig)

  const installFx = fixture()
  const installConfig = readFileSync(join(installFx.codex, 'config.toml'))
  execFileSync('bash', [INSTALL], {
    env: {
      ...process.env,
      HOME: installFx.root,
      CLAUDE_CONFIG_DIR: installFx.claude,
      CODEX_HOME: installFx.codex,
      XDG_CONFIG_HOME: join(installFx.root, '.config'),
    },
    stdio: 'pipe',
  })
  assert.deepEqual(readFileSync(join(installFx.codex, 'config.toml')), installConfig)
  assert.ok(!existsSync(join(installFx.root, '.codex')))
})

const EXPECTED_TEST_NAMES = [
  'testReplacesStaleHooksAndPreservesUnrelatedConfig',
  'testAddsMissingHooksExactlyOnce',
  'testRepeatedRunIsByteIdempotent',
  'testDryRunDoesNotWrite',
  'testInstallScriptWiresCurrentRepo',
  'testDoesNotForgeCodexHookTrust',
]

assert.deepEqual(tests.map(([name]) => name), EXPECTED_TEST_NAMES)
assert.equal(tests.length, 6)

let failed = 0
for (const [name, fn] of tests) {
  try {
    fn()
    console.log(`ok - ${name}`)
  } catch (error) {
    failed += 1
    console.error(`not ok - ${name}`)
    console.error(error?.stack ?? error)
  }
}

if (failed) process.exit(1)
console.log(`${tests.length} draft contract checks green (not a confirmed eval pass)`)
