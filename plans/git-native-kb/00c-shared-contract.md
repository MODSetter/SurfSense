# Phase 0 — Shared contract (resolve before building)

> The load-bearing decisions every later phase depends on. These were left as
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

## C2 — Read contract: raw reads + one citation pattern (Phase 2, 4)

**Decided 2026-07-28 — supersedes this contract's earlier rendered-from-chunks model.** Chunk-render preserved four defects: the agent read a citation-polluted artifact (markers baked into cached file bytes), citations pointed at chunk ids that dangle on every reindex, granularity was the chunker's whim, and reads depended on the derived index. Rohan flagged citation quality; this redesigns it instead of porting it.

**Reads are raw.** `read_file` returns the real file from the turn's worktree (C6), line-numbered, honest `offset`/`limit`. Citation markers never enter file bytes — the handle rides in the envelope only, so edits and commits operate on clean content.

**One citation pattern through both doors (search excerpts and full reads).** All KB content reaches the agent as true-document-line-numbered text inside the same envelope, handle in the opening tag:

```text
<document title="…" path="…" cite="[3]" view="excerpts|full" revision="…">
    340  ## Refunds — annual plans
    341  Annual subscriptions may be refunded within 30 days…
</document>
```

One agent rule, zero per-tool special cases: cite `[n]`, narrowed to the evidence lines seen — `[3:L341-L342]`. Multiple chunks of one document collapse into one envelope, one handle.

**Citation currency = `(path, revision, evidence lines)`.**

- Registry entries are per-document and **self-contained**: `{path, revision, title}`, snapshotted at render time, persisted with the chat. Never a chunk id — rebuilds can't dangle what they can't reach.
- Evidence lines come from the **agent's emitted qualifier**; the normalizer parses the optional `:Lx-Ly` suffix, clamps it to the document length at that revision, and strips it when the entry was rendered un-numbered (see spans paragraph below).
- Resolution touches the chat's registry + git only: `read_as_of(revision, path)` → open at revision, highlight lines; the hover snippet is read from git at those exact lines. Chunk rows are never consulted after render.

**Chunk spans: stored at cut time, never migration-backfilled (amended 2026-07-29, second pass).** Phase 4's indexer writes `start_line`/`end_line` as it cuts (chonkie already returns exact offsets; verified `chunk.text == text[start:end]`). The columns are nullable — an instant, metadata-only ALTER; **what killed PR #1523 and the measured ~21-day chunk backfill was the mandatory table rewrite, not the column**, so no migration step ever fills them. Render-time derivation was considered and rejected: matching chunk text against the blob per query can silently pick the wrong occurrence of repeated text and puts git I/O in the search hot path.

**Legacy chunks (`NULL` spans) render un-numbered and cite at document level — fail-closed.** The mixed period (some excerpts numbered, some not) is a hallucination surface: the agent could invent `Lx-Ly` for un-numbered excerpts. The guard is mechanical, not prompt-hope: registry entries record whether they were rendered with numbers, and the normalizer **strips a `:Lx-Ly` qualifier whose entry was rendered un-numbered** (alongside the existing clamp). Correctness never depends on spans; they are progressive enhancement.

**Convergence = a deadline-free daily fill job (operational, not a migration gate).** Runs on flipped workspaces only. CPU-only, no embeddings: per document, match the stored chunk texts **against the git blob** — the text spans will actually resolve against (`read_as_of`), which post-flip *is* the source of truth; `source_markdown` is by then a derived projection and is never consulted. The match is a cursor scan in position order over *all* the document's chunks (repeated text disambiguates by alignment), updating only the span columns. Walks workspaces **most-used first**, batched/throttled, pausable at any point, until the NULL-span count reaches zero; new chunks always get spans at cut, so the backlog only shrinks.

One fail-closed guard, mandatory: **all-or-nothing per document** — every chunk must match at ascending start offsets or the document is skipped entirely. Every drift scenario falls out correctly from it: blob ahead of chunks (edit/index lag) → no alignment → skip, the next index re-chunks with spans anyway; blob behind Postgres (coexistence git-record failure) → no alignment → skip, correctly, since spans into a stale blob would resolve wrong; untouched-since-seed (the common case) → parity made blob = the chunks' birth text → full alignment, correct spans. Skipped and unmatched chunks stay NULL and keep document-level citations. No path yields confidently wrong line numbers.

`ponytail:` evidence lines are agent-emitted (the Claude Code / Cursor precedent); a sloppy model can mis-cite. Clamp-only in v1; upgrade path = validate cited lines against what was actually shown in the turn.

Structure (`ls`/`glob`/`grep`/`list_tree`) comes from the worktree; derivation stays one-way (git → Postgres, no two-way sync).

## C3 — Concurrency: Redis lock, from v1 (Phase 1, 3)

**Decided — this corrects subplan 01's "in-process asyncio lock (v1)".**

The backend runs as **multiple OS processes**: the API (`python main.py`, uvicorn, default **4** workers per `docker/.env.example`) **and** Celery workers (`SERVICE_ROLE=worker`, autoscale **2–10**), sometimes in one container (`SERVICE_ROLE=all`). An in-process `asyncio.Lock` **cannot** serialize writes across them — it would give false single-writer safety.

- **Use a Redis lock** keyed `knowledge_store:write_lock:{workspace_id}` (token-owned release, TTL + queue-then-fail, fail-if-down). Redis is already a hard dependency (Celery broker/result/app cache), so this adds no infra.
- `ponytail:` v1 ceiling = one Redis lock per workspace held for the duration of a commit; upgrade path = a per-workspace write queue/worker if contention shows up.
- Alternative if Redis is ever removed: a Postgres advisory lock (`pg_advisory_xact_lock(hashtext('knowledge_store:'||workspace_id))`). Redis is the default.

## C4 — Write path: repoint `commit_staged_filesystem_state` (Phase 3, 4)

**Decided — updated 2026-07-28 for the worktree model (C6).** The end-of-turn commit body is `commit_staged_filesystem_state(...)` in `.../kb_persistence/middleware.py` (called by `aafter_agent` and the stream-task fallback). For flagged workspaces, repoint it from "drain staged state keys to Postgres" to "**record the turn's worktree diff** as one revision" (C6: `porcelain.status` → change set → `store.transaction()`).

- **The staged-op state keys and their ordered drain are legacy-path only.** With the worktree, the tree already holds the netted outcome — moves are applied file ops, write-then-`rm` nets to nothing — so the key list (`files`, `staged_dirs`, `pending_moves`, `pending_deletes`, `pending_dir_deletes`, `dirty_paths`, `doc_id_by_path`, …) and the five-step ordering survive only on the unflagged Postgres path until migration deletes them (with `_pending_filesystem_view`, C6).
- **Author** = `created_by_id` (the acting user id passed into the middleware); use `agent` for autonomous writes. **Message** summarizes the turn's ops.
- **Coupling with Phase 4:** the `DocumentRevision`/`FolderRevision` snapshot logic (gated by `flags.enable_action_log`) lives *inside* this function. Deleting those systems (Phase 4) removes that snapshot code from here — sequence Phase 3's rewrite and Phase 4's deletion together for flagged workspaces.
- **Emit the commit SHA** into state/event for Phase 4 (index) and Phase 6 (project). Keep the `dispatch_custom_event` calls (`document_created/updated/deleted`, `folder_deleted`) — the UI depends on them (C5).

## C5 — Index + Zero projection realities (Phase 4, 6)

**Decided / corrected.**

- **An embedding cache exists — extend it, don't build one.** *(Corrected 2026-07-29; the original "no cache exists" claim overlooked `indexing_pipeline/cache/`, in the tree since 2026-06-12.)* `build_chunk_embeddings` serves a document's full chunk+vector set keyed by `(markdown_sha256, embedding_model, dim, chunker_kind, chunker_version)`. `markdown_sha256` is a pure, unsalted content hash — the "content id" property Phase 4 needs — so identical bytes already re-embed nothing. A separate blob-SHA reuse layer is unnecessary; `chunk_reconciler.reconcile` remains the row-level in-place reuse on top. **Do not warm this cache from legacy `Chunk` rows**: they may predate the current `chunker_version`, and writing their boundaries under today's key would poison it.
- **`content_hash` ≠ git blob SHA.** `generate_content_hash(content, workspace_id)` is **workspace-salted**; a git blob SHA is content-only and unsalted. They are different values — you cannot just alias one onto the other. Recommend: key embedding reuse by **blob SHA**; keep `content_hash` for existing document-level checks through migration, drop later if redundant.
- **Real-time UI has two channels, both must survive.** (1) Zero logical replication of the `documents`/`folders` rows (`app/zero_publication.py`); (2) `dispatch_custom_event` SSE from the commit path. Phase 6's git→Postgres projection must **upsert/delete the `documents`/`folders` rows** (so Zero streams them) **and** keep emitting the same custom events. Simplest owner: the Phase-4 post-commit pass does both (index + project) in one shot.

## C6 — In-turn writes live in a per-turn private worktree (Phase 2, 3)

**Decided 2026-07-28 — supersedes this contract's earlier state-overlay model.** The overlay was Postgres-backend debt, not a framework requirement (deepagents' `FilesystemBackend` writes directly to disk). The worktree deletes `_pending_filesystem_view` and the six staged-state keys instead of porting them.

Each turn that touches the KB gets a **private detached git worktree** of the workspace repo, checked out at the current revision:

- **Created lazily** on the turn's first KB tool call (read or write); turns that never touch the KB pay nothing. Measured: ~90 ms checkout for a 500-doc workspace, once per turn.
- **One tree serves the whole turn.** Every `read`/`write`/`edit`/`ls`/`glob`/`grep` in the turn (sub-agents included) is a plain file op on it — one code path, read-your-own-writes by construction, no overlay, no merge logic.
- **Abort/crash = delete the directory.** An age-based janitor prunes orphans. Nothing uncommitted survives.
- **Commit = diff, not snapshot.** At end of turn, `porcelain.status(worktree)` (dulwich; the detached HEAD *is* the base revision) yields the touched paths → mapped to a `writes`/`removes` change set → recorded via `store.transaction()` under the Redis lock (C3), on top of the current head. Committing only the diff means a parallel turn's already-committed work on untouched files is never reverted.
- **Same-file overlap: last-writer-wins, with history.** No merge machinery in v1; the overwritten version stays reachable in the prior revision. `ponytail:` ceiling = no three-way merge / conflict surfacing; upgrade path = git's own three-way merge if concurrent same-file edits become real.
- **Moves are stored as delete+add** — identical to git's own rename storage; no fidelity lost.

`ponytail:` known trade: a mid-turn checkpoint fork/replay does not restore uncommitted worktree files (state staging would have). Accepted — SurfSense has no mid-turn fork feature; revisit only if one appears.

## C7 — Migration seed is adopted, never incrementally indexed (Phase 4, 5)

**Decided 2026-07-29.** The Phase-5 seed commit copies bytes *out of Postgres*, so the existing `chunks` rows and vectors already are its derived index — byte parity is the proof. To `index_revision`, though, the seed looks like "every file added"; feeding it through would re-embed the whole workspace (the ~21-day job class that killed the chunk-column backfill and PR #1523).

- The seeder records the seed revision as the indexer's **starting point**; incremental indexing begins with the first post-seed revision.
- `reindex(workspace)` is disaster recovery + a one-time pilot spot check — never a per-workspace migration gate.
- Migrated chunks converge to the current chunker **lazily, on edit** (reconciler + embedding cache bound the cost). Never eagerly re-chunk, and never warm the cache from legacy rows (C5). The C2 span fill job is the one exception — it updates span columns only (no re-chunk of rows, no embeddings) and gates nothing.

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
| 02 in-turn write visibility; turn isolation (worktree) | C6 |
| 03 author identity; staged-op keys | C4 |
| 04 content_hash vs blob SHA; cache location | C5 |
| 05 parity gate; seed vs incremental indexer | C7 |
| 06 projection owner; consistency | C5 |
