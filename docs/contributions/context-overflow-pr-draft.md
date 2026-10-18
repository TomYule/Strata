# PR draft — not submitted

## Title

fix(serve): recognize Claude context overflow and report exact token budgets

## Summary

Follow-up to #1615: the existing `request exceeds the context window` wording works for Pi, as confirmed there. Claude Code's HTTP-400 classification also depends on provider-specific phrases. This change distinguishes:

- input with no room for even one output token: `prompt is too long: N tokens > M ...`;
- input that fits but whose requested completion does not: `input length and \`max_tokens\` exceed context limit`.

Both retain `request exceeds the context window`, the no-truncation policy, and actionable fitting guidance.

The message reports actual encoded input length, requested/required output, the existing eight-token safety margin, required total, real context capacity, excess tokens and available output. For a prompt-only error, the parsed maximum-input figure explicitly reserves one output token plus the safety margin; the full context capacity is also reported separately.

## Scope

- Error construction only; original admission/fitting control flow is retained.
- HTTP 400, `invalid_request_error`, and the existing JSON envelope stay unchanged.
- No automatic server retries, prompt truncation, summarization, new dependencies or default configuration changes.
- Only `serve/server.py` and `serve/test_context_overflow.py` belong in this patch.

## Validation

- 76 tests run, 75 passed, one skipped; no failures/errors:
  `python -m unittest serve.test_context_overflow serve.test_server.MaxTokens serve.test_server.FitMaxTokens serve.test_responses serve.test_request_accounting serve.test_request_hardening`
- CPU-only HTTP tests cover all three API surfaces, requested streaming on/off, fitting on/off, exact accounting and context boundaries. Refused requests do not reach generation.
- Admission/fitting AST comparison is identical after normalizing raised-error expressions.
- Isolated real-client fixture: native Claude Code 2.1.296 and clawgod 2.1.0 (CLI source 2.1.296). A two-turn conversation receives one synthetic overflow, followed by deterministic valid responses. Both new prefixes result in a compaction boundary, summary handoff and a subsequent inference request. The old message triggers a compatibility resend but no observed compaction.
- Single-exchange requests with the new prompt prefix report `prompt_too_long` and explain that the exchange cannot be compacted; no promise of recovery when system/tools/attachments dominate input.

## Limits

The client fixture uses synthetic counts and a fixed summary reply; it establishes control flow, not real long-context summarization quality. Both tested clients compacted the output-budget case; no automatic lowering of max_tokens was observed. No GPU/performance claim. This does not solve unrelated tool lifecycle stalls or make context unbounded.

## Review notes

Please confirm whether preserving the legacy envelope with detailed message fields is preferred to a future structured error extension. This proposal intentionally avoids bundling server-side compaction or UI changes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
