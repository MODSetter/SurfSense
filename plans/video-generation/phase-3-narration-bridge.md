# Phase 3 — Queued narration bridge and duration policy

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 1 (sandbox harness), Phase 2 (video skill), and Phase 2b (queued deliverable jobs).

## 1. Goal

Run narration as part of the queued video workflow, inside the dedicated worker's invocation of the existing deliverables subagent. The interactive request path only validates and enqueues a `DeliverableJob`; it never synthesizes narration, authors scenes, or waits for rendering.

The trusted worker performs TTS without granting the sandbox network access, writes inert audio bytes into the job-owned workdir, measures the resulting media, and applies the exact 180-second output policy before authoring can proceed to final rendering.

## 2. Worker-owned narration

Reuse `deliverables/tools/synthesize_narration.py` in trusted `execution_mode="queued_job"`:

- Resolve the sandbox and workdir from trusted job context. The sandbox owner is `deliverable-job:{job_id}` and the workdir is `/workspace/deliverable-job-{job_id}`; neither value is model-controlled.
- Reuse current voice/language resolution, provider calls, token/TTS accounting, and quota checks. Narration billing occurs exactly once in the worker; do not add a second video-level reserve around the nested tool.
- Write each generated audio file with `SandboxSession.write_file()` under `<workdir>/public/`, returning filenames suitable for Remotion `staticFile()`.
- Keep credentials and network access on the trusted side. The sandbox remains network-disabled.
- Emit lifecycle progress through queued-job middleware. Progress and phase are trusted job metadata, not model-authored chat text.
- Check for cancellation between provider calls and before project preparation. A cancelling job stops before render, verify, or save.

The tool is available to the existing deliverables subagent only in queued-job mode for video work. Interactive mode exposes the enqueue tool instead, and queued-job mode excludes enqueue and unrelated image, podcast, and legacy-video tools to prevent recursive dispatch.

## 3. Exact duration gate

Duration is output policy, not a worker timeout:

- `max_duration_seconds = 180` is defined by the version-controlled video `DeliverableKindSpec`; do not add an environment variable.
- After narration, measure the exact duration of every generated audio file from the media itself and calculate the transcript/audio total using the same timing inputs that will drive composition metadata.
- Accept an exact total of `180.000` seconds. Reject only when the measured total is strictly greater than 180 seconds.
- On rejection, stop before final render, verification, artifact persistence, or blob upload and mark the job failed with public `failure_code="duration_limit"`.
- Do not expose provider, ffmpeg, Remotion, sandbox, Celery, stack-trace, or subagent-timeout text. Full detail is logged with the job ID and only bounded diagnostics may be stored internally.
- The Remotion harness independently enforces the authoritative second gate after `selectComposition()`: `composition.durationInFrames / composition.fps <= 180` before `renderMedia()`. Narration acceptance never bypasses that composition gate.

The 180-second output cap is independent of bounded worker soft/hard execution limits. The queued worker must not inherit the interactive 300-second subagent timeout and must not run unbounded.

## 4. Lifecycle and failure invariants

- The `DeliverableJob` exists before narration starts; no `Artifact` exists while the job is queued, running, cancelling, failed, or cancelled.
- Narration output is resumable job-owned sandbox input, not an artifact blob.
- Terminal narration, quota, policy, or cancellation paths clean up job-owned temporary output and leave no `Artifact` row or retained PRIMARY blob.
- Automatic retries are limited to typed transient provider/infrastructure failures. Policy and quota failures require the user's explicit Retry, which requeues the same job identity and increments its attempt.
- Sandbox termination runs in worker `finally`; lifecycle state updates survive cleanup errors.

## 5. Checks

- Interactive video execution returns a pending job receipt without invoking TTS.
- The queued worker invokes narration in the existing deliverables subagent and writes N non-empty files under the trusted job workdir's `public/`.
- Billing and quota accounting occur once across worker and narration tool boundaries.
- Measured totals below 180 seconds and exactly 180 seconds pass; any value above 180 seconds fails with `duration_limit` before render.
- Cancellation during multi-scene narration stops subsequent provider calls and never reaches verify/save.
- Public job data and chat output contain only stable failure codes/client-safe copy, never internal exception text.

## 6. Exit criteria

1. Narration is wholly owned by the queued worker workflow and never blocks the interactive turn.
2. Audio reaches the network-disabled, job-isolated sandbox through trusted file writes.
3. The exact post-narration 180-second gate runs before rendering, with the composition-duration gate retained as the final authority.
4. Failed or cancelled narration leaves a durable job lifecycle but no Artifact or retained PRIMARY blob.
