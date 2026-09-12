# Worker — Phase 1: Boot

> Owns: `backend/worker/`, Huey consumer. Schema: [`../00c-data-model.md`](../00c-data-model.md) (shared models with API).

## Goal

Long-lived consumer on same DB as API.

## Work — done

- `worker/consumer.py` runs `Consumer(huey, workers=1)` in the foreground, so
  the process Electron supervises is the one doing the work. Started with `uv
  run worker.py`, next to the API's `main.py` and for the same reason: a script
  is what a PyInstaller spec points at, where a console script would not exist.
- `import_tasks()` in `shared/queue.py`, run before the consumer starts, next to
  the `import_models()` the API already runs. Both are plain import statements a
  person maintains. A task nobody imported is one the consumer cannot
  deserialize: it takes the job off the queue, logs `Error reading from queue`,
  and drops it, which is why the list is not left to be remembered —
  `tests/integration/test_registration.py` reads `modules/*/tasks.py` and
  `modules/*/models.py` off disk in a clean interpreter and fails when either
  list falls behind.

**Already done, in [`../api/02-upload.md`](../api/02-upload.md):** `shared/queue.py`
holds the `SqliteHuey` on `~/.surfsense/huey.db`, its own file so the consumer's
polling does not contend for the write lock on the database serving requests.
Uploads already enqueue `ingest_document`. No echo task was needed — a real one
was waiting in the queue.

**`-w 1` is the whole scaling decision.** Ingest saturates a CPU and writes to
the file the API is serving requests from, so a second worker would spend its
life behind the first one's write lock.

## Acceptance

- Upload a file, start the worker → it picks the job up.
- Worker restart → queue persists.

The test starts `python -m worker` as a real subprocess and waits for the job's
outcome to appear in the result store, rather than watching the queue drain: an
empty queue also describes a worker that never registered the task and threw
the job away.

## Interface from API

Huey in shared module; API only `.delay()`.
