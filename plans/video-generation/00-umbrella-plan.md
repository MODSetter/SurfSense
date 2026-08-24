# Sandbox-Native Queued Video Generation — As-Built Specification

**Status:** IMPLEMENTED through Phase 6. Phases 7 and 8 remain future work.
**Scope:** Interactive video requests create durable background jobs. A backend-owned Celery executor authors, narrates, validates, renders, verifies, and stores one MP4 in an isolated sandbox.

This document is the authoritative architecture. Phase documents describe the implemented details and explicitly identify deferred work.

## 1. As-built architecture

```text
user → main agent → deliverables subagent → enqueue_deliverable_job
     → DeliverableJob + pending chat card
     → deliverables.execute_queued on the shared surfsense Celery worker
     → deterministic backend video executor
     → attempt-scoped sandbox → author → narrate → preflight/stills
     → render → verify exact MP4 → stream to Artifact storage
     → DeliverableJob.ready + artifact_id
     → existing MP4 card/player/download path
```

| Boundary | Responsibility |
|---|---|
| Interactive deliverables subagent | Validate the request, enqueue one idempotent job, and return immediately |
| Celery task | Claim the current attempt, supervise cancellation, map failures, and own cleanup |
| Backend video executor | Run the bounded, ordered video pipeline and assign structural fields deterministically |
| Attempt-owned sandbox | Execute generated TSX, render stills and MP4, and run media checks with network disabled |
| Browser | Subscribe to safe lifecycle state, issue job-specific Cancel/Retry, and play only the saved MP4 |

The queued worker does **not** invoke `run_deliverable_subagent()` in a special mode. It directly invokes `execute_video_deliverable()` from `app/deliverables/video/executor.py`. The shared `celery_worker` handles the task on the default `surfsense` queue; there is no `video_render` queue, service, or image.

## 2. Implemented decisions

- Every request has an independent `DeliverableJob`; kinds share infrastructure, not job instances.
- Interactive video handling is enqueue-only and never waits for TTS, sandbox work, rendering, or persistence.
- The database is the lifecycle source of truth. Celery is asynchronous transport and execution.
- Enqueue commits before broker publication. A periodic reconciler republishes stale queued rows.
- Task IDs, claims, state changes, sandboxes, workdirs, and output paths are attempt-scoped.
- Video policy is code-defined: at most 12 scenes, 180 seconds, two repair cycles, and bounded Celery soft/hard limits.
- Creative content comes from the LLM, while the backend deterministically assigns scene numbers, filenames, ordering, and repair merge rules.
- Generated scenes are complete TSX modules with explicit imports and default exports. The harness does not rewrite source with regexes.
- Narration and model calls remain trusted backend operations; the sandbox has no provider credentials or network access.
- Native Remotion bundling and `selectComposition()` are the compile and metadata preflight.
- Start/middle/end stills per scene and a contact sheet are reviewed before the final render when a vision model is available.
- Structural video verification and a SHA-256-bound receipt gate streaming persistence.
- The existing artifact manifest, HTTP Range, player, viewer, and download paths serve the finished MP4.
- The rollout flag still selects queued video or the legacy generation path. Legacy removal is deferred to Phase 8.

## 3. Durable lifecycle

```text
queued → running → ready
                 ↘ failed

queued → cancelled
running → cancelling → cancelled
failed|cancelled → queued  (explicit Retry)
```

Important invariants:

- unique `(workspace_id, kind, tool_call_id)` prevents duplicate jobs from repeated tool execution;
- a claim is an atomic conditional update bound to the current task attempt;
- worker heartbeats and terminal transitions can be restricted to the current `celery_task_id`;
- Retry preserves the job/card ID, increments `attempt_count`, and assigns a new deterministic task ID;
- public state contains stable failure codes, never provider, Celery, sandbox, Remotion, ffmpeg, path, or stack-trace details;
- sandbox ownership is `deliverable-job-{job_id}-attempt-{attempt_count}`;
- queued cancellation completes immediately; running cancellation is observed by a database watcher that cancels work and terminates the attempt sandbox;
- stale cancelling rows are reconciled; stale running-job reconciliation is not implemented.

## 4. Pipeline

The executor advances trusted phases directly:

```text
preparing → authoring → narrating → preparing
          → reviewing ↔ repairing
          → rendering → verifying ↔ repairing
          → saving → ready
```

The LLM returns a creative draft. Backend normalization produces the strict authored schema, assigns stable scene numbers and filenames, and preserves scene count and narration during repairs. The executor calls narration, project preparation, still review, verification, and artifact services as Python functions rather than exposing a queued tool allowlist.

The Remotion harness supports:

- `node render.mjs --preflight props.json`;
- `node render.mjs --stills props.json outdir`;
- `node render.mjs props.json out.mp4`;
- exact-input bundle caching;
- segmented rendering;
- atomic `progress.json`;
- a cancel marker and signal handling;
- partial-output cleanup.

The current worker reports stage-level progress and cancels by terminating the sandbox. It does not consume frame-level `progress.json` or drive the harness cancel marker.

## 5. Persistence and delivery

The verified MP4 is streamed from the sandbox through `ArtifactFileStreamInput`. Storage calculates byte count and SHA-256 while writing and rejects bytes that do not match the verification receipt.

`save_artifact()` currently commits the Artifact before the worker separately marks the job `ready`. Therefore the intended one-transaction Artifact-link/ready transition is **not** implemented; this is a documented hardening gap.

Zero publishes a safe subset of `deliverable_jobs`. The live card shows user-facing queued/running/cancelling/cancelled/failed/ready states without infrastructure terminology or a progress bar. Cancel and Retry use workspace-scoped REST routes and reconcile from Zero. Web requests use the same-origin proxy; desktop requests use the configured backend and bearer token.

## 6. Phase status

| Phase | Status | Outcome |
|---|---|---|
| 1 — Sandbox harness | IMPLEMENTED | Remotion image, preflight, stills, rendering, segmentation, progress/cancel primitives |
| 2 — Video authoring and routing | IMPLEMENTED | Enqueue-only interactive path and deterministic backend executor |
| 2b — Queued jobs | IMPLEMENTED | Generic lifecycle, shared-worker dispatch, cancellation/retry, APIs, Zero |
| 3 — Narration | IMPLEMENTED | Worker-owned TTS, measured audio, duration policy |
| 4 — Verification | IMPLEMENTED | Still review, structural MP4 verification, byte-bound receipt |
| 5 — Persistence and serving | IMPLEMENTED WITH GAP | Streaming save and HTTP Range; save/ready is not one transaction |
| 6 — Frontend | IMPLEMENTED | Live job card, actions, library in-flight merge, MP4 handoff |
| 7 — Migration/backfill | DESIGN | Re-render every legacy video in the server sandbox and replace client-executed scene code with verified MP4 |
| 8 — Legacy retirement | DESIGN | Remove the old generator, run lifecycle, browser renderer, and stored scene-code execution after Phase 7 |

## 7. Remaining hardening and future work

- Make Artifact creation, job linkage, and `ready` publication atomic or add explicit compensation/reconciliation.
- Decide whether frame-level render progress should be consumed; the current UI intentionally omits percentages.
- Add stale-running reconciliation if production evidence requires it.
- Expand final MP4 visual sampling beyond the current midpoint structural frame check if needed.
- Evaluate a dedicated resource queue only from measured contention; it is not part of the current architecture.
- Complete Phase 7 for every legacy video before removing migration inputs or beginning Phase 8.
- Remove all browser execution of stored video scene code once verified MP4 replacements are complete.

## 8. Acceptance

The implemented path is accepted when:

1. one interactive tool call returns an idempotent pending receipt without waiting;
2. the shared Celery worker claims the correct attempt and executes the complete backend pipeline;
3. concurrent and retried jobs use isolated task IDs, sandboxes, workdirs, and output paths;
4. cancellation stops the current attempt and prevents verify/save;
5. only receipt-matching MP4 bytes are saved through the generic artifact path;
6. Zero advances the same card to ready and the existing MP4 player can seek and download;
7. public lifecycle data remains sanitized and duplicate publication cannot duplicate execution or billing.
