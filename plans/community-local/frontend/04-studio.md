# Frontend — Phase 4: Studio

## Goal

One Studio action end-to-end in UI.

## Work

- Studio entry (nav or button).
- One artifact type for v1.
- Multi-select documents + optional prompt.
- Submit → `POST /workspaces/{id}/studio/jobs`.
- Track the artifact with `useQuery` on `GET .../artifacts/{id}`; `invalidateQueries`
  on the SSE `artifact.updated` event, `refetchInterval` while it runs as fallback
  (freshness decision in [`../00-umbrella-plan.md`](../00-umbrella-plan.md)).
- Viewer: summary / audio / download.

## Acceptance

- Select docs → run Studio → completed artifact in UI.

## Needs from API

[`../api/04-studio.md`](../api/04-studio.md).

## Needs from worker

Job completes — [`../worker/04-studio.md`](../worker/04-studio.md).
