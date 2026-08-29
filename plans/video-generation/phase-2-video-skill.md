# Phase 2 — Video authoring and agent wiring

**Status:** IMPLEMENTED.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 1 and Phase 2b.

## 1. Outcome

Video generation has two separate execution boundaries:

- **interactive deliverables subagent:** validates the request, calls `enqueue_deliverable_job` once, and returns a pending receipt;
- **backend video executor:** performs authoring, narration, preparation, review, rendering, verification, and save inside the Celery task.

There is no trusted `queued_job` mode in `run_deliverable_subagent()`, no queued tool allowlist, and no agent checkpoint used by the worker. The explicit executor is the canonical architecture.

## 2. Interactive routing

When `VIDEO_SANDBOX_RENDERING_ENABLED` and sandboxing are enabled:

1. the existing main-agent routing sends video work to the deliverables subagent;
2. its prompt tells it to enqueue once and return;
3. only `enqueue_deliverable_job` is exposed for video creation;
4. the server supplies kind, workspace, root-thread attribution, creator, tool-call identity, and request version;
5. the tool commits the idempotent job, attempts dispatch, and returns `status="pending"` with `job_id`.

Interactive execution never authors scenes, synthesizes narration, opens a sandbox, waits for completion, verifies output, or saves an Artifact. Broker failures after commit remain recoverable through queued-row reconciliation and are not exposed in chat.

When the flag is off or sandboxing is unavailable, the existing `generate_video_presentation` path remains the rollback behavior until Phase 8.

## 3. Backend-owned authoring

`execute_video_deliverable()` in `app/deliverables/video/executor.py` owns the ordered pipeline. It directly calls trusted Python functions instead of asking an agent to select tools.

```text
creative authoring
  → backend normalization
  → narration
  → deterministic project preparation
  → native preflight
  → still review
  → bounded repair when required
  → final render
  → structural verification
  → bounded repair when required
  → receipt-bound streaming save
```

The worker obtains the billable LLM from the configured provider and wraps generation calls with queued-deliverable accounting. Vision review obtains the configured vision model separately. TTS retains its existing narration billing path.

## 4. Deterministic authoring contract

The LLM controls creative fields:

- title and visual direction;
- scene copy and narration transcript;
- complete TSX body for each scene;
- markdown representation.

The backend controls structural fields:

- scene count validation;
- sequential scene numbers;
- stable scene and audio filenames;
- scene ordering;
- normalization of accepted field-name aliases;
- repair merge behavior;
- preservation of narration and scene count during repair.

This separation prevents probabilistic model output from choosing filesystem identity or producing inconsistent scene numbering. The strict normalized result is `AuthoredVideo`, regardless of harmless naming variations in the creative draft.

## 5. Prompt and skill roles

`executor.py` contains the authoritative author and repair prompts for queued work. They require complete self-contained TSX modules, explicit imports, default exports, safe margins, readable contrast, restrained motion, supported offline fonts, and no duplicate watermark.

`docker/sandbox/skills/video/SKILL.md` remains baked into the sandbox for video guidance and future interactive sandbox use. The queued worker does not load that skill through a subagent and does not expose narration, preparation, review, verification, or save as model-selected tools.

Prompts never explain Celery, queue topology, sandbox ownership, or other infrastructure to the user.

## 6. Repair policy

The executor uses one shared repair counter:

- preflight or blocking still-review findings can trigger one repair before that stage becomes terminal;
- post-render structural verification can trigger repair while the total remains below `VIDEO_SPEC.max_repair_cycles` (currently two);
- repaired output is prepared/rendered and verified again;
- repairs may update scene code and markdown but cannot change narration transcripts or scene count.

The loop is bounded and cannot continue until a worker deadline.

## 7. Lifecycle and failure mapping

The executor writes trusted phase/progress heartbeats directly. Model prose never controls lifecycle state.

Failures map to stable public codes:

- `duration_limit`
- `quota_exceeded`
- `generation_failed`
- `render_failed`
- `verification_failed`
- `cancelled`

Bounded diagnostics may be stored in `internal_error`, but that field and all provider, Celery, OpenSandbox, Remotion, ffmpeg, path, and stack-trace detail remain private.

## 8. Revision behavior

An optional `revision_artifact_id` is stored in the private request. The executor loads the current Artifact and expected generation, authors the requested revision, and saves a new verified generation through optimistic concurrency. It does not edit MP4 bytes in place.

## 9. Acceptance

- the interactive path performs enqueue only;
- repeated tool execution returns the same job;
- the Celery worker has no dependency on `run_deliverable_subagent` or a LangGraph checkpointer;
- backend normalization always assigns deterministic scene identity;
- one worker attempt executes the complete author-to-save pipeline;
- repair, duration, scene count, task time, billing, and cancellation are bounded;
- flag-off continues to select the legacy rollback path.
