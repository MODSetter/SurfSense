# Phase 6 — Frontend reduction to `<video>`

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 5 (MP4 served with Range). `surfsense_web/`.

## 1. Goal

The browser renders **nothing**. A video artifact is a plain `<video>` pointed at the PRIMARY file's `content_url` from the manifest.

## 2. Changes

- Replace the render/compile logic in `components/tool-ui/video-presentation/generate-video-presentation.tsx` and the whole `combined-player.tsx` with a single `<video controls src={contentUrl} />`, where `contentUrl` is the PRIMARY file `content_url` from the artifact manifest.
- **Delete:** `lib/remotion/compile-check.ts` (the `new Function` path), `lib/remotion/constants.ts` if unused elsewhere, `components/tool-ui/video-presentation/combined-player.tsx`.
- **Drop deps** from `surfsense_web/package.json`: `@remotion/player`, `@remotion/web-renderer`, `@remotion/media`, `@babel/standalone` (and `remotion` if nothing else imports it).
- Download button → the artifact `download` endpoint (already returns the PRIMARY MP4).

## 3. Notes / risks

- **Shared imports:** grep for any other consumers of the dropped libs before removal (`@remotion/*`, `@babel/standalone`).
- **Loading/empty states:** keep a poster/skeleton while the artifact is still generating; the manifest already carries indexing/format.

## 4. Checks

- The video artifact view mounts a `<video>` and plays the streamed file with working seek.
- Bundle no longer contains `remotion`/`@babel/standalone` (grep gate on the built output).
- No dead imports remain (typecheck + lint clean).

## 5. Exit criteria

1. Video artifacts play via `<video>` with no client-side compilation or rendering.
2. The four Remotion/Babel web deps are removed.
3. Download works from the artifact endpoint.
