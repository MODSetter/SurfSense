# Frontend — Phase 2: Documents

> Field names: [`../00c-data-model.md`](../00c-data-model.md) (`documents.status`).

## Goal

Upload files and see ingest status.

## Work

- Dropzone → `POST /workspaces/{id}/documents/upload`.
- Document table: title, type, status badge (`pending` | `processing` | `ready` | `failed`).
- Poll `GET /workspaces/{id}/documents` or SSE.
- Show `failed` message from API.

## Acceptance

- Upload PDF → `pending` → `ready` or `failed`.
- Five files queued: list updates as worker finishes.

## Needs from API

[`../api/02-upload.md`](../api/02-upload.md).

## Needs from worker

Documents reach `ready` — [`../worker/02-ingest.md`](../worker/02-ingest.md).
