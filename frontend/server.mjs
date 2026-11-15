import http from 'node:http';
import { readFile, realpath, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { QUESTIONNAIRE_VERSION, validateAnswers, validatePortfolio } from './src/data.js';
import { validateRecommendation } from './src/integration.js';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const HOST = '127.0.0.1';
const PORT = Number(process.env.PORT || 4173);
const AGENT_URL = process.env.AGENT_API_URL || '';
const PORTFOLIO_URL = process.env.PORTFOLIO_API_URL || '';
const MAX_BODY = 64 * 1024;
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.avif': 'image/avif', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ico': 'image/x-icon' };
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const textValue = (value, max = 160) => typeof value === 'string' && value.trim().length > 0 && value.length <= max;

function validQuestionnaire(input) {
  if (!object(input) || input.version !== QUESTIONNAIRE_VERSION || !object(input.answers)) return false;
  return validateAnswers(input.answers);
}

function recommendationFields(result) {
  return {
    runId: result.runId,
    portfolio: { id: result.portfolio.id, name: result.portfolio.name, positions: result.portfolio.positions.map(({ symbol, name, category, group, weight, color }) => ({ symbol, name, category, group, weight, ...(color === undefined ? {} : { color }) })) },
    explanation: result.explanation,
    evidence: result.evidence.map(({ id, source, description }) => ({ id, source, description })),
    limitations: result.limitations,
    compliance: { passed: true },
  };
}

function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': MIME['.json'], 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(data));
}

async function readJson(req) {
  if (!String(req.headers['content-type'] || '').toLowerCase().startsWith('application/json')) throw Object.assign(new Error('Un contenu JSON est attendu.'), { status: 415 });
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY) throw Object.assign(new Error('La requête dépasse 64 Ko.'), { status: 413 });
    chunks.push(chunk);
  }
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { throw Object.assign(new Error('Le JSON est invalide.'), { status: 400 }); }
}

function validPayload(body) {
  return object(body) && typeof body.message === 'string' && body.message.trim().length > 0 && body.message.length <= 5000
    && Array.isArray(body.conversation) && body.conversation.length <= 100
    && body.conversation.every(item => object(item) && ['user', 'assistant'].includes(item.role) && typeof item.content === 'string' && item.content.length <= 10000)
    && validQuestionnaire(body.questionnaire) && object(body.portfolio) && validatePortfolio(body.portfolio);
}

async function upstreamJson(endpointValue, token, body, prefix) {
  const failure = (status, code, message) => Object.assign(new Error(message), { status, code: `${prefix}_${code}` });
  if (!endpointValue) throw failure(503, 'NOT_CONNECTED', prefix === 'PORTFOLIO' ? 'Votre moteur de portefeuille n’est pas encore connecté.' : 'Votre agent n’est pas encore connecté. Votre message reste disponible dans ce navigateur.');
  let endpoint;
  try {
    endpoint = new URL(endpointValue);
    if (!['http:', 'https:'].includes(endpoint.protocol) || endpoint.username || endpoint.password) throw new Error();
  } catch { throw failure(503, 'CONFIGURATION_ERROR', 'La configuration du service est invalide.'); }
  try {
    const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    const upstream = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(body), signal: AbortSignal.timeout(30000), redirect: 'error' });
    if (!upstream.ok) { await upstream.body?.cancel(); throw failure(502, 'UPSTREAM_ERROR', 'Le service a retourné une erreur. Réessayez plus tard.'); }
    const responseChunks = [];
    let responseSize = 0;
    for await (const chunk of upstream.body || []) {
      responseSize += chunk.length;
      if (responseSize > MAX_BODY) throw failure(502, 'INVALID_RESPONSE', 'La réponse du service est trop volumineuse.');
      responseChunks.push(chunk);
    }
    const text = Buffer.concat(responseChunks).toString('utf8');
    let result;
    try { result = JSON.parse(text); } catch { throw failure(502, 'INVALID_RESPONSE', 'Le service doit répondre en JSON.'); }
    return result;
  } catch (error) {
    if (error.status) throw error;
    throw failure(error.name === 'TimeoutError' ? 504 : 502, error.name === 'TimeoutError' ? 'TIMEOUT' : 'UNAVAILABLE', 'Le service ne répond pas pour le moment. Vos données locales sont conservées dans ce navigateur.');
  }
}

async function chat(req, res) {
  const body = await readJson(req);
  if (!validPayload(body)) return json(res, 400, { code: 'INVALID_REQUEST', message: 'Le message, la conversation, les réponses ou le portefeuille est invalide.' });
  const result = await upstreamJson(AGENT_URL, process.env.AGENT_API_TOKEN, body, 'AGENT');
  if (!object(result) || !textValue(result.message, 10000) || (result.proposal !== undefined && !validateRecommendation(result.proposal))) return json(res, 502, { code: 'AGENT_INVALID_RESPONSE', message: 'La réponse du service agent est invalide.' });
  return json(res, 200, { message: result.message, ...(result.proposal === undefined ? {} : { proposal: recommendationFields(result.proposal) }) });
}

async function portfolio(req, res) {
  const body = await readJson(req);
  if (!object(body) || !validQuestionnaire(body.questionnaire)) return json(res, 400, { code: 'INVALID_REQUEST', message: 'Les réponses valides à la version actuelle du questionnaire sont requises.' });
  const result = await upstreamJson(PORTFOLIO_URL, process.env.PORTFOLIO_API_TOKEN, { questionnaire: body.questionnaire }, 'PORTFOLIO');
  if (!validateRecommendation(result)) return json(res, 502, { code: 'PORTFOLIO_INVALID_RESPONSE', message: 'Le résultat du moteur de portefeuille ne respecte pas le contrat attendu.' });
  return json(res, 200, recommendationFields(result));
}

const server = http.createServer(async (req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Frame-Options', 'DENY');
  try {
    const requestHost = String(req.headers.host || '').toLowerCase();
    if (![`${HOST}:${PORT}`, `localhost:${PORT}`].includes(requestHost)) return json(res, 403, { code: 'INVALID_HOST', message: 'Accès local uniquement.' });
    const origin = req.headers.origin;
    if (origin && ![`http://${HOST}:${PORT}`, `http://localhost:${PORT}`].includes(origin)) return json(res, 403, { code: 'INVALID_ORIGIN', message: 'Origine non autorisée.' });
    const url = new URL(req.url, `http://${HOST}:${PORT}`);
    if (url.pathname === '/api/health' && req.method === 'GET') return json(res, 200, { ok: true, service: 'recommand-local' });
    if (url.pathname === '/api/config' && req.method === 'GET') return json(res, 200, { agentConnected: Boolean(AGENT_URL), portfolioConnected: Boolean(PORTFOLIO_URL) });
    if (url.pathname === '/api/agent/chat' && req.method === 'POST') return await chat(req, res);
    if (url.pathname === '/api/portfolio' && req.method === 'POST') return await portfolio(req, res);
    if (url.pathname.startsWith('/api/')) return json(res, 404, { code: 'NOT_FOUND', message: 'Route introuvable.' });
    if (!['GET', 'HEAD'].includes(req.method)) return json(res, 405, { code: 'METHOD_NOT_ALLOWED', message: 'Méthode non autorisée.' });
    let pathname;
    try { pathname = decodeURIComponent(url.pathname); } catch { return json(res, 400, { code: 'INVALID_PATH', message: 'Chemin invalide.' }); }
    if (pathname === '/') pathname = '/index.html';
    const ext = path.extname(pathname).toLowerCase();
    const allowed = pathname === '/index.html' || pathname === '/favicon.svg' || (/^\/(src|assets)\//.test(pathname) && ['.js', '.css', '.svg', '.jpg', '.jpeg', '.png', '.webp', '.avif', '.woff2', '.woff', '.ico'].includes(ext));
    if (!allowed || pathname.includes('\\') || pathname.includes('\0')) return json(res, 404, { code: 'NOT_FOUND', message: 'Fichier introuvable.' });
    const target = await realpath(path.resolve(ROOT, `.${pathname}`));
    if (!target.startsWith(`${ROOT}${path.sep}`)) return json(res, 403, { code: 'FORBIDDEN', message: 'Accès interdit.' });
    const info = await stat(target);
    if (!info.isFile()) return json(res, 404, { code: 'NOT_FOUND', message: 'Fichier introuvable.' });
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream', 'Content-Length': info.size, 'Cache-Control': 'no-cache' });
    if (req.method === 'HEAD') return res.end();
    res.end(await readFile(target));
  } catch (error) {
    if (res.headersSent) return res.end();
    if (['ENOENT', 'ENOTDIR'].includes(error.code)) return json(res, 404, { code: 'NOT_FOUND', message: 'Fichier introuvable.' });
    return json(res, error.status || 500, { code: error.status ? (error.code || 'INVALID_REQUEST') : 'SERVER_ERROR', message: error.status ? error.message : 'Une erreur locale est survenue.' });
  }
});

export { server };

if (!Number.isInteger(PORT) || PORT < 1 || PORT > 65535) {
  console.error('PORT doit être un entier entre 1 et 65535.');
  process.exitCode = 1;
} else {
  server.on('error', error => {
    console.error(error.code === 'EADDRINUSE' ? `Le port ${PORT} est déjà utilisé. Arrêtez l’autre serveur ou définissez PORT.` : `Impossible de lancer le serveur local (${error.code || 'erreur'}).`);
    process.exitCode = 1;
  });
  server.listen(PORT, HOST, () => console.log(`Recommand est disponible sur http://localhost:${PORT}\nAgent : ${AGENT_URL ? 'service configuré (disponibilité non vérifiée)' : 'non connecté'}\nPortefeuille : ${PORTFOLIO_URL ? 'service configuré (disponibilité non vérifiée)' : 'non connecté'}\nCtrl+C pour arrêter.`));
}
