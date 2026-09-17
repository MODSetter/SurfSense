# Frontend — Phase 4: Studio

> Owns: `features/studio/`. Routes: [`../api/04-studio.md`](../api/04-studio.md).
> Freshness: TanStack Query + SSE ([`../00-umbrella-plan.md`](../00-umbrella-plan.md)).

## Goal

A Studio surface: pick a format, pick documents, optional prompt → generate →
track → view or download. Separate from chat, one deliverable at a time.

## Work

Mirror `features/sources/` layout (page, hook, `api.ts`, components):

- **Entry** — a Studio surface off the workspace, distinct from the chat panel.
- **Format picker** from `GET /studio/formats`. Image renders disabled when no
  image-generation role is selected, with a link to the OpenAI-compatible model
  setup. **Infographic is disabled on the same condition** — it declares the same
  `requires_roles` as `image` in `formats.py` — which an earlier version of this
  line got wrong. The frontend does not infer availability from credentials, and
  it does not need to: an image selection may resolve to the bundled local
  sd-server, so "available" does not mean "a remote key is on file".
- **Podcast brief.** `podcast` is the one format with options. The panel reads
  `GET /workspaces/{id}/studio/podcast/brief` and renders `podcast-brief-form`
  before submitting, so the user reviews style, duration and speakers first.
- **Document picker** — multi-select over the workspace's sources (reuse the
  sources list) + an optional prompt / theme field.
- **Submit** → `POST /workspaces/{id}/studio/jobs`, returns the artifact id.
- **Track** with TanStack Query on `GET /artifacts/{id}`; SSE invalidates the
  document event for that id, `refetchInterval` is the fallback while running —
  the same freshness path as ingest, no bespoke polling loop.
- **Viewers by format**, a registry mirroring the worker's builders. Built in
  `viewers/registry.tsx`, and richer than this list planned for: summary →
  Streamdown markdown; **docx, pptx, xlsx and pdf each got a real in-app viewer**
  rather than the download link sketched here, the docx one with fit-to-width and
  ctrl+scroll zoom; html → `<iframe sandbox="allow-scripts allow-popups">`;
  mindmap → Markmap with a fit control; flashcards and quiz → interactive, with
  progress persisted server-side through the `*-state` routes and the viewer
  keyed on `id:generation` so a regenerate starts a clean run; podcast → audio
  player over `files/primary`, transcript rendered as markdown; image and
  infographic → a shared media viewer; a format with no entry → the plain
  `DocumentViewer` fallback.
- **Cancel** a running source or artifact from its row menu, against the
  `/cancel` routes in [`../api/04-studio.md`](../api/04-studio.md).
- **Library** — the workspace's artifacts, listing `ARTIFACT` documents that the
  sources view filters out (data-model list semantics), each opening its viewer.

## Acceptance

- Select documents → run a summary → the completed artifact renders inline; a
  docx/pptx downloads; a podcast plays.
- Image **and infographic** are unrunnable without a valid image-generation
  selection, with the reason and setup link shown.
- A running job resolves on the SSE invalidation, not only on the poll.

## Needs from API / worker

The Studio routes and job completion — [`../api/04-studio.md`](../api/04-studio.md),
[`../worker/04-studio.md`](../worker/04-studio.md).
