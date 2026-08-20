# Phase 4 — Video verification adapter + strategy

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** the verification framework (`app/artifacts/verification/`, `formats/registry.py`, `receipt.py`, `service.py`) and `deliverables/tools/verify_artifact.py`.

## 1. Goal

`verify_artifact(path="/workspace/out.mp4")` produces a **signed receipt bound to the MP4 bytes**, so `save_artifact` accepts the file. This is the authoritative gate; the per-slide stills in Phase 2 are a model-side aid only.

## 2. Why an adapter is required

`save_artifact` (`deliverables/tools/save_artifact.py`) reads the primary at `path`, then requires a receipt whose `format == get_format_adapter(path).name` and whose `primary_sha256 == sha256(bytes)`. Without a video format adapter, `get_format_adapter("out.mp4")` fails and the file can never be saved. So video needs:

1. **Format adapter** (`verification/formats/registry.py`): `.mp4` → name `"video"`, mime `video/mp4`, mapping to `ArtifactFormat.VIDEO`.
2. **Verify strategy** dispatched by that adapter in `service.py`.

## 3. Verify strategy (final MP4)

- **Structural (ffprobe):** duration > 0; resolution 1920×1080; has a video stream **and a non-empty audio stream (mandatory — a mute MP4 is a hard fail)**; container not corrupt. Any failure → blocking finding.
- **Visual (vision LLM):** extract K sample frames with ffmpeg (default: one per slide, deduped/capped), send through the existing `get_vision_llm` path used by document verification. Findings map to the same advisory/blocking model.
- **Receipt:** sign with `format="video"`, `primary_sha256` of the MP4 (no preview — video has no PDF preview; preview is optional in `save_artifact`).

## 4. Tool change

- `deliverables/tools/verify_artifact.py` — extend the docstring to include video; **no signature change** (it already dispatches by adapter via `verify()`).

## 5. Notes / risks

- **Cost:** cap sampled frames (1/slide) to bound vision spend per verify.
- **Byte binding:** the receipt binds to the final MP4; any re-render invalidates it (correct — forces re-verify before save).
- **Preview role:** `save_artifact._read_artifact_file` rejects non-PDF previews; video saves **primary-only**, which the save flow already allows.

## 6. Checks

- Verify the Phase-1 fixture MP4 → `status="verified"`; receipt sha matches file bytes.
- A truncated/corrupt MP4 → `status="failed"` with a structural finding.
- A **mute MP4 (no audio stream) → `status="failed"`** with a blocking structural finding; it can never reach `save_artifact`.
- A mutated MP4 after verify → `save_artifact` rejects on sha mismatch (reuse the existing receipt-mismatch test pattern).

## 7. Exit criteria

1. `get_format_adapter("x.mp4").name == "video"` with `ArtifactFormat.VIDEO`.
2. `verify_artifact` returns a signed, byte-bound receipt for a valid MP4.
3. `save_artifact` accepts a verified MP4 and rejects a changed one.
