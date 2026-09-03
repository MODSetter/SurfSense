# Worker — Phase 1: Boot

> Owns: `backend/worker/`, Huey consumer. Schema: [`../00c-data-model.md`](../00c-data-model.md) (shared models with API).

## Goal

Long-lived consumer on same DB as API.

## Work

- `huey_consumer` entrypoint, **`-w 1`**, draining `shared.queue.huey`.
- Shared SQLAlchemy models (API owns migrations).

**Already done, in [`../api/02-upload.md`](../api/02-upload.md):** `shared/queue.py`
holds the `SqliteHuey` on `~/.surfsense/huey.db`, its own file so the consumer's
polling does not contend for the write lock on the database serving requests.
Uploads already enqueue `ingest_document`; nothing drains it, which is why an
uploaded document sits at `pending`. No echo task is needed — a real one is
waiting in the queue.

## Acceptance

- Upload a file, start the worker → it picks the job up.
- Worker restart → queue persists.

## Interface from API

Huey in shared module; API only `.delay()`.
