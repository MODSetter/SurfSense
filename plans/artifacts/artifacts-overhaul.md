# Artifacts Overhaul — Engineering Spec

**Status:** Phase 1 shipped; phases 2–4 draft for review
**Scope:** All non-media generated deliverables (PDF, DOCX, PPTX, XLSX, Markdown, and future formats). Media artifacts (podcast, video, image) are explicitly out of scope — they work today and keep their pipelines.
**Decision summary:** Replace the genre-based deliverable system (`generate_report`, `generate_resume`, Typst) with a format-based system: the agent writes code in a sandbox using per-format skills, persists real files write-through as `Document` + `DocumentFile`, and the frontend renders by MIME type. Typst is removed entirely. Artifacts are **view-only** (Plate survives only for memory/team-memory editing) and **unversioned** — revisions replace the artifact in place; the conversation is the history. No fallbacks, no feature flags, **no data migration** — legacy code and the `reports` table are deleted outright; previously generated deliverables become inaccessible (§10), announced as a breaking change in release notes.

---

## 1. Motivation & principles

### 1.1 Current failure modes

1. **Two parallel stores that don't know about each other.**
   - `generate_report` / `generate_resume` write immediately to the `reports` table (`app/db.py`, `Report` model) — never `Document`, never `DocumentFile`.
   - `write_file` / `edit_file` commit at end-of-turn as `Document` rows with `DocumentType.NOTE` — via staged agent state on the legacy path, via a git working copy on git-backed workspaces (both paths in §2.2).
   - Users see two different "saved" surfaces (artifacts library vs documents tree) with different behavior.
2. **Silent staged-commit failures.** The legacy KB commit wraps everything in `except: log and return None` (`kb_persistence/middleware.py` ~L1242). The tool already told the model "Updated file …" mid-turn, so when the commit fails the user was promised a save that never happened. This is the "YouTube summary sometimes doesn't save" bug. (The git-native KB write path already fixes this for flagged workspaces — failed receipts, working copy kept for next-turn recovery — but it is still end-of-turn machinery; artifacts remove the bug class entirely by persisting inside the tool call, §1.2.3.)
3. **Verb-gated deliverables.** The report tool docstring only triggers on creation verbs ("write/create/generate/draft…"). "Summarize this video" often fails the gate and the answer stays in chat — inconsistent by design.
4. **Everything renders as markdown.** There is exactly one artifact rendering path (report panel: Plate/markdown, or Typst→PDF recompile for resumes). Asking for a PPTX produces markdown. Asking for a PDF produces a fixed Typst-templated layout the user cannot influence.
5. **Fragile resume pipeline.** Resumes store *Typst source*, not the compiled PDF. Every preview recompiles; a package or environment change after generation breaks a previously "successful" resume.

### 1.2 Design principles

1. **Genre is the model's job. Format is the skill's job. Rendering is the extension's job.**
   There are no genre-specific tools. "Resume", "report", "memo", "invoice" are user intents the model maps to a file format. Evidence: Claude's file-creation feature has no resume tool — the model reasons "a resume is a formal document → .docx/.pdf", loads the format skill, generates, and verifies (Anthropic Agent Skills docs; anthropics/skills repo).
2. **Artifacts are real files with immutable bytes.** What was generated is what renders and what downloads. No recompile-on-view.
3. **Write-through persistence.** The artifact is persisted inside the tool call that produced it, and the tool result carries the `document_id`. Failure is visible to the model in the same turn. No end-of-turn staging for artifacts.
4. **Format knowledge lives in exactly two places:** skills (generation side) and the viewer registry (rendering side). The tool contract, persistence, storage, serving, and deletion layers never enumerate formats. Unknown formats degrade to a download card, never an error.
5. **One store, one model.** Every generated artifact is a `Document` + `DocumentFile` pair — and a **first-class citizen of the git-native knowledge base**: its markdown representation lives in the workspace git repo like any note, its binaries live in the blob store like any upload's original, and the Postgres row is the derived index of both (§4.4). No parallel storage philosophy, no carve-outs. The `reports` table is dropped **without data migration** — legacy deliverables are not carried forward (§10).
6. **No fallbacks.** One sandbox provider per deployment mode, selected by env var. Old code paths are deleted, not flagged off.

---

## 2. Current-state map (what exists today)

### 2.1 Path A — reports/resumes (immediate, `reports` table)

```
task(deliverables) → generate_report | generate_resume
  → LLM produces markdown (report) or Typst body (resume; compiled for page-count validation only, PDF discarded)
  → INSERT Report (content, content_type='markdown'|'typst', report_style, thread_id, workspace_id)
  → with_receipt(...) → ToolMessage JSON
  → frontend: collect-artifacts.ts → artifact card → report-panel.tsx
      content_type 'typst'   → PdfViewer on /api/v1/reports/{id}/preview  (recompiles every view)
      content_type 'markdown'→ Plate editor / MarkdownViewer
  → export: /api/v1/reports/{id}/export (pandoc → report_pdf.typst → typst.compile)
```

Versioning today: each regeneration inserts a **new sibling `Report` row** sharing `report_group_id`; `_get_version_siblings()` in `reports_routes.py` powers the version-switcher dropdown in `report-panel.tsx`. This entire mechanism dies with the table — the new system is deliberately unversioned (§4.3), and nothing replaces the switcher.

Key files:

- Tools: `surfsense_backend/app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/{report.py,resume.py,index.py}`
- Model: `Report` in `surfsense_backend/app/db.py`
- Routes: `surfsense_backend/app/routes/reports_routes.py`, Typst branches in `editor_routes.py`, `public_chat_routes.py`
- Templates: `surfsense_backend/app/templates/report_pdf.typst`, `export_helpers.py`
- Frontend: `surfsense_web/features/chat-artifacts/**`, `features/artifacts-library/**`, `components/report-panel/{report-panel,pdf-viewer}.tsx`, `components/tool-ui/generate-{report,resume}.tsx`, `atoms/chat/report-panel.atom.ts`, `lib/apis/reports-api.service.ts`
- Streaming: `surfsense_backend/app/tasks/chat/streaming/handlers/tools/deliverables/generate_{report,resume}/`
- Deps: `typst>=0.14.0`, rendercv (Typst package, referenced inline in `resume.py`), `pypandoc`

### 2.2 Path B — KB notes (`documents` table; two write paths during the git-KB transition)

KB notes have **two coexisting write paths**, selected per turn by `KNOWLEDGE_STORE_ENABLED` + the per-workspace `workspaces.knowledge_store_enabled` flag (migration 175). Their lifecycle is owned by the git-native KB umbrella ([`plans/git-native-kb/`](../git-native-kb/00-umbrella-plan.md)), not by this spec:

```
Legacy (unflagged workspaces — deleted at the git-KB Phase 5 cut):
write_file | edit_file under /documents/…
  → staged in agent state (dirty_paths)
  → end of turn: KnowledgeBasePersistenceMiddleware.aafter_agent → commit_staged_filesystem_state
  → Document(document_type=NOTE) + chunks + embeddings

Git-native (flagged workspaces):
write_file | edit_file under /documents/…
  → GitTreeBackend writes the turn's private git working copy on disk
  → end of turn: knowledge_store_persistence → one git commit
  → commit-time projection (knowledge_store/index/project.py) upserts the Document row
  → async convergence (knowledge_store/index/converge.py) attaches chunks + embeddings
```

Both remain the home of **incidental notes** — and, under this spec, of the artifact's markdown representation. `save_artifact` persists the row and the file bytes write-through inside the tool call (that part never waits for end-of-turn machinery), and on git-backed workspaces its markdown representation joins the turn's working copy so it rides the same single end-of-turn commit as every other agent write. The full integration contract is §4.4.

### 2.3 Existing infrastructure the new system reuses

- **File storage** (`surfsense_backend/app/file_storage/`): `store_document_file()` writes bytes via the configured backend and adds a `DocumentFile` row (storage key shape `documents/{workspace_id}/{document_id}/{kind}/{uuid}{ext}`, sha256 checksum, size, MIME). Backends: `LocalFileBackend` (Docker volume, self-hosted) and `AzureBlobBackend` (cloud), selected by `FILE_STORAGE_BACKEND`. `open_document_file_stream()` streams in 1 MB chunks. `purge_document_blobs()` handles deletion.
- **Skills system** (`main_agent/skills/`): existing loader used by the `report-writing` builtin skill. Reused as-is for format skills (progressive disclosure: frontmatter metadata always in prompt; body loaded on trigger).
- **PDF viewer** (`surfsense_web/components/report-panel/pdf-viewer.tsx`): virtualized pdf.js canvas viewer with zoom, DPR handling, authenticated fetch (`getAuthHeaders()`), `toolbarActions` slot. Reused unchanged; only the URL source changes. (`pdfjs-dist` already a dependency.)
- **Document viewer plumbing**: `GET .../documents/{id}/editor-content` (`editor_routes.py`) already decides `viewer_mode` per document; extended in this spec with a file shape.
- **Sandbox seam** (`shared/middleware/filesystem/sandbox.py` + `tools/execute_code/` + `routes/sandbox_routes.py`): a working Daytona integration already exists — per-thread sandbox cache with locks and broken-state recovery, KB file sync into the sandbox (`sync_files_to_sandbox` takes state files, so it is agnostic to which Path-B backend produced them), heredoc-based `execute_code` (no persistent kernel), and a local-disk file download path (`SANDBOX_FILES_DIR`). Phase 2 refactors this seam behind the provider protocol (registry logic promoted, Daytona specifics extracted, OpenSandbox added); the local-disk download path is obsoleted by `save_artifact` and deleted in phase 4. Details: [`phase-2-sandbox-pdf.md`](./phase-2-sandbox-pdf.md) §2.1.
- **Git-native knowledge store** (`app/knowledge_store/`, [`plans/git-native-kb/`](../git-native-kb/00-umbrella-plan.md)): **reused as-is.** On git-backed workspaces the artifact's markdown representation is written through the turn's working copy, committed by `knowledge_store_persistence`, its row projected at commit time and its chunks converged asynchronously — the exact pipeline every note already rides (§4.4). No new commit machinery, no artifact-specific code in the store. The one file both efforts touch directly is `editor_routes.py` — the `KnowledgeStore` facade (`knowledge_store/service.py`) records editor saves there, while this spec extends the read side (`editor-content`, §3.2) and phase 4 swaps the Typst export branch; the changes are disjoint.

---

## 3. Frozen contracts

Everything else in this spec can evolve; these two schemas are the interfaces every phase builds on. Changes after phase 1 require a spec revision.

### 3.1 `save_artifact` tool result

```json
{
  "status": "saved",
  "document_id": 123,
  "title": "Indian History — Overview",
  "files": [
    {
      "file_id": 456,
      "role": "primary",
      "filename": "indian-history.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "size_bytes": 48213
    },
    {
      "file_id": 457,
      "role": "preview",
      "filename": "indian-history.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 91240
    }
  ]
}
```

- `files` is empty for markdown artifacts (content lives in `Document.source_markdown`; no blob).
- `role` is `"primary"` (the deliverable), `"preview"` (browser-renderable derivative, currently always PDF), or `"source"` (the script or markup that produced the deliverable — agent-facing, never offered as a download). At most one of each per artifact.
- **Revision:** the tool accepts an optional `document_id` input. Present → revise that artifact **in place** (§4.3): same `document_id`, new `DocumentFile` rows replace the old ones transactionally. Absent → create a new artifact. There is no version history (§8.4). The id has to reach the model for any of that to happen: the deliverables subagent is invoked fresh per `task(…)` call and carries nothing between turns, so "make the header bigger" arrives with no memory of yesterday's PDF. Each run is therefore prefixed with a roster of the artifacts this chat has produced (§6.1). Creating stays the default whenever no id is named, and the asymmetry is deliberate — a missing id costs a duplicate, a wrong one destroys the artifact it names.
- On failure the tool returns `{"status": "failed", "error": "<human-readable reason>"}` — the model sees it in-turn and can retry or tell the user. No silent paths. A failed revision leaves the existing artifact untouched.
- The chat artifact card is built from this payload (`document_id` replaces `report_id` as `entityId` in `features/chat-artifacts/model/artifact.ts`).

### 3.2 `editor-content` response (extended)

The existing endpoint gains a discriminated union on `kind`:

```json
// Text shape — markdown artifacts, notes, all existing documents (unchanged fields)
{
  "kind": "text",
  "document_id": 123,
  "title": "…",
  "source_markdown": "…",
  "generated": false,
  "viewer_mode": "plate" | "monaco",
  "...": "existing fields unchanged"
}

// File shape — documents whose primary content is a stored binary
{
  "kind": "file",
  "document_id": 123,
  "title": "Indian History — Overview",
  "generated": true,
  "files": [
    { "file_id": 456, "role": "primary", "filename": "indian-history.docx",
      "mime_type": "application/vnd...", "size_bytes": 48213,
      "content_url": "/api/v1/workspaces/7/documents/123/files/456/content" },
    { "file_id": 457, "role": "preview", "filename": "indian-history.pdf",
      "mime_type": "application/pdf", "size_bytes": 91240,
      "content_url": "/api/v1/workspaces/7/documents/123/files/457/content" }
  ],
  "updated_at": "…"
}
```

- Backend decides `kind`: a document with a `GENERATED` `DocumentFile` whose primary is non-markdown → `file`; otherwise `text`. The client never guesses. `files` carries primary and preview only — the `source` role is the agent's input for a later revision, not something the panel renders or the user downloads.
- **`generated` is present in both shapes.** `generated: true` → the client renders read-only, unconditionally; `viewer_mode` is ignored for generated documents (it remains meaningful only for regular KB documents, where Plate survives solely for memory/team-memory editing — see §8.4).

---

## 4. Storage design

### 4.1 Data model

**No new tables.** Two additive schema changes (one Alembic migration):

1. `DocumentFileKind.GENERATED` added to the `document_file_kind` enum (`app/file_storage/persistence/enums.py`). Existing kinds (`ORIGINAL`, `REDACTED`, `FILLED_FORM`) untouched.
2. `document_files.role` column: `VARCHAR(16) NOT NULL DEFAULT 'primary'` — values `primary` | `preview` | `source`. Existing rows default to `primary` (correct for uploads).

An artifact is:

- **`Document` row** — title; `source_markdown` = the markdown *representation* of the artifact (full content for markdown artifacts; outline/summary for binary ones — this is what gets chunked and embedded so a PPTX is findable in KB search); `document_metadata` carries `{"generated": true, "thread_id": …, "tool_call_id": …}`; the artifact's tree path is **authored once** on create via the store's `allocate_path` (sanitized filename, `.md`, ` (2)` collision suffix — never a doc id) and follows the git-KB path law from there: the path is the row's durable label, and `unique_identifier_hash` = the standard NOTE path hash for it, kept as the resolver's fallback. Resolution (recorded path first, hash as fallback — the shared primitives in `knowledge_store/index/rows.py`) matches the committed markdown file to this row and adopts it instead of inserting a duplicate (§4.4). Who records that path differs by workspace, and the difference is not incidental. On git-backed workspaces `save_artifact` never writes the row's `PATH_MARKER` — the commit-time projection stamps it on adoption, per the store's rule that a path is recorded only once a commit actually holds the file, since a marked row whose file is not yet in the tree reads as an orphan to the pruner. Legacy workspaces have no commit and no projection, so nothing would ever stamp it and every revision would fall through to guessing the path back from the title — which works for the first document of a given name and fails for the second. There the helper records the marker on create. `document_type` stays `NOTE` (an artifact *is* a note with generated files attached; provenance is fully determined by the `GENERATED` file kind + metadata flag; a new DocumentType would ripple through connector-oriented code for nothing).
- **Up to three `DocumentFile` rows** — `kind=GENERATED`; primary (the deliverable), optionally preview (verification PDF), and for generated files the source that produced it. Markdown artifacts have none of the three: `source_markdown` is simultaneously the deliverable, the representation, and the source, so a revision edits the row and there is nothing to fetch. The source is what makes a revision an *edit* rather than a re-derivation: the sandbox that built the artifact is reaped minutes after the turn, so without a stored copy "change the heading colour" a week later means rebuilding the whole document from a markdown summary and handing back a different document. Created via the existing `store_document_file()`; sha256, size, MIME recorded as today.

Artifacts are deliberately **single-generation**: a Document holds at most one file per role at any time. This differs from uploaded documents, where multiple kinds (`ORIGINAL`, `REDACTED`, `FILLED_FORM`) coexist as siblings — do not unify the two models; uploads keep multi-kind, artifacts are replace-on-revise (§4.3).

**Adjacent tables — explicit fates:**

| Table / store | Fate | Why |
|---|---|---|
| `reports` | **Dropped in phase 4, no data copy** — including every `report_group_id` sibling version | Legacy deliverable store; the no-migration decision (§10) makes its entire history unrecoverable, deliberately |
| `document_versions` | **Untouched by this plan** — owned and deleted by the git-native KB at its Phase 5 cut | Backs KB-document version snapshots on the legacy path (connector indexers via `create_version_snapshot`, restore endpoints/`version-history.tsx`); already dead for git-backed workspaces (restore returns 409 — history is `git revert` there). **Fence:** the `save_artifact` revise path must never call `create_version_snapshot`, or versioning sneaks back into artifacts for however long the table exists |
| `document_revisions` / `folder_revisions` | **Untouched by this plan** — owned and deleted by the git-native KB at its Phase 5 cut | Back the agent-revert feature for legacy-path KB edits (`revert_service.py`); dead code for git-backed workspaces. **Fence:** `save_artifact` creates/revisions are excluded from agent-revert snapshotting — "revert my artifact" would be version history through the back door |
| Git knowledge store (repo per workspace) | **Holds the markdown representation, never the binaries** — the same split uploads already use (extracted markdown in git, original bytes in the blob store) | Owned by [`plans/git-native-kb/`](../git-native-kb/00-umbrella-plan.md); artifacts enter it through the turn's working copy like every agent write (§4.4). **Fence:** `save_artifact` never routes through `prepare_for_indexing`/`index_batch` — the store facade's ingest adapter hooked there (`record_prepared_documents`, `knowledge_store/service.py`) would mint a separate `sync:` commit outside the turn, breaking one-commit-per-turn and double-recording the file |

### 4.2 Physical storage

Unchanged from the existing file-storage layer — this is the point:

| Deployment | `FILE_STORAGE_BACKEND` | Bytes live in |
|---|---|---|
| Self-hosted (docker-compose) | `local` | Files on the storage-root Docker volume: `{root}/documents/{ws}/{doc}/generated/{uuid4}.docx` |
| Production | `azure` | Azure Blob, same key |

Postgres never stores bytes. The `DocumentFile.storage_backend` column records which backend wrote the blob, so reads are correct even across a backend migration.

### 4.3 Limits and lifecycle

- **Size cap:** `ARTIFACT_MAX_FILE_BYTES` (default 30 MB, matching Claude's documented cap) enforced when pulling bytes out of the sandbox. Config value, not per-format.
- **File immutability, forward-only — no version history.** A `DocumentFile`'s bytes are never overwritten — that keeps the sha256 ETag + `immutable` caching correct (§5) and guarantees what was generated is what renders. But artifacts only ever move **forward**: a revision updates the *same* `Document` in place (same `document_id`; title and `source_markdown` update and re-index) and writes **new** `DocumentFile` rows (new `file_id`s, new storage keys); the superseded rows are deleted in the same transaction, and their blobs are purged the moment it commits. The blob store has no transaction to enlist in, so that purge is best-effort in both directions — a failed delete leaves an unreferenced blob and a log line, and a rolled-back save deletes the bytes it just wrote. Consequences, all intended:
  - Every reference (chat cards, library, tree, search, links) is a `document_id` and always resolves to the latest generation — an update propagates everywhere with zero code, exactly Claude's behavior. The chat card is the one that has to be right by construction rather than by refresh, and is: it stores the id alone, and the panel resolves the document's files when it opens, so a card printed before the revision opens the current generation. All that goes stale on it is the format badge, frozen in the tool result the model returned.
  - Cache correctness is free: revised artifacts have new per-`file_id` URLs; old URLs 404 and the panel refetches.
  - A failed revision leaves the previous generation intact — the failure mode is "update didn't happen," never "artifact destroyed."
  - Revisions are **destructive by design**. The prior deliverable is not recoverable from the product; the conversation is the version history, and download is the user's escape hatch for keeping a specific generation. Asking for a change to be undone is the way back, and it costs the same as any other revision because the agent edits the stored source rather than rebuilding from a summary — the artifact moves forward to something equivalent to where it was, never backward to the same bytes. Whether and when to download before revising is the **user's decision** — the product adds no nudges, prompts, or retention mechanisms around it.
  - Retention also **doesn't scale**: each generation carries up to three blobs (primary, preview, source), iterative workflows produce many generations per deliverable, and with no surface ever reading old ones, every retained blob is blob-store rent paid for nothing. Eager purge-on-commit means storage holds exactly the live set — no lifecycle policies, no retention tiers. The one sweep that exists is not retention in disguise: the purge is best-effort against a store with no transaction to enlist in, so a failed delete leaves bytes nothing references and a log line nothing acts on, and a periodic pass reclaims storage keys with no `DocumentFile` row behind them. It reads storage and deletes from storage — never git, never a working copy.
  - **"Unversioned" is a product guarantee, not a storage claim.** On git-backed workspaces the markdown *representation* accrues git history like any note (§4.4) — an inert audit trail. The deliverable bytes were never in git, so nothing behind those history entries is viewable or restorable; the guarantee is that no surface ever reads them for a generated document.
  - **No back doors, at every layer:** the revise path never writes `document_versions` (no `create_version_snapshot` call); it is excluded from agent-revert snapshotting (`document_revisions`); and the git-KB's future revert verb and version-history UI exclude `generated: true` documents (§4.4) — otherwise "revert my turn" or a history screen would resurrect a description whose deliverable no longer exists. See the table fences in §4.1.
- **Deletion:** `purge_document_blobs()` + FK cascade covers it — but the two had never been wired together on the store's delete path, where the cascade dropped the `DocumentFile` rows and left their bytes behind. The projection's `delete_row` now purges before deleting the row. One call, fixing every deleted document's blobs, not just artifacts'.

### 4.4 Integration with the git-native knowledge store

The git-KB pivot ([`plans/git-native-kb/`](../git-native-kb/00-umbrella-plan.md)) makes git the source of truth for indexed KB content and demotes Postgres chunks to a derived, rebuildable index. Artifacts are **full citizens of that model**, not an exception to it. The pattern already exists in the store for uploads — original binary in the blob store, extracted markdown in git, Postgres row derived — and an artifact is the same shape with the arrows reversed:

> **An artifact is a KB note with generated files attached.** Markdown representation in git; deliverable bytes in the blob store; `Document` + chunks derived.

- **Write path — the turn's working copy, like every agent write.** On a git-backed workspace, `save_artifact` persists the `Document` row and `DocumentFile` bytes write-through inside the tool call (the §3.1 promise — `document_id` returns immediately, failure is visible in-turn), and writes the markdown representation into the turn's **private working copy**. It joins the turn's single end-of-turn commit alongside whatever notes the agent edited — one turn = one commit, always (contract C6). No mid-turn direct commits, no separate ingest flow: artifacts inherit the write lock, commit-message generation, and failure recovery (copy kept for next turn) with zero new commit machinery. `prepare_for_indexing`/`index_batch` are never used — the store facade's ingest adapter hooked there would mint its own `sync:` commit outside the turn (§4.1 fence).
- **Indexing — the store's projection and convergence, trusted as-is.** When the turn commits, the commit-time projection (git-KB Phase 6, `knowledge_store/index/project.py`) resolves the committed file to the artifact's existing row — recorded path first, NOTE hash as fallback, via the primitives in `index/rows.py` that the projector and the async converger share so the two moments can never disagree about identity — **adopts** it and stamps `PATH_MARKER`; the convergence then chunks and embeds `source_markdown`, exactly as for any note. Neither contains artifact-specific code or guards: everything they do to a note (adopt, update on change, delete when the file leaves the tree) is precisely what artifacts want done to them. Only the KB **search hit** is eventually consistent on git workspaces (post-convergence, seconds after the turn) — the artifact itself is saved and renderable instantly, and its row is adopted the moment the turn commits.
- **Deletion — one model, both directions.** From the tree: `rm` the artifact's file (agent tools) → the turn commits the removal → the projection purges the blobs and deletes the row → FK cascade drops the `DocumentFile` rows. From the UI: deleting the document routes through the store facade's direct-caller adapter (git-KB Phase 7, `delete_documents`), which removes the file from git in the same motion — row and tree never disagree, nothing resurrects. Notes and artifacts alike.
- **Rebuild — the invariant holds with no exception clause.** `index_tree()` rebuilds artifact chunks from the committed markdown representation like everything else. The binaries were never git's job — the git-KB's own locked decision keeps binaries in the blob store (uploads' originals included) — so "Postgres is rebuildable from git + blob store" covers artifacts verbatim.
- **Forward-only — the one product rule artifacts add.** Because deliverable bytes are destroyed on revise (§4.3), an old git entry for a generated document is only *half* a version: the description survived, the deliverable didn't. Two future git-KB verbs therefore filter on `document_metadata.generated == true`: the **revert verb** excludes generated documents' paths from its inverse diff (reverting a mixed turn restores the notes, leaves the artifact at its latest generation — no description/file mismatch can exist), and any **version-history UI** excludes generated documents (there is nothing viewable or restorable behind their entries). This is not a data guard — it is the "artifacts move forward only, via regeneration" rule (Claude's behavior) applied at the feature level, and it is the *entire* artifact-awareness in the git KB: one metadata predicate, two verbs, neither built yet.
- **Coexistence — one temporary branch.** On legacy (unflagged) workspaces there is no repo, no commit, and no convergence, so `save_artifact` chunks + embeds directly via `IndexingPipelineService.index()` after saving. That `else` branch is a bridge with a scheduled demolition: it is deleted at the git-KB Phase 5 cut together with `kb_persistence` and the rest of the legacy path, leaving the git path as the only path.
- **Retitle never moves the file — the path law, inherited.** The artifact's path is authored once (§4.1); a revise rewrites the file at the row's recorded path, and a title change updates the title column only. Every surface (sidebar, search, chat cards) reads the row's title, and references are id-keyed, so nothing breaks — and no rename can ever drift the row's identity. The file moves only by an explicit move, through the store's own verbs. The law has a second half the store had not yet implemented: if titles never move files, **files must never rename titles**. The commit-time projection re-derived every upserted row's title from its filename, which quietly reverted a retitle at the next commit; it now re-derives only when the path itself changed. General fix, no `generated` predicate — artifacts were simply the first writer to retitle a row without moving it.

---

## 5. Serving design

One new endpoint; everything renders and downloads through it.

```
GET /api/v1/workspaces/{ws_id}/documents/{doc_id}/files/{file_id}/content
```

1. **Auth:** the same workspace-membership dependency as every other document route. Files are always proxied through the backend — no SAS/presigned URLs in v1, so auth is uniform across local and Azure. <!-- ponytail: proxying costs API-server bandwidth; ceiling is large-file throughput at scale, upgrade path is a 302 to a time-limited SAS URL behind this same route -->
2. **Resolve:** `DocumentFile` row must belong to `doc_id`/`ws_id`; 404 otherwise.
3. **Stream:** `StreamingResponse` over `open_document_file_stream()` with headers:
   - `Content-Type: {row.mime_type}`
   - `Content-Disposition`: `inline` for `application/pdf` **only**; `attachment` for everything else. Always includes the original filename. This is the stored-XSS guard: the bytes behind this route are user- or agent-authored, and `inline` means "render on our origin" — an XSS grant for any format that carries script (`.html`, `.svg`), which `nosniff` does not mitigate when the declared `Content-Type` is the honest one. PDF earns its exception because browsers render it in a sandboxed native viewer with no origin access, and no other type has a consumer: the app's own viewers and download buttons fetch bytes with auth headers and ignore disposition entirely, so `inline` only ever serves a human navigating to the raw URL. The allowlist widens per MIME type, by name with a consumer attached — never by wildcard (`image/*` once smuggled in scriptable SVG).
   - `X-Content-Type-Options: nosniff`
   - `ETag: "{row.checksum_sha256}"`, `Cache-Control: private, max-age=31536000, immutable` — files never change (§4.3), the checksum already exists, so previews are cached client-side forever. Honor `If-None-Match` → 304.

The frontend's existing authenticated-fetch pattern (`getAuthHeaders()` in `pdf-viewer.tsx`) works against this endpoint unchanged.

---

## 6. Agent & tools design

### 6.1 The deliverables subagent keeps its seat; its tools are replaced

Supervisor routing (`task(deliverables, …)`) is unchanged. Inside the subagent, `generate_report` and `generate_resume` are **removed** and replaced with the format-blind tools below:

| Tool | Signature (conceptual) | Behavior |
|---|---|---|
| `execute` | `(code_or_command) → stdout/stderr/exit` | Runs in the thread's sandbox session via the provider's persistent kernel (Python) or shell (Node scripts, `soffice`, `pdftoppm`, `pandoc`). |
| `read_sandbox_file` | `(path) → str` | Pulls **UTF-8 text** back — source files, logs, extracted content. Size-capped by `ARTIFACT_MAX_FILE_BYTES`; binary and non-UTF-8 are refused with an error naming the right tool, because image bytes cannot survive this stack's text-only tool-result serialization (§12 open question 2). |
| `inspect_sandbox_images` | `(paths, instructions, mode) → str` | The verification loop's eyes. Reads rendered page JPEGs inside the tool, calls `get_vision_llm()`, and returns a text QA report keyed by filename. The model reads findings, never pixels. Takes every page whatever the count: `mode="each"` reviews each page in its own call, fanned out concurrently; `mode="together"` compares pages in consecutive windows. The caller never sizes a batch or picks a sample (§6.3). JPEG only, size-capped per image. |
| `save_artifact` | `(path, source_path, title, markdown_representation, preview_path?, document_id?) → §3.1 payload` | Write-through persist: reads bytes from the sandbox, creates `Document` + `DocumentFile`(s) in one transaction, returns the contract payload. `source_path` is required beside `path` for generated files — the deliverable without the thing that made it is an artifact that can only ever be replaced, never edited (§4.1). **Also the verification gate** — refuses a primary file whose mtime is newer than the session's most recent verification (a vision inspection or a clean-exit assertion script), so the §6.3 loop is an invariant of the tool rather than a promise repeated in every skill's prose. "Could not verify" is not "did not verify": when no vision model is configured or premium credit runs out mid-loop, the save proceeds with the reason recorded in `document_metadata`. The `markdown_representation` then reaches the search index per §4.4 — written into the turn's working copy on git workspaces (committed + indexed by the KB pipeline), indexed directly on legacy ones. Markdown artifacts pass content directly with no `path`. |
| `load_artifact_source` | `(document_id) → path` | Materializes a saved artifact's stored source into the session workspace and returns its path, so a revision starts by editing what actually produced the file. It reads storage, never the sandbox — the session that built the artifact is reaped long before most change requests arrive, and making the stored copy the only source of truth leaves one code path instead of two that differ by how recently the artifact happened to be made. |

Streaming emission: one generic `save_artifact` handler replaces the per-tool `generate_report/` and `generate_resume/` emission handlers.

The subagent runs fresh per `task(…)` call and keeps nothing between turns, so on its own nothing in the model's context connects "make the header bigger" to the PDF it produced yesterday — it would build a second document, which is exactly the failure §3.1's revise input exists to prevent. Each run is therefore prefixed with a short roster of the artifacts this chat has produced: `document_id`, title, filename, most recent first, capped. The chat is resolved from the invocation's runtime config every time rather than captured when the agent graph is built, because compiled graphs are cached across chats and a captured id would eventually hand one conversation another's artifacts. The roster filters on `document_metadata.generated` and the thread id; the predicate stays in metadata where every fence in §4.1 and §4.4 already reads it, and pays for the query with an expression index rather than by moving the vocabulary into columns and splitting its home.

### 6.2 Skill selection (no new machinery)

The existing skills system provides progressive disclosure exactly as Anthropic's spec describes:

- **Level 1** — each format skill's frontmatter (`name`, `description`) is always present in the subagent prompt (~100 tokens/skill). The description states what the skill does *and when to use it* ("Use whenever the user wants a Word document, .docx, report/memo/letter as Word…"). Level 1 must be in the prompt — reading a roster out of the sandbox would mean starting a sandbox before the model knows whether it needs one — so the roster stays prose and a **check ties it to the skills source**: the frontmatter under `docker/sandbox/skills/*/` is the truth, and a mismatch fails the build. Drift is then a red build rather than a prompt advertising a format the image does not carry, or carrying one it never advertises.
- **Level 2** — the model reads the full `SKILL.md` only when it decides the format is needed (the "Loaded docx skill" step visible in Claude traces).
- **Level 3** — helper scripts (`soffice.py` wrapper, validators, thumbnailers) live in the sandbox image at `/opt/skills/{format}/scripts/` and are executed via `execute`; their source never enters context.

Genre → format mapping is prompt guidance in the subagent system prompt, not code: *"Decide the output format from the user's intent. Resumes/formal documents → docx or pdf. Slides → pptx. Tabular/analytical → xlsx. Ambiguous → pdf, or ask."* The user can always override.

### 6.3 The mandatory verification loop

Every format skill ends with the same discipline (evidence: Anthropic's docx skill "Verify the output" section — this loop is why their documents come out well-formatted). Two shapes exist and each skill states which it uses.

**Visual** — `pdf`, `docx`, `pptx`:

```
1. Generate the file (docx npm / python-pptx / reportlab-weasyprint), keeping the source.
2. Measure what needs no eyes: text outside the margins, blank pages, page count,
   unembedded fonts. Defects here cost no vision call at all.
3. Convert to PDF if not already PDF: soffice --headless --convert-to pdf out.docx
4. Rasterize: pdftoppm -jpeg -r 100 out.pdf page
5. inspect_sandbox_images(all pages, instructions) → findings keyed by filename.
   The tool reviews each page on its own. The model reads a report; never pixels.
6. inspect_sandbox_images(all pages, …, mode="together") → cross-page findings
   (font drift, colour drift, page count) that per-page review cannot produce.
7. Broken? Fix the source and repeat from step 2.
8. Only then: save_artifact(path=out.docx, source_path=out.js, preview_path=out.pdf, …),
   which rejects the save if the file changed after its last verification.
```

**Programmatic** — `xlsx`: no rasterizing and no vision call. Recalculate headless, read the expected cells back, assert. See §7.1 — the recalculated file is the file saved. The two shapes are not exclusive: the visual skills run the measurable checks of step 2 as well, which is the programmatic shape applied to what pixels would answer more expensively.

**Revising enters either shape at the same place**, and nothing about it is per-format: `load_artifact_source(document_id)` before step 1, then edit what comes back rather than rebuild from the markdown representation. The source is simply whatever that format's generate step wrote — a Node script for docx, a Python script for pptx or xlsx, HTML for a weasyprint PDF — and `save_artifact` demands it back without knowing or caring which. A skill therefore says nothing about revision at all, exactly as it says nothing about the verification gate: both are properties of the tools every skill already calls, so a new format inherits them by existing.

**Page count changes how much work happens, never what work happens.**

Every page gets the same treatment — measured, reviewed individually, compared in windows — identically at one page and at forty. Cost is therefore linear in the artifact, which is proportionality rather than a problem to be optimized: a ten-page document costs ten pages of verification because it is ten pages of document. Any rule that varies with length (a batching threshold, a "risky pages" sample) is a judgment the model has to apply, applies wrongly in silence, and buys tokens back by trading away correctness.

Two consequences fall out rather than needing rules. Per-page review keeps the model's attention on one page, so each finding names one fixable defect; the tool fans those calls out concurrently, so a long document costs proportionally more tokens but not proportionally more waiting. And cross-page findings — font drift, colour drift, page count — need pages seen together, which one vision call can only do for a bounded number of images; the tool therefore compares in **consecutive windows**, a uniform rule at every length, instead of asking the skill to choose which pages are worth comparing. Windows also beat a first-and-last sample on the merits, since drift between pages 12 and 13 appears in the window holding both.

*Generation* is the one asymmetry: it can be incremental only where the units are independent. Slides and worksheets can be built and checked one at a time, a flowing PDF cannot — there is no "page 2" until the whole document renders, pagination is emergent, and editing anything above a break moves everything below it. A page-at-a-time PDF skill is not writable.

The verification PDF is the preview file — the office-format preview costs zero extra compute because the quality gate already produced it.

### 6.4 Turn flow, end to end (example: "create me a resume")

```
1. Supervisor → task(deliverables, "create a resume with …").
2. Model reasons: resume → formal document → docx (skill descriptions in prompt).
3. Reads docx SKILL.md (Level 2) via sandbox filesystem.
4. execute: node resume.js  → resume.docx        (docx npm preinstalled)
5. execute: soffice → resume.pdf; structural check (clean); pdftoppm → page-1.jpg
6. inspect_sandbox_images([page-1.jpg], …) → text findings; model fixes the source and regenerates.
   (One page, so the "together" comparison has nothing to compare and says so.)
7. save_artifact(path=resume.docx, source_path=resume.js, preview_path=resume.pdf,
     title="…", markdown_representation="…")
   → Document + 3 DocumentFiles persisted; markdown representation written to the turn's
     working copy (git workspaces); payload returned.
8. Tool result streams; artifact card renders with document_id; right panel auto-opens; PdfViewer streams the preview; Download serves the .docx.
9. End of turn: the working copy commits (one commit for the whole turn, notes + artifact alike);
   the projection adopts the row at commit, the convergence chunks it — the resume is now in
   the KB tree instantly and in search seconds later.
```

Failure at any step is a visible tool error in the same turn — the model retries or reports. There is no path where the user is told "saved" and nothing was saved. (Step 9 failing is the git-KB's own recovered case: the working copy is kept and committed next turn; the artifact itself was already durable at step 7.)

---

## 7. Skills & sandbox design

### 7.1 Launch skills

Four skills, each a directory under the existing skills root (`{format}/SKILL.md` + `scripts/`), authored fresh (Anthropic's skill *files* are license-restricted — "Proprietary, see LICENSE.txt" — so we write our own against the same toolchain, which their docs openly describe):

| Skill | Create with | Verify with | Notes |
|---|---|---|---|
| `pdf` | reportlab / weasyprint (Python) | pypdf measurements → pdftoppm → `inspect_sandbox_images` | Resumes, reports, letters, one-pagers land here or docx. Measurable defects first, then every page reviewed and compared (§6.3) |
| `docx` | `docx` (npm, Node) | soffice → pdf → pdftoppm → `inspect_sandbox_images` | Same loop as `pdf`. Encode the known footguns: DXA table widths, `ShadingType.CLEAR`, numbering for bullets, TOC outline levels, tab stops over PositionalTab |
| `pptx` | python-pptx | soffice → pdf → pdftoppm → `inspect_sandbox_images` | Same loop over slides. Slides are independent, so the skill builds and verifies incrementally instead of rendering all of them first |
| `xlsx` | openpyxl | LibreOffice headless recalc (**mandatory before save**) + read back values | No visual loop; verify programmatically. The recalculated file is the file saved: openpyxl writes formulas with **no cached values**, and the grid viewer renders cached values — an un-recalced file renders blank formula cells (§8.2) |

Adding a format later = one new skill directory + sandbox image rebuild + (optionally) one viewer-registry entry. No backend changes.

### 7.2 Sandbox image (`surfsense/sandbox`)

Single polyglot image, everything preinstalled (the sandbox has **no network egress** at runtime, so skills must never need `pip install`/`npm install`):

- Python 3.12 + `openpyxl`, `python-pptx`, `reportlab`, `weasyprint`, `pypdf`, `pandas`, `matplotlib`
- Node LTS + `docx` (npm, globally installed)
- LibreOffice (`soffice`), Poppler (`pdftoppm`), `pandoc`
- Fonts: DejaVu, Liberation, Noto (incl. CJK) — LibreOffice output quality is font-bound
- Skills at `/opt/skills/`

### 7.3 Provider protocol

```python
class SandboxProvider(Protocol):
    async def get_or_create_session(self, thread_id: str) -> SandboxSession: ...

class SandboxSession(Protocol):
    async def execute(self, code: str, language: str = "python") -> ExecResult: ...
    async def run_command(self, command: str) -> ExecResult: ...
    async def read_file(self, path: str) -> bytes: ...
    async def write_file(self, path: str, data: bytes) -> None: ...
    async def terminate(self) -> None: ...
```

- **Self-hosted:** OpenSandbox — `opensandbox-server` added to `docker-compose.yml`, sandboxes created from `surfsense/sandbox`, persistent-kernel code-interpreter API for warm Python execs (benchmarked rationale: container start 0.3–0.6 s and warm exec ~0.09 s are cheap; the ~450 ms/exec Python import tax is what the persistent kernel eliminates).
- **Cloud:** Daytona, same protocol.
- Selection: `SANDBOX_PROVIDER=opensandbox|daytona` at startup. **A deployment choice, not a fallback chain.**
- Lifecycle: one session per chat thread, created lazily on first `execute`, TTL-reaped (default 15 min idle), hard-killed at thread deletion. Per-workspace concurrent-session limit (default 2) to bound resource use.
- **Gate:** the one-day OpenSandbox spike (compose service up → custom image → persistent-kernel exec → binary file out → kill, measuring warm-exec latency and file egress) must pass before phase 2 implementation starts. If it fails, the fallback *decision* (not runtime fallback) is llm-sandbox's `InteractiveSandboxSession`, accepting that we then own socket security and lifecycle.

---

## 8. Rendering design

### 8.1 One right panel, one registry

The report panel is replaced by a single **artifact panel** that receives a `document_id`, calls `editor-content`, and branches on the §3.2 contract:

- `kind: "text"` → read-only markdown viewer (existing `MarkdownViewer`; **not** Plate).
- `kind: "file"` → the viewer registry picks a component from the **primary** file's MIME type.

### 8.2 Viewer registry (the only format-aware frontend code)

```tsx
const VIEWERS: Record<string, ViewerEntry> = {
  "application/pdf":  PdfFileViewer,      // streams the primary file
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document":   PdfPreviewViewer,
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": PdfPreviewViewer,
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":          XlsxViewer,
};
// unmatched MIME → <FileDownloadCard />   (never an error)
```

- `PdfFileViewer` / `PdfPreviewViewer` are thin wrappers around the existing `pdf-viewer.tsx`, pointed at `content_url` of the primary or preview file respectively; the preview variant adds a "Download {filename}" toolbar action (the `toolbarActions` prop exists) hitting the primary file's URL.
- `XlsxViewer` renders the **primary** file natively — no preview blob exists for xlsx: fetch `content_url` (existing authenticated-fetch pattern, ETag-cached), parse in-browser with **ExcelJS** (MIT — values, fills, fonts, borders, merged ranges, column widths, sheet list), format display text with **`ssf`** (Apache-2.0 — turns raw `10413` + `"$#,##0.00"` into `"$10,413.00"`), and render a read-only virtualized grid with column letters, row numbers, and sheet tabs. Row-capped for huge sheets ("showing N of M rows — download for full data"); parse failure or oversize falls through to `FileDownloadCard`. Fidelity boundary: cell data and styling render; charts, conditional-formatting rules, and pivot tables do not — it is a grid, not an Excel emulator (Claude's viewer shares this boundary).
- All viewers lazy-loaded via `next/dynamic` (pdf.js and ExcelJS stay out of the main bundle).
- Rationale for the matrix: browsers render PDF natively (pdf.js); client-side office renderers were evaluated and rejected on evidence (mammoth discards layout by design; docx-preview approximates; no credible OSS PPTX renderer; MS Office Online viewer requires public URLs). XLSX preview-as-PDF is likewise rejected — it misrepresents spreadsheets (truncated sheets, invisible formulas) — but a native grid does not: ExcelJS + ssf render what Claude's own xlsx viewer renders. Parser selection was evidence-driven: **SheetJS CE rejected** (cell styling is Pro-only — maintainers confirm CE's `cellStyles` reads only row/column metadata); **Univer rejected** (xlsx import is a commercial Pro plugin requiring their server, watermarked and size-capped unlicensed); **ExcelJS chosen** (MIT, parses styles in-browser).

### 8.3 Per-format matrix

| Format | Panel shows | Download serves | New code |
|---|---|---|---|
| PDF | The file itself in pdf.js viewer | The PDF | URL change only |
| Markdown | Read-only rendered markdown | `.md` blob | Panel branch |
| DOCX / PPTX | Preview PDF in pdf.js viewer | The real .docx/.pptx | `PdfPreviewViewer` wrapper |
| XLSX | Native read-only spreadsheet grid (sheet tabs, values + styles) | The real .xlsx | `XlsxViewer` (ExcelJS + ssf) |
| Unknown / oversized / xlsx parse-failure | File card (name, size, icon) | The file | `FileDownloadCard` |

### 8.4 Editing policy

Generated artifacts are **read-only + regenerate in place**. Revision requests go back through the agent (new sandbox run → same `document_id`, files replaced transactionally, §4.3), which reopens the stored source and edits it, so a change asked for a month later is the same operation as one asked for a minute later. Revisions are destructive by design — all chat references converge on the latest generation and prior generations are gone; this is a deliberate product decision mirroring Claude's artifact behavior, not an oversight.

**Product-level boundary:** Plate is retired everywhere except **memory and team-memory** editing — and this overhaul owns that retirement (phase 4), not a separate effort. The artifact panel is strictly a renderer — it has no editing surface for any format, *including markdown artifacts*, and no Plate-parity work is ever in scope for artifacts. The document editor panel (`editor-panel.tsx`) reduces to the same posture: its `document` mode becomes a pure read-only viewer — `MarkdownViewer` normally, Monaco raw view for oversized documents; both branches already exist — shedding the edit/save state machine, the `/documents/{id}/save` call, the Plate size warnings, and the version-history button (already a 409 on git-backed workspaces; its table and endpoints die at the git-KB Phase 5 cut). The `memory` mode keeps Plate untouched; the desktop `local_file` mode is out of scope — it is Monaco, not Plate, and belongs to a different feature. After phase 4, Plate mounts in exactly one place (the two memory panels) and the agent is the only writer of `/documents` content.

One consequence to hand the git-KB effort knowingly rather than let it discover: retiring document editing orphans the UI caller of the store facade's `save_document` verb (`editor_routes.py` → `knowledge_store/service.py`). The verb itself stays — other adapters use it — but the editor-save flow it was shaped around (`title_is_explicit`, the retitle file-drop) loses its only frontend entry point.

### 8.5 Chat surfaces

- `ARTIFACT_TOOL_KINDS` / `collect-artifacts.ts`: `save_artifact` maps to one artifact kind (`file`), with icon and label derived from the payload's primary MIME/filename. `report` and `resume` kinds are removed.
- The inline card shows filename, format badge, size, download button; click opens the panel. Desktop auto-open on completion is preserved.

---

## 9. Deprecation & removal (delete, don't flag)

Executed in phase 4, after the legacy card + release-notes warning land (§10). Nothing here is kept behind a flag.

### 9.1 Backend

| Delete | Location |
|---|---|
| `generate_report`, `generate_resume` tool implementations — registration is already gone, dropped in phase 3 the moment the four skills covered every format | `subagents/builtins/deliverables/tools/{report.py,resume.py}`, `index.py`, `shared/tools/catalog.py`, prune/tool-name lists |
| `report-writing` builtin skill (rigid template) | `main_agent/skills/builtin/report-writing/` |
| Streaming handlers | `tasks/chat/streaming/handlers/tools/deliverables/generate_{report,resume}/` + dead `save_document/` registry name |
| Reports routes (content, preview, export, public preview) | `routes/reports_routes.py`, Typst branches in `public_chat_routes.py` |
| Typst export path for documents | pandoc→typst branch in `editor_routes.py` (PDF export of markdown documents re-routes through weasyprint; other pandoc formats kept) |
| Templates | `app/templates/report_pdf.typst`, `get_typst_template_path()` in `export_helpers.py` |
| `Report` model + `reports` table (incl. `report_group_id` sibling versions, `_get_version_siblings`) | `db.py` + drop migration — dropped cold, no data copy (§10) |
| Schemas | `schemas/reports.py` |
| Dependencies | `typst`, rendercv assumption; `pypdf` only if no remaining user |
| Tests | `tests/unit/agents/new_chat/tools/test_resume_page_limits.py` |

### 9.2 Frontend

| Delete | Location |
|---|---|
| Report panel + atom (incl. the version-switcher UI — nothing replaces it) | `components/report-panel/report-panel.tsx`, `atoms/chat/report-panel.atom.ts` (pdf-viewer.tsx is **kept** and relocated to a shared path) |
| Tool UIs | `components/tool-ui/generate-{report,resume}.tsx` |
| Artifact kinds `report`/`resume`, typst contentType | `features/chat-artifacts/model/artifact.ts`, `collect-artifacts.ts` |
| Reports API client + types | `lib/apis/reports-api.service.ts`, `contracts/types/reports.types.ts` |
| Typst/`pdfOnly` export special cases | `components/shared/ExportMenuItems.tsx` |
| Artifacts library data source | re-pointed to documents query (§10.3), reports fetch removed |
| Document-mode editing (edit/save state machine, `/documents/{id}/save` call, Plate size warnings, `EDITABLE_DOCUMENT_TYPES`) — `document` mode becomes read-only viewing per §8.4; `memory` keeps Plate, `local_file` (Monaco) untouched | `components/editor-panel/editor-panel.tsx` |
| `VersionHistoryButton` mounts (the component + restore endpoints themselves belong to the git-KB Phase 5 cut) | `editor-panel.tsx` usages of `components/documents/version-history.tsx` |

---

## 10. Legacy deliverables (previously generated files)

**There is no data migration.** The only two coherent options were (a) backfill `reports` rows into Documents, or (b) drop the table and stop showing old deliverables — anything in between means keeping `reports_routes.py` + the report panel alive indefinitely, which defeats the retirement. Option (b) is the decision: phase 4 drops `reports` cold, and previously generated reports/resumes (including all `report_group_id` sibling versions) become **permanently inaccessible**. This is a chosen product trade, consistent with the unversioned-artifacts philosophy (§4.3), not an accident.

What replaces the backfill — two purely presentational things:

### 10.1 Legacy card in old threads

Old chat threads contain `generate_report`/`generate_resume` tool-call parts that something must render forever. They render a **static legacy card**: title from the tool payload, plus "Generated with the previous artifact system — no longer available. Ask me to regenerate it." No lookup, no data fetch, no click-through to a panel. This is the minimal something.

### 10.2 Release-notes breaking-change warning

The release that drops `reports` carries a prominent breaking-change note so self-hosted users can export any deliverables they care about **before** upgrading (the export endpoints exist right up until that version). Documentation, not code — the export decision stays with the user, per the product boundary in §4.3.

### 10.3 Surfaces

- Artifacts library queries Documents (`document_metadata.generated == true` / `GENERATED` file kind) instead of `reportsApiService.list`. Old deliverables simply stop appearing in it on upgrade.
- No `migrated_from_report_id`, no verification gate, no lazy re-indexing, no Typst compile at upgrade time — the `typst` dependency is removed with zero final use.

---

## 11. Delivery phases

Each phase ships independently and leaves the product working. Detailed task breakdowns, file-level plans, and exit criteria live in per-phase spec files; **this document owns the contracts (§3) and the architecture — phase files own execution detail and are revised independently.** A phase file may not contradict §3 without a revision here first.

| Phase | Spec file | One-line scope | Exit gate |
|---|---|---|---|
| 1 — Foundation *(shipped)* | [`phase-1-foundation.md`](./phase-1-foundation.md) | Schema, `save_artifact` (markdown path), streaming endpoint, `editor-content` discrimination, artifact panel + registry | Markdown artifacts persist write-through and render; seeded binary file streams + downloads correctly |
| 2 — Sandbox + PDF | [`phase-2-sandbox-pdf.md`](./phase-2-sandbox-pdf.md) | OpenSandbox spike (gate), provider protocol, sandbox image + compose service, `execute`/`read_sandbox_file`, `pdf` skill, `PdfFileViewer` | "Create me a resume as a PDF" flows through the new pipeline with a verified PDF; zero Typst involvement |
| 3 — Office skills | [`phase-3-office-skills.md`](./phase-3-office-skills.md) | docx/pptx/xlsx skills, preview-PDF pairing, `PdfPreviewViewer`, `XlsxViewer` (native grid), download-card polish, legacy tools demoted to "never use" | All four formats per the §8.3 matrix; unknown formats degrade to the card with no code changes |
| 4 — Demolition | [`phase-4-migration-demolition.md`](./phase-4-migration-demolition.md) | Legacy card + release-notes warning (§10), surface re-pointing, then the full §9 deletion inventory incl. Typst and the `reports` drop | Zero references to `Report`/`typst`/legacy tools; old threads render legacy cards with no data fetch |

Ordering constraints: 1 → 2 → 3 → 4 strictly; the OpenSandbox spike (phase 2, task 0) blocks all phase-2 integration work; the legacy card + release-notes warning (phase 4, §1) land before any deletion PR.

---

## 12. Risks & open questions

| Risk | Mitigation |
|---|---|
| OpenSandbox spike fails (pre-1.0 project) | Decision-level fallback documented (§7.3): llm-sandbox `InteractiveSandboxSession`; protocol isolates the blast radius to one provider file |
| LibreOffice conversion fidelity (fonts, complex layouts) | Fonts baked into image; verification loop catches visual breakage before save — the model sees what LibreOffice renders, not what Word would |
| Sandbox resource exhaustion (self-hosted, small VPS) | Per-workspace session cap, TTL reaper, 30 MB file cap; compose memory limit on the sandbox service |
| Skill licensing | Anthropic skill files are proprietary; ours are authored fresh against the publicly documented toolchain |
| Verification loop cost (one vision call per page/slide, §6.3) | Cost is linear in pages by design; **latency is not**, because the tool fans the per-page calls out concurrently, so a long document waits roughly as long as a short one. Two cost levers are already spent: measurable defects are found by pypdf before any vision call, and render resolution is pinned at `-r 100` (~1.1–1.3k tokens for an A4 page) since tokens scale with pixel dimensions, not bytes — compressing the JPEG harder saves the cap and the transfer without saving a token, and going below 100 dpi makes small type illegible so the loop starts reporting render artifacts as document defects. Remaining lever, deferred: content-addressed skipping — hash each rendered image and reuse the previous finding when bytes are unchanged. It pays for decks, where slides are independent, and barely pays for reflowing documents, where a fix changes every page after it. Internal to `inspect_sandbox_images`; changes no signature, skill, or spec |
| Per-page verification multiplies premium credit debits (hosted plan) | `get_vision_llm` wraps premium global configs so every `ainvoke` is a `billable_call` reserve/finalize plus a `TokenUsage` row — per page under §6.3, not per document. BYOK and free configs are unwrapped, so self-hosting is unaffected. Two consequences are handled rather than absorbed: verification carries its own `usage_type` so the spend stays attributable, and credit exhausted mid-loop takes the §6.1 "could not verify" branch instead of discarding a finished deliverable |
| Users lose old deliverables on upgrade (no-migration decision, §10) | Deliberate product trade; release-notes breaking-change warning + pre-upgrade export window are the mitigation — no code |
| Projection or convergence creates a duplicate row instead of adopting the artifact's (identity mismatch) | Artifact rows resolve like any note's — recorded path first, standard NOTE hash as fallback (§4.4); both moments share one resolution primitive (`index/rows.py`), and adoption is integration-tested in phase 1 — one row, marker stamped, chunks present, no ghost sibling |
| A revision names the wrong `document_id` and destroys an artifact the user still wanted | Three layers, none of them a confirmation prompt: the roster the model reads is scoped to the current chat, so an id from another conversation is not offered; the helper re-checks workspace ownership and the `generated` flag before touching anything; and creating is the default whenever no id is named, which puts the cheap failure (a duplicate) on the path the model takes when unsure |
| A future git-KB verb resurrects an old generation (revert / version-history UI) | The forward-only rule: both verbs filter `generated: true` documents (§4.3/§4.4); the constraint is cross-referenced in the git-KB umbrella so the verb's implementer inherits it |
| Large workbook parsed in the browser (`XlsxViewer`) | Viewer lazy-loaded (ExcelJS never in the main bundle); row-capped render with a "download for full data" notice <!-- ponytail: row cap, not streamed parsing; ceiling is very large sheets rendering partially, upgrade path is a streaming/worker parse -->; parse failure or oversize degrades to the download card, never an error |

**Open questions (decide during phase 1 review):**

1. Public/shared-chat rendering of artifacts (public token → file streaming) — **decided as a deferral in phase 1**: share-token visitors get the artifact card, inert, because both `editor-content` and the §5 route demand workspace membership. Serving them needs a token-scoped variant of the §5 route (share token → thread → the artifacts that thread produced); scheduled with phase 3, when there are binary artifacts worth sharing.
2. Image inspection — **resolved in phase 2**: image bytes cannot survive this
   stack's text-only tool-result serialization. `inspect_sandbox_images` reads
   rendered JPEGs inside the tool, calls the workspace's dedicated
   `get_vision_llm()` per call, and returns text QA findings.
   `read_sandbox_file` remains UTF-8 text-only.

*(Resolved: retention/GC for superseded versions — moot; revisions replace files in place with no history, §4.3. The orphan sweep that §4.3 does keep is a different thing: it reclaims blobs a best-effort purge failed to delete, and never resurrects anything, because a blob with no row behind it is unreachable by every surface.)*
