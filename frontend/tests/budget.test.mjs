import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/budget.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { effectiveCost, categoryProgress, recalculatePreviewBudget, optionKey } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const item = { category: 'catering', allocated: 100, estimated: 120, verified: null, notes: '' };
const budget = { total_budget: 100, items: [item], remaining: 0, overage: 20, is_over_budget: true };

test('verified costs, including zero, take precedence over estimates', () => {
  assert.equal(effectiveCost(item), 120);
  assert.equal(effectiveCost({ ...item, verified: 80 }), 80);
  assert.equal(effectiveCost({ ...item, verified: 0 }), 0);
  assert.deepEqual(recalculatePreviewBudget({ ...budget, items: [{ ...item, verified: 80 }] }), { ...budget, items: [{ ...item, verified: 80 }], remaining: 20, overage: 0, is_over_budget: false });
});
test('category bars cap at 100% while retaining the true excess and percentage', () => {
  assert.deepEqual(categoryProgress(item), { percentage: 120, width: 100, excess: 20 });
  assert.deepEqual(categoryProgress({ ...item, estimated: 50 }), { percentage: 50, width: 50, excess: 0 });
  assert.deepEqual(categoryProgress({ ...item, allocated: 0, estimated: 0 }), { percentage: 0, width: 0, excess: 0 });
  assert.deepEqual(categoryProgress({ ...item, allocated: 0 }), { percentage: 100, width: 100, excess: 120 });
});
test('sample recalculation handles balanced, over-budget, empty, and fractional costs', () => {
  assert.equal(recalculatePreviewBudget(budget).overage, 20);
  assert.equal(recalculatePreviewBudget({ ...budget, items: [] }).remaining, 100);
  assert.equal(recalculatePreviewBudget({ ...budget, items: [{ ...item, estimated: 100 }] }).is_over_budget, false);
  assert.equal(recalculatePreviewBudget({ ...budget, items: [{ ...item, estimated: 99.99 }] }).remaining, .01);
  assert.equal(budget.items[0].estimated, 120);
});
test('applied-option matching distinguishes changed actions and savings', () => {
  const option = { title: 'Seasonal menu', total_savings_inr: 100, tradeoffs: [{ category: 'catering', action: 'Simplify menu', savings_inr: 100 }] };
  assert.equal(optionKey(option), optionKey(structuredClone(option)));
  assert.notEqual(optionKey(option), optionKey({ ...option, total_savings_inr: 200 }));
  assert.notEqual(optionKey(option), optionKey({ ...option, tradeoffs: [{ ...option.tradeoffs[0], action: 'Reduce guest count' }] }));
});
