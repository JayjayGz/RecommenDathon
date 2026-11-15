"""Real local HTTP transport and launcher; no live model or user .env reads."""
from contextlib import contextmanager
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen

import pytest

from alphaforge.presentation.local_server import create_server
from alphaforge.application.orchestrator import RecommendationOrchestrator
from test_investor_workflow import investor_source, questionnaire
from test_orchestrator import source, MemoryAudit, ROOT


@contextmanager
def serving(**kwargs):
    server = create_server(0, **kwargs)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def send(port, method='GET', path='/health', body=None, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=20)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    result = response.status, json.loads(response.read())
    connection.close()
    return result


def test_local_http_uses_real_handler_engine_release_and_audit(investor_source, monkeypatch):
    audit = MemoryAudit()
    workflow = RecommendationOrchestrator(investor_source, audit)
    monkeypatch.setattr('alphaforge.presentation.lambda_handler.get_orchestrator', lambda: workflow)
    with serving() as port:
        assert send(port)[0] == 200
        status, result = send(port, 'POST', '/portfolio', json.dumps({'questionnaire': questionnaire(), 'as_of': '2025-03-01'}))
        assert status == 200 and result['compliance']['passed'] and result['analysis']['suggestions']
        assert audit.saved[0][1]['result']['states'][-1] == 'COMPLETED'
        status, chat = send(port, 'POST', '/chat', json.dumps({'questionnaire': questionnaire(),
            'as_of': '2025-03-01', 'portfolio': result['portfolio'], 'message': 'Add NVDA 1%'}))
        assert status == 200 and chat['proposal']['compliance']['passed']
        assert len(audit.saved) == 2


@pytest.mark.parametrize('method,path,body,headers,expected', [
    ('GET', '/.env', None, {}, 404),
    ('GET', '/anything', None, {}, 404),
    ('GET', '/health', None, {'Host': 'attacker.invalid'}, 403),
    ('POST', '/portfolio', None, {'Origin': 'https://attacker.invalid'}, 403),
    ('POST', '/portfolio', '{}', {'Content-Type': 'text/plain'}, 400),
    ('POST', '/portfolio', 'invalid-json', {}, 400),
    # Header rejection must happen before reading a body. Sending an unrelated
    # two-byte body with a 70000-byte declaration can reset Windows TCP on close.
    ('POST', '/portfolio', None, {'Content-Length': '70000', 'Expect': '100-continue'}, 413),
    ('POST', '/portfolio', None, {'Content-Length': '-1'}, 400),
])
def test_local_transport_rejects_invalid_and_cross_origin_requests(method, path, body, headers, expected):
    with serving() as port:
        assert send(port, method, path, body, headers)[0] == expected


def test_local_transport_serializes_workflows_but_health_stays_available():
    entered, release = threading.Event(), threading.Event()
    def blocked(event, _):
        if event['rawPath'] != '/health':
            entered.set()
            assert release.wait(10)
        return {'statusCode': 200, 'body': '{"ok":true}'}
    with serving(dispatch=blocked) as port:
        thread = threading.Thread(target=lambda: send(port, 'POST', '/portfolio', '{}'))
        thread.start()
        try:
            assert entered.wait(5)
            assert send(port)[0] == 200
            status, result = send(port, 'POST', '/portfolio', '{}')
            assert status == 503 and result['error']['code'] == 'WORKFLOW_BUSY'
        finally:
            release.set()
            thread.join(timeout=5)


def test_local_adapter_does_not_echo_private_exception():
    def failed(*_):
        raise RuntimeError('private-credential-marker')
    with serving(dispatch=failed) as port:
        status, result = send(port)
        assert status == 500 and 'private-credential-marker' not in json.dumps(result)


def test_startup_reports_missing_dependency_without_private_details(monkeypatch, capsys):
    from botocore.exceptions import MissingDependencyException
    from alphaforge.presentation.local_server import initialize
    def failed():
        raise MissingDependencyException(msg='private-credential-marker')
    monkeypatch.setattr('alphaforge.presentation.local_server.get_orchestrator', failed)
    assert initialize() is False
    output = capsys.readouterr().out
    assert 'boto3[crt]' in output and 'private-credential-marker' not in output
    monkeypatch.setattr('alphaforge.presentation.local_server.get_orchestrator', lambda: object())
    assert initialize() is True


def test_launcher_loads_dotenv_with_shell_precedence_and_strips_frontend_credentials(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node required')
    config = tmp_path / '.env'
    config.write_text('ALPHAFORGE_MODE=local\nBEDROCK_MODEL_ID="fixture-model"\n'
        'AWS_BEARER_TOKEN_BEDROCK="fixture-token-with-#-and-=characters"\nAWS_REGION=us-east-1\n')
    script = """import assert from 'node:assert/strict';
import {loadConfiguration,frontendEnvironment} from './scripts/start_local.mjs';
process.env.AWS_REGION='shell-region';
const env=loadConfiguration(process.cwd(),process.argv[1]);
assert.equal(env.AWS_REGION,'shell-region');assert.equal(env.BEDROCK_MODEL_ID,'fixture-model');
assert.equal(env.AWS_BEARER_TOKEN_BEDROCK,'fixture-token-with-#-and-=characters');
const front=frontendEnvironment({...env,AWS_SECRET_ACCESS_KEY:'fixture-secret'},8000,4173);
assert.equal(Object.keys(front).some(k=>/^(AWS_|BEDROCK_)/i.test(k)),false);
assert.equal(front.PORTFOLIO_API_URL,'http://127.0.0.1:8000/portfolio');
assert.equal(loadConfiguration(process.cwd(),process.argv[1],true).BEDROCK_MODEL_ID,'');
"""
    env = {key: value for key, value in os.environ.items() if not key.startswith(('AWS_', 'BEDROCK_', 'ALPHAFORGE_'))}
    result = subprocess.run(['node', '--input-type=module', '-e', script, str(config)], cwd=ROOT,
                            env=env, text=True, capture_output=True)
    assert result.returncode == 0, 'Launcher configuration test failed (output withheld to protect fixture credentials)'


@pytest.mark.parametrize('python_selection', ['explicit', 'virtual_environment'])
def test_single_launcher_starts_proxy_and_engine_and_stops_both(tmp_path, python_selection):
    if not shutil.which('node'):
        pytest.skip('Node required')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env_file = tmp_path / '.env'
    env_file.write_text('ALPHAFORGE_MODE=local\n')
    env = {**os.environ, 'PYTHON_EXECUTABLE': sys.executable, 'AUDIT_DIR': str(tmp_path / 'audit')}
    if python_selection == 'virtual_environment':
        env.pop('PYTHON_EXECUTABLE')
        env['VIRTUAL_ENV'] = sys.prefix
    process = subprocess.Popen(['node', 'scripts/start_local.mjs', '--offline', '--env-file', str(env_file),
        '--port', str(port), '--backend-port', '0'], cwd=ROOT, env=env, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    lines = []
    def collect():
        for line in process.stdout:
            lines.append(line)
    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    backend_port = None
    try:
        base = f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:
                with urlopen(base + '/api/config', timeout=.5) as response:
                    assert json.load(response) == {'agentConnected': True, 'portfolioConnected': True}
                break
            except OSError:
                assert process.poll() is None, 'Local launcher exited before readiness'
                time.sleep(.1)
        else:
            pytest.fail('Launcher did not become ready')
        backend_port = int(next(line for line in lines if line.startswith('Backend: ')).strip().rsplit(':', 1)[1])
        request = {'questionnaire': json.loads((ROOT / 'backend/events/questionnaire-fr.json').read_text())['request']['questionnaire'],
                   'as_of': '2026-11-15'}
        with urlopen(Request(base + '/api/portfolio', data=json.dumps(request).encode(),
            headers={'Content-Type': 'application/json'}), timeout=30) as response:
            result = json.load(response)
        assert result['compliance']['passed'] and result['analysis']['review']['profile_fit']['status'] == 'PASS'
        assert len(list((tmp_path / 'audit').glob('*/result.json'))) == 1
        assert all('AWS_BEARER_TOKEN_BEDROCK' not in line for line in lines)
    finally:
        if process.poll() is None:
            process.stdin.write('stop\n')
            process.stdin.flush()
        process.wait(timeout=15)
        reader.join(timeout=2)
    if backend_port:
        with pytest.raises(OSError):
            urlopen(f'http://127.0.0.1:{backend_port}/health', timeout=1)
    with pytest.raises(OSError):
        urlopen(base + '/api/health', timeout=1)


def test_launcher_rejects_occupied_website_before_starting_backend(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node required')
    config = tmp_path / '.env'
    config.write_text('ALPHAFORGE_MODE=local\n')
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        env = {**os.environ, 'PYTHON_EXECUTABLE': 'python-must-not-start-for-an-occupied-website'}
        result = subprocess.run(['node', 'scripts/start_local.mjs', '--offline', '--env-file', str(config),
            '--port', str(port), '--backend-port', '0'], cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
    assert result.returncode == 1
    assert f'Website port {port} is already in use or unavailable' in result.stderr
    assert 'Backend:' not in result.stdout and 'could not start' not in result.stderr


def test_website_child_failure_stops_backend_process_tree(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node required')
    config = tmp_path / '.env'
    failure_module = tmp_path / 'fail-website.cjs'
    failure_module.write_text("if (process.argv[1]?.replaceAll('\\\\', '/').endsWith('/plateforme/server.mjs')) "
        "throw new Error('Simulated website startup failure');\n")
    # Node can apply a preload during dotenv loading too. Fail only the website
    # entry point, so the backend really starts before cleanup is exercised.
    config.write_text(f'ALPHAFORGE_MODE=local\nNODE_OPTIONS=\'--require "{failure_module.as_posix()}"\'\n')
    with socket.socket() as first, socket.socket() as second:
        first.bind(('127.0.0.1', 0))
        second.bind(('127.0.0.1', 0))
        port, backend_port = first.getsockname()[1], second.getsockname()[1]
    env = {**os.environ, 'PYTHON_EXECUTABLE': sys.executable}
    env.pop('NODE_OPTIONS', None)
    result = subprocess.run(['node', 'scripts/start_local.mjs', '--offline', '--env-file', str(config),
        '--port', str(port), '--backend-port', str(backend_port)], cwd=ROOT, env=env, text=True,
        capture_output=True, timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert result.returncode != 0 and f'Backend: http://127.0.0.1:{backend_port}' in result.stdout
    for stopped_port in (port, backend_port):
        with pytest.raises(OSError):
            socket.create_connection(('127.0.0.1', stopped_port), timeout=1)
