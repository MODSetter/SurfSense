# Frontend — Phase 3: Chat + onboarding

> Copy citation/stream UI from `surfsense_web/`.

## Goal

Grounded chat with citations; first-run wizard.

## Work

- Wizard: path A/B/C + RAM tier → `PATCH /settings`.
- Settings: model URL, model name.
- Thread list, messages, composer.
- Stream assistant reply (SSE or fetch stream).
- Citation chips → source chunk/document.
- Empty states: no model, no documents, ingest in progress.

## Acceptance

- Wizard + ingested doc → streaming answer with clickable citations.
- Path C: Ollama URL → chat works.

## Needs from API

[`../api/03-chat.md`](../api/03-chat.md).
