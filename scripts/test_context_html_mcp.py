"""Exercise the installed context-mode MCP fetch tool via stdio, outside the CLI classifier."""
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

home = Path.home()
plugin = home / '.claude/plugins/cache/context-mode/context-mode/1.0.169'
with tempfile.TemporaryDirectory(prefix='context-html-smoke-') as tmp:
    env = dict(os.environ)
    env['CONTEXT_MODE_DIR'] = tmp
    proc = subprocess.Popen(['C:/nvm4w/nodejs/node_modules/bun/bin/bun.exe', str(plugin / 'server.bundle.mjs')],
                            cwd=tmp, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    output = queue.Queue()
    def drain(stream, kind):
        for line in stream:
            output.put((kind, line))
    threading.Thread(target=drain, args=(proc.stdout, 'out'), daemon=True).start()
    threading.Thread(target=drain, args=(proc.stderr, 'err'), daemon=True).start()
    def send(method, params, ident=None):
        body = {'jsonrpc': '2.0', 'method': method, 'params': params}
        if ident is not None:
            body['id'] = ident
        proc.stdin.write(json.dumps(body) + '\n'); proc.stdin.flush()
    def receive(ident, seconds=45):
        deadline = time.monotonic() + seconds
        errors = []
        while time.monotonic() < deadline:
            try:
                kind, line = output.get(timeout=1)
            except queue.Empty:
                if proc.poll() is not None:
                    raise RuntimeError('MCP exited: ' + ''.join(errors)[-1000:])
                continue
            if kind == 'err':
                errors.append(line); continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if data.get('id') == ident:
                return data
        raise TimeoutError('MCP response timeout: ' + ''.join(errors)[-1000:])
    try:
        send('initialize', {'protocolVersion':'2024-11-05', 'capabilities':{}, 'clientInfo':{'name':'html-repair-smoke','version':'1'}}, 1)
        result = receive(1); assert 'result' in result, result
        send('notifications/initialized', {})
        send('tools/list', {}, 2)
        tools = receive(2)['result']['tools']
        name = next(t['name'] for t in tools if t['name'].endswith('fetch_and_index'))
        send('tools/call', {'name':name, 'arguments':{'url':'https://example.com','source':'HTML repair smoke','force':True}}, 3)
        result = receive(3)
        print(json.dumps(result, ensure_ascii=True)[:5500])
        assert 'error' not in result and not result.get('result',{}).get('isError'), 'MCP fetch failed'
        print('PASS: installed MCP HTML fetch/index completed without missing dependency errors.')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=5)
