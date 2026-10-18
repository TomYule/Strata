"""Back up and register the local Strata provider without touching remote providers.

Run with Strata's Python using -I. JSON files are merged, not replaced wholesale.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
PROVIDER = {
    "name": "Strata local - select backend first",
    "npm": "@ai-sdk/openai-compatible",
    "options": {"baseURL": "http://127.0.0.1:8080/v1", "apiKey": "sk-strata-local"},
    "models": {},
}
for key, name in [
    ("qwen3.8-flash-next-iq3_s", "Qwen IQ3_S (start matching Strata server)"),
    ("qwen3.8-flash-next-unsloth-ud-iq4_xs", "Qwen UD-IQ4_XS (start matching Strata server)"),
    ("qwen3.8-flash-next-iq2_xs", "Qwen IQ2_XS (start matching Strata server)"),
    ("orcarouter-qwen3.8-flash-next-uncensored-iq2_xxs", "Orca IQ2_XXS (start matching Strata server)"),
]:
    PROVIDER["models"][key] = {
        "name": name,
        "limit": {"context": 98304, "input": 73728, "output": 8192},
        "modalities": {"input": ["text"], "output": ["text"]},
    }


def main() -> int:
    global_path = HOME / ".config/opencode/opencode.json"
    isolated_path = HOME / ".local/opencode-strata/opencode/opencode.json"
    db_path = HOME / ".cc-switch/cc-switch.db"
    if not global_path.exists() or not db_path.exists():
        raise RuntimeError("Existing OpenCode config / CC Switch database not found.")
    live = json.loads(global_path.read_text(encoding="utf-8-sig"))
    if "strata" in live.get("provider", {}) and live["provider"]["strata"] != PROVIDER:
        raise RuntimeError("A different live 'strata' provider already exists; not overwriting it.")
    with sqlite3.connect(db_path) as db:
        existing = db.execute("SELECT settings_config FROM providers WHERE id='strata' AND app_type='opencode'").fetchone()
        if existing and json.loads(existing[0]) != PROVIDER:
            raise RuntimeError("A different CC Switch 'strata' provider already exists; not overwriting it.")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = HOME / ".cc-switch/backups" / ("strata-clients-" + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    targets = {
        "opencode-global.json": global_path,
        "opencode-isolated.json": isolated_path,
        "clawgod-s.cmd": HOME / ".local/bin/clawgod-s.cmd",
        "clawgod-ss.cmd": HOME / ".local/bin/clawgod-ss.cmd",
        "opencode-s.cmd": HOME / ".local/bin/opencode-s.cmd",
        "opencode-s-isolated.cmd": HOME / ".local/bin/opencode-s-isolated.cmd",
    }
    for name, path in targets.items():
        if path.exists():
            shutil.copy2(path, backup / name)
    with sqlite3.connect(db_path) as db, sqlite3.connect(backup / "cc-switch.db") as snap:
        db.backup(snap)
    (backup / "restore-map.json").write_text(json.dumps({k: str(v) for k, v in targets.items()}, indent=2), encoding="utf-8")
    # CC Switch stores OpenCode providers as raw provider blocks. Its current CLI
    # set-current handler expects a different envelope, so do not use it here.
    with sqlite3.connect(db_path) as db:
        existing = db.execute("SELECT settings_config FROM providers WHERE id='strata' AND app_type='opencode'").fetchone()
        if existing and json.loads(existing[0]) != PROVIDER:
            raise RuntimeError("A different CC Switch 'strata' provider already exists; not overwriting it.")
        db.execute(
            "INSERT OR IGNORE INTO providers (id,app_type,name,settings_config,created_at,meta,is_current,notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            ("strata", "opencode", "Strata local (4 models)", json.dumps(PROVIDER, ensure_ascii=False),
             int(datetime.datetime.now().timestamp() * 1000), json.dumps({"liveConfigManaged": True}), 0,
             "Local 8080 supports one loaded model. Select matching backend first; opencode-s verifies health. "
             "Client budget 96K, output 8K, conservative compaction. No cloud endpoint."),
        )
    providers = live.setdefault("provider", {})
    if "strata" in providers and providers["strata"] != PROVIDER:
        raise RuntimeError("A different live 'strata' provider already exists; not overwriting it.")
    providers["strata"] = PROVIDER
    global_path.write_text(json.dumps(live, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Minimal fallback reads the same registered provider at runtime; no second
    # hand-maintained model list. Ordinary launch still uses the global config.
    isolated_path.parent.mkdir(parents=True, exist_ok=True)
    isolated_path.write_text('{"$schema":"https://opencode.ai/config.json"}\n', encoding="utf-8")
    python = ROOT / ".venv/Scripts/python.exe"
    helper = ROOT / "scripts/local-client.py"
    for filename, mode in [("opencode-s.cmd", "opencode"), ("opencode-s-isolated.cmd", "opencode-isolated"),
                           ("clawgod-s.cmd", "clawgod"), ("clawgod-ss.cmd", "clawgod-safe")]:
        target = HOME / ".local/bin" / filename
        if target.exists() and filename not in targets:
            shutil.copy2(target, backup / filename)
        text = ("@echo off\r\nsetlocal\r\nrem Local model selector; CC Switch owns the OpenCode provider.\r\n"
                f'"{python}" -I "{helper}" {mode} %*\r\nexit /b %ERRORLEVEL%\r\n')
        target.write_bytes(text.encode("ascii"))
    print(f"Backup: {backup}")
    print("Registered CC Switch OpenCode provider: strata (4 models).")
    print("Existing remote defaults, plugins and other providers were preserved.")
    print("Installed: opencode-s, opencode-s-isolated, clawgod-s, clawgod-ss.")
    print("No server was stopped or started. Restart CC Switch to refresh its provider list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
