import assert from 'node:assert/strict';
import { test } from 'node:test';
import { once } from 'node:events';
import { createServer } from 'node:net';
import { QUESTIONS, QUESTIONNAIRE_VERSION } from '../src/data.js';

test('HTTP adapter accepts the typed Word contract and rejects stale or malformed answers', async t => {
  const probe = createServer();
  probe.listen(0,'127.0.0.1');
  await once(probe,'listening');
  process.env.PORT = String(probe.address().port);
  await new Promise(resolve => probe.close(resolve));
  process.env.AGENT_API_URL = '';
  process.env.PORTFOLIO_API_URL = '';
  const { server } = await import('../server.mjs');
  if (!server.listening) await once(server,'listening');
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = `http://127.0.0.1:${server.address().port}`;
  const answers = Object.fromEntries(QUESTIONS.filter(q=>!q.optional).map(q=>[q.id,q.type==='number'?0:q.type==='multi'?[q.options[0][0]]:q.options[0][0]]));
  answers.withdrawalTiming = 'under_1';
  const send = (version, values) => fetch(`${base}/api/portfolio`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({questionnaire:{version,answers:values}})});
  const accepted = await send(QUESTIONNAIRE_VERSION,answers);
  assert.equal(accepted.status,503); // Valid input reaches the explicitly unconfigured adapter.
  assert.equal((await accepted.json()).code,'PORTFOLIO_NOT_CONNECTED');
  assert.equal((await send('rendements-seuls-v1',answers)).status,400);
  assert.equal((await send(QUESTIONNAIRE_VERSION,{...answers,emergencyFund:-5})).status,400);
  assert.equal((await send(QUESTIONNAIRE_VERSION,{...answers,unexpected:'field'})).status,400);
  assert.equal((await send(QUESTIONNAIRE_VERSION,{...answers,withdrawalTiming:undefined})).status,400);
  for (const path of ['/', '/src/theme.css','/src/questionnaire.css','/src/illustrations.js']) assert.equal((await fetch(base+path)).status,200,path);
  for (const path of ['/.env','/../.env','/docs/AGENT_INTEGRATION.md']) assert.equal((await fetch(base+path)).status,404,path);
});
