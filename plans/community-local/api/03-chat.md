# API — Phase 3: Settings + chat

> Schema: [`../00c-data-model.md`](../00c-data-model.md) (`chat_threads`, `chat_messages`).

## Goal

Settings persistence; chat endpoints calling shared search + LLM stream.

## Work

- `app_settings` or `settings.json` under `~/.surfsense/`.
- `GET/PATCH /settings` — onboarding path, tier, Ollama/llama.cpp URL, model name.
- `GET/POST /workspaces/{id}/chat/threads`, `POST .../messages`.
- Chat handler: `backend/shared/search.py` → trim → stream LLM → save `chat_messages` with citation refs.
- Ollama / llama.cpp client at `127.0.0.1`; add chat routes + pydantic models.

## Acceptance

- Ollama + ingested doc → streamed reply with citation payload for frontend.

## Interface to worker

`search_workspace()` in [`../worker/03-search.md`](../worker/03-search.md). Synchronous call; no Huey for chat v1.
