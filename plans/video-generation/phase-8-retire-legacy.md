# Phase 8 — Retire the legacy generation path

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** queued-video production validation and Phase 7's reconciled migration ledger.

## 1. Goal and scope

Retire the legacy video authoring graph, legacy video Celery task, `VideoPresentationRun` lifecycle, and their run-oriented frontend UI only after the queued path is proven in production.

This phase is not a retirement of Celery or background deliverables. The following are the target architecture and must remain:

- the generic `DeliverableJob` model, state machine, APIs, Zero publication, and job card;
- `execute_queued_deliverable(job_id)` and its reconciliation tasks;
- the dedicated `video_render` queue and worker service;
- concurrency `1` initially, using the existing backend/Celery image and broker;
- queued-job sandbox ownership, progress, cancellation, retry, billing, verification, and streaming save;
- the existing `VIDEO_SANDBOX_RENDERING_ENABLED` rollout flag throughout cutover and rollback validation.

Do not combine queue cutover with deletion of generic infrastructure, broad artifact-platform cleanup, or unrelated podcast/task lifecycle changes.

## 2. Required validation gates

Do not remove a legacy dispatch or read path until all applicable gates pass:

1. A real queued video completes enqueue → pending card → `video_render` worker → verified MP4 → ready card/player.
2. Production observation covers progress, cancellation, explicit retry, worker loss/redelivery, stale queued-row reconciliation, sanitized failures, and exactly-once Artifact linkage/billing.
3. Same-thread concurrent requests prove separate jobs, sandboxes, workdirs, cancellation, and Artifact identities.
4. Queue wait, render duration, memory, and failure metrics are acceptable with concurrency `1`; scaling is not required to declare correctness.
5. The Phase 7 ledger reconciles every legacy artifact to Backfilled, Already migrated, or Frozen.
6. No nonterminal `VideoPresentationRun` remains, and historical rows needed for attribution have been snapshotted or migrated.
7. Public/shared legacy videos and every Frozen artifact have an explicit supported playback decision.
8. The flag has been exercised both ways during the rollback window without corrupting queued jobs or already-created MP4 artifacts.

A failed gate stops retirement. It does not justify bypassing the generic worker, routing video onto the default queue, or adding another image.

## 3. Staged cutover and flag semantics

### Stage A — dual-path validation

Keep the legacy path intact while `VIDEO_SANDBOX_RENDERING_ENABLED` selects interactive authoring:

- off: legacy authoring remains the rollback path;
- on: the deliverables subagent validates and enqueues a `DeliverableJob`, then returns immediately.

The flag controls new request routing only. It must not stop already queued tasks, hide existing job cards, change MP4 playback, or alter backfill execution.

### Stage B — queued path authoritative

After the gates pass, keep the flag on through a defined soak window. Disable new legacy run creation first while retaining enough legacy read/UI support to observe already-created runs and frozen artifacts. Drain and reconcile all legacy tasks and runs before deleting their registrations.

### Stage C — legacy execution retirement

Remove the legacy authoring/task/run surfaces listed below. Keep the rollout flag temporarily as a kill switch for new queued video requests: after legacy dispatch is gone, off means video generation is unavailable with a safe product message, not an implicit fallback to deleted code.

Removing the flag is a later, separate cleanup after the post-retirement rollback window. Do not remove it in the queue cutover change.

## 4. Backend legacy execution to remove

After Stage B drain:

- delete `deliverables/tools/video_presentation.py` and remove only its legacy imports/registration;
- delete `app/tasks/celery_tasks/video_presentation_tasks.py` and only its task registration/routing;
- delete `app/agents/video_presentation/` after proving narration/language behavior needed by queued jobs is independently implemented;
- remove the `generate_video_presentation` entries from the tool catalog, context-prune list, legacy receipt/activity handlers, and deliverables wait logic;
- remove prompt text that routes to the legacy tool while preserving queued enqueue and queued-job-mode instructions;
- remove legacy task-specific reservation/billing code only after proving generic queued execution and narration account exactly once.

Retain `app/celery_app.py`, the generic deliverable task registration, late acknowledgements, prefetch `1`, worker-lost rejection, reconciliation schedules, and kind-based routing. Retain the `video_render` worker services in both Compose files; they continue using the existing image.

Do not route queued video through the removed `video_presentation_tasks.py` name as a compatibility alias. Producers must dispatch the generic task with the kind policy selecting `video_render`.

## 5. Retire `VideoPresentationRun`, not `DeliverableJob`

Once no legacy task can create or update a run and all rows are terminal:

- remove `VideoPresentationRun` and `VideoPresentationStatus` from the runtime model;
- add a new Alembic migration that drops the legacy table; never edit historical migrations;
- remove only `video_presentation_runs` from Zero publication;
- remove legacy run REST endpoints and serializers;
- remove stale-run reconciliation or polling code that exists solely for `VideoPresentationRun`.

The replacement is already-live generic lifecycle data. Do not drop, rename to video-specific, or narrow `DeliverableJob`. Its safe Zero columns, GET/Cancel/Retry routes, failure-code contract, outbox reconciliation, heartbeat, attempts, and Artifact linkage remain authoritative for video and future deliverable kinds.

Migration rollback must be explicit: dropping the legacy table is the last backend schema step, after a backup/snapshot and after application rollback no longer depends on those rows.

## 6. Frontend run UI to remove

Remove UI that is keyed to `generate_video_presentation` or polls `VideoPresentationRun`:

- the legacy generate-video tool card, `StatusPoller`, and run-status rendering;
- `video_presentation_runs` Zero schema/query registrations and live hooks;
- assistant-message, thread, icon/label, and artifact-collection entries used only by the legacy tool/run receipt;
- public-thread legacy tool registration only after the shared-snapshot gate is resolved.

Retain the generic deliverable-job card and its queued, running, cancelling, cancelled, failed, retry, and ready states. Retain the ready handoff to the existing MP4 artifact card, manifest/Range serving, and `Mp4VideoPlayer`.

The browser Remotion/`new Function` renderer may be removed only when the Phase 7 ledger contains no Frozen artifact or shared snapshot that still requires it. If any remain, keep that read-only compatibility viewer isolated from new generation until those artifacts have a supported immutable replacement. Do not equate “no legacy runs” with “no legacy artifact reads.”

Remove `@remotion/*`, `@babel/standalone`, or related web dependencies only after a repository-wide import check proves no retained compatibility viewer or unrelated feature uses them.

## 7. Artifact and public-read cleanup is separate

Legacy writers, per-slide audio storage, `_legacy_ref` metadata, legacy artifact routes, and public snapshot endpoints are not part of the task/run cutover by default. Remove each only after:

- no queued or backfill job can read it;
- no Frozen or shared artifact needs it;
- blob and database counts are snapshotted and reconciled;
- MP4 playback covers the corresponding authenticated and public use case;
- the rollback window has closed.

This cleanup may follow Phase 8 as a separate change. Never delete backfill inputs merely because legacy task dispatch has stopped.

## 8. Configuration cleanup

Keep `VIDEO_SANDBOX_RENDERING_ENABLED` during cutover. Remove it only in a later change after the queued path is the accepted permanent implementation and an operational kill switch exists through normal deployment controls.

Remove obsolete settings only when their final caller is deleted. In particular:

- remove legacy in-process admission and segmentation environment settings if the queued worker and code-level policies supersede them;
- retain FPS, default language, and any narration/render setting still used by the queued pipeline;
- retain the version-controlled 180-second, 12-scene, repair-count, queue, and worker-limit policies as code, not new environment variables;
- do not add queue-name, worker-concurrency, or replacement rollout environment variables.

## 9. Tests and deletion gates

- A video request with the rollout flag on creates a `DeliverableJob`, dispatches the generic task to `video_render`, returns a pending receipt, and never invokes the legacy graph/task.
- Turning the flag off during the Stage A rollback window routes new requests to legacy without affecting already queued jobs. After Stage C, it safely disables new video generation instead.
- No producer or Celery route references the legacy video task after retirement.
- Generic deliverable claim, progress, cancellation, retry, reconciliation, billing, verification, save, and job-card tests remain.
- No `VideoPresentationRun` server publication, API, Zero client schema/query, or status poller remains after its drop migration.
- MP4 playback and Range seeking remain unchanged.
- Frozen/private/public legacy samples continue to work until their separately gated read cleanup.
- Compose validation shows `video_render` consuming only the generic task with the existing image and concurrency `1`.
- Backend tests, migration upgrade/downgrade, frontend lint/typecheck/tests, and one real queued-video acceptance run pass.

Use focused grep gates for deleted legacy task/run symbols. References in immutable migrations, migration ledgers, or deliberately retained read-only compatibility code are expected and must be reviewed, not mechanically erased.

## 10. Exit criteria

1. No new request can dispatch the legacy video graph or legacy Celery task.
2. Every legacy run is terminal and `VideoPresentationRun` plus its Zero/API/frontend polling surface is retired through a new migration.
3. Video generation uses `DeliverableJob` and `execute_queued_deliverable(job_id)` routed to the dedicated `video_render` worker on the existing image.
4. The generic queue, worker, lifecycle APIs/publication/card, cancellation/retry, reconciliation, and Artifact path remain intact.
5. The rollout flag remains available through cutover and is scheduled for separate removal after the rollback window.
6. Legacy artifact readers or blobs remain wherever Frozen/shared artifacts still require them; their eventual removal has its own evidence and gate.
