# Phase 7 — Migration & backfill

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phases 1–6 and the generic `DeliverableJob` worker described by the queued-deliverables plan. Runs before Phase 8 retires any legacy video path.

## 1. Goal

Convert every reproducible legacy video artifact from an audio PRIMARY plus browser-rendered `scene_codes` to a verified MP4 PRIMARY without asking the user to regenerate it.

This is a re-render, not a transcode: legacy artifacts contain narration and scene source, but no MP4. Backfill must use the production sandbox harness, verification gate, streaming persistence path, and durable job lifecycle. It must not introduce a second video worker, a second lifecycle table, or an in-process rendering path.

The rollout flag remains an authoring cutover control. Backfill may run while `VIDEO_SANDBOX_RENDERING_ENABLED` is either value, but only after the queued worker path has passed production acceptance. Backfill dispatches directly from trusted server code; it is never exposed as an interactive model tool.

## 2. Reuse the generic job system

Keep `surfsense_backend/scripts/backfill_video_mp4.py` as a separate one-time enumerator. Do not extend `backfill_video_artifacts.py`, whose historical purpose is `VideoPresentationRun` to Artifact migration.

The script does only control-plane work:

1. Select legacy video artifacts whose PRIMARY is still `audio/mpeg`.
2. Determine whether all required scene and per-slide audio inputs exist.
3. In dry-run mode, report reproducible, already-migrated, and frozen candidates without creating jobs.
4. In apply mode, create or return one idempotent `DeliverableJob` per source artifact and dispatch the existing generic `execute_queued_deliverable(job_id)` task.
5. Record a bounded migration ledger from job outcomes; do not poll Celery internals or render in the CLI process.

Use the existing video kind policy and its `video_render` route. Store a trusted backfill intent and source artifact ID in the private request/checkpoint payload; do not add a public backfill schema, a video-specific job model, or a second Celery task. The idempotency key must be deterministic for the source artifact and migration version so rerunning the script cannot create duplicate jobs or billing.

The generic worker continues to own:

- atomic claim, heartbeat, progress, cancellation, retry, and stale-job reconciliation;
- the isolated job sandbox and trusted workdir;
- queue routing to `video_render`;
- bounded soft/hard execution limits and worker-loss behavior;
- verification, streaming save, Artifact linkage, failure sanitization, and cleanup.

Backfill uses the same dedicated `video_render` worker service, concurrency `1`, broker, and existing backend/Celery image as new video jobs. It receives no separate image, queue, worker implementation, or capacity environment variable. New and backfill jobs therefore share the same resource ceiling and FIFO capacity behavior.

## 3. Deterministic backfill execution

Backfill does not need the model to invent or rewrite content. In trusted queued-job mode, the worker loads the stored inputs and follows the deterministic video preparation/render path:

1. Stream the stored per-slide audio into the job-owned workdir.
2. Reconstruct typed project inputs from the stored `scene_codes`, timing, and audio references.
3. Apply an explicit legacy-source compatibility adapter before the normal native bundler preflight. Keep this adapter confined to migration input handling; do not restore regex rewriting to the live scene contract.
4. Run preflight, distributed still/contact-sheet checks where supported, final render, authoritative video verification, and byte-bound save.
5. Save the MP4 as a new PRIMARY generation on the same source `artifact_id`, then link that artifact to the job and mark the job ready atomically.

The compatibility adapter may supply the historical injected symbols required by stored scenes, but it must never modify source with regexes or promote exports heuristically. Validate the adapter against representative real legacy artifacts before enqueueing the full batch.

The normal 180-second and 12-scene product limits govern newly authored videos. They must not silently strand historical artifacts that previously exceeded those limits. Inventory those artifacts during dry-run and define a versioned migration policy before apply: either permit their existing measured duration/scene count only for trusted backfill, within the worker's bounded execution budget, or classify them as frozen. User input cannot select this exception.

## 4. Outcomes and persistence safety

Each source artifact has exactly one terminal migration outcome:

- **Backfilled:** verification succeeds and the MP4 becomes the artifact's PRIMARY generation.
- **Already migrated:** the source already has a valid MP4 PRIMARY; no job is dispatched.
- **Frozen:** required source data is missing, compatibility preflight fails, visual/frame sanity fails, or a terminal render/verification failure remains after the bounded retry policy.

Frozen means immutable and explicitly accounted for; it does not mean silently deleting the artifact or asking the user to regenerate it. Phase 8 must not remove the playback/data path needed by frozen artifacts unless they have first been migrated, exported to a supported immutable representation, or covered by an approved product decision.

No queued, running, failed, cancelled, or frozen job may replace the source PRIMARY. Storage success followed by database failure uses the same compensating blob cleanup as live queued video generation. Per-slide audio and legacy scene metadata remain intact until the migration ledger and rollback window are closed.

## 5. Idempotency, load, and operations

- Use a versioned source-artifact key as the tool-call/idempotency identity.
- Commit the `DeliverableJob` before broker publication and let the normal queued-row reconciler recover publication failures.
- Skip MP4 PRIMARY artifacts before job creation and recheck after worker claim to close races.
- Do not create all jobs at once. Enqueue bounded batches and observe queue wait, render duration, worker memory, failures, and live-job latency before continuing.
- Live and backfill work share `video_render`; pause the enumerator, rather than adding an ad hoc admission gate, if migration load harms interactive jobs.
- Cancel and retry through the generic job state machine. Retry preserves the same job identity and increments its attempt.
- Keep internal compatibility and render diagnostics private. Reports expose source ID, terminal category, stable failure code, and timestamps only.

## 6. Validation and rollout

1. Run dry-run inventory over a representative production sample and then the full population.
2. Validate real examples for injected-symbol compatibility, fonts, audio timing, legacy durations, missing blobs, and blank/solid-color output.
3. Backfill one artifact through `DeliverableJob` and observe queued/running progress, verification, streamed save, ready linkage, and MP4 playback.
4. Prove cancellation leaves the original PRIMARY untouched and retry resumes through the same job.
5. Prove duplicate enumeration and duplicate task publication do not create duplicate jobs, Artifacts, blobs, or billing.
6. Run bounded batches while measuring both backfill and newly requested video queue latency.
7. Re-run inventory after drain and reconcile every source artifact to Backfilled, Already migrated, or Frozen.

## 7. Exit criteria

1. Every legacy video artifact is represented in the migration ledger with a terminal outcome.
2. Every reproducible artifact has a verified MP4 PRIMARY on the same artifact identity; no user was asked to regenerate.
3. Backfill used the generic `DeliverableJob` state machine, generic Celery task, `video_render` queue, existing worker image, sandbox isolation, verification, and streaming save path.
4. Re-running enumeration is a no-op except for explicitly retried failed/cancelled jobs.
5. Frozen artifacts and their required legacy playback/data dependencies are explicitly enumerated for Phase 8.
6. Per-slide audio and legacy metadata remain available through the production validation and rollback window.
