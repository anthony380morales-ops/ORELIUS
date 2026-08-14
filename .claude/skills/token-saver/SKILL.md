---
name: token-saver
description: >-
  ORELIUS credit & token optimizer. Use whenever adding or changing anything
  that calls the Claude/Anthropic API in this repo, or when asked to reduce
  cost, save credits, make responses cheaper, or keep the daily bill low.
  Covers model choice (Haiku 4.5), prompt caching, response caching, history
  trimming, dynamic output caps, and usage/cost tracking.
---

# Token & Credit Saver

ORELIUS is called on every day, so every API call must be cheap and the credit
balance must last. This skill is the playbook the backend already implements in
`backend/app/core/token_optimizer.py`, `claude_client.py`, and `oreilus_engine.py`.
Follow it any time you touch model-calling code.

## The model

Use **Claude Haiku 4.5** (`claude-haiku-4-5`) — the cheapest efficient Claude
model: **$1 / 1M input, $5 / 1M output**. It is set in `settings.oreilus_model`.
Do not silently upgrade to Sonnet/Opus; escalate to the Master first if a task
truly needs it. (A cheap-chat / escalate-hard-tasks split is a supported future
option — route everyday messages to Haiku, only hard requests elsewhere.)

## The five levers (in priority order)

1. **Response cache — the biggest win.** Identical repeat questions are served
   from an in-process TTL cache for **0 API credits**. See
   `TokenOptimizer.get_cached_response` / `store_response`. Key on the persona
   prefix + the last user message (normalized). Toggle: `enable_response_cache`.

2. **Prompt caching.** Mark the stable persona system prompt cacheable with
   `cache_control: {"type": "ephemeral"}` so it bills at ~0.1x on reuse. On Haiku
   4.5 the cached prefix must be **≥ 4096 tokens** or it silently won't cache —
   keep the persona prefix stable (never interpolate timestamps/UUIDs into it) so
   cache hits keep landing. Toggle: `enable_prompt_caching`.

3. **History trimming.** Sending the whole conversation every turn is the #1
   hidden cost. Keep only the last `max_history_messages` turns within
   `max_history_tokens`. See `TokenOptimizer.trim_history`. Always ensure the
   first message sent is a `user` turn.

4. **Dynamic output cap.** `max_tokens` is a hard ceiling. Default to a small cap
   (`oreilus_max_tokens`, 1500) for chat; only raise to `oreilus_report_max_tokens`
   (4096) when the user asks for a report / plan / blueprint / strategy /
   breakdown. See `TokenOptimizer.choose_max_tokens`.

5. **Usage tracking.** Record `input`, `output`, `cache_read`, and `cache_write`
   tokens from `response.usage` after every call and estimate USD cost + savings.
   See `UsageTracker`. Surfaced at `GET /api/system/optimization`.

## Rules when editing model-calling code

- Never hardcode a model string — read `settings.oreilus_model`.
- Never send `temperature` **and** `top_p` together. Haiku 4.5 accepts
  `temperature`; it does **not** support `effort` or adaptive thinking — omit them.
- Never put volatile data (dates, IDs) ahead of the cached prefix.
- Always capture `response.usage` (use `stream.get_final_message()` when streaming)
  and feed it to the tracker.
- Parse tool inputs with `json.loads`, never raw string matching.

## Quick cost math (Haiku 4.5)

- 1,000 daily chat turns, ~800 in / ~300 out each, persona cached:
  ~$0.8 input + ~$1.5 output ≈ **~$2.30/day** before response-cache hits.
- Each response-cache hit and each prompt-cache read cuts that further.
- Check live numbers any time: `GET /api/system/optimization`.
