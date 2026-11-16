import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from 'node:net';
import http from 'node:http';
import { test } from 'node:test';

test('Render exposes the public hostname while preserving host and origin checks', async t => {
  const probe=createServer();probe.listen(0,'127.0.0.1');await once(probe,'listening');
  const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
  process.env.PORT=String(port);process.env.WEB_HOST='0.0.0.0';
  process.env.RENDER_EXTERNAL_URL='https://recommand-test.onrender.com';
  const {server}=await import('../server.mjs');
  if(!server.listening)await once(server,'listening');
  t.after(()=>new Promise(resolve=>server.close(resolve)));
  const get=headers=>new Promise((resolve,reject)=>{
    const req=http.get({hostname:'127.0.0.1',port,path:'/api/health',headers},res=>{res.resume();res.on('end',()=>resolve(res.statusCode));});req.on('error',reject);
  });
  assert.equal(server.address().address,'0.0.0.0');
  assert.equal(await get({Host:'recommand-test.onrender.com',Origin:'https://recommand-test.onrender.com'}),200);
  assert.equal(await get({Host:`localhost:${port}`}),200);
  assert.equal(await get({Host:'attacker.invalid'}),403);
  assert.equal(await get({Host:'recommand-test.onrender.com',Origin:'https://attacker.invalid'}),403);
});
