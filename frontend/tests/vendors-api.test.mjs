import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/api.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText.replace("from 'axios'", `from ${JSON.stringify(import.meta.resolve('axios'))}`);
const { api, plannerApi, apiError } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const { default: axios } = await import('axios');
const requests = [];
let responseData;
api.defaults.adapter = async config => {
  requests.push(config);
  return { data: responseData, status: 200, statusText: 'OK', headers: {}, config };
};
test('analysis submits quote and category once with server persistence enabled', async () => {
  const request = { quote_text: 'A messy vendor email\nGST extra.\nTotal ₹10000.', category: 'catering' };
  responseData = { vendor_name: 'Sample Caterer', total_quoted: 10000, hidden_fees: ['GST extra'] };
  const before = requests.length;
  assert.deepEqual(await plannerApi.analyzeVendor('session/a', request), responseData);
  assert.equal(requests.length, before + 1);
  assert.equal(requests.at(-1).method, 'post');
  assert.equal(requests.at(-1).url, '/sessions/session%2Fa/analyze-vendor');
  assert.deepEqual(requests.at(-1).params, { add_to_state: true });
  assert.deepEqual(JSON.parse(requests.at(-1).data), request);
  responseData = { vendors: [responseData], config: { session_id: 'session/a' } };
  assert.deepEqual(await plannerApi.getSession('session/a'), responseData);
  assert.equal(requests.at(-1).method, 'get');
});
test('questions use the existing planning chat endpoint and return its actual reply', async () => {
  responseData = { reply: '{"questions":["Is GST included?"]}', session_id: 'event-1', suggested_actions: ['Review updated budget'] };
  assert.deepEqual(await plannerApi.chat('event-1', { message: 'Ask questions about this exact quote.' }), responseData);
  assert.equal(requests.at(-1).url, '/sessions/event-1/chat');
  assert.equal(requests.at(-1).method, 'post');
  assert.deepEqual(JSON.parse(requests.at(-1).data), { message: 'Ask questions about this exact quote.' });
});
test('analysis failures show friendly feedback without being treated as a quote', async () => {
  const savedAdapter = api.defaults.adapter;
  api.defaults.adapter = async config => { throw new axios.AxiosError('Unavailable', 'ERR_BAD_RESPONSE', config, {}, { status: 503, data: { detail: 'Quote analysis is temporarily unavailable.' }, headers: {}, statusText: 'Unavailable', config }); };
  try {
    await assert.rejects(plannerApi.analyzeVendor('event-1', { quote_text: 'Sample vendor quote' }), error => apiError(error) === 'Your planning companion is taking a little break. Please try again shortly.');
  } finally { api.defaults.adapter = savedAdapter; }
});

test('technical details never leak into friendly error feedback', () => {
  for (const status of [400, 401, 403, 404, 409, 410, 422, 429, 500, 502, 503, 504]) {
    const error = new axios.AxiosError('Provider traceback', 'ERR_BAD_RESPONSE', undefined, {}, { status, data: { detail: 'RAW_PROVIDER_SECRET' }, headers: {}, statusText: 'Failed' });
    assert.doesNotMatch(apiError(error), /RAW_PROVIDER_SECRET|traceback/);
    assert.ok(apiError(error).length > 20);
  }
  assert.match(apiError(new axios.AxiosError('timeout', 'ECONNABORTED')), /longer/);
  assert.match(apiError(new axios.AxiosError('network')), /connection/);
});
