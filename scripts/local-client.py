"""Local Strata client selector. Never stops or switches a running server."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
PROFILES = [
    ("iq3_s", "qwen3.8-flash-next-iq3_s", "IQ3_S - balanced candidate"),
    ("unsloth-ud-iq4_xs", "qwen3.8-flash-next-unsloth-ud-iq4_xs", "UD-IQ4_XS - quality candidate"),
    ("iq2_xs", "qwen3.8-flash-next-iq2_xs", "IQ2_XS - smaller quant"),
    ("orca-iq2_xxs", "orcarouter-qwen3.8-flash-next-uncensored-iq2_xxs", "Orca IQ2_XXS - custom model"),
]
OPENCODE = Path("C:/ProgramData/chocolatey/lib/opencode/tools/opencode.exe")
BUN = Path("C:/nvm4w/nodejs/node_modules/bun/bin/bun.exe")
CLAUDE = HOME / ".local/bin/claude.orig.exe"
GLOBAL_CONFIG = HOME / ".config/opencode/opencode.json"
BASE_SETTINGS = HOME / ".claude/local-settings-strata.json"
GUIDE = ROOT / "docs/LOCAL-CLIENT-CONTEXT-RULES.md"
COMPACTION_PROMPT = (
    "Write a compact continuation handoff, preferably under 1200 tokens. "
    "Keep the user's goal, constraints, exact file paths, changes already made, "
    "test results, blockers, and the next concrete action. Do not copy earlier "
    "summaries verbatim, whole source files, tool logs, or repeated instructions. "
    "Merge repeated facts and retain unresolved issues. State which files were "
    "already read so the next agent does not repeatedly read the same files. "
    "Do not execute tools or continue the task; return only the handoff."
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def health() -> dict | None:
    try:
        # Bypass inherited HTTP proxies for this local-only request.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:8080/health", timeout=4) as response:
            value = json.load(response)
        return value if value.get("service") == "strata" else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def model_id(profile: tuple) -> str:
    config = ROOT / f"strata-{profile[0]}.json"
    return load_json(config).get("model_name", profile[1]) if config.exists() else profile[1]


def parse_args(argv: list[str]) -> tuple[str | None, bool, bool, list[str]]:
    selected = None
    check = False
    listing = False
    rest = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            rest.extend(argv[i + 1:])
            break
        if arg == "--local-model":
            i += 1
            if i == len(argv):
                raise ValueError("--local-model needs a model key (use --local-list).")
            selected = argv[i]
        elif arg.startswith("--local-model="):
            selected = arg.split("=", 1)[1]
        elif arg == "--local-check":
            check = True
        elif arg == "--local-list":
            listing = True
        else:
            rest.append(arg)
        i += 1
    return selected, check, listing, rest


def choose(selected: str | None, state: dict | None, interactive: bool) -> tuple | None:
    if selected:
        for profile in PROFILES:
            if selected in (profile[0], profile[1], model_id(profile)):
                return profile
        raise ValueError(f"Unknown local model: {selected}. Use --local-list.")
    if not interactive:
        for profile in PROFILES:
            if state and model_id(profile) == state.get("model"):
                return profile
        raise ValueError("No matching active server. Pass --local-model KEY.")
    print("\nStrata local models (one server/model at a time):")
    for i, profile in enumerate(PROFILES, 1):
        active = " [ACTIVE]" if state and model_id(profile) == state.get("model") else ""
        ready = "" if (ROOT / f"strata-{profile[0]}.json").exists() else " [SETUP NEEDED]"
        print(f"  {i}. {profile[2]}{active}{ready}")
    answer = input("Choose 1-4, Enter for the active model, or Q to quit: ").strip()
    if answer.lower() == "q":
        return None
    if not answer:
        return choose(None, state, False)
    if answer in ("1", "2", "3", "4"):
        return PROFILES[int(answer) - 1]
    raise ValueError("Invalid selection.")


def ensure_server(profile: tuple, state: dict | None) -> bool:
    wanted = model_id(profile)
    if state and state.get("loaded") and state.get("model") == wanted:
        return True
    print(f"Selected: {wanted}")
    if state:
        print(f"Server:   {state.get('model')} (loaded={state.get('loaded')})")
        print("Close the existing Strata server window before changing models.")
    else:
        print("Strata is not ready on http://127.0.0.1:8080.")
    print(f"Start:    {ROOT / ('run-' + profile[0] + '.bat')}")
    print("Then run this client command again. No running process was stopped.")
    return False


def budget(state: dict) -> dict:
    actual = int(state.get("max_context", 0))
    if actual < 32768:
        raise ValueError(f"Server context {actual} is too small for this coding profile (minimum 32768).")
    # Keep server headroom for tool schemas, tokenization differences and a large tool result.
    context = min(98304, actual - 16384)
    output = min(8192, context // 4)
    input_limit = context - min(16384, context // 3)
    reserved = min(16384, max(4096, input_limit // 4))
    threshold = max(4096, input_limit - reserved)
    return dict(context=context, input=input_limit, output=output, reserved=reserved, threshold=threshold)


def client_config(client: str, profile: tuple, state: dict) -> tuple[dict, dict, list[str]]:
    limits = budget(state)
    name = model_id(profile)
    env = dict(os.environ)
    if client.startswith("opencode"):
        live = load_json(GLOBAL_CONFIG)
        provider = live.get("provider", {}).get("strata")
        if not provider or name not in provider.get("models", {}):
            raise ValueError("Enable the Strata local provider in CC Switch first; it is absent from the live OpenCode config.")
        if provider.get("options", {}).get("baseURL") != "http://127.0.0.1:8080/v1":
            raise ValueError("Strata provider must point directly to http://127.0.0.1:8080/v1.")
        provider = copy.deepcopy(provider)
        for model in provider["models"].values():
            model["limit"] = {k: limits[k] for k in ("context", "input", "output")}
        config = {
            "$schema": "https://opencode.ai/config.json",
            "model": "strata/" + name,
            "small_model": "strata/" + name,
            "provider": {"strata": provider},
            "compaction": {"auto": True, "prune": True, "reserved": limits["reserved"],
                           "tail_turns": 2, "preserve_recent_tokens": 8192},
            "tool_output": {"max_lines": 200, "max_bytes": 12000},
            "instructions": [str(GUIDE)],
            "agent": {"compaction": {"prompt": COMPACTION_PROMPT}},
        }
        # Provider definitions still come from CC Switch's live config. The overlay only
        # adds per-process local-model limits; it never changes remote defaults.
        for key in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG_DIR",
                    "OPENCODE_DISABLE_AUTOCOMPACT", "OPENCODE_DISABLE_PRUNE"):
            env.pop(key, None)
        env["XDG_CONFIG_HOME"] = str(HOME / ".config")
        if client == "opencode-isolated":
            env["XDG_CONFIG_HOME"] = str(HOME / ".local/opencode-strata")
            env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "true"
        return config, env, [str(OPENCODE)]
    config = load_json(BASE_SETTINGS)
    settings_env = config.setdefault("env", {})
    settings_env.update({
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:8080",
        "ANTHROPIC_AUTH_TOKEN": "sk-strata-local",
        "ANTHROPIC_MODEL": name,
        "CLAUDE_CODE_SUBAGENT_MODEL": name,
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": str(limits["context"]),
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(limits["output"]),
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW": str(limits["input"]),
        "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "80",
        "CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT": "0",
        "DISABLE_AUTO_COMPACT": "0",
        "DISABLE_COMPACT": "0",
    })
    for family in ("SONNET", "OPUS", "HAIKU", "FABLE"):
        settings_env[f"ANTHROPIC_DEFAULT_{family}_MODEL"] = name
        settings_env[f"ANTHROPIC_DEFAULT_{family}_MODEL_NAME"] = name
    config["model"] = name
    env.update(settings_env)
    env["CLAUDE_CODE_EXECPATH"] = str(HOME / ".local/bin/claude.orig.exe")
    env["CLAUDE_CODE_PATH"] = env["CLAUDE_CODE_EXECPATH"]
    env["CLAUDE_CODE_GIT_BASH_PATH"] = "C:/Program Files/Git/bin/bash.exe"
    command = [str(CLAUDE)] if client == "claude" else [str(BUN), str(HOME / ".clawgod/cli.cjs")]
    command += ["--setting-sources", "project,local",
                "--strict-mcp-config", "--mcp-config", str(HOME / ".claude/context-mode-mcp.json"),
                "--effort", "low", "--append-system-prompt-file", str(GUIDE)]
    if client == "claude":
        command += ["--permission-mode", "default"]
    elif client == "clawgod":
        command += ["--dangerously-skip-permissions", "--allowedTools", "Bash(*)"]
    else:
        command += ["--tools", "Bash,Read,Edit,Write,Glob,Grep", "--allowedTools", "Bash(*)"]
    return config, env, command


def runtime_context(client: str, profile: tuple, state: dict) -> str:
    limits = budget(state)
    runtime = "Claude Code via claude.orig.exe" if client == "claude" else "clawgod CLI"
    return (
        "# Verified local runtime for this launch\n\n"
        f"Client application: {runtime}.\n"
        "Inference server: Strata (service=strata), NOT LM Studio.\n"
        "Anthropic-compatible base URL: http://127.0.0.1:8080.\n"
        f"Loaded model reported by /health at launch: {model_id(profile)}.\n"
        f"Server context: {state['max_context']} tokens; client budget: {limits['context']} tokens.\n"
        "The client application name is not the identity of the inference model. "
        "Describe yourself as a coding assistant in this client, backed by the local model above. "
        "Historical Claude-LM/LM Studio/port 8000 memories describe other launches, not this one. "
        "These facts were checked at launch; recheck /health if the server is later changed. "
        "List only skills/tools actually available in this session.\n\n"
        + GUIDE.read_text(encoding="utf-8")
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("claude", "clawgod", "clawgod-safe", "opencode", "opencode-isolated"):
        raise ValueError("Use local-client.py claude|clawgod|clawgod-safe|opencode|opencode-isolated [options].")
    client = argv.pop(0)
    selected, check, listing, rest = parse_args(argv)
    if listing:
        for profile in PROFILES:
            print(f"{profile[0]:23} {model_id(profile)}")
        print("Options: --local-model KEY, --local-check, --local-list. Other arguments go to the client.")
        return 0
    if rest in (["--version"], ["--help"], ["-h"]):
        if client == "claude":
            command = [str(CLAUDE)]
        else:
            command = [str(OPENCODE)] if client.startswith("opencode") else [str(BUN), str(HOME / ".clawgod/cli.cjs")]
        return subprocess.call(command + rest)
    if any(arg in ("-m", "--model", "--settings", "--setting-sources") or
           arg.startswith(("--model=", "--settings=", "--setting-sources=")) for arg in rest):
        raise ValueError("Use --local-model KEY instead of overriding this launcher's model/settings.")
    state = health()
    profile = choose(selected, state, not check and sys.stdin.isatty())
    if profile is None:
        return 0
    if not ensure_server(profile, state):
        return 3
    limits = budget(state)
    config, env, command = client_config(client, profile, state)
    print(f"Active model: {model_id(profile)}")
    print(f"Server context: {state['max_context']}; client budget: {limits['context']}; output: {limits['output']}")
    print(f"OpenCode compaction trigger: {limits['threshold']}; Claude/clawgod trigger approx: {int(limits['input'] * .8)}")
    print("Model selection here does not switch server weights. Restart this launcher after changing the server.")
    if check:
        print(f"Executable: {command[0]} (exists={Path(command[0]).exists()})")
        print("CHECK OK: no config written, no client started, no model request sent.")
        return 0
    if not Path(command[0]).exists():
        raise ValueError(f"Client executable not found: {command[0]}")
    runtime = HOME / ".local/strata-clients"
    runtime.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="run-", dir=runtime) as temp:
        path = Path(temp) / "settings.json"
        path.write_text(json.dumps(config, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        if client.startswith("opencode"):
            env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, ensure_ascii=True)
        else:
            context_path = Path(temp) / "runtime-context.md"
            context_path.write_text(runtime_context(client, profile, state), encoding="utf-8")
            command[command.index("--append-system-prompt-file") + 1] = str(context_path)
            command += ["--settings", str(path)]
        try:
            return subprocess.call(command + rest, env=env)
        except KeyboardInterrupt:
            return 130


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        print(f"Local client: {error}", file=sys.stderr)
        raise SystemExit(2)
