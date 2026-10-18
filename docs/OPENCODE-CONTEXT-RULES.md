# OpenCode context and tool recovery rules

Use the user's language. These rules apply to both local and remote models.

- Locate symbols first, then read bounded ranges (normally 80-200 lines).
- Do not repeatedly read unchanged files or the complete saved output of a truncated command. Search the saved output for the relevant section.
- Keep a short record of files checked, conclusions, changes, test results and next action. Preserve this during compaction instead of copying large logs or previous summaries.
- When using Strata, allow for a smaller context and slower cold prefill. Do not increase concurrent requests to compensate.
- A printed command result does not prove that the tool process has completed. If a command exceeds its requested timeout without returning, report a tool lifecycle problem rather than claiming it is still model thinking.
- OpenCLI browser work requires a connected bridge. If doctor reports a missing extension, stop browser actions and ask the user to connect it; code inspection can continue independently.
- Do not run a repeated doctor/restart loop. A healthy daemon should be reused. Do not restart a daemon or terminate processes that may serve another active task without confirmation.
- After an interrupted tool, check whether its side effects occurred before retrying. Never mark an unfinished tool successful by editing the session database.

- For Strata-backed web search, use the verified OpenCLI alternatives: `opencli google search "QUERY" --limit 5 -f json` (preferred), or `opencli brave search "QUERY" --limit 5 -f json` (currently cleaner original URLs). Send public search terms only, not private code/secrets/transcripts. Google redirect URLs need destination verification before citing them as original sources.
- DuckDuckGo currently requires manual human verification on this profile. Do not automatically retry it. Stop any provider showing CAPTCHA/rate limits; report the blocker instead of bypassing it or calling the response zero results. No search platform is guaranteed CAPTCHA-free.

These are behavior guidelines, not permission grants or hard execution limits.
