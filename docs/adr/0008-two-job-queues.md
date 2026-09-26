# ADR 0008: Ingest and Studio jobs run on separate Huey queues, each drained by its own worker

- **Status:** Accepted
- **Date:** 2026-09-15
- **Source:** commit [28ae63dde](https://github.com/MODSetter/SurfSense/commit/28ae63ddeeedacf381ee13ad5242266c10a71ce2), [Umbrella plan L91](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00-umbrella-plan.md#L91), [Data model L13](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00c-data-model.md#L13), [Data model L289](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00c-data-model.md#L289), [Pivot plan L230](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L230)

## Context

Background work comes in two kinds. Ingest jobs parse, chunk and embed, and they saturate the CPU. A Studio job spends most of its time waiting on a model. On one queue, a large import would sit in front of every summary the user asks for. Both kinds of job are described in [documents](../architecture/documents.md) and [studio](../architecture/studio.md).

## Decision

- Two `SqliteHuey` queues, `ingest` and `studio`, share one `huey.db` ([`shared/queue.py`](../../surfsense_local/backend/shared/queue.py)). The queue file is separate from `surfsense.db`, so Huey's constant polling does not hold the database's write lock.
- `ingest` is drained by one thread and `studio` by four (`STUDIO_WORKERS` in [`worker/consumer.py`](../../surfsense_local/backend/worker/consumer.py)).
- Electron runs each consumer as its own sidecar, `worker-ingest` and `worker-studio`, from the same worker binary with the queue name as its argument ([`sidecars/python.ts`](../../surfsense_local/electron/src/main/sidecars/python.ts)).
- Huey holds queue mechanics only. What the user sees is the row's own state, such as `documents.status`.

## Consequences

- An import never queues ahead of a summary, and up to four Studio jobs overlap while they wait on a model.
- There are two worker processes to supervise and reap instead of one.
- The thread counts are laptop defaults. The `ponytail:` in `worker/consumer.py` says they become a setting for power users.
- The queue is persistent, so quitting in the middle of an import is safe: the workers finish what was enqueued when the app starts again.
