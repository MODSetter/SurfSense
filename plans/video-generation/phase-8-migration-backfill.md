# Phase 8 — Migration & backfill

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phases 1–5 (a working sandbox render path). Reuses `surfsense_backend/scripts/backfill_video_artifacts.py` patterns.

## 1. Goal

Existing video artifacts (stored as `scene_codes` + per-slide audio in metadata, no MP4) either gain a real MP4 PRIMARY or are cleanly marked legacy — so the Phase-6 `<video>` frontend has something to play and nothing 500s.

## 2. Options (decide before running)

- **Backfill (preferred):** for each legacy video artifact, reconstruct `props.json` from stored `scene_codes` + audio, run the Phase-1 sandbox render, and attach the MP4 as PRIMARY (a new generation on the same `artifact_id`).
- **Freeze:** if backfill scope is too large, mark legacy video artifacts read-only and surface a "re-generate to view" affordance instead of rendering.

## 3. Backfill mechanics

- One-off script (Celery or CLI) iterating legacy video artifacts by `_legacy_ref.kind == "video"`.
- Rehydrate audio from the retiring per-slide storage keys into the render workdir `public/` before it is removed (order Phase 8 before Phase 5's storage deletion, or snapshot keys first).
- Reuse the render + `save_artifact` path so backfilled artifacts are byte-verified like new ones.

## 4. Risks

- **Injected-globals contract:** legacy `scene_codes` assume the browser's `INJECTED_NAMES`. The harness preamble (Phase 1 §4) must supply the same symbols or old code fails to bundle — **validate on a real legacy sample first** (also Phase 1 exit criterion 4).
- **Audio availability:** backfill must run before per-slide audio blobs are deleted (Phase 5), or snapshot those keys.
- **Missing data:** artifacts lacking `scene_codes`/audio cannot be rebuilt → route to the Freeze option.

## 5. Checks

- Dry-run backfill on one sample legacy artifact yields a playable MP4 that the Phase-6 `<video>` renders.
- A legacy artifact with missing sources is handled (Freeze), not crashed.

## 6. Exit criteria

1. Legacy video artifacts either have an MP4 PRIMARY or a defined frozen state.
2. No orphaned per-slide audio blobs remain after backfill + Phase-5 cleanup.
3. `VideoPresentationRun` tables can be dropped (Phase 7 migration) once backfill no longer needs them.
