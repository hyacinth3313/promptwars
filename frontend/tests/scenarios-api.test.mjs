import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/api.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText.replace("from 'axios'", `from ${JSON.stringify(import.meta.resolve('axios'))}`);
const { api, plannerApi } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const requests = [];
let responseData;
api.defaults.adapter = async config => { requests.push(config); return { data: responseData, status: 200, statusText: 'OK', headers: {}, config }; };
test('what-if submits relative controls to the simulation endpoint without writing the committed state', async () => {
  const delta = { budget_change: -100000, guest_count_delta: 40, new_date: '2027-03-14' };
  responseData = { scenario_id: 'scenario_123', committed_state: { config: { guest_count: 150 } }, updated_config: { guest_count: 190 } };
  const before = requests.length;
  assert.deepEqual(await plannerApi.whatIf('session/a', { delta }), responseData);
  assert.equal(requests.length, before + 1);
  assert.equal(requests.at(-1).method, 'post');
  assert.equal(requests.at(-1).url, '/sessions/session%2Fa/what-if');
  assert.deepEqual(JSON.parse(requests.at(-1).data), { delta });
});
test('commit submits only the reviewed scenario ID, not editable form values or client budget data', async () => {
  responseData = { last_committed_scenario_id: 'scenario_123', config: { guest_count: 190 } };
  assert.deepEqual(await plannerApi.commitScenario('event-1', { scenario_id: 'scenario_123' }), responseData);
  assert.equal(requests.at(-1).url, '/sessions/event-1/commit-scenario');
  assert.equal(requests.at(-1).method, 'post');
  assert.deepEqual(JSON.parse(requests.at(-1).data), { scenario_id: 'scenario_123' });
});
