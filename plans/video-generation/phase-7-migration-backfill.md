# Phase 7 — Migration & backfill

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phases 1–5 (a working sandbox render path). Runs **before** Phase 8 removes any legacy code.

**Flag-independent.** `VIDEO_SANDBOX_RENDERING_ENABLED` gates the *agent authoring* entrypoint (Phase 2). Backfill does not go through the agent — it drives the `ArtifactBuilder` directly — so it renders regardless of the flag's value; it only requires the Phase-1–5 render/verify/persist path to be deployed.

**New script:** `surfsense_backend/scripts/backfill_video_mp4.py` — a **separate, dedicated** migrator. Do **not** extend `backfill_video_artifacts.py` (that script solved a different migration: legacy `VideoPresentationRun` rows → the artifact table with audio-as-primary). This one takes *already-migrated* video artifacts and renders them to MP4; keeping it separate avoids overloading the older script's semantics and lets it be deleted independently once the migration is done.

## 1. Goal

Every existing video artifact **gains a real MP4 PRIMARY automatically** — or is cleanly frozen — so the Phase-6 `<video>` frontend has something to play and nothing 500s. **Hard requirement: no user ever re-generates a video.** Migration is a server-side batch; from the user's side their existing video simply starts playing as an MP4.

Backfill is a **re-render, not a transcode.** Legacy artifacts store no MP4 — the PRIMARY is the concatenated narration `.mp3`, with the visuals held only as `scene_codes` (they were composited in the browser at view time). So there is nothing to transcode; we *reproduce* the video by running the stored code + audio back through the Phase-1 pipeline. Because the audio is byte-identical, `calculateMetadata` yields the same durations, so timing/sync match what users saw before.

## 2. Two outcomes per artifact

- **Backfill (the default):** reconstruct `props.json` from stored `scene_codes` + audio, run the Phase-1 sandbox render, and attach the MP4 as PRIMARY (a new generation on the same `artifact_id`). The MP4 supersedes the legacy `audio/mpeg` PRIMARY.
- **Freeze (fallback for the un-reproducible few):** an artifact that genuinely cannot be rebuilt (see §4) is left **read-only in its current state** — the existing audio-PRIMARY artifact stays playable as-is; it is flagged, not deleted, and the user is **never** prompted to re-generate. Freeze is a per-artifact exception, not a bulk escape hatch.

## 3. Backfill mechanics (eager batch)

Eager (render everything at migration time), not lazy-on-view — so the legacy browser renderer can be deleted in Phase 8 with no dual-path lingering. New script, concrete shape (`backfill_video_mp4.py`):

```python
def reconstruct_props(artifact) -> dict          # stored scene_codes + audio filenames → props.json (Phase 1 §4)
async def render_one(session, props) -> bytes     # provision sandbox, write inputs, node render.mjs → MP4 bytes
def is_reproducible(artifact) -> bool             # has scene_codes + all per-slide audio → Backfill, else Freeze
async def attach_mp4(artifact_id, mp4_bytes)      # structural-verify → save_artifact (MP4 as new PRIMARY)
async def main(apply: bool, limit: int | None, workspace_id: str | None)
```

Two layers:

- **Orchestration — backend batch (`backfill_video_mp4.py`, CLI or Celery), no agent/LLM.** It enumerates legacy video artifacts (`_legacy_ref.kind == "video"` whose PRIMARY is still `audio/mpeg`), and for each: rehydrates per-slide audio via `open_stream(audio_storage_key)`, provisions a sandbox session, `write_file`s `public/slide-N.mp3` + the reconstructed `props.json`, invokes the render, reads the MP4 back, verifies, and calls `save_artifact`. Because backfill uses stored code (no authoring), it drives the `ArtifactBuilder` **directly, bypassing the agent loop**.
- **Execution — inside the OpenSandbox container.** The actual render (`node render.mjs` → headless Chrome + FFmpeg → MP4) runs in the same network-denied jail and image as live/new-video renders — never in the backend process, never in the browser. Long decks segment + `ffmpeg concat` to fit `SANDBOX_OPERATION_TIMEOUT_SECONDS`.
- **Idempotent + resumable + throttled.** Skip artifacts already on a `video/mp4` PRIMARY (re-runnable after a crash; each artifact commits independently). The `--apply` flag gates dry-run vs. write. Bound concurrent sandbox sessions (the admission-gate shape, used offline) so the migration never starves live traffic.
- **Structural + frame-sanity verify.** Backfill runs the **same gate as the live path** (Phase 4 — ffprobe: 1920×1080, duration > 0, video + audio stream; plus the single-frame content-sanity histogram and, for segmented decks, the concat-duration check). There is no quality-gate special-casing to reason about: it faithfully reproduces already-shipped content, and this gate is exactly what a re-render of known-good decks should clear. It produces the byte-bound receipt `save_artifact` requires. Genuine failures (won't bundle, audio missing) route to Freeze, not a quality rejection.
  - **The frame-sanity check earns its keep here specifically.** Live renders have the Phase-2 authoring loop (the model inspects its own stills) as an advisory visual net; **backfill has no model in the loop**. A legacy deck that re-renders solid-black — because of Remotion-version drift, an injected-globals mismatch that bundles but paints nothing, or a font that no longer resolves — would be structurally perfect and would silently *replace* a video that previously worked. The histogram floor turns that into a Freeze (keep the still-playable legacy artifact) instead of a silent regression. Route a frame-sanity failure to Freeze, not a crash.
- **Ordering.** Runs **before** Phase 8 deletes per-slide audio storage (those blobs are the render inputs), or snapshot the keys first.

## 4. Risks

- **Injected-globals contract:** legacy `scene_codes` assume the browser's `INJECTED_NAMES`. The harness preamble (Phase 1 §4) must supply the same symbols or old code fails to bundle — **validate on a real legacy sample first** (also Phase 1 exit criterion 4).
- **Audio availability:** backfill must run before per-slide audio blobs are deleted (Phase 8), or snapshot those keys.
- **Missing data:** artifacts lacking `scene_codes`/audio cannot be rebuilt → route to the Freeze option.

## 5. Checks

- **Fidelity gate (run first):** `backfill_video_mp4.py --apply=false` over a representative sample of *real* legacy artifacts reports the reproduction success rate before any write. High → run the full batch; a failing class → known Freeze volume, decided before touching production.
- A single sample artifact backfills to a playable MP4 that the Phase-6 `<video>` renders, with the same slide pacing as the original.
- Re-running the batch is a no-op on already-migrated artifacts (idempotency).
- A legacy artifact with missing sources is handled (Freeze), not crashed.

## 6. Exit criteria

1. Every legacy video artifact has an MP4 PRIMARY or a defined frozen state — and **no user was asked to re-generate**.
2. Per-slide audio blobs are preserved until this phase completes (their deletion is Phase 8).
3. `backfill_video_mp4.py` is self-contained and can be removed after the migration without touching `backfill_video_artifacts.py`.
4. Backfill success/Freeze counts are recorded so Phase 8 can confirm nothing legacy remains unhandled before deleting the old path.
