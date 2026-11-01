import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/api.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText.replace("from 'axios'", `from ${JSON.stringify(import.meta.resolve('axios'))}`);
const { api, plannerApi } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const requests = [];
let responseData;
api.defaults.adapter = async config => {
  requests.push(config);
  return { data: responseData, status: 200, statusText: 'OK', headers: {}, config };
};
test('task status calls encode identifiers and return the full cascaded task list', async () => {
  for (const status of ['pending', 'in_progress', 'completed', 'late']) {
    responseData = { task: { id: 'task/a', status }, downstream_affected_task_ids: ['child'], timeline_shifted: status === 'late', tasks: { tasks: [{ id: 'child', due_date: '2027-02-01' }] } };
    assert.deepEqual(await plannerApi.updateTask('session/a', 'task/a', status), responseData);
    assert.equal(requests.at(-1).url, '/sessions/session%2Fa/tasks/task%2Fa/status');
    assert.equal(requests.at(-1).method, 'post');
    assert.deepEqual(JSON.parse(requests.at(-1).data), { status });
  }
});
test('date shifts send the backend new_date field and refresh the whole event afterward', async () => {
  responseData = { reasoning: 'Schedule moved', critical_risks: ['Reconfirm vendors'], updated_tasks: { tasks: [{ id: 'child', due_date: '2027-03-01' }] } };
  assert.deepEqual(await plannerApi.shiftTimeline('event-1', { new_date: '2027-03-14', late_task_ids: [] }), responseData);
  assert.equal(requests.at(-1).url, '/sessions/event-1/shift-timeline');
  assert.equal(requests.at(-1).method, 'post');
  assert.deepEqual(JSON.parse(requests.at(-1).data), { new_date: '2027-03-14', late_task_ids: [] });
  responseData = { config: { session_id: 'event-1', event_date: '2027-03-14' }, tasks: responseData.updated_tasks };
  assert.deepEqual(await plannerApi.getSession('event-1'), responseData);
  assert.equal(requests.at(-1).method, 'get');
});
test('full timeline review does not submit the same late task IDs again', async () => {
  responseData = { reasoning: 'Saved dependencies reviewed', critical_risks: [], updated_tasks: { tasks: [] } };
  await plannerApi.shiftTimeline('event-1', { late_task_ids: [] });
  assert.deepEqual(JSON.parse(requests.at(-1).data), { late_task_ids: [] });
});
