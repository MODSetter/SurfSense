# Phase 2b — Queued deliverable jobs

**Status:** IMPLEMENTED.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Role:** Authoritative generic job, dispatch, worker, cancellation/retry, API, and live-state contract.

## 1. Architecture

```text
interactive enqueue
  → DeliverableJob
  → deliverables.execute_queued on shared surfsense Celery worker
  → kind-specific backend executor
  → verified Artifact
```

The model and lifecycle are generic, but only the `video` kind is registered today. The shared worker uses the existing backend/Celery image and sandbox-provider configuration. There is no dedicated `video_render` queue, worker service, image, or `DeliverableKindSpec.queue`.

## 2. Data model

Migration `186_add_deliverable_jobs.py` adds `DeliverableJob` and stable enums rather than extending `VideoPresentationRun`.

The row stores:

- `kind`, `title`, workspace, root thread, creator, and tool-call identity;
- private versioned request and checkpoint JSON;
- status, phase, progress, and nullable `artifact_id`;
- current Celery task ID and attempt count;
- stable failure code and bounded private diagnostic;
- cancellation, claim, heartbeat, finish, create, and update timestamps.

Unique `(workspace_id, kind, tool_call_id)` makes enqueue idempotent. Video limits remain in `app/deliverables/jobs/policy.py`, not format-specific columns.

## 3. State machine

```text
queued → running → ready
                 ↘ failed

queued → cancelled
running → cancelling → cancelled
failed|cancelled → queued  (explicit Retry)
```

Transitions use conditional SQL updates:

- claim requires `queued`, no artifact, and the expected attempt/task identity;
- running heartbeats and terminal transitions can be bound to `celery_task_id`;
- `ready` requires an Artifact ID;
- queued cancellation becomes terminal without worker execution;
- running cancellation first becomes `cancelling`;
- Retry keeps the same row/card ID, increments `attempt_count`, clears terminal fields, and assigns `deliverable-job:{id}:attempt:{attempt}`;
- compile, policy, quota, render, and verification failures require explicit user Retry;
- only classified transient provider failures use bounded Celery retry.

`checkpoint` is present in the generic schema but the current video executor does not persist or resume mid-pipeline checkpoints.

## 4. Kind policy

`DeliverableKindSpec` currently defines for video:

- maximum duration: 180 seconds;
- maximum scenes: 12;
- repair cycles: 2;
- soft task limit: 3600 seconds;
- hard task limit: 3900 seconds.

Queue routing is intentionally absent. `deliverables.execute_queued` uses the default `surfsense` queue. A dedicated resource queue is a future operational option only if production measurements justify it.

## 5. Enqueue and outbox behavior

`enqueue_deliverable_job` accepts title, brief, source references, and optional revision artifact. The server builds trusted request v1.

1. Create or retrieve the idempotent row.
2. Assign and persist the deterministic attempt task ID.
3. Commit before broker publication.
4. Publish `deliverables.execute_queued(job_id)`.
5. Return a pending receipt immediately.

The tool never calls `wait_for_deliverable`. Publication failure leaves a valid queued row and safe receipt. `deliverables.reconcile_queued` runs every minute and republishes queued rows older than two minutes. Atomic claim makes duplicate publication harmless.

## 6. Celery task

`app/tasks/celery_tasks/deliverable_job_tasks.py`:

1. opens a Celery-safe async database session;
2. claims the expected queued attempt;
3. invokes the registered kind executor (`execute_video_deliverable` for video);
4. runs a parallel cancellation/supersession watcher;
5. marks the current attempt ready, failed, cancelled, requeued, or ignored;
6. bills worker LLM calls through the existing accounting boundary;
7. terminates the attempt sandbox in `finally`.

Task behavior retains late acknowledgement, worker-lost rejection, and global prefetch multiplier `1`. The async runner resets process-wide loop-bound sandbox SDK handles before each fresh task event loop.

The worker does not invoke a queued subagent, use a LangGraph checkpointer, or run only `renderMedia()`.

## 7. Attempt isolation

```text
task id: deliverable-job:{job_id}:attempt:{attempt_count}
owner:   deliverable-job-{job_id}-attempt-{attempt_count}
workdir: /workspace/deliverable-job-{job_id}-attempt-{attempt_count}
output:  /workspace/deliverable-job-{job_id}-attempt-{attempt_count}.mp4
```

This prevents concurrent jobs and retried attempts from sharing files, sandbox ownership, cancellation, or state transitions.

## 8. Cancellation and retry

The database is the cancellation source of truth:

- `POST .../{job_id}/cancel` atomically cancels queued work or changes running work to `cancelling`;
- the worker watcher polls every 0.5 seconds in a separate session;
- on cancellation it cancels the executor task, terminates the exact attempt sandbox, and commits `cancelled`;
- if task identity changes, the old attempt is superseded and ignored;
- stale cancelling rows older than five minutes are force-completed and their sandboxes are terminated.

`POST .../{job_id}/retry` accepts failed/cancelled jobs, creates the next attempt identity, commits, and republishes. Repeated action is idempotent once that retry is already queued.

The worker terminates the sandbox rather than writing the Remotion cancel marker. Stale-running reconciliation is not implemented.

## 9. Save and completion

The executor validates a signed receipt, streams the exact MP4 through generic artifact storage, and receives an Artifact ID. The task then calls `complete_deliverable_job`.

These are currently separate commits: `save_artifact()` commits the Artifact first, then job completion commits `artifact_id` and `ready`. A fully atomic save/link transition described in earlier designs is not implemented and remains a hardening item.

## 10. Public lifecycle

Migration 187 and `zero_publication.py` expose only:

- ID, kind, title;
- status, phase, progress, failure code;
- Artifact ID;
- workspace/thread IDs;
- creation/update timestamps.

Request/checkpoint JSON, task IDs, attempts, heartbeats, cancellation internals, sandbox data, billing, and `internal_error` remain private.

Authenticated workspace routes provide GET, Cancel, and Retry. Public failure codes are stable and user copy is mapped on the client.

## 11. Frontend contract

The chat card subscribes by stable job ID through Zero and represents queued, running, cancelling, cancelled, failed, and ready. Cancel and Retry target that exact workspace/job pair. Controls are disabled while their request is pending, and the resulting state comes from Zero rather than optimistic mutation.

Ready hands `artifact_id` to the existing MP4 artifact card. The artifacts library merges queued/running/cancelling video jobs; failed/cancelled jobs are currently omitted and ready jobs come from the normal Artifact list.

## 12. Implemented coverage and known gaps

Coverage includes lifecycle transitions, idempotent enqueue, task identities, duplicate dispatch, cancellation watcher, stale-cancelling reconciliation, retry, sandbox isolation, safe publication/API fields, frontend states/actions, shared-worker Compose configuration, and MP4 handoff.

Known gaps:

- no atomic Artifact-save/job-ready transaction;
- no stale-running reconciler;
- no executor checkpoint/resume;
- no frame-level `progress.json` consumption;
- no dedicated resource queue;
- no end-to-end migration/backfill path.
