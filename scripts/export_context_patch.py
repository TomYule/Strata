"""Export only the overflow helper/call sites and their tests, never local patches."""
import ast
import difflib
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/contributions/context-overflow.patch'


def head(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', 'HEAD:' + path]).decode('utf-8')


def export():
    before = head('serve/server.py')
    local = (ROOT / 'serve/server.py').read_text(encoding='utf-8')
    tree = ast.parse(local)
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'context_overflow_message')
    helper_source = ast.get_source_segment(local, helper)
    after = before.replace('def _timeout_env(', helper_source + '\n\n\ndef _timeout_env(', 1)
    start = '        room = ctx - CTX_SLACK - len(ids)\n'
    a = before.index(start); b = before.index('        if images:\n', a)
    x = local.index(start); y = local.index('        if images:\n', x)
    old_block, new_block = before[a:b], local[x:y]
    after = after.replace(old_block, new_block, 1)
    # Assert only error construction changed, not admission/fitting logic.
    def normalized(block):
        node = ast.parse('def check():\n' + block)
        for item in ast.walk(node):
            if isinstance(item, ast.Raise):
                item.exc = ast.Call(func=ast.Name(id='ValueError', ctx=ast.Load()), args=[ast.Constant(value='overflow')], keywords=[])
        return ast.dump(node, include_attributes=False)
    assert normalized(old_block) == normalized(new_block), 'admission logic changed'
    files = {'serve/server.py': (before, after),
             'serve/test_context_overflow.py': (head('serve/test_context_overflow.py'), (ROOT/'serve/test_context_overflow.py').read_text(encoding='utf-8'))}
    patch = ''.join(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                            fromfile='a/'+name, tofile='b/'+name)) for name, (old, new) in files.items())
    assert 'stream_tools=False' not in patch
    assert 'Administrator' not in patch and '.dmp' not in patch
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(patch, encoding='utf-8', newline='\n')
    # Apply-check against pristine HEAD files in a disposable non-repository tree.
    with tempfile.TemporaryDirectory(prefix='strata-patch-check-') as tmp:
        root = Path(tmp)
        for name, (old, _) in files.items():
            p = root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(old, encoding='utf-8', newline='\n')
        subprocess.run(['git', 'apply', '--check', str(OUT)], cwd=tmp, check=True)
    print('Exported:', OUT)
    print('PASS: clean apply; admission AST unchanged; unrelated streaming patch excluded.')
    print('Files: serve/server.py, serve/test_context_overflow.py')


if __name__ == '__main__':
    export()
