# Phase 4 — Worker-owned video verification

**Status:** IMPLEMENTED.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 1, Phase 2b, Phase 3, and the artifact verification framework.

## 1. Outcome

Verification is the backend-owned gate between rendering and persistence. `execute_video_deliverable()` calls verification services directly; the interactive path and browser do not verify generated output.

The pipeline has two review boundaries:

```text
preflight + generated still review
  → final MP4 render
  → structural MP4 verification + signed receipt
  → receipt-bound streaming save
```

## 2. Pre-render review

The executor runs:

1. native Remotion preflight;
2. start/middle/end still rendering for every scene;
3. one contact sheet;
4. `review_video_stills()` with the configured vision model when available.

The review schema normalizes supported model field aliases into a strict result. Its rubric covers clipping, overflow, contrast, hierarchy, blank frames, and safe margins. Only blocking findings trigger repair; warnings can proceed.

If no vision model is configured, still review reports unavailable and does not block the pipeline. Native preflight remains mandatory.

At most one preflight/still repair is attempted before that stage fails.

## 3. Video adapter and receipt

`app/artifacts/verification/formats/video.py` is registered for canonical format `video`, `.mp4`, and MIME type `video/mp4`.

Sandbox verification:

- probes the container with ffprobe;
- requires one 1920×1080 video stream;
- requires an audio stream with packets;
- requires positive duration;
- compares final duration with the segmented-render sidecar within tolerance;
- extracts a midpoint frame and rejects blank/single-color output;
- calculates SHA-256 without loading the MP4 into backend memory.

The verification service signs a receipt bound to the output path, format, and digest. Any repair or re-render invalidates the old receipt.

The current adapter uses one midpoint structural frame check. Distributed final-MP4 frame sampling and a final vision pass are not implemented; visual quality is reviewed from the pre-render scene stills.

## 4. Duration behavior

The 180-second limit is enforced before final rendering by:

- measured narration total; and
- selected Remotion composition metadata.

Final structural verification checks media consistency against expected segment timing. It does not independently apply a separate `duration <= 180` policy branch.

## 5. Repair and failure behavior

Post-render structural failure can trigger a backend repair while the shared repair count remains below `VIDEO_SPEC.max_repair_cycles` (two). The executor merges repaired scene code/markdown into the existing authored structure, preserving narration and scene count, then prepares, renders, and verifies again.

Terminal verification failure maps to `verification_failed`; render failures map to `render_failed`; earlier policy failures may retain a more specific code. Public payloads never expose raw ffmpeg, Remotion, provider, sandbox, Celery, path, or stack detail.

## 6. Cancellation and persistence boundary

The worker's database watcher can cancel the executor and terminate the attempt sandbox during review, render, or verification. Heartbeats are attempt-bound; a cancelled or superseded attempt cannot complete the job.

Before persistence, `_save_verified()` reads the receipt and verifies that it covers the exact output path and canonical video format. Streaming storage recomputes SHA-256 and rejects mismatched bytes.

No unverified MP4 can be saved through this executor path.

## 7. Acceptance

- native preflight and blocking still findings gate final rendering;
- valid output produces a signed receipt bound to its exact SHA-256;
- corrupt, mute, malformed, wrong-resolution, duration-inconsistent, or midpoint-blank output fails;
- changing bytes after verification causes streaming save to reject them;
- repair is bounded and repaired output is re-verified;
- cancellation prevents verification completion and save;
- only stable public failure codes leave the worker boundary.

Distributed post-render frame sampling remains a possible hardening task, not an implemented Phase-4 contract.
