# Worker — Phase 1: Boot

> Owns: `backend/worker/`, Huey consumer. Schema: [`../00c-data-model.md`](../00c-data-model.md) (shared models with API).

## Goal

Long-lived consumer on same DB as API.

## Work

- Huey `SqliteHuey` → `~/.surfsense/huey.db`.
- `huey_consumer` entrypoint, **`-w 1`**.
- Shared SQLAlchemy models (API owns migrations).
- Echo task for spike / integration test.

## Acceptance

- API enqueues echo → worker completes.
- Worker restart → queue persists.

## Interface from API

Huey in shared module; API only `.delay()`.
