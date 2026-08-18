#!/usr/bin/env node
import fs from 'node:fs';

const expected = {
  schema: 'plugify.illustrated-story-slides.contract/1',
  primaryInput: 'warm-narrative-script',
  primaryOutput: [
    'deck.json',
    'frames/*.png',
    'storyboard.md',
    'captions.vtt',
    'preview.html',
    'sources.md',
  ],
  canvas: '1920x1080',
  truthModes: ['FACT', 'MEMORY', 'SYMBOLIC', 'UNVERIFIED'],
  namedStyleImitation: 'forbidden',
  broadcastFramesAsGenerationReference: 'forbidden',
  presentationUIInFrames: 'forbidden',
  unverifiedLiteralReenactment: 'forbidden',
  promptPolicy: 'english-observable-attributes-only',
  generationInputs: 'structured-per-scene',
  namedStyleList: 'must-be-empty',
  broadcastReferenceTokens: 'reject',
  imageToolUnavailable: 'storyboard-only-visuals-pending',
  storyboardFallbackOutput: ['deck.json', 'storyboard.md', 'captions.vtt', 'sources.md'],
  storyboardFallbackCommand: 'python3 $ILLUSTRATED_STORY_SKILL_DIR/scripts/build_preview.py --storyboard-only',
  productionStatuses: ['planning', 'visuals-pending', 'rendered'],
  informationDeckRoute: 'presentation_slides',
  singleVisualizationRoute: 'visualize',
};

function sameArray(actual, wanted) {
  return Array.isArray(actual)
    && actual.length === wanted.length
    && actual.every((value, index) => value === wanted[index]);
}

function extract(text) {
  for (const match of text.matchAll(/```json\s*([\s\S]*?)```/g)) {
    try {
      const value = JSON.parse(match[1]);
      if (value?.schema === expected.schema) return value;
    } catch {
      // Ignore unrelated JSON examples.
    }
  }
  return null;
}

function checks(contract) {
  return [
    ['surfaces', contract?.primaryInput === expected.primaryInput && sameArray(contract?.primaryOutput, expected.primaryOutput)],
    ['canvas-truth', contract?.canvas === expected.canvas && sameArray(contract?.truthModes, expected.truthModes)],
    ['non-imitation', contract?.namedStyleImitation === 'forbidden' && contract?.broadcastFramesAsGenerationReference === 'forbidden'],
    ['non-presentation', contract?.presentationUIInFrames === 'forbidden' && contract?.unverifiedLiteralReenactment === 'forbidden'],
    ['generation-input-policy', contract?.promptPolicy === expected.promptPolicy
      && contract?.generationInputs === expected.generationInputs
      && contract?.namedStyleList === expected.namedStyleList
      && contract?.broadcastReferenceTokens === expected.broadcastReferenceTokens],
    ['honest-fallback', contract?.imageToolUnavailable === expected.imageToolUnavailable
      && sameArray(contract?.storyboardFallbackOutput, expected.storyboardFallbackOutput)
      && contract?.storyboardFallbackCommand === expected.storyboardFallbackCommand],
    ['status-machine', sameArray(contract?.productionStatuses, expected.productionStatuses)],
    ['routing', contract?.informationDeckRoute === expected.informationDeckRoute && contract?.singleVisualizationRoute === expected.singleVisualizationRoute],
  ];
}

function selfTest() {
  const negatives = [
    ['no-contract', null, ['surfaces', 'canvas-truth', 'non-imitation', 'non-presentation', 'generation-input-policy', 'honest-fallback', 'status-machine', 'routing']],
    ['named-style-allowed', { ...expected, namedStyleImitation: 'allowed' }, ['non-imitation']],
    ['presentation-ui-allowed', { ...expected, presentationUIInFrames: 'allowed' }, ['non-presentation']],
    ['named-style-list-allowed', { ...expected, namedStyleList: 'allowed' }, ['generation-input-policy']],
    ['broadcast-tokens-ignored', { ...expected, broadcastReferenceTokens: 'ignore' }, ['generation-input-policy']],
    ['fake-fallback', { ...expected, imageToolUnavailable: 'use-stock-placeholder-and-report-complete' }, ['honest-fallback']],
    ['missing-fallback-command', { ...expected, storyboardFallbackCommand: '' }, ['honest-fallback']],
    ['status-collapse', { ...expected, productionStatuses: ['rendered'] }, ['status-machine']],
    ['wrong-route', { ...expected, informationDeckRoute: 'illustrated-story-slides' }, ['routing']],
  ];
  let failed = 0;
  for (const [name, contract, expectedFailures] of negatives) {
    const actualFailures = checks(contract).filter(([, passed]) => !passed).map(([id]) => id);
    const passed = expectedFailures.every((id) => actualFailures.includes(id));
    console.log(`${passed ? 'PASS' : 'FAIL'} negative:${name} failed=[${actualFailures.join(',')}]`);
    if (!passed) failed += 1;
  }
  console.log(`SELF_TEST ${negatives.length - failed}/${negatives.length}`);
  return failed === 0;
}

if (process.argv[2] === '--self-test') process.exit(selfTest() ? 0 : 1);

const skillPath = process.argv[2];
if (!skillPath || !fs.existsSync(skillPath)) {
  console.error('FAIL expected path to illustrated-story-slides/SKILL.md');
  process.exit(2);
}
const contract = extract(fs.readFileSync(skillPath, 'utf8'));
const result = checks(contract);
let failures = 0;
for (const [name, passed] of result) {
  console.log(`${passed ? 'PASS' : 'FAIL'} ${name}`);
  if (!passed) failures += 1;
}
console.log(`SUMMARY ${result.length - failures}/${result.length}`);
process.exit(failures === 0 ? 0 : 1);
