"""Install only claude-s; do not touch CC Switch or other launchers."""
from pathlib import Path
import datetime
import shutil

root = Path(__file__).resolve().parents[1]
target = Path.home() / ".local/bin/claude-s.cmd"
exe = target.with_name("claude.orig.exe")
if not exe.is_file():
    raise SystemExit(f"Native Claude executable not found: {exe}")
text = ('@echo off\r\nsetlocal\r\n'
        'rem Native Claude with local Strata selection; no clawgod runtime.\r\n'
        f'"{root / ".venv/Scripts/python.exe"}" -I "{root / "scripts/local-client.py"}" claude %*\r\n'
        'exit /b %ERRORLEVEL%\r\n').encode('ascii')
if target.exists() and target.read_bytes() != text:
    backup = target.with_name(target.name + '.bak-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    shutil.copy2(target, backup)
    print(f"Backup: {backup}")
target.write_bytes(text)
print(f"Installed: {target}")
print(f"Runtime: {exe}")
print("Uses clawgod-s local model/menu/context settings, with Claude's default permission checks.")
