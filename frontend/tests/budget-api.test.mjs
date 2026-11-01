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
test('recalculate posts to the session endpoint and returns budget and prepared options', async () => {
  responseData = { budget: { total_budget: 100, remaining: 0, overage: 20, is_over_budget: true, items: [] }, tradeoffs: { options: [] } };
  assert.deepEqual(await plannerApi.recalculateBudget('session/a'), responseData);
  const request = requests.at(-1);
  assert.equal(request.method, 'post');
  assert.equal(request.url, '/sessions/session%2Fa/recalculate-budget');
});
test('generation explicitly requests fresh trade-off recommendations', async () => {
  responseData = { options: [{ title: 'Seasonal menu' }], guidance_notes: 'Consider a seasonal menu.' };
  assert.deepEqual(await plannerApi.generateTradeoffs('event-1'), responseData);
  assert.equal(requests.at(-1).url, '/sessions/event-1/tradeoffs');
  assert.equal(requests.at(-1).method, 'post');
  assert.deepEqual(requests.at(-1).params, { force_refresh: true });
});
test('apply sends the reviewed option explicitly; a subsequent GET retrieves the full saved state', async () => {
  const option = { title: 'Seasonal menu', total_savings_inr: 100, tradeoffs: [] };
  responseData = { config: { session_id: 'event-1' }, applied_tradeoffs: [option], tasks: { tasks: [{ title: 'Agree revised menu' }] } };
  assert.deepEqual(await plannerApi.applyTradeoff('event-1', { option }), responseData);
  assert.equal(requests.at(-1).method, 'post');
  assert.equal(requests.at(-1).url, '/sessions/event-1/apply-tradeoff');
  assert.deepEqual(JSON.parse(requests.at(-1).data), { option });
  assert.deepEqual(await plannerApi.getSession('event-1'), responseData);
  assert.equal(requests.at(-1).method, 'get');
  assert.equal(requests.at(-1).url, '/sessions/event-1');
});
