# Verification record: context-overflow recovery

Date: 2026-10-17. Local preparation only; no upstream submission.

## Server regression suite

```text
python -m unittest serve.test_context_overflow serve.test_server.MaxTokens serve.test_server.FitMaxTokens serve.test_responses serve.test_request_accounting serve.test_request_hardening
```

Result: **76 tests run, 75 passed, 1 skipped, no failures/errors** (25.385 seconds).

Coverage includes Messages, Chat Completions and Responses; streaming-requested errors before SSE starts; one/zero-token room; fitting enabled/disabled; accurate input/output/slack/excess accounting; non-context errors; valid retries after reducing input or output.

MockEngine only: no GPU benchmark and no large requests sent to the active model.

## Installed clients against a synthetic loopback endpoint

Test script: `scripts/probe_context_recovery.py`.

Clients: native Claude Code 2.1.296 (`claude.orig.exe`); clawgod 2.1.0, patched CLI source 2.1.296.

Isolation: temporary working/config directories, `--bare`, no hooks, no tools, empty MCP config, no session persistence, placeholder local auth. Requests captured only as counts/sizes; no user conversations. clawgod's wrapper printed an update-available notice, so this is not claimed as a complete process-wide network sandbox; the captured inference requests were to the loopback fixture.

Fixture limitation: reports **synthetic** token counts in its 400 error; the actual test input is small. Subsequent replies are fixed `PROBE_OK`, including the summary reply. This tests client control flow, not real tokenizer accuracy or summary quality.

### Two-turn experiment

The first request succeeds. The second request returns one selected error. Later requests receive a valid small response.

| Runtime | Error message | Message counts by request | compact_boundary | Summary handoff | Exit |
|---|---|---|---|---|---|
| native | Current upstream `request exceeds the context window` | 1, 3, 3 | no | no | 0 |
| clawgod | Current upstream text | 1, 3, 3 | no | no | 0 |
| native | `prompt is too long: N tokens > M ...` | 1, 3, 3, 1 | yes | yes | 0 |
| clawgod | Same prompt-too-long prefix | 1, 3, 3, 1 | yes | yes | 0 |
| native | `input length and \`max_tokens\` exceed context limit` | 1, 3, 3, 1 | yes | yes | 0 |
| clawgod | Same output-budget prefix | 1, 3, 3, 1 | yes | yes | 0 |

For the new wording, the real clients emitted compaction boundary/continuation events and issued another inference request after summarization. The fake summary was not assessed for usefulness.

**Important:** the old wording also caused a compatibility re-send, but no compaction was observed. Its exit=0 is not evidence it would recover from a persistent real overflow: the fixture accepts later calls regardless of size. Do not claim the old client never retries.

**Output-budget errors:** in this fixture both clients chose compaction; max_tokens stayed 8192. Do not claim a verified automatic decrease to the advertised available_output_tokens.

### Single-turn experiment

- Native and clawgod with the prompt-too-long prefix: one request, terminal_reason=prompt_too_long, clear explanation that a single exchange cannot be compacted and system/tools/attachments may dominate input.
- Native with output-budget prefix: same single-exchange compaction limitation.
- Native with old text: a compatibility resend, no demonstrated history compaction.

This is expected evidence for honest failure rather than an unlimited retry promise.

## Reproduction

From any shell, invoke the script with the local Python, e.g.:

```text
python -I scripts/probe_context_recovery.py --runtime native --case prompt --multi-turn
python -I scripts/probe_context_recovery.py --runtime clawgod --case prompt --multi-turn
python -I scripts/probe_context_recovery.py --runtime native --case old --multi-turn
python -I scripts/probe_context_recovery.py --runtime native --case budget --multi-turn
```

The script is a local verification aid, not included in the two-file upstream patch; it assumes the locally installed executable paths. A portable public fixture is follow-up work if maintainers want it.

## Patch isolation

`context-overflow.patch` contains only:

- `serve/server.py`: helper + error construction in existing rejection branches.
- `serve/test_context_overflow.py`: regression assertions/tests.

Verified:

- clean `git apply --check` on pristine HEAD copies;
- original admission/fitting AST identical after normalizing the raised error expression;
- local `stream_tools=False` patch excluded;
- no personal paths, credentials, model files, or crash dumps included.

No commit, push, issue comment or PR has been published. Runtime Strata still needs a controlled restart to load changed Python code.
