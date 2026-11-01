import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

async function loadTs(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
}
const { groupTimelineTasks, timelineStats, timelineShiftRequest, validEventDate, updateDemoTask, shiftDemoTimeline } = await loadTs('../src/lib/timeline.ts');
const { demoState } = await loadTs('../src/lib/demo.ts');

test('milestones retain their order, include empty groups, and sort tasks by due date', () => {
  const tasks = structuredClone(demoState.tasks.tasks).reverse();
  const before = structuredClone(tasks);
  const groups = groupTimelineTasks(tasks);
  assert.deepEqual(groups.map(group => group.label), ['3 Months Out', '1 Month Out', '1 Week Out', 'Day Of']);
  assert.deepEqual(groups[0].tasks.map(task => task.id), ['venue', 'catering']);
  assert.equal(groups[3].tasks.length, 0);
  assert.deepEqual(tasks, before);
});
test('progress counts all statuses distinctly and safely handles an empty board', () => {
  const tasks = structuredClone(demoState.tasks.tasks);
  tasks[3].status = 'late';
  assert.deepEqual(timelineStats(tasks), { total: 4, completed: 1, in_progress: 1, pending: 1, late: 1, completion_percentage: 25 });
  assert.deepEqual(timelineStats([]), { total: 0, completed: 0, in_progress: 0, pending: 0, late: 0, completion_percentage: 0 });
});
test('timeline review never submits already-cascaded late task IDs a second time', () => {
  assert.deepEqual(timelineShiftRequest('2027-02-14'), { late_task_ids: [] });
  assert.deepEqual(timelineShiftRequest('2027-02-14', '2027-02-14'), { late_task_ids: [] });
  assert.deepEqual(timelineShiftRequest('2027-02-14', '2027-03-14'), { new_date: '2027-03-14', late_task_ids: [] });
});
test('date validation rejects missing or impossible dates and handles leap years', () => {
  assert.equal(validEventDate(''), false);
  assert.equal(validEventDate('2027-02-29'), false);
  assert.equal(validEventDate('2028-02-29'), true);
  assert.equal(validEventDate('2027-02-31'), false);
  assert.equal(validEventDate('2027-13-01'), false);
  assert.equal(validEventDate('2027-03-14'), true);
});
test('sample Late cascades transitively, protects completed tasks, and leaves the input untouched', () => {
  const state = structuredClone(demoState);
  const base = state.tasks.tasks[1];
  state.tasks.tasks.push({ ...base, id: 'child', depends_on: ['catering'], due_date: '2027-01-01', status: 'pending' });
  state.tasks.tasks.push({ ...base, id: 'grandchild', depends_on: ['child'], due_date: '2027-01-04', status: 'pending' });
  state.tasks.tasks.push({ ...base, id: 'done', depends_on: ['catering'], due_date: '2026-11-10', status: 'completed' });
  const before = structuredClone(state);
  const result = updateDemoTask(state, 'catering', 'late');
  assert.equal(result.task.status, 'late');
  assert.ok(result.downstream_affected_task_ids.includes('child'));
  assert.ok(result.downstream_affected_task_ids.includes('grandchild'));
  assert.equal(result.tasks.tasks.find(task => task.id === 'child').due_date, '2027-01-06');
  assert.equal(result.tasks.tasks.find(task => task.id === 'grandchild').due_date, '2027-01-09');
  assert.deepEqual(result.tasks.tasks.find(task => task.id === 'done'), before.tasks.tasks.find(task => task.id === 'done'));
  assert.deepEqual(state, before);
  const repeated = updateDemoTask({ ...state, tasks: result.tasks }, 'catering', 'late');
  assert.equal(repeated.downstream_affected_task_ids.length, 0);
});
test('sample date changes move unfinished tasks and preserve completed tasks exactly', () => {
  const before = structuredClone(demoState);
  const result = shiftDemoTimeline(demoState, { new_date: '2027-02-24', late_task_ids: [] });
  assert.deepEqual(result.updated_tasks.tasks.find(task => task.id === 'venue'), before.tasks.tasks.find(task => task.id === 'venue'));
  assert.equal(result.updated_tasks.tasks.find(task => task.id === 'catering').due_date, '2026-11-30');
  assert.equal(result.updated_tasks.tasks.find(task => task.id === 'details').due_date, '2027-02-17');
  assert.ok(result.critical_risks.length);
  assert.deepEqual(demoState, before);
});
test('reviewing a previously saved late update does not add another delay', () => {
  const changed = updateDemoTask(demoState, 'catering', 'late');
  const state = { ...demoState, tasks: changed.tasks };
  const result = shiftDemoTimeline(state, timelineShiftRequest(state.config.event_date));
  assert.deepEqual(result.updated_tasks.tasks, changed.tasks.tasks);
  assert.ok(result.critical_risks.some(risk => risk.includes('late')));
});
