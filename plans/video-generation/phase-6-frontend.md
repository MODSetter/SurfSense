# Phase 6 — Frontend reduction to `<video>`

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 5 (MP4 served with Range). `surfsense_web/`.

## 1. Goal

For an MP4 artifact the browser renders **nothing** — it is a plain `<video>` pointed at the PRIMARY file's `content_url`. **This phase is additive**: it adds the `<video>` path and selects it by PRIMARY **mime**, while the legacy player stays for artifacts that are still audio + `scene_codes` (flag-off output and not-yet-backfilled artifacts). The old player and its deps are deleted in Phase 8, once Phase 7 backfill has left no legacy-shaped artifact behind.

## 2. Changes

- **New component** `components/tool-ui/video-presentation/mp4-player.tsx` — `Mp4VideoPlayer({ src, poster? })` renders `<video controls src={src} />` (hits the Phase-5 Range route). No Remotion, no `new Function`.
- **Mime-branch in the viewer** — in `generate-video-presentation.tsx`, select the renderer from the PRIMARY file's mime: `video/mp4` → `Mp4VideoPlayer`; legacy `audio/mpeg` + `scene_codes` → the existing `combined-player.tsx`. Data-driven, **not** flag-driven, so both shapes render correctly during rollout and rollback.
- **Keep (do not delete yet):** `combined-player.tsx`, `lib/remotion/compile-check.ts`, `lib/remotion/constants.ts`, and the `@remotion/*` / `@babel/standalone` deps — the legacy branch still needs them until Phase 8.
- Download button → the artifact `download` endpoint (already returns the PRIMARY file for both shapes).

## 3. Notes / risks

- **Transition correctness:** the branch must handle an artifact flipping from legacy to MP4 (post-backfill) without a reload path that 500s — key off the manifest's current PRIMARY mime each render.
- **Loading/empty states:** keep a poster/skeleton while the artifact is still generating; the manifest already carries indexing/format.

## 4. Checks

- An MP4 artifact mounts `Mp4VideoPlayer` and plays the streamed file with working seek.
- A legacy (audio + `scene_codes`) artifact still mounts `combined-player.tsx` and plays (regression guard — nothing is removed here).
- No new dead imports (typecheck + lint clean). The Remotion/Babel deps are **still present** (their removal is a Phase-8 check).

## 5. Exit criteria

1. MP4 artifacts play via `<video>` with no client-side compilation or rendering.
2. Legacy artifacts still play via the retained player (dual-render by mime).
3. Download works from the artifact endpoint for both shapes.
