import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

// Exercise the real TypeScript utility without adding a separate test runtime.
const source = await readFile(new URL('../src/lib/priorities.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { rebalancePriorities, defaultPriorities, priorityCategories, prioritiesAreValid } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('every slider value preserves exactly 100%, integer weights, and the requested share', () => {
  for (const { key } of priorityCategories) {
    for (let percentage = 0; percentage <= 100; percentage++) {
      const result = rebalancePriorities(defaultPriorities, key, percentage);
      assert.equal(result[key], percentage);
      assert.equal(Object.values(result).reduce((a, b) => a + b, 0), 100);
      assert.ok(Object.values(result).every(value => Number.isInteger(value) && value >= 0));
      assert.ok(prioritiesAreValid(result));
      const payload = Object.values(result).map(value => value / 100);
      assert.ok(Math.abs(payload.reduce((a, b) => a + b, 0) - 1) < 0.000001);
    }
  }
});
test('an all-in category can be reduced when every other weight is zero', () => {
  const allIn = rebalancePriorities(defaultPriorities, 'catering', 100);
  const result = rebalancePriorities(allIn, 'catering', 0);
  assert.deepEqual(result, { catering: 0, venue: 25, decor: 25, photography: 25, logistics: 25 });
});
test('repeated changes across categories preserve a valid allocation without mutating inputs', () => {
  let weights = { ...defaultPriorities };
  for (let i = 0; i < 1000; i++) {
    const before = { ...weights };
    const next = rebalancePriorities(weights, priorityCategories[i % 5].key, i * 37 % 101);
    assert.deepEqual(weights, before);
    assert.ok(prioritiesAreValid(next));
    weights = next;
  }
});
test('invalid totals, negative, non-finite, and missing weights are rejected', () => {
  assert.equal(prioritiesAreValid({ ...defaultPriorities, venue: 20 }), false);
  assert.equal(prioritiesAreValid({ ...defaultPriorities, venue: -1 }), false);
  assert.equal(prioritiesAreValid({ ...defaultPriorities, venue: NaN }), false);
  assert.equal(prioritiesAreValid({ catering: 100 }), false);
});
