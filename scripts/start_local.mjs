// Local development launcher. Node's built-in dotenv parser keeps secrets out of commands/logs.
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn, spawnSync } from 'node:child_process';
import { createInterface } from 'node:readline';
import { createServer } from 'node:net';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export function loadConfiguration(root, envFile, offline = false) {
  const selected = envFile ? path.resolve(envFile) : path.join(root, '.env');
  if (envFile || existsSync(selected)) process.loadEnvFile(selected);
  const env = { ...process.env, ALPHAFORGE_MODE: process.env.ALPHAFORGE_MODE || 'local' };
  if (env.ALPHAFORGE_MODE !== 'local') throw new Error('The local launcher requires ALPHAFORGE_MODE=local.');
  env.AWS_REGION ||= 'us-east-1';
  env.DATA_DIR = path.resolve(root, env.DATA_DIR || 'dataset');
  env.PROFILES_PATH = path.resolve(root, env.PROFILES_PATH || 'profiles.json');
  env.AUDIT_DIR = path.resolve(root, env.AUDIT_DIR || '.local-runs');
  if (offline) env.BEDROCK_MODEL_ID = '';
  return env;
}

export function pythonExecutable(env, root = ROOT) {
  if (env.PYTHON_EXECUTABLE) return env.PYTHON_EXECUTABLE;
  const relative = process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python';
  for (const directory of [env.VIRTUAL_ENV, path.join(root, '.venv'), path.join(root, '..', '.venv')].filter(Boolean)) {
    const executable = path.join(directory, relative);
    if (existsSync(executable)) return executable;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

export function frontendEnvironment(env, backendPort, port) {
  const clean = Object.fromEntries(Object.entries(env).filter(([key]) => !/^(AWS_|BEDROCK_)/i.test(key)));
  return { ...clean, PORT: String(port), AGENT_API_URL: `http://127.0.0.1:${backendPort}/chat`,
    PORTFOLIO_API_URL: `http://127.0.0.1:${backendPort}/portfolio`, AGENT_API_TOKEN: '', PORTFOLIO_API_TOKEN: '' };
}

async function requireFreePort(port, label) {
  const probe = createServer();
  await new Promise((resolve, reject) => {
    probe.once('error', () => reject(new Error(`${label} port ${port} is already in use or unavailable. Open the existing app, stop its terminal, or use --port 4174 --backend-port 8001.`)));
    probe.listen(port, '127.0.0.1', () => probe.close(resolve));
  });
}

function stopChild(child) {
  if (!child.pid || child.exitCode !== null || child.signalCode !== null) return;
  if (process.platform === 'win32') {
    // venv python.exe can launch a second interpreter. Stop only this spawned
    // child's tree so a wrapper cannot leave the actual HTTP server running.
    const executable = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe');
    const result = spawnSync(executable, ['/PID', String(child.pid), '/T', '/F'],
      { windowsHide: true, stdio: 'ignore', timeout: 5000 });
    if (result.status !== 0) child.kill();
  } else child.kill();
}

export async function main(args = process.argv.slice(2)) {
  if (args.includes('--help')) {
    console.log('node scripts/start_local.mjs [--offline] [--port 4173] [--backend-port 8000] [--env-file PATH]');
    return;
  }
  const options = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--offline') options.offline = true;
    else if (['--port', '--backend-port', '--env-file'].includes(args[i]) && args[i + 1]) options[args[i].slice(2)] = args[++i];
    else throw new Error('Invalid launcher option. Use --help.');
  }
  let env;
  try { env = loadConfiguration(ROOT, options['env-file'], options.offline); }
  catch { throw new Error('Could not load local configuration. Check the root .env and ALPHAFORGE_MODE=local.'); }
  const port = Number(options.port || env.PORT || 4173);
  const backendPort = Number(options['backend-port'] ?? env.BACKEND_PORT ?? 8000);
  if (!Number.isInteger(port) || port < 1 || port > 65535 || !Number.isInteger(backendPort)
      || backendPort < 0 || backendPort > 65535 || backendPort === port) throw new Error('Invalid or overlapping local ports.');
  await requireFreePort(port, 'Website');
  if (backendPort !== 0) await requireFreePort(backendPort, 'Backend');
  env.PYTHONPATH = [path.join(ROOT, 'backend/src'), env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  const children = [];
  const control = createInterface({ input: process.stdin });
  let stopping = false;
  const stop = code => {
    if (stopping) return;
    stopping = true;
    control.close();
    process.stdin.destroy();
    for (const child of children) stopChild(child);
    process.exitCode = code;
  };
  control.on('line', line => { if (line.trim() === 'stop') stop(0); });
  process.once('SIGINT', () => stop(0));
  process.once('SIGTERM', () => stop(0));
  const launch = (executable, argv, childEnv, stdio) => {
    const child = spawn(executable, argv, { cwd: ROOT, env: childEnv, stdio, windowsHide: true });
    children.push(child);
    child.on('error', () => { console.error('A local service could not start. Check Python/Node and dependencies.'); stop(1); });
    child.on('exit', code => { if (!stopping) stop(code || 1); });
    return child;
  };
  try {
    const backend = launch(pythonExecutable(env), ['-u', '-m', 'alphaforge.presentation.local_server',
      '--port', String(backendPort), '--frontend-port', String(port)], env, ['ignore', 'pipe', 'inherit']);
    const actualPort = await new Promise((resolve, reject) => {
      const lines = createInterface({ input: backend.stdout });
      const timer = setTimeout(() => reject(new Error('Local backend startup timed out.')), 10000);
      const done = callback => { clearTimeout(timer); lines.close(); callback(); };
      lines.on('line', line => {
        const match = /^Local backend ready: http:\/\/127\.0\.0\.1:(\d+)$/.exec(line);
        if (match) done(() => resolve(Number(match[1])));
      });
      backend.once('exit', () => done(() => reject(new Error('Local backend stopped before it was ready.'))));
      backend.once('error', () => done(() => reject(new Error('Local backend could not start.'))));
    });
    if (stopping) return;
    launch(process.execPath, ['plateforme/server.mjs'], frontendEnvironment(env, actualPort, port), 'inherit');
    console.log(`Backend: http://127.0.0.1:${actualPort}`);
    console.log(env.BEDROCK_MODEL_ID ? 'Explanation: Bedrock configured (access checked on request).' : 'Explanation: deterministic fallback.');
    console.log('Root .env loaded when present; terminal variables take precedence. Ctrl+C stops both services.');
  } catch (error) {
    stop(1);
    throw error;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
