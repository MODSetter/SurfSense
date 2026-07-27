# Phase 0 — Shared contract (resolve before building)

> The five load-bearing decisions every later phase depends on. These were left as
> per-phase "open questions" in the first draft; they are **shared**, so they live here
> once and the phases reference them. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
> Grounded in the current code — symbols and paths below are real.

This doc is the answer to "is it clear enough for a dev to implement?" — it pins the
contracts that phases 1–6 assume. Read it first.

---

## C1 — Repo location & tree layout (Phase 1, 5)

**Decided.**

- **One repo per workspace** at `{FILE_STORAGE_LOCAL_PATH}/knowledge_store/{workspace_id}` (nested **under** the shared blob-store volume, so every OS process sees the same history). Persistent working tree per workspace (not bare + ephemeral checkout) — simpler, and the per-workspace lock (C3) makes a single live checkout safe.
- **Tree layout mirrors today's virtual paths, minus the `/documents` root.** A doc currently at virtual `/documents/<folder>/<title>.xml` lives in git at `<folder>/<title>.xml`.
- **Reuse the existing filename rules** — do **not** reinvent them. `safe_filename`, `safe_folder_segment`, and the ` (<doc_id>).xml` collision suffix all come from `app/agents/chat/runtime/path_resolver.py`. Keep the `.xml` extension in v1 (changing to `.md` would break `unique_identifier_hash`, which is computed from the virtual path — see C2).
- **Git stores the source text** (the agent's note = `Document.source_markdown`/`content`), one file per document. Not the rendered XML view (that's derived — see C2). Not binaries (stay in the blob store).
- **Identity mapping preserved.** `unique_identifier_hash = generate_unique_identifier_hash(DocumentType.NOTE, virtual_path, workspace_id)` (`app/utils/document_converters.py`) stays the stable doc identity across the git↔Postgres boundary and for connector re-sync. Store it in the derived `documents` row (as today); the git path is the human-facing identity.

## C2 — Read contract: rendered-from-chunks, NOT raw blobs (Phase 2)

**Decided — this corrects subplan 02's "reads hit git".**

Today `read_file` does **not** return file bytes. `KBPostgresBackend.aload_document` builds a `RenderableDocument` from `Chunk` rows in document order, `render_full_document` wraps it as XML, and the `read_file` tool registers each chunk's `[n]` label into the conversation `CitationRegistry`. Citations are chunk-level.

- **v1 keeps the rendered-from-chunks read path** so agent citations don't regress. `GitTreeBackend` serves **structure** from the git tree (`ls`/`glob`/existence/`list_tree`) but **document content for `read_file` continues to render from the derived `Chunk` rows** (Postgres, one-way-derived from git — still no two-way sync).
- `grep` may scan git working-tree files directly (raw source) — it already returns coarse `<chunk-match>` snippets, so raw-source matches are acceptable.
- **Deferred:** serving raw markdown from git with per-document (coarse) citations. Revisit once the content model changes (Karpathy `raw/`+`wiki/`).

Net: Phase 2 replaces the **path/tree computation** (`path_resolver` + DB folder walk) with the real git tree; it does **not** move content rendering off chunks in v1.

## C3 — Concurrency: Redis lock, from v1 (Phase 1, 3)

**Decided — this corrects subplan 01's "in-process asyncio lock (v1)".**

The backend runs as **multiple OS processes**: the API (`python main.py`, uvicorn, default **4** workers per `docker/.env.example`) **and** Celery workers (`SERVICE_ROLE=worker`, autoscale **2–10**), sometimes in one container (`SERVICE_ROLE=all`). An in-process `asyncio.Lock` **cannot** serialize writes across them — it would give false single-writer safety.

- **Use a Redis lock** keyed `knowledge_store:write_lock:{workspace_id}` (token-owned release, TTL + queue-then-fail, fail-if-down). Redis is already a hard dependency (Celery broker/result/app cache), so this adds no infra.
- `ponytail:` v1 ceiling = one Redis lock per workspace held for the duration of a commit; upgrade path = a per-workspace write queue/worker if contention shows up.
- Alternative if Redis is ever removed: a Postgres advisory lock (`pg_advisory_xact_lock(hashtext('knowledge_store:'||workspace_id))`). Redis is the default.

## C4 — Write path: repoint `commit_staged_filesystem_state` (Phase 3, 4)

**Decided.** The end-of-turn commit body is `commit_staged_filesystem_state(...)` in `.../kb_persistence/middleware.py` (called by `aafter_agent` and the stream-task fallback). Repoint it from "write rows to Postgres" to "apply staged ops to the git working tree → one `commit`".

- **State keys are already defined** (read them straight from state — no guesswork): `files`, `staged_dirs`, `staged_dir_tool_calls`, `pending_moves`, `pending_deletes`, `pending_dir_deletes`, `dirty_paths`, `dirty_path_tool_calls`, `doc_id_by_path`, `kb_anon_doc`, `tree_version`.
- **Preserve the existing ordering**, which already exists for correctness: (1) folders/`staged_dirs`, (2) `pending_moves`, (3) `dirty_paths` writes/edits (skip paths also queued for `rm`; `_final_path` chases move aliases), (4) file `pending_deletes`, (5) dir `pending_dir_deletes`. Apply the same order to the working tree, then **one commit**.
- **Author** = `created_by_id` (the acting user id passed into the middleware); use `agent` for autonomous writes. **Message** summarizes the turn's ops.
- **Coupling with Phase 4:** the `DocumentRevision`/`FolderRevision` snapshot logic (gated by `flags.enable_action_log`) lives *inside* this function. Deleting those systems (Phase 4) removes that snapshot code from here — sequence Phase 3's rewrite and Phase 4's deletion together for flagged workspaces.
- **Emit the commit SHA** into state/event for Phase 4 (index) and Phase 6 (project). Keep the `dispatch_custom_event` calls (`document_created/updated/deleted`, `folder_deleted`) — the UI depends on them (C5).

## C5 — Index + Zero projection realities (Phase 4, 6)

**Decided / corrected.**

- **No embedding cache exists to "extend".** `embed_texts` (`app/utils/document_converters.py`) just calls the model under a threading lock — no `(model, hash)→vector` store. Today's reuse is `chunk_reconciler.reconcile` matching by **chunk text** to keep existing `Chunk` rows' vectors. Phase 4's blob-SHA keying is therefore **new**: add a `(embedding_model_version, blob_sha)` reuse layer, or generalize the reconciler from chunk-text identity to blob identity.
- **`content_hash` ≠ git blob SHA.** `generate_content_hash(content, workspace_id)` is **workspace-salted**; a git blob SHA is content-only and unsalted. They are different values — you cannot just alias one onto the other. Recommend: key embedding reuse by **blob SHA**; keep `content_hash` for existing document-level checks through migration, drop later if redundant.
- **Real-time UI has two channels, both must survive.** (1) Zero logical replication of the `documents`/`folders` rows (`app/zero_publication.py`); (2) `dispatch_custom_event` SSE from the commit path. Phase 6's git→Postgres projection must **upsert/delete the `documents`/`folders` rows** (so Zero streams them) **and** keep emitting the same custom events. Simplest owner: the Phase-4 post-commit pass does both (index + project) in one shot.

---

## What stays exactly as-is (do not touch)

- Hybrid search (`.../shared/retrieval/hybrid_search.py`) — reads the same `chunks` table.
- Live connectors (Slack/Gmail) — never stored/indexed.
- Desktop-local backend (`MultiRootLocalFolderBackend`) — real filesystem already.
- Blob store for binaries.

## Resolved-here index (was per-phase "open questions")

| Was open in | Now decided in |
|---|---|
| 01 lock granularity; repo layout; repo root | C3, C1 |
| 02 read rendering; glob/grep source | C2 |
| 03 author identity; staged-op keys | C4 |
| 04 content_hash vs blob SHA; cache location | C5 |
| 06 projection owner; consistency | C5 |
