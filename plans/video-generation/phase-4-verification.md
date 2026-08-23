# Phase 4 — Video verification adapter + strategy

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** the verification framework (`app/artifacts/verification/`, `formats/registry.py`, `receipt.py`, `service.py`) and `deliverables/tools/verify_artifact.py`.

## 1. Goal

`verify_artifact(path="/workspace/out.mp4")` produces a **signed receipt bound to the MP4 bytes**, so `save_artifact` accepts the file. The gate is **structural + a zero-cost content-sanity check** (`ffprobe` + one sampled frame's histogram) — **deliberately no per-frame *vision-LLM* review**. Sampled-still *vision* adds real per-verify cost, a hard vision-model dependency, and uncontrolled provider fan-out that does not survive target concurrency (§5), for little gain on a constrained slide template. Visual quality is handled advisory-side by the Phase-2 authoring loop, where the model inspects its own stills; the authoritative save gate stays fast, free, and provider-independent — but it still catches the one catastrophic silent failure structural checks miss (a solid-black / single-color render), which matters most for **backfill** (Phase 7), where there is no model in the loop to notice.

## 2. Why an adapter is required

`save_artifact` (`deliverables/tools/save_artifact.py`) reads the primary at `path`, then requires a receipt whose `format == get_format_adapter(path).name` and whose `primary_sha256 == sha256(bytes)`. Without a video format adapter, `get_format_adapter("out.mp4")` fails and the file can never be saved. So video needs:

1. **New adapter module** `verification/formats/video.py` — `check_video(...) -> StructuralCheckResult` (the ffprobe structural + frame-sanity gate, §3). New file, parallel to `formats/pdf.py`/`xlsx.py`. Video has no pages, so it returns `page_count=None`.
   - **Probe in the sandbox, not over a materialized copy — the one deliberate deviation from the `check(data: bytes)` pattern.** `check_pdf`/`check_xlsx` are pure functions of the whole bytes because documents are small. An MP4 is not: reading it into backend memory to `ffprobe` a temp file is the same per-render spike that scales with the admission gate (Phase 5 §2), so verify avoids it too. The video path runs `ffprobe` (and the frame sample, §3) **inside the sandbox** via `session.run_command` against `/workspace/out.mp4`, and only the small JSON + histogram summary cross back. `service.py` therefore hands the video adapter the **session + path**, not `data` — a narrow, documented exception carried only by this adapter (the structural-only branch already special-cases; this rides that seam).
   - **Receipt sha without a full read.** The receipt still binds `primary_sha256`, computed by `sha256sum /workspace/out.mp4` **in the sandbox** (trusted binary, render-output file). It is re-bound trusted-side at save: `save_artifact` **stream-hashes the upload** (Phase 5 `put_stream`) and rejects on mismatch, so the whole file is never buffered in the backend at verify *or* save, and a tampered digest cannot slip through.
2. **Registry entry** in `verification/formats/registry.py` — add `MP4_MIME = "video/mp4"` and a `".mp4": FormatAdapter(name="video", suffix=".mp4", mime_type=MP4_MIME, convert_to_pdf=False, check=check_video, requires_visual_review=False)` line — **the same shape as the existing `.xlsx` adapter**, which is likewise structural-only. `requires_visual_review=False` *is* the strategy: it routes video through the structural-only branch that already exists in `service.py` (§3), so **no new verify pipeline is written** and `ReviewKind` is left untouched. The adapter's `name="video"` is the **canonical format identity**: what the receipt is signed with (§3) and what persistence records verbatim (Phase 5); the `.mp4` filename suffix is only the registry lookup key and never decides the stored `Artifact.format`.
3. **No `service.py` or `base.py` change.** Because `requires_visual_review=False`, `_verify_artifact` takes its existing structural-only branch (the one `.xlsx` uses): run `adapter.check`, and on a clean result write a `visual="not_required"` receipt and return verified — no render, no frame extraction, no vision call, no `ReviewKind` extension. **Video adds an adapter, not a pipeline.**

**Flag-agnostic (register unconditionally).** The adapter is a plain dict entry — inert unless an `.mp4` is actually verified — so it ships independent of `VIDEO_SANDBOX_RENDERING_ENABLED` and needs no gating; a legacy build with the flag off simply never produces an `.mp4` to look up.

## 3. Verify strategy (final MP4)

Structural gate only — no jailed render, no vision pass. It reuses the exact structural-only path `.xlsx` already takes:

- **Structural (ffprobe, in-sandbox):** `check_video` — duration > 0; resolution 1920×1080; has a video stream **and a non-empty audio stream (mandatory — a mute MP4 is a hard fail)**; container not corrupt. Any failure → blocking finding.
- **Concat-duration consistency (long decks):** when the deck was rendered in segments and `ffmpeg concat`-joined (Phase 2 §5), stream-copy concat is A/V-desync- and truncation-prone at boundaries. Assert the final container `duration ≈ Σ sceneDurations / fps` within a small tolerance **and** the audio stream spans the whole file (no early cutoff). Catches a silently-truncated or desynced join before it becomes the saved artifact. Single-segment renders skip this check.
- **Content sanity (one frame, no LLM):** sample a single frame with the baked ffmpeg (`ffmpeg -ss <mid> -frames:v 1`) and reject a **near-zero-entropy / single-color** frame (histogram/stddev threshold). This is the cheap net for the catastrophic silent failure — a solid-black or blank render that is structurally perfect (1920×1080 + audio + duration>0). ~ms, no provider, no `review_pages`. It is **not** a quality judgement (layout/contrast/pacing stay advisory in the Phase-2 loop) — only a "the render produced actual pixels" floor. Most valuable in backfill (Phase 7), which has no authoring loop.
- **No vision-LLM pass.** Video takes the `requires_visual_review=False` branch, so verify never calls `review_pages` or a vision model. The frame-sanity check above is a local histogram, not a model call — it keeps the gate fast, free, and provider-independent.
- **Receipt:** written by the structural-only branch with `visual="not_required"`, `format="video"` — the authoritative identity threaded into persistence (Phase 5) — and the sandbox-computed `primary_sha256` (§2). `preview_path=None` (video has no preview; `save_artifact` already allows primary-only).

## 4. Tool change

- `deliverables/tools/verify_artifact.py` — extend the docstring to include video; **no signature change** (it already dispatches by adapter via `verify()`).

## 5. Notes / risks

- **Why structural-only (no vision gate):** sampled-still vision review does not survive target concurrency. `review_pages` fans out with **no global rate limiter** (`VISION_CONCURRENCY` is per-call), so N concurrent long-video verifies burst into N× provider calls and millions of tokens — hitting TPM/RPM ceilings, `120s`-timeout-induced *false* blocking findings, and the re-render loops those trigger — on top of a hard vision-model dependency and per-verify token cost. The marginal catch on a fixed 1920×1080 slide template is low. So the gate is structural (~ms, free, provider-independent). **Reversible:** flip the adapter's `requires_visual_review=True` (and add frame sampling) for a bounded, *queued* visual pass later, if defects show up in practice.
- **Byte binding:** the receipt binds to the final MP4; any re-render invalidates it (correct — forces re-verify before save).
- **Preview role:** `save_artifact._read_artifact_file` rejects non-PDF previews; video saves **primary-only**, which the save flow already allows.
- **Queued scale-out (umbrella §4):** under the deferred render-fleet mode, this same verify + the subsequent `save_artifact` run **inside the render worker** after the final MP4 (not inline in the agent turn). The strategy and receipt binding are unchanged — only the call site moves.

## 6. Checks

- Verify the Phase-1 fixture MP4 → `status="verified"`; receipt sha matches the file (sandbox `sha256sum`), and re-hashing the streamed upload at save matches the receipt.
- A truncated/corrupt MP4 → `status="failed"` with a structural finding.
- A **mute MP4 (no audio stream) → `status="failed"`** with a blocking structural finding; it can never reach `save_artifact`.
- A **solid-black / single-color MP4 → `status="failed"`** on the frame-sanity histogram (structurally perfect but blank), proving the silent-black net fires.
- A **segmented deck whose concat is truncated/desynced → `status="failed"`** on the duration-consistency check (`duration ≉ Σ sceneDurations/fps`).
- A mutated MP4 after verify → `save_artifact` rejects on sha mismatch (reuse the existing receipt-mismatch test pattern).
- A valid MP4 verifies on a workspace with **no vision model configured** (the gate never touches the vision path — the frame check is a local histogram, not a model call — so no `"unavailable"` degradation).
- Verify **holds no full-MP4 buffer**: the probe/hash run in-sandbox and only small results cross back (assert the backend never `read_file`s the whole MP4 at verify).

## 7. Exit criteria

1. `get_format_adapter("x.mp4").name == "video"`; that name is what the receipt carries and what persists as `ArtifactFormat.VIDEO` (Phase 5) — independent of the filename suffix.
2. `verify_artifact` returns a signed, byte-bound receipt for a valid MP4.
3. `save_artifact` accepts a verified MP4 and rejects a changed one.
