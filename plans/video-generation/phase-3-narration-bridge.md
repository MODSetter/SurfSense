# Phase 3 — Queued narration bridge and duration policy

**Status:** IMPLEMENTED.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phases 1, 2, and 2b.

## 1. Outcome

Narration runs inside the backend-owned queued video executor. The interactive request path only enqueues a job and never performs TTS or waits for audio.

The executor directly calls `synthesize_narration()` as a trusted Python function. It does not expose narration as an interactive model tool or invoke it through a queued subagent mode.

## 2. Trusted narration flow

For each normalized scene:

1. resolve voice/language and the configured TTS provider using existing video narration policy;
2. call the provider from the trusted backend with existing quota and billing;
3. write returned audio bytes into the attempt workdir's `public/` directory through `SandboxSession.write_file()`;
4. probe each file with ffprobe;
5. return the filename and measured duration used by Remotion.

Scene audio synthesis runs concurrently with `asyncio.gather`. Credentials and provider network access never enter the sandbox.

Attempt ownership is:

```text
owner:   deliverable-job-{job_id}-attempt-{attempt_count}
workdir: /workspace/deliverable-job-{job_id}-attempt-{attempt_count}
audio:   <workdir>/public/slide-{scene_number}.{extension}
```

## 3. Duration policy

`VIDEO_SPEC.max_duration_seconds` is 180.

- The narration bridge sums measured media durations after synthesis.
- A total at or below 180 seconds proceeds.
- A total above 180 seconds raises the typed duration-limit failure before final rendering or persistence.
- The Remotion harness independently calls `selectComposition()` and rejects selected composition duration above 180 seconds.

The product duration cap is independent of the Celery task's 3600-second soft and 3900-second hard limits.

## 4. Lifecycle, cancellation, and billing

The executor writes the trusted `narrating` heartbeat before synthesis and commits it. Model text cannot set phase or progress.

The cancellation watcher runs in parallel with the full executor. A cancellation request cancels the executor task and terminates the attempt sandbox. Because all scene TTS calls are started together, cancellation does not serially prevent “later” provider calls; it cancels the in-flight narration operation as part of executor cancellation.

Narration keeps its existing `video_presentation_generation` billing boundary and quota reserve. Worker creative LLM calls use the separate queued-deliverable billing wrapper. No duplicate outer narration reserve is added.

Transient provider failures may use the bounded Celery retry path. Duration and quota failures are terminal for the current attempt and require explicit Retry.

## 5. Persistence invariants

- `DeliverableJob` exists before TTS starts.
- Narration files are temporary attempt-owned sandbox inputs, not Artifact files.
- No Artifact is created during narration.
- Cancellation or narration failure prevents render, verification, and save.
- Sandbox cleanup is attempted in worker `finally`; cleanup failure does not change the committed lifecycle result.

## 6. Acceptance

- interactive enqueue invokes no TTS;
- queued execution writes non-empty audio under the exact attempt workdir;
- provider secrets remain outside the sandbox;
- billing and quota checks occur through the existing narration boundary;
- measured output above 180 seconds fails before render;
- selected composition duration is checked again by the harness;
- failed/cancelled narration creates no Artifact.
