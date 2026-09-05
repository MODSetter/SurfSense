# API — Phase 3: Settings + chat

> Schema: [`../00c-data-model.md`](../00c-data-model.md) (`chat_threads`, `chat_messages`).

## Goal

Settings persistence; chat endpoints calling shared search + LLM stream.

## Work

- `app_settings` or `settings.json` under `~/.surfsense/`.
- `GET/PATCH /settings` — onboarding path, tier, Ollama/llama.cpp URL, model name.
- `GET/POST /workspaces/{id}/chat/threads`, `POST .../messages`.
- Chat handler: load thread history → build the message list → retrieve → prepend
  system prompt + context → stream the selected model → save `chat_messages` with
  citation refs.

## History and context window

- A thread's history is its `chat_messages` in `created_at` order: a flat list,
  one row per turn. No branching.
- Each turn loads that history, appends the new user message, and prepends the
  system prompt and retrieved chunks before calling the model.
- Sliding window: the system prompt and retrieved context stay pinned; the most
  recent turns that fit the token budget are kept and older ones dropped. The
  budget is a fraction of the model's context length.

**Already built** ([`modules/llm/`](../../../surfsense_local/backend/modules/llm/)):
the provider layer and model selection. `GET /llm/providers`, `.../models`,
`.../catalog`, `POST .../pull`, and `GET/PUT /llm/selection/{role}` exist, and
`OllamaProvider.chat()` streams deltas. This phase reads the selected model,
retrieves, and turns that stream into SSE with citations — it does not re-add the
provider client.

## Acceptance

- Ollama + ingested doc → streamed reply with citation payload for frontend.

## Interface to worker

`retrieve()` in [`../worker/03-search.md`](../worker/03-search.md). Synchronous call; no Huey for chat v1.
