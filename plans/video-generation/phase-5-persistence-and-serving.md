# Phase 5 — Persistence & serving

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 4 (video adapter); artifact serving (`app/routes/artifacts_routes.py`, `app/routes/document_files_routes.py`, `app/artifacts/storage.py`).

## 1. Goal

The verified MP4 is persisted as the PRIMARY artifact file via the generic path, and the browser streams it with seeking — reusing the artifact spine, adding only HTTP Range. **This phase is purely additive**: it introduces the MP4 read/write path *beside* the legacy one and **deletes nothing**. The legacy writers, routes, and per-slide audio blobs stay live — they still serve flag-off/legacy artifacts and are the **inputs Phase 7 backfill renders from**. Their removal is consolidated into Phase 8, after backfill.

## 2. Persistence

- **MP4-as-PRIMARY rides the generic `save_artifact` — no new recorder.** Once the Phase-4 adapter exists, the verified MP4 becomes the PRIMARY `ArtifactFile` (`video/mp4`), primary-only (no preview), and its blob is offloaded by the same persistence path documents already use.
- **Persist the format explicitly from the receipt, not the filename suffix.** `save_artifact`'s `_artifact_format` falls back to the primary's suffix when no `format=` is passed, so an `.mp4` would persist as `format="mp4"` — a string that neither `ArtifactFormat.VIDEO` (`"video"`) nor the frontend format-meta ever match. The deliverables `save_artifact_tool` already reads the verify receipt (whose `format` is checked to equal the adapter name, i.e. `"video"`), so it threads that through in the one existing persistence call: `save_artifact(..., format=verification.format)`. A single argument — it mirrors how the media shim `persist_artifact` already sets `format=` explicitly, and `_artifact_format(explicit=...)` records it verbatim. The Markdown-only branch passes nothing and stays `format="markdown"`.
- The legacy writers `app/artifacts/media/video/record.py` (audio-as-primary + `scene_codes` in metadata) and `storage.py` (per-slide audio offload) are **left untouched here** — they still produce/serve legacy artifacts and hold backfill inputs. Deleted in Phase 8.

## 3. Serving

- **`stream_artifact_file`** (`artifacts_routes.py`) — add HTTP `Range` handling: parse `Range`, return `206 Partial Content` + `Content-Range` + `Accept-Ranges: bytes`; keep the existing `ETag` + `immutable` cache. Requires a ranged read in the storage layer: `open_artifact_file_stream(record, start, end)` (object stores → range GET; local disk → `seek`). Works on every backend incl. local disk; preserves per-request RBAC. Additive and format-neutral — benefits every artifact, so it needs no flag.
- **`_is_inline`** (`document_files_routes.py`) — return inline for `video/mp4` (MP4 is not scriptable; the SVG XSS concern does not apply). The comment already invites widening "by MIME type, by name with a consumer attached".
- The legacy `/artifacts/{id}/video` and `/artifacts/{id}/slides/{n}/audio` routes **stay live here** (backfill and flag-off legacy playback still depend on them). Deleted in Phase 8.
- **Download** reuses `download_artifact` unchanged (streams the PRIMARY file).

## 4. Notes / risks

- **Range correctness:** cover open-ended (`bytes=N-`) and closed (`bytes=A-B`) ranges and an out-of-range `416`; off-by-one in `Content-Range` is the classic bug.
- **Signed URLs deferred** (umbrella §4): backend Range first; direct-to-blob signed URLs + CDN are the later, capability-gated read-path scale-out. Because the MP4 is already the PRIMARY blob, that path is a serving-layer swap — no change to how the artifact is produced or persisted here.

## 5. Checks

- Save the Phase-1 fixture MP4 → GET `/files/{id}/content` with `Range: bytes=0-1023` returns `206` + correct `Content-Range`, mime `video/mp4`, inline.
- Full GET (no Range) still returns `200` and the whole file.
- The legacy `/video` and `/slides/{n}/audio` routes still respond (they are **not** removed in this phase) — a regression guard that flag-off playback and backfill inputs remain intact.

## 6. Exit criteria

1. A verified MP4 persists as PRIMARY with `format="video"` (`ArtifactFormat.VIDEO`, from the receipt — not the `.mp4` suffix) and appears in the artifact manifest with a `content_url`.
2. `<video>` playback + seeking works via `206` responses on every storage backend.
3. Nothing is deleted: legacy writers, routes, and per-slide audio storage remain until Phase 8.
