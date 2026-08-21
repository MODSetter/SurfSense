# Phase 6 — Frontend reduction to `<video>`

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 5 (MP4 served with Range). `surfsense_web/`.

## 1. Goal

For an MP4 artifact the browser renders **nothing but a plain, lazy `<video>`** pointed at the PRIMARY file's ranged `content_url` — no Remotion, no `new Function`, no compile step. It appears in **two** places, both playing the same file over HTTP Range: **inline in the chat message** where it was produced (the same place podcasts play), and — because a video is a first-class artifact — in the **KB documents right panel** when opened from the roster, carrying a correct **Video** identity (icon + label) instead of the "Presentation" it inherits today. **This phase is additive**: it adds the `video/mp4` branches, selected by the PRIMARY file's **mime**, and leaves the legacy player for artifacts still shaped as audio + `scene_codes` (flag-off output and not-yet-backfilled artifacts). The old player and its deps are deleted in Phase 8, once Phase 7 backfill has left no legacy-shaped artifact behind.

## 2. Where it renders — two surfaces, both mime-keyed

Both branches key off the PRIMARY file's `mime_type` (data-driven, not flag-driven, so rollout and rollback are automatic):

- **Inline in chat — the save-artifact card** (`components/tool-ui/save-artifact.tsx`). The new MP4 arrives through the **generic `save_artifact`** tool (Phase 2), so this card is its chat UI — **not** the legacy `generate-video-presentation.tsx`. The card today renders a file chip that opens the side-panel; branch it: `video/mp4` → render `Mp4VideoPlayer` **inline** in place of the chip (keep the download button); anything else → today's chip-opens-panel behavior, unchanged. `viewingMode: "video" → "inline-media"` in `artifact-format-meta.ts` already encodes this: clicking the video in the roster scrolls to this inline card rather than opening the panel.
- **KB documents panel — the artifact viewer** (`features/artifacts/artifact-panel.tsx` → `features/artifacts/viewer-registry.ts`). Opened from the documents list, the panel dispatches by PRIMARY mime through the `VIEWERS` map — which today has **no** `video/mp4` entry, so a new-arch video would fall to the "can't preview" fallback. Register `video/mp4 → Mp4FileViewer` (the same player wrapped as `FileViewerProps`, reading `buildBackendUrl(primary.content_url)`). This **supersedes** the earlier "viewer-registry is not touched" note: a video is browsable in the KB panel like any other artifact — it simply isn't the *primary* play surface (chat is), so both mounts exist.

## 3. Artifact identity — Video, not Presentation

Today `artifact-format-meta.ts` maps `format="video"` to the **Presentation** icon and label under the "Presentations" group — which, combined with the legacy audio-backed primary, is exactly why a saved video shows a "ppt" icon yet plays as mp3. Fix the `video` entry to a real video identity: `icon: Video` (lucide), `label: "Video"`, `detailLabel: "MP4"`, and its own group — add `videos` / "Videos" to `ArtifactGroupKey` and `ARTIFACT_GROUP_ORDER`. Because every surface reads `getArtifactFormatMeta`, this single change is authoritative at once across the KB documents node, the save-artifact card, the artifact roster/library, and mentions. `viewingMode` stays `"inline-media"` (chat is the primary play surface; the panel open is served by the §2 viewer, independent of this field).

## 4. The player — lazy by construction

- **New component** `components/tool-ui/video-presentation/mp4-player.tsx` — `Mp4VideoPlayer({ src, poster? })` → `<video controls playsInline preload="none" poster={poster} src={src} />`. No Remotion, no `new Function`. The KB-panel viewer (§2) is a thin `FileViewerProps` wrapper over this same element — **one player, two mounts**.
- **`preload="none"` *is* the lazy-load.** The browser fetches **zero** media bytes until the user presses play, so a thread with many saved videos costs ~nothing at rest (a poster image at most) — the native, no-JS answer to "load only when the user actually views it". Add an `IntersectionObserver` to defer even mounting the element **only** if long threads prove it necessary; don't build that speculatively.
- **`src`** is the primary file's ranged content route: `buildBackendUrl(content_url)` → `…/workspaces/{workspaceId}/artifacts/{artifactId}/files/{file_id}/content` (the Phase-5 Range endpoint). The card result already carries `artifact_id` + `file_id` and knows `workspaceId`, and the manifest exposes `content_url` directly — either source builds the URL.

## 5. Notes / risks

- **Lazy playback *requires* Phase 5 Range.** With `preload="none"` the first play and every seek issue a `Range` request; if `stream_artifact_file` doesn't answer `206`, scrubbing breaks and some browsers refuse to start playback at all. Phase 6 therefore hard-depends on Phase 5 — that dependency is exactly what makes lazy loading safe rather than a broken-seek trap.
- **Poster is optional in v1.** A thumbnail would come from a verify frame, but `save_artifact._read_artifact_file` rejects non-PDF secondary files, so shipping a poster means either widening that to accept one JPEG poster or going posterless (a neutral first frame). Off the critical path — defer.
- **Transition — identity is format-keyed, playback is mime-keyed.** Both legacy and new videos are `format="video"`, so the §3 fix gives a not-yet-backfilled legacy video the new **Video** icon/label immediately — while it is still audio-backed it keeps playing via its legacy chat player and is download-only (unviewable) in the KB panel until Phase 7 converts it to `mp4`. Cosmetic and self-healing. The playback branches key off the **current** PRIMARY mime each render, so both shapes render correctly during rollout and rollback with no reload path that 500s.
- **Legacy stays (do not delete yet):** the audio-+-`scene_codes` shape keeps rendering via `generate-video-presentation.tsx` → `combined-player.tsx` (its own tool-call UI), with `lib/remotion/compile-check.ts`, `lib/remotion/constants.ts`, and the `@remotion/*` / `@babel/standalone` deps. All removed in Phase 8.

## 6. Checks

- A saved MP4 renders an **inline** `<video>` inside the save-artifact card, plays, and seeks via `206` — and issues **no** content request until play is pressed (the lazy-load guard).
- **Opening that MP4 from the KB documents panel** plays it in-panel via `Mp4FileViewer` (`video/mp4` registered), not the "can't preview" fallback.
- **A video artifact shows the Video icon and "Video" label** (not Presentation) in the documents node, the save-artifact card, and the roster.
- A legacy (audio + `scene_codes`) artifact still mounts `combined-player.tsx` and plays (regression guard — nothing is removed here).
- Download still works from the card for both shapes.
- No new dead imports (typecheck + lint clean). The Remotion/Babel deps are **still present** (their removal is a Phase-8 check).

## 7. Exit criteria

1. MP4 artifacts play via a plain inline `<video>` in chat, with no client-side compilation or rendering.
2. Opening an MP4 from the KB documents panel plays it in-panel; the artifact carries a **Video** icon/label on every surface (was Presentation).
3. `preload="none"` loads bytes only on play; seeking works via Phase-5 `206` on every storage backend.
4. Legacy artifacts still play via the retained player (dual-render by mime).
5. Download works from the card for both shapes.
