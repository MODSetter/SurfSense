# Phase 4 — Worker-owned video verification

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 1 (deterministic harness), Phase 2b (queued deliverable jobs), Phase 3 (narration duration gate), and the existing artifact verification framework.

## 1. Goal

Make verification the authoritative worker-owned gate between a rendered MP4 and persistence. The existing deliverables subagent, running in trusted queued-job mode on the dedicated video worker, calls the existing `verify_artifact` tool after render. Interactive execution never verifies or waits.

A pending `DeliverableJob` card exists before any artifact. An `Artifact` must not exist until the exact rendered MP4 has passed verification and `save_artifact` completes.

## 2. Video adapter and byte-bound receipt

Register `verification/formats/video.py` for `.mp4` with canonical adapter identity `video` and MIME type `video/mp4`. `verify_artifact` keeps its existing public signature and dispatches through the adapter.

Verification produces a signed receipt bound to the final MP4's SHA-256:

- Probe and hash the MP4 in the job-owned sandbox so the backend does not materialize the full video in memory.
- Return only bounded probe, frame-analysis, duration, and digest results to the trusted verification service.
- Any mutation or repair render invalidates the receipt and requires verification again.
- `save_artifact` must stream-hash the exact uploaded bytes and reject a digest that does not match the signed receipt.
- The receipt's `format="video"` is the canonical persistence format; the filename suffix is only adapter lookup.

The adapter is inert unless an MP4 is verified and may be registered independently of rollout state. The existing rollout flag controls whether queued video generation is offered, not receipt validity.

## 3. Authoritative final checks

Preserve the existing stream, audio, duration, and hash checks and improve visual sampling:

- Require a readable MP4 container, at least one non-empty video stream, mandatory non-empty audio, positive duration, and 1920×1080 output.
- Recheck the exact duration policy from composition/media metadata. `duration <= 180.000` seconds passes; any value strictly above 180 seconds fails with `failure_code="duration_limit"`.
- For segmented output, compare final duration with expected scene duration within a documented small tolerance and require audio to span the file.
- Sample multiple distributed frames across the final MP4, not only one midpoint. Reject blank, black, single-color, corrupt, or missing samples.
- Preserve the bounded pre-render still review from the authoring loop: start/middle/end frames per scene plus a contact sheet may use the existing configured vision model. This review has no fixed slide-template assumption and checks clipping, overflow, contrast, hierarchy, blank frames, and safe margins.
- Final verification remains authoritative even when advisory still review passed. It must remain bounded and cannot fan out without limit.

The workflow permits at most one final-verification repair after the earlier compile/still repair. A repaired output is rendered and verified from scratch. Failure after the second total repair cycle is terminal until explicit user Retry.

## 4. Queue, progress, and cancellation

Verification executes inside `execute_queued_deliverable(job_id)` through the same queued deliverables subagent—not through a second video agent or a standalone render-only task.

- Queued-job middleware sets a trusted verification phase/progress value before calling the tool.
- Progress is lifecycle metadata and is published through the job row; model text cannot set it.
- Check cancellation immediately before verification and again before save.
- A running cancellation transitions through `cancelling`; the worker stops before persistence and marks `cancelled`.
- Compile, policy, quota, and verification failures are terminal for the current attempt. Only typed transient infrastructure/provider failures may be automatically retried with bounded backoff.

## 5. Failure and cleanup invariants

- Verification failure maps to stable public `failure_code="verification_failed"` unless a more specific policy code such as `duration_limit` applies.
- Public/chat/Zero payloads never contain Celery, OpenSandbox, ffmpeg, Remotion, stack-trace, provider, or subagent-timeout text.
- Full diagnostics are logged with the job ID; only bounded internal detail is stored, and `internal_error` is never published.
- Failed or cancelled verification leaves no `Artifact` row and no retained PRIMARY blob.
- Partial renders, segments, and outputs are removed in worker cleanup. Ready/failed/cancelled state transitions must survive sandbox cleanup errors.

## 6. Checks

- A valid queued MP4 verifies to a signed receipt whose hash matches the stream-hash used by save.
- Exact 180-second output passes; output above 180 seconds fails before save with `duration_limit`.
- Corrupt, mute, truncated/desynchronized, and distributed-frame blank output fail verification.
- A changed MP4 is rejected by `save_artifact` because its hash no longer matches the receipt.
- Cancellation before or during the verify/save boundary produces `cancelled` and leaves no Artifact/blob.
- Verification failure exposes only a stable failure code while preserving bounded internal diagnostics.
- The queued path enforces the two-repair ceiling and never loops until the worker deadline.

## 7. Exit criteria

1. Verification runs wholly in the queued worker's existing deliverables-subagent workflow.
2. A valid MP4 receives a signed, byte-bound `format="video"` receipt after exact duration and distributed-frame checks.
3. Verification, policy failure, or cancellation cannot create an Artifact or retain a PRIMARY blob.
4. Only a successfully verified MP4 may proceed to worker-owned streaming save.
