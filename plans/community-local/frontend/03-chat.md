# Frontend — Phase 3: Chat + onboarding

> Copy citation/stream UI from `surfsense_web/`.

## Goal

Grounded chat with citations; first-run wizard.

## Work

- Wizard: path A/B/C + RAM tier → `PATCH /settings`.
- Settings: model URL, model name.
- Thread list, messages, composer — lists via `useQuery`.
- Stream the assistant reply over the chat SSE endpoint ([`../api/03-chat.md`](../api/03-chat.md));
  render `data:` deltas until `[DONE]`. This is the chat token stream, separate
  from the `/events` freshness channel (see [`../00-umbrella-plan.md`](../00-umbrella-plan.md)).
- Citation chips → source chunk/document.
- Empty states: no model, no documents, ingest in progress.

## Acceptance

- Wizard + ingested doc → streaming answer with clickable citations.
- Path C: Ollama URL → chat works.

## Needs from API

[`../api/03-chat.md`](../api/03-chat.md).
