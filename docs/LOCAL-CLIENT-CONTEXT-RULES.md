# Local coding context discipline

Use the user's language. This is a local single-model service, not an unlimited-context cloud model.

- Search for a symbol/path first. Read the relevant 80-200 lines, not entire large files.
- Do not repeat an unchanged read. Keep a short file/range/findings index and reuse it after compaction.
- For long logs/tests, process locally and return counts, failing cases and a small excerpt. Keep full output on disk.
- Do not read a complete saved tool-output file after truncation; search or read a bounded range.
- For multi-file tasks, keep a short task handoff file when useful: goal, constraints, files already checked, changes, test results, blockers and next action. Do not copy whole transcripts into it.
- Before compaction, preserve exact identifiers and unresolved work, not long source code or repeated summaries.
- After compaction, continue from the saved next action rather than re-exploring every file.
- If the same reads or compactions repeat without progress, stop the loop and explain the blocker. Ask for a fresh session with the concise handoff instead of retrying the same oversized request.
- Keep searches and tool outputs narrow. Extra thinking, subagents and concurrent requests are not a substitute for limiting input size.

- This local Strata server does not implement Anthropic hosted WebSearch. An empty built-in WebSearch response is not evidence of zero matches. Use a separately configured search MCP/CLI only after verifying it works; if unavailable, report that search is unavailable. Fetching a known URL with context-mode is not a replacement for discovering search results.
- Infer the current endpoint from this launch's runtime configuration and health check, not from global settings.json or an old memory. A global CC Switch endpoint can coexist with this process's direct Strata endpoint.

- Verified on 2026-10-17: `opencli google search "QUERY" --limit 5 -f json` and `opencli brave search "QUERY" --limit 5 -f json` returned real results. Prefer Google; Brave is an independent alternative and currently returns cleaner original URLs. Keep queries public and minimal; do not send private source code, secrets, or session text to search engines. Google redirect URLs are not verified original URLs: use Brave or verify the destination before citing it.
- DuckDuckGo currently presents a human-verification challenge on this browser profile; do not automatically retry it. No provider is guaranteed CAPTCHA-free. Stop a challenged/rate-limited provider and report it; do not automate challenges, rotate identities, or retry in a loop. Use only an explicitly chosen independent alternative.
- These OpenCLI search adapters require a working browser bridge on this installation. Keeping Surfingkeys disabled restored attach in the verified test; if attach fails again, diagnose it rather than claiming zero search results.

These instructions guide behavior; they do not enforce a hard token limit or grant extra permissions.
