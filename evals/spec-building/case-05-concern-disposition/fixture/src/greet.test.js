const { test } = require('node:test');
const assert = require('node:assert');
const { greet } = require('./greet');

test('이름 포함 인사', () => {
  assert.strictEqual(greet('철수'), '안녕, 철수!');
});

test('빈 이름은 기본 인사', () => {
  assert.strictEqual(greet(''), '안녕!');
});
