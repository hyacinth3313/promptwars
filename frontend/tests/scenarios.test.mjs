import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

async function moduleUrl(path, dependencies = {}) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8');
  let compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2021 } }).outputText;
  for (const [name, url] of Object.entries(dependencies)) compiled = compiled.replace(`from '${name}'`, `from ${JSON.stringify(url)}`);
  return `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`;
}
const { validateScenarioInputs, scenarioBudgetRows, scenarioAffectedTasks } = await import(await moduleUrl('../src/lib/scenarios.ts'));
const { demoState } = await import(await moduleUrl('../src/lib/demo.ts'));
const budgetUrl = await moduleUrl('../src/lib/budget.ts');
const timelineUrl = await moduleUrl('../src/lib/timeline.ts');
const { previewDemoScenario, commitDemoScenario } = await import(await moduleUrl('../src/lib/scenarioDemo.ts', { './budget': budgetUrl, './timeline': timelineUrl }));

test('scenario controls accept signed deltas and send an optional actual date change', () => {
  assert.deepEqual(validateScenarioInputs(demoState, { budget: '-100000', guests: '+40', date: '2027-03-14' }), { delta: { budget_change: -100000, guest_count_delta: 40, new_date: '2027-03-14' }, errors: {} });
  assert.deepEqual(validateScenarioInputs(demoState, { budget: '', guests: '-25', date: demoState.config.event_date }), { delta: { budget_change: 0, guest_count_delta: -25 }, errors: {} });
  assert.equal(validateScenarioInputs(demoState, { budget: '+100.25', guests: '', date: '' }).delta.budget_change, 100.25);
});
test('invalid controls and non-positive resulting plans cannot run', () => {
  for (const value of ['Infinity', 'NaN', '1,00,000', '1e10', '-1500000']) assert.ok(validateScenarioInputs(demoState, { budget: value, guests: '', date: '' }).errors.budget);
  for (const value of ['1.5', '-150', 'Infinity', '9007199254740992']) assert.ok(validateScenarioInputs(demoState, { budget: '', guests: value, date: '' }).errors.guests);
  assert.ok(validateScenarioInputs(demoState, { budget: '', guests: '', date: '2027-02-31' }).errors.date);
  assert.ok(validateScenarioInputs(demoState, { budget: '', guests: '', date: '' }).errors.form);
});
test('comparison keeps removed and added categories, normalizes décor, and uses verified zero', () => {
  const current = { ...demoState.budget, items: [{ category: 'Décor', allocated: 100, estimated: 90, verified: 0, notes: '' }, { category: 'Venue', allocated: 100, estimated: 100, verified: null, notes: '' }] };
  const proposed = { ...current, items: [{ category: 'decor', allocated: 100, estimated: 200, verified: 0, notes: '' }, { category: 'Catering', allocated: 150, estimated: 150, verified: null, notes: '' }] };
  const rows = scenarioBudgetRows(current, proposed);
  assert.equal(rows.length, 3);
  assert.equal(rows.find(row => row.key === 'decor').costChange, 0);
  assert.equal(rows.find(row => row.key === 'venue').costChange, -100);
  assert.equal(rows.find(row => row.key === 'catering').costChange, 150);
});
test('sample preview is isolated, preserves verified costs, and only commit replaces the sample plan', () => {
  const base = structuredClone(demoState);
  base.budget.items[1].verified = 500000;
  const before = structuredClone(base);
  const preview = previewDemoScenario(base, { budget_change: -100000, guest_count_delta: 40, new_date: '2027-02-24' });
  assert.deepEqual(base, before);
  assert.equal(preview.updated_config.total_budget, 1400000);
  assert.equal(preview.updated_config.guest_count, 190);
  assert.equal(preview.updated_budget.items[1].verified, 500000);
  assert.deepEqual(preview.updated_tasks.tasks[0], base.tasks.tasks[0]);
  const committed = commitDemoScenario(preview);
  assert.equal(committed.config.guest_count, 190);
  assert.equal(committed.config.event_date, '2027-02-24');
  assert.equal(committed.last_committed_scenario_id, preview.scenario_id);
  assert.deepEqual(committed.budget, preview.updated_budget);
  assert.deepEqual(base, before);
});
test('affected tasks merge IDs, titles, moved dates, and review-only suggestions without duplicates', () => {
  const preview = previewDemoScenario(demoState, { budget_change: 0, guest_count_delta: 0, new_date: '2027-02-24' });
  preview.affected_tasks = ['catering', 'Plan a menu to remember', 'Reconfirm transport'];
  const affected = scenarioAffectedTasks(preview);
  assert.equal(affected.filter(task => task.key === 'catering').length, 1);
  assert.ok(affected.some(task => task.title === 'Reconfirm transport' && !task.current));
  assert.ok(affected.some(task => task.current && task.scenario && task.current.due_date !== task.scenario.due_date));
});
