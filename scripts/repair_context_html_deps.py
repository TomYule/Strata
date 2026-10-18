"""Repair only missing HTML conversion packages from the existing Bun cache.

No network, lifecycle scripts, package upgrades or changes to package.json.
"""
from pathlib import Path
import json
import shutil

home = Path.home()
root = home / '.claude/plugins/cache/context-mode/context-mode/1.0.169'
cache = home / '.bun/install/cache'
packages = [('turndown', '7.2.4', 'lib/turndown.cjs.js'),
            ('turndown-plugin-gfm', '1.0.2', 'lib/turndown-plugin-gfm.cjs.js'),
            ('@mixmark-io/domino', '2.2.0', 'lib/index.js')]
for name, version, entry in packages:
    source = cache / (name + '@' + version + '@@@1')
    metadata = json.loads((source / 'package.json').read_text(encoding='utf-8'))
    if metadata.get('name') != name or metadata.get('version') != version or not (source / entry).exists():
        raise SystemExit(f'Cache validation failed for {name}')
    target = root / 'node_modules' / name
    if target.exists():
        print(f'Already exists, left unchanged: {target}')
        continue
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('node_modules', '.git'))
    print(f'Restored {name}@{version} to {target}')
print('Restart/reconnect context-mode if an existing process cached the import failure.')
