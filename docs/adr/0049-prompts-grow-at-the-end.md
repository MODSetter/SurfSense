# ADR 0049: A prompt changes only at its end, so the cached start of it is never read again

- **Status:** Accepted
- **Date:** 2026-10-05
- **Source:** measured on Qwen3 1.7B at `b11050`, recorded in [chat](../architecture/chat.md#grounding-shape), [Studio](../architecture/studio.md#grounding) and [the llama.cpp runtime](../architecture/local-models/runtime.md#the-preset-file)

## Context

llama-server reuses a prompt up to its first changed token and reads the rest; on a laptop, reading is most of the wait before the first word, about 210 tokens a second for Qwen3 1.7B on integrated graphics. Remote providers cache the same way, by an identical start, and most need nothing asked of them. The app built prompts that changed near their start: chat put each turn's retrieved passages in the system message and trimmed history one message at a time, and every podcast segment opened with its own position. Chat, Studio and the agent share llama-server's few slots, and llama.cpp's own 8 GiB of host memory for saving a slot's prompt when it changes hands was set by nobody.

## Decision

- What every request of a conversation or a job shares comes first; what is new comes last. A chat's system message is its instruction alone, and the turn's passages ride with its question, which is labelled after them so a short follow-up keeps its subject. A podcast segment's whole draft prompt follows the sources every segment shares, behind a fixed one-line system prompt.
- History is cut by whole exchanges to 75% of its budget when it overflows, and the thread records where it now starts, so the next turns start there too.
- Each local model's preset pins `cache-ram`: a quarter of the memory the capacity budget gives a model, at most llama.cpp's 8,192 MiB.
- A remote conversation is named only to a host known to route by the name: `session_id` to OpenRouter, with a top-level `cache_control` for an `anthropic/` model, and `prompt_cache_key` to OpenAI and to a ChatGPT plan. Every other host gets nothing new, because a strict endpoint rejects a field it does not know.
- Each reply's reported reuse is logged, never sent anywhere ([ADR 0016](0016-no-telemetry.md)).

## Consequences

- A follow-up reads from the previous question on, a podcast reads its sources once, and an agent step after another caller restores its prompt from host memory instead of reading it again.
- A change that puts anything per-turn ahead of what a conversation shares, such as a date in a system prompt, gives the gain back; the reuse in the log is where it shows.
- Unloading the model, which a local image or a podcast's voicing does, and restarting the router, which every install or delete does, still empty the cache.
- Claude through Anthropic's OpenAI-compatible endpoint is never cached: that endpoint does not support it.
