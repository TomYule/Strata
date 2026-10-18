"""Install the same watchdog in ordinary and isolated OpenCode; no provider changes."""
from pathlib import Path
import datetime
import shutil

root = Path(__file__).resolve().parents[1]
module = (root / "scripts/opencode-watchdog/plugin.mjs").as_uri()
text = "// Ten-minute lifecycle guard; pauses for human approval/questions.\nexport { default } from '" + module + "';\n"
for base in [Path.home() / ".config/opencode", Path.home() / ".local/opencode-strata/opencode"]:
    target = base / "plugins/00-tool-watchdog.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_text(encoding="utf-8") == text:
            print(f"Already installed: {target}")
            continue
        backup = target.with_suffix(".ts.bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(target, backup)
        print(f"Backup: {backup}")
    target.write_text(text, encoding="utf-8")
    print(f"Installed: {target}")
print("Restart OpenCode to load the 600-second watchdog. Existing sessions/processes were not interrupted.")
