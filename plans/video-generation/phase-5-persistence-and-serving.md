# Phase 5 — Persistence & serving

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 4 (video adapter); artifact serving (`app/routes/artifacts_routes.py`, `app/routes/document_files_routes.py`, `app/artifacts/storage.py`).

## 1. Goal

The verified MP4 is persisted as the PRIMARY artifact file via the generic path, and the browser streams it with seeking — reusing the artifact spine, adding only HTTP Range. **This phase is purely additive**: it introduces the MP4 read/write path *beside* the legacy one and **deletes nothing**. The legacy writers, routes, and per-slide audio blobs stay live — they still serve flag-off/legacy artifacts and are the **inputs Phase 7 backfill renders from**. Their removal is consolidated into Phase 8, after backfill.

## 2. Persistence

- **MP4-as-PRIMARY rides the generic `save_artifact` — no new recorder.** Once the Phase-4 adapter exists, the verified MP4 becomes the PRIMARY `ArtifactFile` (`video/mp4`), primary-only (no preview), persisted through the **same `save_artifact` records and schema** documents use — no new recorder, table, or route. Only the blob *transfer* differs: it streams rather than buffering (next bullet).
- **Stream the MP4 in, never buffer it — required by the concurrency model, not a preference.** The generic path reads the primary fully into memory (`save_artifact._read_artifact_file` → `store_artifact_file(data: bytes)` → `backend.put(key, data)`) twice — once to hash, once to upload. That is fine for a document but wrong for a video: at ~2–5 Mbps a deck is tens to a few hundred MB, and with the admission gate admitting `N` concurrent renders (Phase 2 §5) the backend would hold up to `N ×` full MP4s in process memory on top of live traffic — an OOM that *worsens exactly as the system scales*. Buffering here would contradict the fleet-oriented design everything else assumes, so the video path streams:
  - `StorageBackend.put_stream(key, chunks, *, content_type)` — the write-side twin of the `open_range` read this phase already adds (§3). **Azure:** hand `upload_blob` the async chunk iterable and let the SDK chunk it internally (do **not** hand-roll `stage_block`/`commit_block_list` unless profiling demands it). **Local:** open once, write chunks. ~15 lines per backend, no full buffer.
  - A streaming `store_artifact_file` variant whose source is the **sandbox session + path**: it reads `/workspace/out.mp4` in chunks, feeds `put_stream`, and **simultaneously** updates a `sha256` + byte counter. The digest is checked against the Phase-4 receipt (trusted-side re-bind, Phase 4 §2) and the count fills `ArtifactFile.size_bytes` — one pass, nothing buffered, no spool-to-disk.
  - Documents keep the existing bytes path unchanged; only the large-primary (video) path takes the streaming path. Keep it minimal: the win is removing the memory ceiling, not building a general streaming framework — the read half (`open_range`) is mandatory for Range playback regardless, so the write half is the only net-new surface.
- **Persist the format explicitly from the receipt, not the filename suffix.** `save_artifact`'s `_artifact_format` falls back to the primary's suffix when no `format=` is passed, so an `.mp4` would persist as `format="mp4"` — a string that neither `ArtifactFormat.VIDEO` (`"video"`) nor the frontend format-meta ever match. The deliverables `save_artifact_tool` already reads the verify receipt (whose `format` is checked to equal the adapter name, i.e. `"video"`), so it threads that through in the one existing persistence call: `save_artifact(..., format=verification.format)`. A single argument — it mirrors how the media shim `persist_artifact` already sets `format=` explicitly, and `_artifact_format(explicit=...)` records it verbatim. The Markdown-only branch passes nothing and stays `format="markdown"`.
- The legacy writers `app/artifacts/media/video/record.py` (audio-as-primary + `scene_codes` in metadata) and `storage.py` (per-slide audio offload) are **left untouched here** — they still produce/serve legacy artifacts and hold backfill inputs. Deleted in Phase 8.

## 3. Serving

- **`stream_artifact_file`** (`artifacts_routes.py`) — add HTTP `Range` handling: parse `Range`, return `206 Partial Content` + `Content-Range` + `Accept-Ranges: bytes`; keep the existing `ETag` + `immutable` cache. Requires a ranged read in the storage layer: `open_artifact_file_stream(record, start, end)`, backed by a backend-level `StorageBackend.open_range(key, start, end)` (Azure → ranged `download_blob(offset, length)`; local disk → `seek`) — the read-side twin of the `put_stream` write method (§2). Works on every backend incl. local disk; preserves per-request RBAC. Additive and format-neutral — benefits every artifact, so it needs no flag.
- **`_is_inline`** (`document_files_routes.py`) — return inline for `video/mp4` (MP4 is not scriptable; the SVG XSS concern does not apply). The comment already invites widening "by MIME type, by name with a consumer attached".
- The legacy `/artifacts/{id}/video` and `/artifacts/{id}/slides/{n}/audio` routes **stay live here** (backfill and flag-off legacy playback still depend on them). Deleted in Phase 8.
- **Download** reuses `download_artifact` unchanged (streams the PRIMARY file).

## 4. Notes / risks

- **Range correctness:** cover open-ended (`bytes=N-`) and closed (`bytes=A-B`) ranges and an out-of-range `416`; off-by-one in `Content-Range` is the classic bug.
- **Multi-range is out of scope.** A multi-part `Range: bytes=0-99,200-299` (which needs a `multipart/byteranges` body) is not produced by `<video>` seeking. Serve the first range or the whole file (`200`) instead of implementing multipart — an explicit non-goal, not an oversight.
- **Signed URLs deferred** (umbrella §4): backend Range first; direct-to-blob signed URLs + CDN are the later, capability-gated read-path scale-out. Because the MP4 is already the PRIMARY blob, that path is a serving-layer swap — no change to how the artifact is produced or persisted here.

## 5. Checks

- Save the Phase-1 fixture MP4 → GET `/files/{id}/content` with `Range: bytes=0-1023` returns `206` + correct `Content-Range`, mime `video/mp4`, inline.
- Full GET (no Range) still returns `200` and the whole file; an unsatisfiable `Range` returns `416`.
- **Streaming ingest holds no full buffer:** saving the fixture MP4 via `put_stream` produces a blob whose bytes and `size_bytes` match, and whose one-pass `sha256` equals the Phase-4 receipt — asserting the save never materializes the whole file. Runs on **both** `local` and `azure` backends.
- The legacy `/video` and `/slides/{n}/audio` routes still respond (they are **not** removed in this phase) — a regression guard that flag-off playback and backfill inputs remain intact.

## 6. Exit criteria

1. A verified MP4 persists as PRIMARY with `format="video"` (`ArtifactFormat.VIDEO`, from the receipt — not the `.mp4` suffix) and appears in the artifact manifest with a `content_url`.
2. `<video>` playback + seeking works via `206` responses on every storage backend.
3. Nothing is deleted: legacy writers, routes, and per-slide audio storage remain until Phase 8.
