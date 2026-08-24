# Phase 8 — Retire the legacy generation path

**Status:** DESIGN. Not implemented.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Queued-video production validation and a reconciled Phase-7 migration decision/ledger.

## 1. Goal

Remove the legacy video authoring graph, legacy video Celery task, `VideoPresentationRun` lifecycle, run-specific frontend UI, and browser execution of stored scene code after the backend executor is proven and Phase 7 has converted every legacy video to MP4.

The security boundary is mandatory: historical scene source is untrusted code. After Phase 7, video playback must consume only verified MP4 bytes; no video Artifact may invoke Remotion, `new Function`, Babel, or stored TSX/JavaScript in the client.

This phase must retain the implemented target architecture:

- generic `DeliverableJob` model and state machine;
- `deliverables.execute_queued` and reconciliation tasks;
- `execute_video_deliverable()` deterministic backend pipeline;
- shared `celery_worker` on the `surfsense` queue;
- attempt-scoped sandbox ownership and cooperative database cancellation;
- GET/Cancel/Retry routes and safe Zero publication;
- live deliverable-job card;
- verification, streaming Artifact save, MP4 manifest/Range/player/download paths.

There is no dedicated `video_render` worker to retain or retire.

## 2. Validation gates

Do not remove a legacy dispatch or reader until:

1. real queued videos complete enqueue → shared worker → verified MP4 → ready card/player;
2. production observation covers cancellation, explicit retry, redelivery, stale queued/cancelling reconciliation, safe failures, billing, and sandbox cleanup;
3. concurrent same-thread requests prove separate rows, attempts, sandboxes, workdirs, outputs, and actions;
4. worker CPU, memory, queue wait, render duration, and failures are acceptable;
5. the Artifact-save/job-ready transactional gap has an accepted mitigation;
6. Phase 7 has converted every legacy video to a verified MP4 or confirmed it already had one;
7. no nonterminal `VideoPresentationRun` remains;
8. private, public, and shared legacy videos play through the MP4 path without client code execution;
9. rollback through `VIDEO_SANDBOX_RENDERING_ENABLED` has been exercised during a defined soak period.

A failed gate stops retirement; it does not justify deleting required readers or replacing the current executor.

## 3. Staged cutover

### Stage A — dual-path validation

- flag off: legacy `generate_video_presentation`;
- flag on with sandbox available: `enqueue_deliverable_job`;
- changing the flag affects only new requests, not queued jobs or existing MP4 playback.

### Stage B — queued path authoritative

Keep the flag enabled through a production soak. Disable new legacy-run creation while retaining legacy read/UI support needed for existing runs and artifacts. Drain and reconcile all legacy tasks.

### Stage C — execution retirement

Remove legacy authoring/task/run surfaces. Temporarily retain the flag as a kill switch: after legacy dispatch is gone, disabled means video generation is unavailable with safe copy, not fallback to deleted code.

Remove the flag only in a later deployment cleanup after the rollback window.

## 4. Backend execution removal

After drain:

- delete `deliverables/tools/video_presentation.py` and its registration;
- delete `app/tasks/celery_tasks/video_presentation_tasks.py` and legacy task routing;
- delete `app/agents/video_presentation/` only after queued narration/language dependencies are independent;
- remove `generate_video_presentation` catalog, prompt, context-prune, receipt, activity, and wait-path handling;
- remove legacy-only reservation/billing code after accounting parity is proven.

Retain:

- `app/deliverables/video/executor.py`;
- generic deliverable jobs policy/service/dispatch/task code;
- late acknowledgements, prefetch `1`, worker-lost rejection, and reconciliation schedules;
- shared-worker sandbox environment;
- queued narration, still review, verification, and streaming storage.

## 5. Retire `VideoPresentationRun`

Only after no legacy task can create/update a run and all rows are terminal:

- remove `VideoPresentationRun` and `VideoPresentationStatus` runtime use;
- add a **new** Alembic migration to drop the table; do not edit historical migrations;
- remove `video_presentation_runs` from backend and frontend Zero schemas/queries;
- remove legacy run routes, serializers, reconciliation, and polling.

Do not alter or narrow `DeliverableJob`. Its lifecycle, safe publication, routes, attempts, cancellation/retry, and Artifact link remain authoritative.

Dropping the legacy table is the final schema step after backup and after application rollback no longer depends on the rows.

## 6. Frontend removal

Remove UI keyed to `generate_video_presentation` or `VideoPresentationRun`:

- legacy generation tool card and status poller;
- legacy Zero schema, queries, and hooks;
- assistant-message, public-thread, artifact-collection, icon, and label entries used only by the legacy receipt/run.
- browser Remotion, Babel compilation, `new Function`, `prepareSource()`, and stored scene-code playback.

Retain:

- `deliverable-job.tsx` and `use-deliverable-job-live.ts`;
- Cancel/Retry client and same-origin routing;
- artifacts-library deliverable-job merge;
- `Mp4ArtifactCard`, `Mp4VideoPlayer`, KB viewer, manifest, download, and Range serving.

Phase 7 must remove the need for a browser compatibility renderer before this phase starts. Delete related web dependencies after a repository-wide import check proves no unrelated feature uses them.

## 7. Artifact readers and data cleanup

Legacy per-slide audio, scene metadata, `_legacy_ref`, public snapshots, and compatibility routes can be deleted only after:

- no queued/backfill path reads it;
- every private/public/shared video has a verified MP4 replacement;
- database and blob counts are reconciled;
- MP4 playback covers the corresponding use case;
- the rollback window is closed.

Stopping legacy task dispatch is not permission to delete migration inputs before Phase 7 and rollback validation finish. After those gates pass, no client playback path may retain or execute the old scene source.

## 8. Configuration cleanup

Keep `VIDEO_SANDBOX_RENDERING_ENABLED` during cutover. Remove a setting only after its final caller is gone.

Retain the settings actually used by the queued path, including TTS policy and sandbox render concurrency/segmentation/frame-timeout settings. The current queue remains the shared `surfsense` queue unless a separate measured architecture change is approved.

## 9. Exit criteria

1. No new request can dispatch the legacy graph or task.
2. Every legacy run is terminal and its runtime table/Zero/API/poller is removed through a new migration.
3. New generation uses `DeliverableJob`, the generic Celery task, and deterministic backend executor.
4. Generic cancellation/retry, reconciliation, verification, save, card, and MP4 delivery remain intact.
5. The rollout flag remains through the defined post-cutover rollback window.
6. Browser rendering and all stored scene-code execution paths are removed from video playback.
7. Every legacy/private/public/shared video plays through a verified MP4 path.
8. Backend tests, migration checks, frontend validation, and a real queued-video acceptance run pass after deletion.
