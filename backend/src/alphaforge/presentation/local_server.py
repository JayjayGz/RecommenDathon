"""Loopback-only development HTTP adapter for the real Lambda handler."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore
from urllib.parse import urlsplit
from botocore.exceptions import MissingDependencyException

from .lambda_handler import handler, get_orchestrator

MAX_BODY = 64 * 1024


def create_server(port=8000, frontend_port=4173, dispatch=handler):
    busy = BoundedSemaphore(1)

    class LocalHandler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # No questionnaire, headers, model output or credentials in HTTP logs.

        def reply(self, status, payload):
            body = json.dumps(payload, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def handle_request(self):
            authority = {f'{host}:{self.server.server_port}' for host in ('localhost', '127.0.0.1')}
            origins = {f'http://{host}:{p}' for host in ('localhost', '127.0.0.1')
                       for p in (frontend_port, self.server.server_port)}
            if self.headers.get('Host', '').lower() not in authority:
                return self.reply(403, {'error': {'code': 'INVALID_HOST'}})
            if self.headers.get('Origin') and self.headers['Origin'] not in origins:
                return self.reply(403, {'error': {'code': 'INVALID_ORIGIN'}})
            path = urlsplit(self.path).path
            if (self.command, path) not in {('GET', '/health'), ('POST', '/portfolio'), ('POST', '/chat')}:
                return self.reply(404, {'error': {'code': 'ROUTE_NOT_FOUND'}})
            body = None
            if self.command == 'POST':
                length = self.headers.get('Content-Length', '')
                if self.headers.get('Transfer-Encoding') or not length.isascii() or not length.isdigit():
                    return self.reply(400, {'error': {'code': 'INVALID_BODY_LENGTH'}})
                if len(length) > 8 or int(length) > MAX_BODY:
                    return self.reply(413, {'error': {'code': 'REQUEST_TOO_LARGE'}})
                try:
                    self.connection.settimeout(10)
                    raw = self.rfile.read(int(length))
                    if len(raw) != int(length):
                        raise ValueError('Incomplete body')
                    body = raw.decode('utf-8')
                except (UnicodeError, ValueError, OSError):
                    return self.reply(400, {'error': {'code': 'INVALID_BODY'}})
            acquired = self.command != 'POST' or busy.acquire(blocking=False)
            if not acquired:
                return self.reply(503, {'error': {'code': 'WORKFLOW_BUSY'},
                                        'message': 'Another local evaluation is running. Try again shortly.'})
            try:
                event = {'requestContext': {'http': {'method': self.command}}, 'rawPath': path,
                         'headers': {'Content-Type': self.headers.get('Content-Type', 'application/json')}}
                if body is not None:
                    event['body'] = body
                result = dispatch(event, None)
                return self.reply(result['statusCode'], json.loads(result['body']))
            except Exception:
                return self.reply(500, {'error': {'code': 'LOCAL_BACKEND_FAILED'}})
            finally:
                if self.command == 'POST':
                    busy.release()

        do_GET = handle_request
        do_POST = handle_request

    server = ThreadingHTTPServer(('127.0.0.1', port), LocalHandler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--frontend-port', type=int, default=4173)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535 or not 1 <= args.frontend_port <= 65535:
        parser.error('Invalid local port')
    if not initialize():
        return 1
    try:
        server = create_server(args.port, args.frontend_port)
    except OSError:
        print('Local backend could not bind its port. Stop the other server or choose another port.', flush=True)
        return 1
    print(f'Local backend ready: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def initialize():
    """Check client construction without model calls; keep exceptions out of logs."""
    try:
        get_orchestrator()
        return True
    except MissingDependencyException:
        print('Backend initialization needs the AWS CRT dependency. Run: python -m pip install "boto3[crt]"', flush=True)
    except Exception as error:
        print(f'Backend initialization failed ({type(error).__name__}). Check mode, region and SDK configuration.', flush=True)
    return False


if __name__ == '__main__':
    raise SystemExit(main())
