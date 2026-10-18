"""Apply context safeguards to ordinary OpenCode, preserving all provider settings."""
import datetime
import json
from pathlib import Path
import shutil


def apply(config: dict) -> dict:
    result = json.loads(json.dumps(config))
    rules = str(Path(__file__).resolve().parents[1] / "docs/OPENCODE-CONTEXT-RULES.md")
    instructions = result.setdefault("instructions", [])
    if rules not in instructions:
        instructions.append(rules)
    result.setdefault("tool_output", {}).update(max_lines=200, max_bytes=12000)
    result.setdefault("compaction", {}).update(auto=True, prune=True, tail_turns=2, preserve_recent_tokens=8192)
    # Do not set a global reserved token count: remote models keep their default,
    # while the Strata provider's input/output limits trigger around 64K.
    result.setdefault("agent", {}).setdefault("compaction", {})["prompt"] = (
        "Write a concise continuation handoff, preferably under 1200 tokens. "
        "Preserve the user's goal, constraints, exact paths, changes, test results, "
        "blockers and next action. Merge repeated facts. Do not copy previous "
        "summaries, whole files or tool output verbatim. List files already checked "
        "to prevent repeated exploration. Return only the handoff; do not continue the task."
    )
    return result


def main():
    path = Path.home() / ".config/opencode/opencode.json"
    original = json.loads(path.read_text(encoding="utf-8-sig"))
    updated = apply(original)
    if updated == original:
        print("OpenCode safeguards already applied.")
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(path.name + ".bak-tool-stall-" + stamp)
    shutil.copy2(path, backup)
    temp = path.with_name(path.name + ".tmp-tool-stall")
    temp.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)
    print(f"Backup: {backup}")
    print("Ordinary OpenCode safeguards applied. Restart OpenCode to load them.")
    print("Providers, credentials, default models, permissions and plugins were preserved.")
    print("This is context mitigation, not a proven fix for the stuck tool lifecycle.")


if __name__ == "__main__":
    main()
