# Phase 6 — Frontend reduction to `<video>`

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 5 (MP4 served with Range). `surfsense_web/`.

## 1. Goal

For an MP4 artifact the browser renders **nothing but a plain, lazy `<video>`, inline in the chat message where it was produced** — the same place podcasts play, **not** the artifact side-panel. It points at the PRIMARY file's ranged `content_url`; no Remotion, no `new Function`, no compile step. **This phase is additive**: it adds the inline `<video>` branch, selected by the PRIMARY file's `video/mp4` **mime**, and leaves the legacy player for artifacts that are still audio + `scene_codes` (flag-off output and not-yet-backfilled artifacts). The old player and its deps are deleted in Phase 8, once Phase 7 backfill has left no legacy-shaped artifact behind.

## 2. Where it renders — inline in the card, not the panel

The new MP4 arrives through the **generic `save_artifact`** tool (Phase 2), so its chat UI is the save-artifact card (`components/tool-ui/save-artifact.tsx`) — **not** the legacy `generate-video-presentation.tsx`. That card today renders a file chip that opens the side-panel; branch it on the PRIMARY file's `mime_type`:

- `video/mp4` → render `Mp4VideoPlayer` **inline in the card** in place of the chip (keep the download button). The video plays where it was produced, mirroring the podcast card; it does **not** route to the panel.
- anything else → today's chip-opens-panel behavior, unchanged.

`viewingMode: "video" → "inline-media"` in `artifact-format-meta.ts` already encodes this intent and stays as is. The panel `viewer-registry.ts` is **not** touched — video never opens in the panel on the new path.

## 3. The player — lazy by construction

- **New component** `components/tool-ui/video-presentation/mp4-player.tsx` — `Mp4VideoPlayer({ src, poster? })` → `<video controls playsInline preload="none" poster={poster} src={src} />`. No Remotion, no `new Function`.
- **`preload="none"` *is* the lazy-load.** The browser fetches **zero** media bytes until the user presses play, so a thread with many saved videos costs ~nothing at rest (a poster image at most) — the native, no-JS answer to "load only when the user actually views it". Add an `IntersectionObserver` to defer even mounting the element **only** if long threads prove it necessary; don't build that speculatively.
- **`src`** is the primary file's ranged content route: `buildBackendUrl(content_url)` → `…/workspaces/{workspaceId}/artifacts/{artifactId}/files/{file_id}/content` (the Phase-5 Range endpoint). The card result already carries `artifact_id` + `file_id` and knows `workspaceId`, and the manifest exposes `content_url` directly — either source builds the URL.

## 4. Notes / risks

- **Lazy playback *requires* Phase 5 Range.** With `preload="none"` the first play and every seek issue a `Range` request; if `stream_artifact_file` doesn't answer `206`, scrubbing breaks and some browsers refuse to start playback at all. Phase 6 therefore hard-depends on Phase 5 — that dependency is exactly what makes lazy loading safe rather than a broken-seek trap.
- **Poster is optional in v1.** A thumbnail would come from a verify frame, but `save_artifact._read_artifact_file` rejects non-PDF secondary files, so shipping a poster means either widening that to accept one JPEG poster or going posterless (a neutral first frame). Off the critical path — defer.
- **Transition correctness:** an artifact may flip legacy→MP4 after backfill; the branch keys off the **current** PRIMARY mime each render, so both shapes render correctly during rollout and rollback with no reload path that 500s.
- **Legacy stays (do not delete yet):** the audio-+-`scene_codes` shape keeps rendering via `generate-video-presentation.tsx` → `combined-player.tsx` (its own tool-call UI), with `lib/remotion/compile-check.ts`, `lib/remotion/constants.ts`, and the `@remotion/*` / `@babel/standalone` deps. All removed in Phase 8.

## 5. Checks

- A saved MP4 renders an **inline** `<video>` inside the save-artifact card, plays, and seeks via `206` — and issues **no** content request until play is pressed (the lazy-load guard).
- A legacy (audio + `scene_codes`) artifact still mounts `combined-player.tsx` and plays (regression guard — nothing is removed here).
- Download still works from the card for both shapes.
- No new dead imports (typecheck + lint clean). The Remotion/Babel deps are **still present** (their removal is a Phase-8 check).

## 6. Exit criteria

1. MP4 artifacts play via a plain inline `<video>` in chat, with no client-side compilation or rendering and no panel round-trip.
2. `preload="none"` loads bytes only on play; seeking works via Phase-5 `206` on every storage backend.
3. Legacy artifacts still play via the retained player (dual-render by mime).
4. Download works from the card for both shapes.
