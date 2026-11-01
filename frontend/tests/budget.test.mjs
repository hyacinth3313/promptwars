import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/budget.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { effectiveCost, categoryProgress, recalculatePreviewBudget, optionKey, costIncreasePreview } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
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

test('cost simulation increases only the largest unverified estimate and preserves the original plan', () => {
  const current = { total_budget: 300000, items: [
    { ...item, category: 'venue', estimated: 150000, verified: 140000 },
    { ...item, category: 'catering', estimated: 120000 },
    { ...item, category: 'decor', estimated: 20000 },
  ], remaining: 20000, overage: 0, is_over_budget: false };
  const original = structuredClone(current);
  const result = costIncreasePreview(current);
  assert.equal(result.category, 'catering');
  assert.equal(result.increase, 40000);
  assert.equal(result.budget.items[1].estimated, 160000);
  assert.equal(result.budget.overage, 20000);
  assert.equal(result.budget.is_over_budget, true);
  assert.deepEqual(result.budget.items[0], current.items[0]);
  assert.deepEqual(result.budget.items[2], current.items[2]);
  assert.deepEqual(current, original);
  assert.equal(costIncreasePreview(result.budget), null);
  assert.equal(costIncreasePreview({ ...current, items: [] }), null);
  assert.equal(costIncreasePreview({ ...current, items: [{ ...item, verified: 0 }] }), null);
  const spacious = costIncreasePreview({ ...current, total_budget: 400000, remaining: 120000 });
  assert.equal(spacious.increase, 140000);
  assert.equal(spacious.budget.is_over_budget, true);
  assert.equal(spacious.budget.remaining, 0);
  assert.equal(spacious.budget.overage, 20000);
  const staleSummary = costIncreasePreview({ ...current, remaining: 0, total_budget: 300000.25 });
  assert.equal(staleSummary.increase, 40000.25);
  assert.equal(staleSummary.budget.overage, 20000);
});
