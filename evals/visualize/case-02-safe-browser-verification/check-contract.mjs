#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const expected = {
  schema: 'plugify.visualize.browser-safety/1',
  defaultSandboxChromeGuiBinary: 'forbidden',
  supportedBrowserTool: 'first',
  cliFirstLaunch: 'escalated-or-unsandboxed',
  sandboxProbe: 'forbidden',
  userDataDir: 'fresh-temporary-isolated',
  requiredCliFlags: [
    '--user-data-dir=<fresh-temp-dir>',
    '--no-first-run',
    '--no-default-browser-check',
  ],
  viewportRuns: 'sequential',
  parallelBrowserProcesses: 'forbidden',
  sandboxCrashSignals: [
    'exit-134',
    'SIGABRT',
    'LaunchServices-sandbox-denial',
  ],
  onSandboxCrash: 'stop-retries-then-tool-fallback-or-report',
  userChromeProcess: 'no-kill',
  userChromeProfile: 'no-reuse',
};

function sameArray(actual, wanted) {
  return Array.isArray(actual)
    && actual.length === wanted.length
    && actual.every((value, index) => value === wanted[index]);
}

function extractContract(text) {
  const blocks = text.matchAll(/```json\s*([\s\S]*?)```/g);
  for (const match of blocks) {
    try {
      const parsed = JSON.parse(match[1]);
      if (parsed?.schema === expected.schema) return parsed;
    } catch {
      // Ignore unrelated or invalid JSON blocks.
    }
  }
  return null;
}

function validate(contract) {
  return [
    ['sandbox-direct-gui-ban', contract?.defaultSandboxChromeGuiBinary === expected.defaultSandboxChromeGuiBinary],
    ['supported-browser-tool-first', contract?.supportedBrowserTool === expected.supportedBrowserTool],
    ['first-cli-escalated-no-probe', contract?.cliFirstLaunch === expected.cliFirstLaunch && contract?.sandboxProbe === expected.sandboxProbe],
    ['isolated-profile-flags', contract?.userDataDir === expected.userDataDir && sameArray(contract?.requiredCliFlags, expected.requiredCliFlags)],
    ['sequential-no-parallel', contract?.viewportRuns === expected.viewportRuns && contract?.parallelBrowserProcesses === expected.parallelBrowserProcesses],
    ['abort-stop-fallback', sameArray(contract?.sandboxCrashSignals, expected.sandboxCrashSignals) && contract?.onSandboxCrash === expected.onSandboxCrash],
    ['user-chrome-profile-untouched', contract?.userChromeProcess === expected.userChromeProcess && contract?.userChromeProfile === expected.userChromeProfile],
  ];
}

function runSelfTests() {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const fixturePath = path.join(here, 'fixture', 'negative-contracts.json');
  const cases = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
  let failures = 0;

  for (const testCase of cases) {
    const contract = testCase.noContract
      ? extractContract(testCase.keywordStuffing)
      : { ...expected, ...testCase.overrides };
    const failedNames = validate(contract)
      .filter(([, passed]) => !passed)
      .map(([name]) => name);
    const passed = testCase.mustFail.every((name) => failedNames.includes(name));
    console.log(`${passed ? 'PASS' : 'FAIL'} negative:${testCase.name} failed=[${failedNames.join(',')}]`);
    if (!passed) failures += 1;
  }

  console.log(`SELF_TEST ${cases.length - failures}/${cases.length}`);
  return failures === 0;
}

if (process.argv[2] === '--self-test') {
  process.exit(runSelfTests() ? 0 : 1);
}

const skillPath = process.argv[2];
if (!skillPath || !fs.existsSync(skillPath)) {
  console.error('FAIL skill-path: expected skills/visualize/SKILL.md');
  process.exit(2);
}

const contract = extractContract(fs.readFileSync(skillPath, 'utf8'));
const checks = validate(contract);
let failures = 0;
for (const [name, passed] of checks) {
  console.log(`${passed ? 'PASS' : 'FAIL'} ${name}`);
  if (!passed) failures += 1;
}
console.log(`SUMMARY ${checks.length - failures}/${checks.length}`);
process.exit(failures === 0 ? 0 : 1);
