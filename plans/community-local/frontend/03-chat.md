# Frontend — Phase 3: Chat + onboarding

> Copy citation/stream UI from `surfsense_web/`.

## Goal

Grounded chat with citations; first-run wizard.
The dashboard layout, backend-owned assistant-ui runtime, thread lifecycle, SSE
parser, and Sources panel contract are specified in
[`01-dashboard.md`](01-dashboard.md).

## Work

- Wizard: path A/B/C + RAM tier → `PATCH /settings`.
- Reuse the validated generation selection from
  [`01-shell.md`](01-shell.md); Chat does not maintain a second model URL/name
  setting.
- Complete the thread list, assistant-ui messages, and composer specified in
  [`01-dashboard.md`](01-dashboard.md); lists via `useQuery`.
- Stream assistant replies through the chunk-safe SSE adapter; render `data:`
  deltas until `[DONE]`. This is the chat token stream, separate from the
  `/events` freshness channel (see [`../00-umbrella-plan.md`](../00-umbrella-plan.md)).
- Citation controls update and open the dashboard Sources panel.
- Empty states: no model, no documents, ingest in progress.

## Acceptance

- Wizard + ingested doc → streaming answer with clickable citations.
- Path C: Ollama URL → chat works.

## Needs from API

[`../api/03-chat.md`](../api/03-chat.md).
