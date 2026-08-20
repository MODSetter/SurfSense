# Phase 5 — Persistence & serving

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 4 (video adapter); artifact serving (`app/routes/artifacts_routes.py`, `app/routes/document_files_routes.py`, `app/artifacts/storage.py`).

## 1. Goal

The verified MP4 is persisted as the PRIMARY artifact file via the generic path, and the browser streams it with seeking — reusing the artifact spine, adding only HTTP Range.

## 2. Persistence

- `save_artifact` already handles it once the Phase-4 adapter exists: the MP4 becomes the PRIMARY `ArtifactFile` (`video/mp4`), offloaded to blob by `persist_artifact`; `format = ArtifactFormat.VIDEO` from the adapter; primary-only (no preview).
- **Retire** the bespoke writers: `app/artifacts/media/video/record.py` (audio-as-primary + `scene_codes` in metadata) and `app/artifacts/media/video/storage.py` (per-slide audio offload). Scene sources, if kept at all, live in metadata as private re-render source and are never served.

## 3. Serving

- **`stream_artifact_file`** (`artifacts_routes.py`) — add HTTP `Range` handling: parse `Range`, return `206 Partial Content` + `Content-Range` + `Accept-Ranges: bytes`; keep the existing `ETag` + `immutable` cache. Requires a ranged read in the storage layer: `open_artifact_file_stream(record, start, end)` (object stores → range GET; local disk → `seek`). Works on every backend incl. local disk; preserves per-request RBAC.
- **`_is_inline`** (`document_files_routes.py`) — return inline for `video/mp4` (MP4 is not scriptable; the SVG XSS concern does not apply). The comment already invites widening "by MIME type, by name with a consumer attached".
- **Retire** `/artifacts/{id}/video` (ships `scene_codes`) and `/artifacts/{id}/slides/{n}/audio` (`artifacts_routes.py`) — both exist only to feed the browser renderer. Audio is now inside the MP4; there is nothing separate to serve.
- **Download** reuses `download_artifact` unchanged (streams the PRIMARY file).

## 4. Notes / risks

- **Range correctness:** cover open-ended (`bytes=N-`) and closed (`bytes=A-B`) ranges and an out-of-range `416`; off-by-one in `Content-Range` is the classic bug.
- **Signed URLs deferred** (umbrella §4): backend Range first; direct-to-blob signed URLs + CDN are the later, capability-gated read-path scale-out. Because the MP4 is already the PRIMARY blob, that path is a serving-layer swap — no change to how the artifact is produced or persisted here.

## 5. Checks

- Save the Phase-1 fixture MP4 → GET `/files/{id}/content` with `Range: bytes=0-1023` returns `206` + correct `Content-Range`, mime `video/mp4`, inline.
- Full GET (no Range) still returns `200` and the whole file.
- Legacy `/video` and `/slides/{n}/audio` routes are gone (404).

## 6. Exit criteria

1. A verified MP4 persists as PRIMARY and appears in the artifact manifest with a `content_url`.
2. `<video>` playback + seeking works via `206` responses on every storage backend.
3. Per-slide audio storage and the render-only endpoints are removed.
