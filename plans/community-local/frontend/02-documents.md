# Frontend — Phase 2: Documents

> Field names: [`../00c-data-model.md`](../00c-data-model.md) (`documents.status`).

## Goal

Upload files and see ingest status.

## Work

- Dropzone → `POST /workspaces/{id}/documents/upload`.
- Document table: title, type, status badge (`pending` | `processing` | `ready` | `failed`).
- List via `useQuery` on `GET /workspaces/{id}/documents`, passing `?limit=`/`?offset=`.
  Freshness: subscribe to the SSE `/events` stream and `invalidateQueries` on
  `document.updated`; a `refetchInterval` while any row is in flight is the fallback.
  See the freshness decision in [`../00-umbrella-plan.md`](../00-umbrella-plan.md).
- Show `failed` message from `error_message`, with a retry button →
  `POST .../documents/{doc}/retry`.
- Row actions: rename → `PATCH .../documents/{doc}`, delete → `DELETE` the same path.
- The list returns ARTIFACT rows too. Filter with `?document_type=FILE&document_type=NOTE`
  so Studio output does not appear as something the user uploaded.
- Open a document → `GET .../documents/{doc}` for its extracted text; notes are
  editable in place and go back to `pending` when saved.

## Acceptance

- Upload PDF → `pending` → `ready` or `failed`.
- Five files queued: list updates as worker finishes.
- A failed document shows why, and retry puts it back in the queue.
- A note can be written, edited and deleted without touching the filesystem.

## Needs from API

[`../api/02-upload.md`](../api/02-upload.md).

## Needs from worker

Documents reach `ready` — [`../worker/02-ingest.md`](../worker/02-ingest.md).
