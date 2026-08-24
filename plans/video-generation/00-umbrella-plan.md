# Sandbox-Native Queued Video Generation — Umbrella Plan

**Status:** DESIGN. No phase implemented yet.
**Scope:** Replace the monolithic `generate_video_presentation` LangGraph and browser-side Remotion renderer with a queued, sandbox-executed, verify-before-save deliverable that produces one MP4.
**Shape:** The interactive deliverables subagent validates and enqueues. A dedicated Celery worker runs that same subagent in trusted `queued_job` mode through authoring, narration, preflight, visual review, rendering, verification, and streaming persistence.

This document is the authoritative architecture. Phase documents add implementation detail but must not override these contracts.

## 1. Why

The current video path executes model-authored code in the browser, renders without a quality loop, and maintains video-only orchestration and storage. Video should instead use the artifact platform's existing verification, persistence, and serving path while gaining durable background execution, progress, cancellation, retry, and resource isolation.

Queuing only `renderMedia()` is insufficient: authoring, narration, compile repair, still review, final verification, and save all contribute to the workflow's runtime. The complete workflow therefore runs in the queued worker.

## 2. Target architecture

```text
user → main agent → interactive deliverables → enqueue tool
     → DeliverableJob + pending card → video_render queue
     → existing deliverables subagent (trusted queued_job mode)
     → isolated sandbox → preflight/stills/render
     → verify exact MP4 → stream save → Artifact + ready job
     → existing MP4 player
```

| Zone | Trust | Responsibility |
|---|---|---|
| Interactive deliverables subagent | Trusted | Validate a video request, enqueue an idempotent job, and return immediately |
| Queued deliverables subagent | Trusted | Own the whole authoring loop, TTS, billing, progress, policy, verification, and save |
| Job-owned sandbox | Untrusted-code jail; network denied | Bundle and execute complete TSX scene modules, render stills and MP4 |
| Browser | Client | Display job lifecycle, Cancel/Retry, and play only a verified MP4 |

No Artifact exists while a job is queued, running, failed, or cancelled. The MP4 and Artifact are created only after verification succeeds.

## 3. Locked decisions

- **Queued execution is v1.** Interactive video requests enqueue and return a pending receipt; no render is awaited in the chat turn.
- **Reuse the existing deliverables subagent.** A generic Celery task invokes it with trusted `execution_mode="queued_job"`; there is no second video agent or duplicate pipeline.
- **One generic durable lifecycle.** Every request gets an independent `DeliverableJob`. Video and future long-running deliverables share the model, transition service, executor, API, and card—not a job instance.
- **Kind-specific queue routing.** Video uses the code-defined `video_render` queue. A dedicated worker service reuses the existing backend/Celery image and broker, starts at concurrency `1`, and scales only from observed queue wait and memory headroom.
- **No new environment variables.** Keep the existing transitional `VIDEO_SANDBOX_RENDERING_ENABLED` rollout flag. Queue name, duration, scene count, repair count, worker budgets, Remotion delay-render limits, and worker concurrency are code/Compose policy.
- **Bounded product and execution policy.** Output is at most 180 seconds and 12 scenes. The worker has separate bounded soft/hard execution limits suitable for a three-minute 1080p render and never inherits the interactive 300-second subagent timeout.
- **Complete TSX modules, written verbatim.** Every scene imports its own dependencies and has a default export. No regex parsing, import stripping, named-export promotion, injected-global preamble, or fixed slide templates.
- **Deterministic preparation.** A trusted typed project-writer tool writes scene files with `SandboxSession.write_file()` and serializes `props.json`; model code is never interpolated through Python strings or shell quoting.
- **Native validation.** Remotion bundling and `selectComposition()` are the compile/metadata preflight. Duration policy is enforced after narration and again from selected composition metadata before rendering.
- **Bounded quality loop.** Review start/middle/end frames for each scene plus a contact sheet. Permit at most one compile/still repair and one final-verification repair.
- **Verification gates persistence.** `save_artifact` accepts only the exact MP4 covered by a signed verification receipt, streams it through the existing artifact storage path, and links the Artifact while marking the job ready transactionally.
- **Legacy remains a rollback during rollout.** The rollout flag selects the old or queued authoring entrypoint. Existing MP4 artifacts remain playable independent of the flag. Legacy deletion stays in Phase 8 after production validation/backfill.

## 4. Durable orchestration contract

The authoritative job and worker details are in [`phase-2b-queued-deliverable-jobs.md`](phase-2b-queued-deliverable-jobs.md).

At minimum:

- `queued → running → ready|failed`
- `queued|running → cancelling → cancelled`
- `failed|cancelled → queued` only by explicit Retry
- unique `(workspace_id, kind, tool_call_id)` idempotency
- commit the job before broker publication; reconcile old undispatched queued rows as a small outbox
- deterministic task IDs per attempt and atomic worker claims make duplicate publication harmless
- sanitized stable failure codes are public; internal diagnostics, Celery IDs, payloads, and checkpoints are not
- artifact attribution uses the root thread, while sandbox ownership is `deliverable-job:{job_id}` with a separate checkpoint thread key
- cancellation is cooperative through a trusted marker and Remotion cancel signal
- the job-owned sandbox is always terminated in `finally`, without allowing cleanup failure to overwrite the lifecycle result

## 5. Harness and authoring contract

The sandbox image remains based on `opensandbox/code-interpreter` and bakes Remotion, Chrome Headless Shell, ffmpeg/ffprobe, the harness, dependencies, and offline fonts. It is not the Celery worker image; the worker uses the existing backend/Celery image and creates a normal sandbox through the provider.

The harness:

- accepts typed scene metadata whose code is already a complete self-contained TSX module;
- writes modules verbatim and lets esbuild/Remotion report missing or malformed default exports;
- supports `--preflight`, multi-frame still rendering, contact-sheet generation, and full MP4 rendering;
- caches exact-input bundles by SHA-256 within the trusted job workdir and reuses them across preflight, still review, and final render;
- reports concise structured diagnostics and writes atomic progress snapshots;
- checks a cancel marker from `onProgress`, handles termination cooperatively, and removes partial output in `finally`;
- uses audio-derived timing and rejects narration or selected-composition duration over 180 seconds;
- imposes no template or fixed layout.

## 6. Progress, APIs, and frontend

Progress is trusted lifecycle metadata, not model-authored text. Middleware advances bounded phases across narration, project preparation, preflight, still review, render, verify, and save.

Zero publishes only lifecycle-safe columns. Authenticated APIs provide GET, Cancel, and Retry with workspace authorization. The generic live card represents queued, running, cancelling, cancelled, failed, and ready states; maps stable failure codes to client copy; and hands a ready video to the existing manifest/Range/`Mp4VideoPlayer` path. It must never expose provider, Celery, Remotion, ffmpeg, stack-trace, or subagent-timeout detail.

## 7. Phase index

| Phase | Subplan | Status |
|---|---|---|
| 1 | [`phase-1-sandbox-harness.md`](phase-1-sandbox-harness.md) — deterministic Remotion harness, preflight, progress, cancellation, and still review | DESIGN |
| 2 | [`phase-2-video-skill.md`](phase-2-video-skill.md) — mode-specific tools and the queued authoring loop | DESIGN |
| 2b | [`phase-2b-queued-deliverable-jobs.md`](phase-2b-queued-deliverable-jobs.md) — generic durable lifecycle, dispatch, worker, API, and card contracts | DESIGN |
| 3 | [`phase-3-narration-bridge.md`](phase-3-narration-bridge.md) — worker-owned TTS and exact duration policy | DESIGN |
| 4 | [`phase-4-verification.md`](phase-4-verification.md) — distributed-frame video verification | DESIGN |
| 5 | [`phase-5-persistence-and-serving.md`](phase-5-persistence-and-serving.md) — worker-owned streaming save, MP4 primary, and Range | DESIGN |
| 6 | [`phase-6-frontend.md`](phase-6-frontend.md) — generic live job card and ready MP4 handoff | DESIGN |
| 7 | [`phase-7-migration-backfill.md`](phase-7-migration-backfill.md) — reuse the queued worker for backfill where practical | DESIGN |
| 8 | [`phase-8-retire-legacy.md`](phase-8-retire-legacy.md) — retire legacy video orchestration after validation | DESIGN |

## 8. Sequencing and acceptance

Build the harness and generic job boundary first, then mode-specific agent wiring, narration, verification/save, APIs/card, and migration. The smallest end-to-end acceptance is:

1. interactive mode creates one idempotent pending job and returns without authoring;
2. one task reaches `video_render`, atomically claims the job, and runs the existing deliverables subagent in `queued_job` mode;
3. a fresh job-owned sandbox preflights complete TSX modules, emits progress, reviews multiple frames, renders within policy, and supports cancellation;
4. verification binds the exact MP4; streaming save creates and links the only Artifact;
5. Zero transitions the same card to ready and the existing MP4 player loads it;
6. duplicate dispatch, worker loss, terminal compile/policy failures, explicit retry, and concurrent same-thread jobs preserve idempotency, billing, and sandbox isolation.

Roll out behind the existing flag. Do not combine queue cutover with deletion of the legacy graph, run table, browser renderer, or old capacity settings; those removals remain a separately validated Phase-8 change.
