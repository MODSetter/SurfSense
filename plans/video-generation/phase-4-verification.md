# Phase 4 — Video verification adapter + strategy

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** the verification framework (`app/artifacts/verification/`, `formats/registry.py`, `receipt.py`, `service.py`) and `deliverables/tools/verify_artifact.py`.

## 1. Goal

`verify_artifact(path="/workspace/out.mp4")` produces a **signed receipt bound to the MP4 bytes**, so `save_artifact` accepts the file. The gate is **structural only** (`ffprobe`) — **deliberately no per-frame vision review**. Sampled-still vision adds real per-verify cost, a hard vision-model dependency, and uncontrolled provider fan-out that does not survive target concurrency (§5), for little gain on a constrained slide template. Visual quality is handled advisory-side by the Phase-2 authoring loop, where the model inspects its own stills; the authoritative save gate stays fast, free, and provider-independent.

## 2. Why an adapter is required

`save_artifact` (`deliverables/tools/save_artifact.py`) reads the primary at `path`, then requires a receipt whose `format == get_format_adapter(path).name` and whose `primary_sha256 == sha256(bytes)`. Without a video format adapter, `get_format_adapter("out.mp4")` fails and the file can never be saved. So video needs:

1. **New adapter module** `verification/formats/video.py` — `check_video(data: bytes) -> StructuralCheckResult` (the ffprobe structural gate, §3). New file, parallel to `formats/pdf.py`/`xlsx.py`. Like `check_pdf`, it is a **pure function of the bytes** run trusted-side (`service.py` calls it at the structural gate — the only verify step for video), so it shells `ffprobe` over a temp file using the backend image's ffmpeg — the same trusted-side probe the legacy `_get_audio_duration` already relies on. Video has no pages, so it returns `page_count=None`.
2. **Registry entry** in `verification/formats/registry.py` — add `MP4_MIME = "video/mp4"` and a `".mp4": FormatAdapter(name="video", suffix=".mp4", mime_type=MP4_MIME, convert_to_pdf=False, check=check_video, requires_visual_review=False)` line — **the same shape as the existing `.xlsx` adapter**, which is likewise structural-only. `requires_visual_review=False` *is* the strategy: it routes video through the structural-only branch that already exists in `service.py` (§3), so **no new verify pipeline is written** and `ReviewKind` is left untouched. The adapter's `name="video"` is the **canonical format identity**: what the receipt is signed with (§3) and what persistence records verbatim (Phase 5); the `.mp4` filename suffix is only the registry lookup key and never decides the stored `Artifact.format`.
3. **No `service.py` or `base.py` change.** Because `requires_visual_review=False`, `_verify_artifact` takes its existing structural-only branch (the one `.xlsx` uses): run `adapter.check`, and on a clean result write a `visual="not_required"` receipt and return verified — no render, no frame extraction, no vision call, no `ReviewKind` extension. **Video adds an adapter, not a pipeline.**

**Flag-agnostic (register unconditionally).** The adapter is a plain dict entry — inert unless an `.mp4` is actually verified — so it ships independent of `VIDEO_SANDBOX_RENDERING_ENABLED` and needs no gating; a legacy build with the flag off simply never produces an `.mp4` to look up.

## 3. Verify strategy (final MP4)

Structural gate only — no jailed render, no vision pass. It reuses the exact structural-only path `.xlsx` already takes:

- **Structural (ffprobe, trusted-side):** `check_video` on the MP4 bytes — duration > 0; resolution 1920×1080; has a video stream **and a non-empty audio stream (mandatory — a mute MP4 is a hard fail)**; container not corrupt. Same pure-bytes `check` contract as `check_pdf`/`check_xlsx`. Any failure → blocking finding.
- **No visual pass.** Video takes the `requires_visual_review=False` branch, so verify stops at the structural gate — no frame extraction, no `review_pages`. (Rationale in §5; the Phase-2 authoring loop is the advisory visual net.)
- **Receipt:** written by that existing structural-only branch with `visual="not_required"`, `format="video"` — the authoritative identity threaded into persistence (Phase 5) — and `primary_sha256` of the MP4. `preview_path=None` (video has no preview; `save_artifact` already allows primary-only).

## 4. Tool change

- `deliverables/tools/verify_artifact.py` — extend the docstring to include video; **no signature change** (it already dispatches by adapter via `verify()`).

## 5. Notes / risks

- **Why structural-only (no vision gate):** sampled-still vision review does not survive target concurrency. `review_pages` fans out with **no global rate limiter** (`VISION_CONCURRENCY` is per-call), so N concurrent long-video verifies burst into N× provider calls and millions of tokens — hitting TPM/RPM ceilings, `120s`-timeout-induced *false* blocking findings, and the re-render loops those trigger — on top of a hard vision-model dependency and per-verify token cost. The marginal catch on a fixed 1920×1080 slide template is low. So the gate is structural (~ms, free, provider-independent). **Reversible:** flip the adapter's `requires_visual_review=True` (and add frame sampling) for a bounded, *queued* visual pass later, if defects show up in practice.
- **Byte binding:** the receipt binds to the final MP4; any re-render invalidates it (correct — forces re-verify before save).
- **Preview role:** `save_artifact._read_artifact_file` rejects non-PDF previews; video saves **primary-only**, which the save flow already allows.
- **Queued scale-out (umbrella §4):** under the deferred render-fleet mode, this same verify + the subsequent `save_artifact` run **inside the render worker** after the final MP4 (not inline in the agent turn). The strategy and receipt binding are unchanged — only the call site moves.

## 6. Checks

- Verify the Phase-1 fixture MP4 → `status="verified"`; receipt sha matches file bytes.
- A truncated/corrupt MP4 → `status="failed"` with a structural finding.
- A **mute MP4 (no audio stream) → `status="failed"`** with a blocking structural finding; it can never reach `save_artifact`.
- A mutated MP4 after verify → `save_artifact` rejects on sha mismatch (reuse the existing receipt-mismatch test pattern).
- A valid MP4 verifies on a workspace with **no vision model configured** (structural-only never touches the vision path — no `"unavailable"` degradation).

## 7. Exit criteria

1. `get_format_adapter("x.mp4").name == "video"`; that name is what the receipt carries and what persists as `ArtifactFormat.VIDEO` (Phase 5) — independent of the filename suffix.
2. `verify_artifact` returns a signed, byte-bound receipt for a valid MP4.
3. `save_artifact` accepts a verified MP4 and rejects a changed one.
