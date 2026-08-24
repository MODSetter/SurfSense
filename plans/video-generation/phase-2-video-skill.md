# Phase 2 — Video skill + mode-specific agent wiring

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 1 and [`phase-2b-queued-deliverable-jobs.md`](phase-2b-queued-deliverable-jobs.md).

## 1. Goal

Keep the existing deliverables subagent as the sole video owner while giving it two sharply separated modes:

- **interactive:** validate and enqueue one video deliverable job, then return a pending receipt;
- **trusted `queued_job`:** perform the complete authoring, narration, preflight, still review, render, verification, and streaming-save workflow.

Interactive mode never authors scenes, synthesizes narration, opens a sandbox, waits for completion, calls `wait_for_deliverable`, or invokes `renderMedia()`.

## 2. Skill contract

`docker/sandbox/skills/video/SKILL.md` is baked into `/opt/skills/video/` and is loaded only for trusted queued video work. It describes:

- 1920×1080 output, safe margins, readable contrast, restrained motion, and one clear purpose per scene;
- the closed offline font set: Inter, Lora, and JetBrains Mono;
- explicit imports and complete self-contained TSX modules with `export default`;
- arbitrary layouts—no fixed slide templates;
- narration through the existing trusted `synthesize_narration` tool, never runtime network fetches;
- the 12-scene and 180-second product limits;
- a bounded quality loop with at most two repair cycles.

The skill must not document injected globals, a compile-check preamble, regex export rewriting, browser rendering, inline execution, or environment-controlled render sizing.

## 3. Interactive mode

When the existing rollout flag enables sandbox video:

1. Main-agent routing sends a video request to the existing deliverables subagent.
2. The subagent normalizes a narrow brief: title, source references, requested content, and optional revision target.
3. It calls the thin video enqueue tool backed by the generic deliverable-job adapter.
4. The tool creates or returns the idempotent `DeliverableJob`, commits it, dispatches the generic task, and returns `status="pending"` plus `job_id`.
5. The subagent tells the user that the card tracks progress and returns immediately.

Only the enqueue tool is video-specific. The server, not the model, supplies the trusted kind, attribution, execution mode, checkpoint identity, sandbox owner, and policy.

Interactive mode keeps normal document/podcast/image behavior, but video does not receive queued-only authoring tools. Infrastructure errors are never echoed into chat. If broker publication fails after commit, return the durable pending receipt and let reconciliation republish the queued row.

## 4. Trusted queued-job mode

The generic Celery task loads the durable job, resolves its kind policy, atomically claims it, establishes trusted queued context, creates an isolated sandbox/workdir, and invokes the same `run_deliverable_subagent()` implementation.

Queued context includes trusted:

- `execution_mode="queued_job"`;
- `deliverable_job_id`;
- root thread/workspace/creator attribution;
- checkpoint key `{root_thread_id}::deliverable_job:{job_id}`;
- sandbox owner `deliverable-job:{job_id}`;
- fixed workdir `/workspace/deliverable-job-{job_id}`;
- normalized request and optional revision checkpoint.

These values are not model arguments.

### Queued tool allowlist

Queued video mode includes only tools needed for the workflow, including:

- load video instructions/source/revision material;
- typed `prepare_video_project`;
- narration synthesis;
- sandbox execution/preflight;
- multi-frame still review;
- final verification;
- streaming `save_artifact`.

It excludes:

- enqueue (prevents recursive jobs);
- podcast;
- image generation;
- legacy video generation;
- unrelated deliverable creation tools.

## 5. Complete queued authoring loop

The queued subagent:

1. drafts a durable scene/deck specification containing each scene's on-screen content and narration;
2. checks the 12-scene policy before authoring;
3. synthesizes narration through the existing trusted tool and rejects measured total audio above 180 seconds;
4. writes complete default-export TSX modules and trusted props through `prepare_video_project`;
5. runs native preflight (`bundle()` + `selectComposition()`), including the authoritative selected-duration gate;
6. renders and reviews start/middle/end frames per scene plus the contact sheet;
7. if needed, performs at most one compile/still repair;
8. renders one final MP4 with progress and cooperative cancellation;
9. calls `verify_artifact` on that exact MP4 using distributed frame plus stream/audio/duration/hash checks;
10. if needed, performs at most one final-verification repair and re-renders/re-verifies;
11. calls `save_artifact` with the unchanged deck specification as `markdown_representation`;
12. links the verified Artifact and marks the job ready.

After the two allowed repairs are consumed, failure is terminal until the user explicitly retries. The agent must never loop until the worker deadline.

The complete loop runs in queued-job mode. Moving only final rendering to Celery is explicitly non-compliant because it leaves authoring and repairs bounded by the interactive turn.

## 6. Progress, failure, and billing behavior

Trusted middleware—not model prose—maps narration, preparation, preflight, still review, rendering, verification, and save into job phase/progress updates.

The job boundary maps typed failures to stable public codes such as:

- `duration_limit`
- `quota_exceeded`
- `generation_failed`
- `render_failed`
- `verification_failed`
- `cancelled`

Full diagnostics are logged with the job ID and may be stored only as bounded internal detail. Celery, provider, ffmpeg, Remotion, stack trace, and subagent-timeout text never reaches the receipt, Zero, API, card, or chat.

Worker LLM/TTS usage is billed exactly once using existing accounting. Quota checks occur in the worker. Do not reserve or bill a duplicate wrapper around already billed narration.

## 7. Rollout and revision

Reuse the existing `VIDEO_SANDBOX_RENDERING_ENABLED` flag as the single authoring-entrypoint switch:

- off: current legacy video path remains available for rollback;
- on: interactive video requests enqueue the generic durable job.

Do not add environment variables. Queue routing, output limits, repair limits, worker time budgets, and Remotion limits are code policy; dedicated worker concurrency is Compose/Celery configuration.

Video revision remains regenerate-from-markdown: queued mode loads the current Artifact plus the stored deck specification, re-authors from that specification and the new instruction, and saves a verified new generation. It does not edit MP4 bytes or depend on persisted scene source.

## 8. Prompt and routing requirements

The main-agent and deliverables prompts must say:

- video requests return after enqueue;
- the pending card is the lifecycle source of truth;
- the existing deliverables subagent later performs the entire workflow in trusted queued-job mode;
- no scene code or raw infrastructure error is returned in chat;
- the browser receives only the verified MP4.

Prompt composition and tool loading must derive from the same execution mode and rollout decision so a prompt cannot advertise a tool that is absent.

## 9. Checks

- Interactive mode exposes video enqueue but not video authoring/render tools.
- Interactive video creates one idempotent job, returns pending, and performs no TTS/sandbox/render/verify/save work.
- Queued mode excludes enqueue, podcast, image, and legacy video tools.
- Trusted context creates unique checkpoint/workdir/sandbox ownership for concurrent jobs from one thread.
- One queued run executes the full authoring-to-save loop and publishes trusted phase progress.
- Native compile/still failure allows one repair; final verification failure allows one repair; no third repair occurs.
- Cancellation stops before verify/save and creates no Artifact.
- Public failures are stable/sanitized, and LLM/TTS billing occurs exactly once.
- Flag-off behavior remains the legacy rollback path; flag-on behavior uses the queue.

## 10. Exit criteria

1. Interactive video handling is enqueue-only.
2. The same deliverables subagent executes the whole workflow in trusted queued-job mode.
3. Mode-specific tool allowlists prevent recursive dispatch and unrelated work.
4. A successful queued run creates exactly one verified Artifact and marks its job ready.
5. Repairs, execution time, output duration, cancellation, failures, and billing are bounded and testable.
