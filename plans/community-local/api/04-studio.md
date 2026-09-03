# API — Phase 4: Studio routes

> Schema: [`../00c-data-model.md`](../00c-data-model.md) (`artifacts`).

## Goal

Accept Studio jobs; expose artifact status.

## Work

- `POST /workspaces/{id}/studio/jobs` — type, document ids, optional prompt.
- Insert `artifacts` `status=pending`; `studio_job.delay(artifact_id)`.
- `GET /workspaces/{id}/artifacts`, `GET /artifacts/{id}` — status, path when ready.

## Acceptance

- POST returns artifact id; GET shows `ready` + downloadable path.

## Interface to worker

`studio_job(artifact_id)` — [`../worker/04-studio.md`](../worker/04-studio.md).
