# Frontend — Phase 4: Studio

> Owns: `features/studio/`. Routes: [`../api/04-studio.md`](../api/04-studio.md).
> Freshness: TanStack Query + SSE ([`../00-umbrella-plan.md`](../00-umbrella-plan.md)).

## Goal

A Studio surface: pick a format, pick documents, optional prompt → generate →
track → view or download. Separate from chat, one deliverable at a time.

## Work

Mirror `features/sources/` layout (page, hook, `api.ts`, components):

- **Entry** — a Studio surface off the workspace, distinct from the chat panel.
- **Format picker** from `GET /studio/formats`. Visual formats
  (`requires_key`) render disabled with a "needs OpenRouter" affordance linking
  to model setup, so the BYO ceiling is obvious, not a broken run.
- **Document picker** — multi-select over the workspace's sources (reuse the
  sources list) + an optional prompt / theme field.
- **Submit** → `POST /workspaces/{id}/studio/jobs`, returns the artifact id.
- **Track** with TanStack Query on `GET /artifacts/{id}`; SSE invalidates the
  document event for that id, `refetchInterval` is the fallback while running —
  the same freshness path as ingest, no bespoke polling loop.
- **Viewers by format**, a registry mirroring the worker's builders: summary →
  markdown; docx/pptx → preview PDF or download; xlsx → download; html →
  sandboxed iframe; mindmap → Markmap over the markdown; flashcards/quiz →
  interactive; podcast → audio player (streams `files/primary`); image →
  `<img>`; unknown → download link.
- **Library** — the workspace's artifacts, listing `ARTIFACT` documents that the
  sources view filters out (data-model list semantics), each opening its viewer.

## Acceptance

- Select documents → run a summary → the completed artifact renders inline; a
  docx/pptx downloads; a podcast plays.
- A visual format is unrunnable without an OpenRouter key, with the reason shown.
- A running job resolves on the SSE invalidation, not only on the poll.

## Needs from API / worker

The Studio routes and job completion — [`../api/04-studio.md`](../api/04-studio.md),
[`../worker/04-studio.md`](../worker/04-studio.md).
