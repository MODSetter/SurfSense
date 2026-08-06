# Phase 1 — Foundation (no sandbox)

**Status:** Implemented (migration `177` → `tests/integration/artifacts/`). §2 below describes what shipped; the three places the build corrected the plan are called out inline.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) — contracts in §3 are authoritative; this file does not restate them.
**Goal:** prove the artifact model end to end (write-through persistence → streaming → rendering) using markdown artifacts only, plus the full binary serving/rendering path exercised with manually seeded files. No sandbox, no skills, no deletions.
**Ships to users:** reliable "save this as a document" from chat (no more silent staged-commit losses for deliverables), and the new artifact panel.

---

## 1. Scope

In:

- Schema additions (`GENERATED` kind, `document_files.role`)
- `save_artifact` tool (markdown path only) + write-through persistence helper, including both KB-indexing branches (working-copy write on git workspaces, direct index on legacy — master spec §4.4)
- File-content streaming endpoint
- `editor-content` `kind: text | file` discrimination
- Artifact panel shell + viewer registry (markdown viewer + `FileDownloadCard`)
- Chat artifact card keyed on `document_id`

Out (later phases): sandbox, `execute`/`read_sandbox_file`, any binary *generation*, office viewers, any deletion. `generate_report`/`generate_resume` remain untouched and callable.

---

## 2. Tasks

### 2.1 Backend — schema (1 Alembic migration)

1. Add `GENERATED` to the `document_file_kind` enum (`app/file_storage/persistence/enums.py` + migration `ALTER TYPE`).
2. Add `document_files.role VARCHAR(16) NOT NULL DEFAULT 'primary'` (values `primary|preview`; keep it a plain string column, no enum churn for two values). Backfill needs nothing — default is correct for all existing rows (uploads).

### 2.2 Backend — persistence helper

New module `app/artifacts/service.py`:

- `async def save_artifact(session, *, workspace_id, thread_id, tool_call_id, title, markdown_representation, files: list[ArtifactFileInput], document_id: int | None = None) -> ArtifactSaved`
- **Create path** (`document_id=None`): allocates the artifact's tree path **once** via the store's `allocate_path` (sanitized filename, `.md`, ` (2)` collision suffix — the authored-once path law, master spec §4.1), then creates the `Document` (`document_type=NOTE`, `document_metadata={"generated": true, "thread_id", "tool_call_id"}`, `unique_identifier_hash` = the standard NOTE path hash for that path, `source_markdown=markdown_representation`), then `store_document_file()` per file with `kind=GENERATED` and the given `role`, **in one transaction**. The row and bytes are durable when the tool returns — that is the §3.1 write-through promise.
  - The `taken` set handed to `allocate_path` is the union of every recorded `PATH_MARKER` in the workspace **and** the files already sitting in the turn's working copy, and the resulting path's NOTE hash is re-checked against `documents.unique_identifier_hash` before it is accepted. The working-copy half is what keeps two artifacts saved in the same turn apart: neither has a marker yet (the projection stamps those at the commit), so recorded paths alone would hand both the same name.
- **Search indexing branches on the workspace's KB mode** (master spec §4.4) — the only branch in the helper, keyed off the same `knowledge_store_enabled` flag the git KB uses:
  - *Git-backed workspace:* write `markdown_representation` into the turn's working copy at the allocated path. The end-of-turn commit does the rest — the commit-time projection adopts the row and stamps `PATH_MARKER` (never this helper), the async convergence attaches chunks + embeddings. The row is in the tree the moment the tool returns and adopted at the commit; only the search hit is eventually consistent (seconds).
  - *Legacy workspace:* chunk + embed immediately via a direct `IndexingPipelineService.index()` call on the row, once the persistence transaction has committed. Never `prepare_for_indexing`/`index_batch` in either mode — the store facade's ingest adapter hooked there would mint a separate `sync:` commit outside the turn. This branch is a bridge: it is deleted at the git-KB Phase 5 cut with the rest of the legacy path.
    Indexing after the commit is what makes the write-through promise unconditional (an embedding outage cannot cost the user their document), and it buys one honest wart: an index failure raises, so the tool reports `failed` for an artifact that *was* saved and the model's retry creates a second one. Acceptable while the branch is scheduled for deletion; the fix, if it ever outlives that schedule, is to return the `document_id` alongside the failure so the retry revises.
- **Revise path** (`document_id` set, master spec §4.3): validates the target is a generated document in this workspace; updates title/`source_markdown`; writes the new `DocumentFile` rows and deletes the replaced ones **in the same transaction**; the replaced *blobs* are deleted best-effort **after** that transaction commits, because a blob store has no rollback to enlist in — a failed delete leaves an unreferenced blob and a warning, never a broken artifact. (Symmetrically, a rollback deletes the blobs the failed attempt just wrote.) Re-indexing follows the same branch as the create path — on git workspaces, rewrite the file at the row's **recorded path** (`PATH_MARKER`); the path is an authored-once label under the store's path law, so a retitle updates the title column and never moves the file. Same-turn revises have no marker yet (it lands at the turn's single commit), so the helper falls back to matching the working copy's files by NOTE hash, then to re-deriving the path from the row's *pre-revision* title — the same three inputs the allocation used, in reverse. Direct re-index on legacy. Forward-only, no version history — a failed revision leaves the previous generation untouched.
- **Fences (master spec §4.1/§4.3/§4.4):** neither path ever calls `create_version_snapshot` (`document_versions` is for KB/connector versioning, not artifacts); `save_artifact` writes are excluded from agent-revert snapshotting (`document_revisions`); and the forward-only rule extends to future git-KB verbs — revert and version-history UI exclude `generated: true` documents (cross-referenced in the git-KB umbrella). All three are the same rule: no version history for artifacts through any back door.
- Returns the §3.1 payload shape. Raises on any failure — callers surface the error in the tool result; nothing is swallowed.
- Phase 1 callers pass `files=[]` (markdown only), but the helper is written and tested against the binary and revise paths now (seeded bytes, §2.8), so phases 2–3 only add callers.
- **No guards anywhere.** The convergence, commit path, and deletion machinery carry zero artifact-specific code — no `generated` predicate exists anywhere in the store — because an artifact row is indistinguishable from a note at the indexer's level, and everything the indexer does to a note (adopt, update, delete-with-the-tree) is exactly what artifacts want. What phase 1 adds instead is the proof: the adoption integration test in §2.8.
- **Two corrections in `knowledge_store/index/rows.py`** — both general store fixes that artifacts were merely the first caller to need, not exceptions carved out for them:
  1. `upsert_row` re-derived `document.title` from the filename on **every** upsert, so the commit following a revise renamed the row back to its original filename. It now re-derives the title only when the path actually changed (or when the row's `unique_identifier_hash` disagrees with the path's). This is the second half of the path law: if titles never move files, files must never rename titles.
  2. `delete_row` deletes the `Document`, and the FK cascade drops its `DocumentFile` rows — but a cascade cannot reach the blob store, so every deleted upload or artifact leaked its bytes. It now calls `purge_document_blobs()` before the delete. (Master spec §4.3's "no new code" for deletion was wrong on this point; it is corrected there.)

### 2.3 Backend — `save_artifact` tool

- New tool in `subagents/builtins/deliverables/tools/save_artifact.py`: markdown-only signature `(title, content, description?, document_id?)` — `document_id` is the §3.1 revise input, and passing it is the only way the model updates an artifact instead of creating a sibling. Wraps the helper; returns the §3.1 payload via `with_receipt` (receipt `route=deliverables`, `type=artifact`, `external_id=str(document_id)`), and returns `{"status": "failed", "error"}` on any raise.
- Register in `tools/index.py` + `shared/tools/catalog.py`. Subagent prompt: prefer `save_artifact` for markdown deliverables; legacy tools remain for everything else this phase.
- One generic streaming emission handler under `tasks/chat/streaming/handlers/tools/deliverables/save_artifact/` (card payload = §3.1 fields).

### 2.4 Backend — serving endpoint

`GET /api/v1/workspaces/{ws_id}/documents/{doc_id}/files/{file_id}/content` in a new `routes/document_files_routes.py`:

- Workspace-membership auth (same dependency as `editor_routes.py`).
- 404 unless the `DocumentFile` belongs to `doc_id` within `ws_id`.
- `StreamingResponse` over `open_document_file_stream()`; headers per master spec §5 (inline for `application/pdf` only, attachment for everything else; `nosniff`; `ETag` = sha256; `Cache-Control: private, max-age=31536000, immutable`; `If-None-Match` → 304).

### 2.5 Backend — `editor-content` discrimination

In `editor_routes.py`: if the document has a `GENERATED` file with `role=primary` whose MIME type is outside `{text/markdown, text/x-markdown}` → return the `kind: "file"` shape (master spec §3.2) with `content_url`s, primary first; else return the existing response + `kind: "text"`. **Both shapes carry `generated: boolean`** (from `document_metadata.generated`); `generated: true` means the client renders read-only regardless of `viewer_mode`. Existing clients ignore the new fields until updated.

### 2.6 Frontend — artifact panel + registry

- `features/artifacts/` (new): panel shell that takes `document_id`, fetches `editor-content`, branches on `kind`.
  - `text` → read-only `MarkdownViewer` (existing component; no Plate).
  - `file` → `VIEWERS[primary.mime_type] ?? FileDownloadCard`.
  - The panel is **strictly a renderer** — no editing surface for any format (master spec §8.4: Plate survives only for memory/team-memory editing, outside artifact surfaces). Download is the only action besides viewing.
- Registry file `features/artifacts/viewer-registry.ts`; entries lazy-loaded via `next/dynamic`. Phase 1 registry: empty map (everything falls through to `FileDownloadCard`) — PDF entry lands in phase 2.
- `FileDownloadCard`: filename, extension badge, human size, download button → `content_url`.
- New atom `atoms/chat/artifact-panel.atom.ts` (`{ isOpen, documentId }`), plus an `artifact` tab in `rightPanelTabAtom` so the panel joins the existing right-panel surfaces rather than fighting them: it claims the tab on open, sits above `report` in the fallback order, restores the pre-open collapsed state on close, and takes the same 640px width as the report panel. The legacy report-panel atom stays untouched.

### 2.7 Frontend — chat artifact card

- `features/chat-artifacts/model/artifact.ts`: add kind `file` mapped from `save_artifact`; `entityId` = `document_id`; `contentType` union gains `"file"`.
- `collect-artifacts.ts`: parse the §3.1 payload; card click opens the artifact panel atom. Legacy `report`/`resume` kinds continue opening the legacy report panel (unchanged this phase).
- Tool UI `components/tool-ui/save-artifact.tsx`: pending/success/error states; auto-open panel on desktop, matching current report behavior. Public threads register the same component but render the card **inert** (no click-through, no auto-open): the streaming endpoint and `editor-content` both demand workspace membership, so a share-token visitor has nothing to open. Serving artifacts to public threads needs a token-scoped route and is deferred with master spec §12's first open question.

### 2.8 Checks

- `tests/integration/artifacts/test_service.py` — the helper against a real session and a fake blob backend (it writes rows, so it is an integration test despite reading like a unit one): transaction atomicity (a mid-write storage failure leaves neither Document nor blob), payload shape, binary create + revise with seeded bytes (files replaced, old blob gone, same `document_id`), a forced failure mid-revision leaving the previous generation fully intact, and **zero rows in `document_versions` or `document_revisions`** — the §2.2 fences, asserted rather than assumed.
- `tests/integration/artifacts/test_git_adoption.py` — the **adoption test** on a real repo with projection and convergence: save an artifact, commit the turn, converge; exactly **one** row exists at every step (no duplicate sibling — the shared `index/rows.py` resolution is the thing under test), `PATH_MARKER` stamped by the commit and not by the helper, chunks searchable after convergence. Then revise and commit again: the new title survives the projection while the marker stays on the original path (the §2.2 correction, and the path law's only observable consequence). Then `rm` the file, commit, converge: row deleted, `DocumentFile`s cascaded, blob store empty.
- `tests/unit/routes/test_document_files_routes.py` — 403 cross-workspace, 404 mismatched file/doc, ETag 304, and disposition per MIME including the two that must **not** render on our origin (`text/html`, `image/svg+xml`).
- `tests/integration/artifacts/test_tool.py` (legacy workspace) — markdown artifact through the tool → Document row + immediate KB search hit; `tests/integration/artifacts/test_editor_content.py` — both §3.2 shapes off real rows.

---

## 3. Exit criteria

1. "Write me a summary of X and save it" → `save_artifact` → Document exists **within the tool call** (verified by `document_id` in the tool result), card renders, panel shows read-only markdown. The document appears in the documents tree immediately in both KB modes (the row is written inside the tool call); the KB search hit is immediate on legacy workspaces and lands once the turn's commit converges (seconds) on git-backed ones (master spec §4.4).
2. Tool-level failure (e.g., forced storage error) surfaces as a failed tool result the model reacts to — demonstrably no silent path.
3. A manually inserted `GENERATED` PDF DocumentFile streams with correct headers and downloads; its document returns the `file` shape and renders the download card.
4. Both §3 contracts implemented byte-for-byte as specced; any deviation = master spec revision first.
