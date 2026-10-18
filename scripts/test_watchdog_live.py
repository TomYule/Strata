"""Smoke test the actual OpenCode server/plugin without calling an LLM.

Uses a temporary config/project and a new, empty test session. No user session is
aborted. Stops only the server process created by this test.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EXE = "C:/ProgramData/chocolatey/lib/opencode/tools/opencode.exe"


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="opencode-watchdog-test-") as temp:
        base = Path(temp)
        config_home = base / "config"
        (config_home / "opencode").mkdir(parents=True)
        module = (ROOT / "scripts/opencode-watchdog/plugin.mjs").as_uri()
        cfg = {"$schema": "https://opencode.ai/config.json", "plugin": [module],
               "permission": {"*": "allow"}}
        (config_home / "opencode/opencode.json").write_text(json.dumps(cfg), encoding="utf-8")
        env = dict(os.environ)
        for key in ["OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG_DIR", "OPENCODE_SERVER_PASSWORD"]:
            env.pop(key, None)
        env.update(XDG_CONFIG_HOME=str(config_home), OPENCODE_DISABLE_PROJECT_CONFIG="true",
                   OPENCODE_DISABLE_AUTOUPDATE="true")
        url = f"http://127.0.0.1:{port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def request(path, data=None):
            req = urllib.request.Request(url + path, data=None if data is None else json.dumps(data).encode(),
                                         headers={"Content-Type": "application/json"})
            with opener.open(req, timeout=60) as response:
                return json.load(response)
        with (base / "server.log").open("wb") as log:
            proc = subprocess.Popen([EXE, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
                                    cwd=base, env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL)
            try:
                for _ in range(80):
                    if proc.poll() is not None:
                        raise RuntimeError("Test server exited during startup")
                    try:
                        request("/global/health")
                        break
                    except OSError:
                        time.sleep(.25)
                else:
                    raise RuntimeError("Test server did not become ready")
                session = request("/session", {"title": "Watchdog plugin smoke test (no LLM)"})
                sid = session["id"]
                print("Test session:", sid)
                result = request(f"/session/{sid}/shell", {"agent": "build", "command": "echo WATCHDOG_SMOKE_OK"})
                print("Shell response type:", type(result).__name__)
                messages = request(f"/session/{sid}/message")
                tools = [p for m in messages for p in m.get("parts", []) if p.get("type") == "tool"]
                print("Shell tool states:", [(p.get("tool"), p.get("state", {}).get("status")) for p in tools])
                # Verify the same read-only status routes used at checkpoints.
                if tools:
                    mid = tools[0]["messageID"]
                    detail = request(f"/session/{sid}/message/{mid}")
                    print("Message status API:", [p.get("state", {}).get("status") for p in detail.get("parts", []) if p.get("type") == "tool"])
                statuses = request("/session/status")
                print("Session status API:", statuses.get(sid, {"type": "idle"}))
                time.sleep(.2)
                watchdog_log = Path.home() / ".local/state/opencode/tool-watchdog.jsonl"
                records = [json.loads(line) for line in watchdog_log.read_text(encoding="utf-8").splitlines()]
                relevant = [x for x in records if x.get("sessionID") == sid or x.get("directory") == str(base)]
                print("Plugin events:", [(x.get("kind"), x.get("tool")) for x in relevant])
                assert any(x.get("kind") == "loaded" for x in relevant), "plugin did not load"
                assert any(x.get("kind") == "started" for x in relevant), "plugin did not receive tool events"
                assert any(x.get("kind") == "finished" for x in relevant), "plugin did not observe completion"
                print("PASS: actual server loaded plugin; shell lifecycle and read-only status APIs worked; no model request.")
            except Exception:
                log.flush()
                text = (base / "server.log").read_text(encoding="utf-8", errors="replace")
                print("Test server diagnostics:", text[-7000:])
                raise
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait(timeout=5)
        text = (base / "server.log").read_text(encoding="utf-8", errors="replace")
        errors = [line[:500] for line in text.splitlines() if "ERROR" in line or "error:" in line.lower()]
        print("Server errors:", errors[-5:])


if __name__ == "__main__":
    main()
