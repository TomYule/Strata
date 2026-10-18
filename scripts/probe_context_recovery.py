"""Real CLI recovery probe against a loopback-only fake Anthropic endpoint.

No model inference, tool execution, saved user sessions or cloud credentials.
The first Messages request receives the chosen overflow; later requests get a
small valid response. Counts are synthetic to exercise client recovery only.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = Path.home()


def probe(runtime, case, multi_turn=False):
    requests = []
    lock = threading.Lock()
    messages = {
        "old": "request exceeds the context window: prompt (150722 tokens) leaves no room to answer in the context (131072); requests are never truncated",
        "prompt": "prompt is too long: 150722 tokens > 131063 maximum input tokens with 1 output token and 8 safety tokens reserved. request exceeds the context window; input_tokens=150722, context_limit_tokens=131072, excess_tokens=19659",
        "budget": "input length and `max_tokens` exceed context limit: request exceeds the context window; input_tokens=125000, requested_output_tokens=8192, safety_tokens=8, context_limit_tokens=131072, excess_tokens=2128, available_output_tokens=6064. Retry with max_tokens <= 6064.",
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def json_response(self, status, obj):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.json_response(200, {"data": [], "has_more": False})

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError):
                self.json_response(400, {"error": {"type": "invalid_request_error", "message": "probe expected JSON"}})
                return
            if self.path.split('?')[0].endswith('/count_tokens'):
                self.json_response(200, {"input_tokens": 100})
                return
            if self.path.split('?')[0] != '/v1/messages':
                self.json_response(200, {})
                return
            with lock:
                requests.append({"max_tokens": body.get("max_tokens"), "message_count": len(body.get("messages", [])),
                                 "body_bytes": len(raw), "stream": body.get("stream")})
                index = len(requests)
            if index == (2 if multi_turn else 1):
                self.json_response(400, {"type": "error", "error": {"type": "invalid_request_error", "message": messages[case]}})
                return
            if index > 8:
                self.json_response(400, {"type": "error", "error": {"type": "invalid_request_error", "message": "probe request cap reached"}})
                return
            message = {"id": "msg_probe", "type": "message", "role": "assistant", "model": "strata-probe",
                       "content": [{"type": "text", "text": "PROBE_OK"}], "stop_reason": "end_turn",
                       "stop_sequence": None, "usage": {"input_tokens": 100, "output_tokens": 3}}
            if not body.get("stream"):
                self.json_response(200, message)
                return
            start = dict(message, content=[], stop_reason=None, usage={"input_tokens": 100, "output_tokens": 0})
            events = [
                ("message_start", {"type": "message_start", "message": start}),
                ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "PROBE_OK"}}),
                ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 3}}),
                ("message_stop", {"type": "message_stop"}),
            ]
            data = ''.join(f'event: {name}\ndata: {json.dumps(event)}\n\n' for name, event in events).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='strata-cli-probe-') as tmp:
            env = dict(os.environ)
            for key in list(env):
                if key.startswith(('ANTHROPIC_', 'CLAUDE_', 'CLAWGOD_')) or key in ('CLAUDECODE', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
                    env.pop(key, None)
            settings_env = {
                'ANTHROPIC_BASE_URL': f'http://127.0.0.1:{httpd.server_port}',
                'ANTHROPIC_AUTH_TOKEN': 'local-probe-only', 'ANTHROPIC_MODEL': 'strata-probe',
                'CLAUDE_CODE_MAX_CONTEXT_TOKENS': '131072', 'CLAUDE_CODE_MAX_OUTPUT_TOKENS': '8192',
                'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'DISABLE_AUTOUPDATER': '1',
                'CLAUDE_CODE_MAX_RETRIES': '0',
            }
            env.update(settings_env)
            env['CLAUDE_CONFIG_DIR'] = str(Path(tmp)/'config')
            env['NO_PROXY'] = '127.0.0.1,localhost'
            settings = Path(tmp)/'settings.json'
            settings.write_text(json.dumps({'env': settings_env, 'model': 'strata-probe', 'disableAllHooks': True}), encoding='utf-8')
            mcp = Path(tmp)/'mcp.json';mcp.write_text('{"mcpServers":{}}')
            command = [str(HOME/'.local/bin/claude.orig.exe')] if runtime == 'native' else [
                'C:/nvm4w/nodejs/node_modules/bun/bin/bun.exe', str(HOME/'.clawgod/cli.cjs')]
            command += ['--bare', '--setting-sources', '', '--settings', str(settings), '--strict-mcp-config',
                        '--mcp-config', str(mcp), '--tools', '', '--no-session-persistence',
                        '--system-prompt', 'You are a local test assistant. Reply briefly.',
                        '--model', 'strata-probe', '--effort', 'low', '-p', 'Reply PROBE_OK.', '--output-format', 'json']
            input_text = None
            if multi_turn:
                command[command.index('-p') + 1] = ''
                command[command.index('--output-format') + 1] = 'stream-json'
                command += ['--input-format', 'stream-json', '--verbose']
                input_text = '\n'.join(json.dumps({'type': 'user', 'message': {'role': 'user', 'content': text}})
                                       for text in ['Remember this synthetic test fact: alpha.', 'Now recall the synthetic fact.']) + '\n'
            try:
                result = subprocess.run(command, input=input_text, env=env, cwd=tmp, capture_output=True, text=True,
                                        encoding='utf-8', errors='replace', timeout=50)
                return {'runtime': runtime, 'case': case, 'multi_turn': multi_turn, 'exit': result.returncode, 'requests': requests,
                        'compact_boundary_seen': '"subtype":"compact_boundary"' in result.stdout,
                        'summary_handoff_seen': 'before compaction' in result.stdout,
                        'stdout': result.stdout[-2500:], 'stderr': result.stderr[-1200:]}
            except subprocess.TimeoutExpired:
                return {'runtime': runtime, 'case': case, 'timeout': True, 'requests': requests}
    finally:
        httpd.shutdown(); httpd.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', choices=['native', 'clawgod'], default='native')
    parser.add_argument('--case', choices=['old', 'prompt', 'budget'], default='prompt')
    parser.add_argument('--multi-turn', action='store_true')
    args = parser.parse_args()
    print(json.dumps(probe(args.runtime, args.case, args.multi_turn), ensure_ascii=True, indent=2))
