# Phase 2b — Queued deliverable jobs

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Role:** Authoritative generic job, dispatch, worker-mode, lifecycle API, and live-card specification for queued video and future long-running deliverables.

## 1. Goal

Add one reusable durable adapter around the existing deliverables subagent. Video is the first kind:

```text
interactive enqueue
  → DeliverableJob
  → generic Celery task routed to video_render
  → existing deliverables subagent in trusted queued_job mode
  → verified Artifact
```

Each request has its own row, task attempt, sandbox, billing, cancellation, retry, and Artifact linkage. Deliverable kinds share infrastructure, never a job instance.

## 2. Generic model

Add `DeliverableJob` and stable enums through a new migration; do not extend the legacy `VideoPresentationRun`.

Store only generic lifecycle data:

- kind and title;
- workspace, root thread, and creator attribution;
- tool-call idempotency key;
- trusted request/checkpoint JSON;
- status, phase, and progress percentage;
- nullable final `artifact_id`;
- Celery task ID and attempt count;
- stable public failure code and bounded internal diagnostic detail;
- cancellation timestamp;
- claim, heartbeat, finish, creation, and update timestamps.

Enforce unique `(workspace_id, kind, tool_call_id)`. Repeated tool execution returns the existing job and cannot dispatch or bill twice.

Do not create format-specific columns. Video-specific constants belong in trusted kind policy.

## 3. State machine

The service permits only:

```text
queued → running → ready
                 ↘ failed

queued|running → cancelling → cancelled
failed|cancelled → queued       (explicit Retry only)
```

Use conditional SQL updates for atomic claims/transitions. No repository abstraction is needed beyond the small set of lifecycle queries.

Rules:

- `ready` requires a linked verified Artifact.
- No Artifact is present in queued, running, cancelling, failed, or cancelled states.
- Pending cancellation reaches `cancelled` without worker execution.
- Running cancellation reaches `cancelling`; worker cooperation stops before verify/save.
- Retry preserves the same job/card identity, increments the attempt, rechecks policy/quota, assigns a deterministic new task ID, and returns to queued.
- Automatic retry is limited to classified transient broker/provider failures with bounded backoff. Compile, product policy, quota, and verification failures require explicit Retry.

## 4. Trusted kind registry

A code-defined `DeliverableKindSpec` registry selects queue, policy, and worker budgets. Video defines:

- queue: `video_render`;
- maximum duration: 180 seconds;
- maximum scenes: 12;
- repair cycles: one compile/still repair and one final-verification repair;
- bounded soft/hard worker time limits suitable for a three-minute 1080p output.

Do not add environment variables for these values, queue names, concurrency, or Remotion delay-render limits. Future kinds add one registry entry and a thin enqueue tool. They share `video_render` only if CPU, memory, latency, and operational characteristics are genuinely similar.

## 5. Enqueue, idempotency, and outbox

The video enqueue tool exposes only a narrow schema: title, normalized brief/source references, and optional revision target. The server constructs kind and trusted context.

Enqueue:

1. create or return the idempotent job in a database transaction;
2. commit before broker publication;
3. preassign and persist a deterministic task ID for the attempt;
4. publish `execute_queued_deliverable(job_id)` to the registry-selected queue;
5. return `{"status":"pending","job_id":...}` immediately.

It never calls `wait_for_deliverable`.

Treat queued rows as a small outbox. If publication fails after commit, retain and return the durable queued job without broker detail. A periodic reconciler republishes old queued rows whose dispatch is absent/stale. Deterministic task IDs plus atomic worker claims make duplicate publication harmless.

## 6. Generic Celery executor

Implement one `execute_queued_deliverable(job_id)` task. It:

1. opens the Celery database session and atomically claims the job;
2. loads trusted request data and the kind policy;
3. establishes heartbeat and lifecycle monitoring;
4. creates a fresh isolated sandbox and trusted workdir;
5. invokes the existing `run_deliverable_subagent()` with `execution_mode="queued_job"`;
6. records ready, failed, or cancelled through typed state transitions;
7. always terminates the job-owned sandbox in `finally`.

Preserve `acks_late`, `worker_prefetch_multiplier=1`, and `task_reject_on_worker_lost`.

Artifact attribution uses `root_thread_id`. Background checkpoint state uses `{root_thread_id}::deliverable_job:{job_id}`. Sandbox ownership uses `deliverable-job:{job_id}`. This separation prevents same-thread jobs from sharing state or terminating each other's sandbox.

The task runs the whole deliverables workflow—not just `renderMedia()`.

## 7. Queue and worker topology

Add a dedicated worker service for `video_render` to production and development Compose:

- reuse the existing backend/Celery image and broker;
- listen only to the code-defined `video_render` queue;
- start with concurrency `1`;
- process later video requests in queue order while the slot is occupied;
- scale replicas/concurrency only after production metrics show queue pressure and sufficient CPU/memory headroom.

Do not create a Docker image, queue-name environment variable, or concurrency environment variable.

Different resource classes use different queues while retaining the same task and model. For example, a future I/O-heavy export can use `io_deliverables` and its own worker so it does not contend with Chrome rendering.

## 8. Progress and cooperative cancellation

Trusted middleware maps lifecycle phases such as narration, preparation, preflight, still review, rendering, verification, and save to bounded percentages. Model text never controls status or progress.

During render, the harness atomically writes progress JSON. A worker monitor:

- updates the job heartbeat/progress;
- notices a database transition to `cancelling`;
- writes the trusted cancel marker consumed by Remotion's cancellation signal.

SIGTERM/SIGINT and user cancellation remove partial output and stop before verification/save. State updates survive cleanup errors.

Reconciliation republishes undispatched queued rows. It marks a running job failed only when both task state and heartbeat are stale; elapsed render time alone is not evidence of failure.

## 9. Verification and transactional save

Queued mode reuses narration, verification, artifact streaming, and persistence services.

`save_artifact` must:

1. confirm the signed verification receipt matches the exact MP4 hash;
2. stream bytes through the existing `ArtifactFileStreamInput` path;
3. link `job.artifact_id` and transition the job to ready in one database transaction;
4. compensate by deleting the uploaded blob if storage succeeds but the database transaction fails.

Failed/cancelled jobs retain neither an Artifact row nor a PRIMARY blob.

Worker LLM and TTS billing uses existing accounting exactly once. Quota checks run in the worker; no duplicate video-level reserve wraps nested narration billing.

## 10. Public lifecycle and APIs

Publish only lifecycle-safe job fields through Zero:

- id, kind, title;
- status, phase, progress, failure code;
- artifact ID;
- workspace/root-thread IDs;
- lifecycle timestamps.

Never publish request/checkpoint JSON, task IDs, heartbeat internals, sandbox details, or internal diagnostics.

Authenticated endpoints provide GET, Cancel, and Retry. They enforce workspace authorization and ownership, reject cancellation after Artifact linking begins, and apply state-machine/idempotency rules.

Public errors are stable codes such as `duration_limit`, `quota_exceeded`, `generation_failed`, `render_failed`, `verification_failed`, and `cancelled`. Provider, Celery, OpenSandbox, Remotion, ffmpeg, stack trace, and subagent-timeout details remain internal.

## 11. Generic live job card

Create a generic card for:

- queued;
- running with phase/progress;
- cancelling;
- cancelled;
- failed;
- ready.

The card subscribes through the existing authorized thin-row/Zero pattern. Cancel is available until Artifact linking starts. Retry is available for failed/cancelled jobs and preserves card identity. Failure copy is mapped client-side from stable codes.

When video becomes ready, the card hands the linked Artifact to the existing manifest/HTTP Range/`Mp4VideoPlayer` path. It does not request media before playback and does not introduce a second video player.

Merge in-flight jobs into the artifacts library using the existing lifecycle merge pattern. Podcasts may retain their dedicated lifecycle initially.

## 12. Checks and exit criteria

Backend coverage:

- transition legality and conditional-claim races;
- idempotent enqueue, deterministic attempts, and outbox reconciliation;
- duplicate broker delivery and worker loss;
- mode-specific tool allowlists;
- same-thread sandbox/checkpoint isolation;
- cancellation before and during render;
- explicit retry and quota recheck;
- sanitized public failures;
- billing exactly once;
- no Artifact before verified transactional save.

Integration coverage:

- migration upgrade/downgrade;
- enqueue → `video_render` → queued subagent → verify → streaming save → ready;
- stale heartbeat/task reconciliation;
- cancellation and failed verification;
- concurrent jobs from one thread;
- Compose configuration with the existing image and concurrency `1`.

Frontend coverage:

- every lifecycle state;
- safe failure-code mapping;
- Cancel/Retry;
- ready handoff to the existing MP4 player and library identity.

Exit when one real queued video shows durable progress, survives chat disconnect, supports cancellation/retry, creates no premature Artifact, and reaches ready with one verified MP4.
