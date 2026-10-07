---
status: in-progress
code:
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/backend/modules/folders/
  - surfsense_local/backend/modules/source_roots/
  - surfsense_local/backend/modules/source_scope/
  - surfsense_local/backend/modules/documents/
  - surfsense_local/backend/modules/chat/
  - surfsense_local/backend/modules/artifacts/
  - surfsense_local/backend/modules/agent/
  - surfsense_local/backend/modules/migration/
  - surfsense_local/backend/shared/search.py
  - surfsense_local/backend/shared/migrations.py
  - surfsense_local/backend/api/main.py
  - surfsense_local/backend/worker/ingestion/
  - surfsense_local/backend/worker/studio/shared/
  - surfsense_local/backend/pyproject.toml
  - surfsense_local/backend/bundling/api.spec
  - surfsense_local/electron/src/main/
  - surfsense_local/electron/src/preload/
  - surfsense_local/electron/electron-builder.yml
  - surfsense_local/frontend/src/features/sources/
  - surfsense_local/frontend/src/features/chat/
  - surfsense_local/frontend/src/features/studio/
  - surfsense_local/frontend/src/features/dashboard/
---

# Sources and folders

> A workspace's sources sit in folders. Every workspace has one library root whose folders the user makes in the app. It may also link folders on disk as further roots. SurfSense indexes a linked folder in place, watches it, and never writes to it. A delete in the library goes to a Trash first, and a linked folder that seems to lose most of its files asks before anything is removed. What the user ticks in the tree is a source scope of folder and document ids. The scope is stored on the chat thread, recorded on each turn and artifact version, and resolved by the server, so chat, Studio and the agent read the same sources however many there are. The agent sees the scope as a per-thread folder of text files that mirrors the tree. Engines reach an original only by its source id. The first phase needs no folders: it fixes the bug that hides every source after the 50th from chat and Studio, and it snapshots the database before any migration runs.

This is one stream of the [file agent proposal](README.md). It answers the open questions of [`../agent/05-sources-folder.md`](../agent/05-sources-folder.md) and keeps its decisions: link, don't copy; watch, then reconcile; re-read only on change; read in place; no writes. Facts were checked against the repo on 3 Oct 2026. Estimates are marked as such.

## Today

**Data**
- Sources are flat `documents` rows (`FILE`, `NOTE`, `ARTIFACT`), with no `folder_id` and no path column ([`modules/documents/models.py`](../../../surfsense_local/backend/modules/documents/models.py), [data model](../../architecture/data-model.md#documents)).
- Bytes sit in id-named directories. Only `original_path()` ([`original_file.py`](../../../surfsense_local/backend/modules/documents/original_file.py)) and Electron's `managedOriginalPath()` ([`document-files.ts`](../../../surfsense_local/electron/src/main/document-files.ts)) turn a document into a path. `original_path()` returns `Path | None`, and its three callers test for `None`: chat's image sources ([`chat/images/sources.py`](../../../surfsense_local/backend/modules/chat/images/sources.py)), the `/original` route ([`documents/router.py`](../../../surfsense_local/backend/modules/documents/router.py)) and ingest's parser ([`parsing.py`](../../../surfsense_local/backend/worker/ingestion/parsing.py)).
- Chunks, indexes, citations and artifact source lists key on ids. Moving a document between folders would touch no chunk.
- `documents` may gain a column only by plain `ALTER TABLE`. A batch rebuild drops the table, which with foreign keys on cascades into every chunk ([`0022_embedding_indexes.py`](../../../surfsense_local/backend/alembic/versions/0022_embedding_indexes.py) docstring). So no new `document_type` or `status` value is safe. Head is `0023`.
- The API applies pending revisions at every start: its lifespan calls `upgrade_to_head(engine)`, which runs `command.upgrade(config, "head")` on `surfsense.db` in the data directory with no copy taken first ([`shared/migrations.py`](../../../surfsense_local/backend/shared/migrations.py), [`api/main.py`](../../../surfsense_local/backend/api/main.py), [`shared/config.py`](../../../surfsense_local/backend/shared/config.py)).
- No released install has run a rebuild of `documents` on a non-empty database. v2.0.0 (18 Sep 2026) is this app's first release; the earlier tags up to v0.0.40 built the hosted product's desktop wrapper from `surfsense_desktop` (`.github/workflows/desktop-release.yml` at v0.0.40), and no `local-v*` tag exists. `0011` is the only revision that rebuilds `documents`, and `0005` rebuilds `workspaces`, from which `documents` cascades. Both first shipped in v2.0.0, so in a released build they have only ever run at a first start, before any document existed. `0012`–`0018` first shipped in v2.0.3 and `0019`–`0023` are unreleased; none of them rebuilds `documents`, and `0021` rebuilds `chat_threads` only in its downgrade. Checked with `git tag --contains` on each revision's first commit.
- Four code paths create `Document` rows: `create_note` and `upload_documents` in [`documents/router.py`](../../../surfsense_local/backend/modules/documents/router.py), `_import_document` in [`migration/service.py`](../../../surfsense_local/backend/modules/migration/service.py) and `create_artifact_job` in [`artifacts/service.py`](../../../surfsense_local/backend/modules/artifacts/service.py). `NoteCreate` has no folder field ([`documents/schemas.py`](../../../surfsense_local/backend/modules/documents/schemas.py)).
- Uploads are deduplicated per workspace: `documents_workspace_dedup_key` is unique on `(workspace_id, dedup_key)`. `upload_documents` returns a twin under `duplicates` and creates nothing; `_import_document` drops a twin silently.
- Cloud import keeps the hosted hierarchy as `document_metadata.folder_path`, "since the local schema has no folder table" (`_import_document`). Empty hosted folders do not travel ([export contract](../../contracts/03-export-bundle.md)).
- A document delete is permanent: its chunks cascade, and their triggers clear both indexes (`delete_document`).
- Every transaction starts with `BEGIN IMMEDIATE`, reads included, and the busy timeout is 5 s ([`shared/db.py`](../../../surfsense_local/backend/shared/db.py)). `transact()` holds the write lock from `BEGIN` to commit ([`api/dependencies.py`](../../../surfsense_local/backend/api/dependencies.py)).

**Selection**
- **Verified bug.** The sources panel requests FILE and NOTE rows with no `limit` (`listDocuments`, [`features/sources/api.ts`](../../../surfsense_local/frontend/src/features/sources/api.ts)). `list_documents` defaults to 50. `includedDocumentIds` covers loaded rows only ([`use-sources.ts`](../../../surfsense_local/frontend/src/features/sources/use-sources.ts)). Chat always sends that list ([`features/chat/api.ts`](../../../surfsense_local/frontend/src/features/chat/api.ts) `streamMessage`), and so does Studio ([`studio-panel.tsx`](../../../surfsense_local/frontend/src/features/studio/studio-panel.tsx)). Above 50 sources, chat and Studio silently never see the older ones.
- The panel's ticks are `includedDocumentIds`. `use-sources.ts` also keeps a second selection, `selectedDocumentIdSet`, with `setDocumentSelected` and `deleteSelected`. [`dashboard-page.tsx`](../../../surfsense_local/frontend/src/features/dashboard/dashboard-page.tsx) passes `deleteSelected` to the panel's `onDeleteSelected`, which the delete dialog calls for a `"selected"` target ([`sources-panel.tsx`](../../../surfsense_local/frontend/src/features/sources/sources-panel.tsx)). Nothing sets that target or calls `setDocumentSelected`, so the multi-delete path is wired but cannot be reached from the panel today.
- No scope is stored. `chat_threads` has no scope column, and a user turn's `chat_messages.content` is JSON `{"text", images?}` ([`modules/chat/models.py`](../../../surfsense_local/backend/modules/chat/models.py)).
- The agent ignores the selection. `agent_turn` reads only text and images ([`agent_threads/turn.py`](../../../surfsense_local/backend/modules/agent/agent_threads/turn.py)). It runs `sync_sources_folder` inside `transact()`, which writes every ready FILE/NOTE flat into one per-workspace `sources/` and reads every body on every turn, all under the write lock (`sources_folder.py`, replaced by per-thread folders in 2c; [agent](../../architecture/agent.md), Known gaps).
- opencode may edit only paths matching `*/agent/outputs/*` ([`opencode_config.py`](../../../surfsense_local/backend/modules/agent/opencode_config.py) `PERMISSION`).
- `create_artifact`'s `source_ids` are checked only against the workspace: `load_selected_sources` filters on `workspace_id` and not on type ([`documents/sources.py`](../../../surfsense_local/backend/modules/documents/sources.py), [`create_artifact.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/create_artifact.py)).

**Search and Studio**
- `retrieve()` filters by an expanding `IN`. The vector leg takes the 20 nearest chunks across every workspace before filtering ([`shared/search.py`](../../../surfsense_local/backend/shared/search.py) `_vector_leg`; [search](../../architecture/search.md#ceiling)). A narrow scope in a big library gets keyword candidates only.
- **Checked for this proposal** against the locked sqlite-vec 0.1.9 in the backend venv: a vec0 KNN query accepts `rowid IN (SELECT …)`, including a `json_each(:ids)` subquery, inside its own CTE, and filters **before** taking `k`. On 100,000 random 384-wide vectors in memory, a scoped KNN took 20–83 ms against 42 ms unscoped (one machine; an estimate for a disk-backed library). Fixing the starvation needs no new vector table.
- `gather()` sends the whole selection if it fits `BUDGET_CHARS = 24_000`, otherwise an even share per document (`_shares`, [`gather.py`](../../../surfsense_local/backend/worker/studio/shared/gather.py)). At 200 documents that is 120 characters each; at 5,000 it would be 4.
- Regenerate re-runs `artifact_metadata.source_document_ids`, which have no foreign key, so deleted sources silently shrink a job, down to none ([`modules/artifacts/service.py`](../../../surfsense_local/backend/modules/artifacts/service.py)).

**Ingest**
- One `ingest` thread runs Docling on the CPU ([ADR 0008](../../adr/0008-two-job-queues.md)). That costs about 3.0 s a born-digital page and 5.2 s a scanned one on a Ryzen 7 5800X ([parser-gpu](../parser-gpu.md#where-the-time-goes-on-a-cpu)).
- huey 3.3.4's `SqliteStorage` dequeues by `order by priority desc, id`, and `task(..., priority=n)` sets the priority per call. Both were checked in the installed package. Neither is used.
- `begin_job` sets the row `processing` unless it was cancelled, and `pipeline.run` skips a deleted row ([`worker/jobs.py`](../../../surfsense_local/backend/worker/jobs.py), [`pipeline.py`](../../../surfsense_local/backend/worker/ingestion/pipeline.py)). Bulk cancel and bulk delete therefore need no per-task revoke. `replace_chunks` swaps a document's chunks only at the end of a successful parse, so the old chunks stay until then.

**Electron and packaging**
- There is no `dialog.showOpenDialog`. A dropped folder is reported as unsupported ([documents](../../architecture/documents.md#upload)).
- The main process already calls the API: `watchImageModel` polls `/llm/image/local/runtime` on the loopback port every 5 s ([`main/index.ts`](../../../surfsense_local/electron/src/main/index.ts)). The sentence in [documents](../../architecture/documents.md#the-original-file) saying it never calls the backend is stale.
- Electron 44 has no `File.path`; `webUtils.getPathForFile` replaced it in Electron 32 ([breaking changes](https://www.electronjs.org/docs/latest/breaking-changes#removed-filepath)).
- [`electron-builder.yml`](../../../surfsense_local/electron/electron-builder.yml) gives macOS an entitlements file and no `extendInfo`, so the app declares no `NS*UsageDescription` strings.
- watchfiles 1.2.0 is locked only because `uvicorn[standard]` pulls it in ([`uv.lock`](../../../surfsense_local/backend/uv.lock), [`pyproject.toml`](../../../surfsense_local/backend/pyproject.toml)). [`api.spec`](../../../surfsense_local/backend/bundling/api.spec) collects uvicorn's submodules and nothing of watchfiles by name.
- On Windows, `time.monotonic()` is `GetTickCount64()` (checked in the backend venv, Python 3.12). Microsoft documents only its unbiased counterpart as excluding sleep ([QueryUnbiasedInterruptTime](https://learn.microsoft.com/en-us/windows/win32/api/realtimeapiset/nf-realtimeapiset-queryunbiasedinterrupttime)), so comparing it with wall time cannot be trusted to show a sleep.

**Precedent.** Hosted SurfSense had folders, with `MAX_FOLDER_DEPTH = 8` and recursive-CTE depth and cycle checks ([`folder_service.py`](https://github.com/MODSetter/SurfSense/blob/archive/hosted-2026-09/surfsense_backend/app/services/folder_service.py)). Its `get_folder_depth` counts a top-level folder as 1 because its CTE starts at `1 AS depth`. It used dynamic folder selection ([`FolderTreeView.tsx`](../../../surfsense_web/components/documents/FolderTreeView.tsx)), default excludes `.git`, `node_modules`, `__pycache__`, `.DS_Store`, `.obsidian` and `.trash`, and a 1.0 s mtime tolerance ([`local_folder_indexer.py`](https://github.com/MODSetter/SurfSense/blob/archive/hosted-2026-09/surfsense_backend/app/tasks/connector_indexers/local_folder_indexer.py)). Its `folder-sync-finalize` deleted every document missing from a listing, with no availability check ([`documents_routes.py`](https://github.com/MODSetter/SurfSense/blob/archive/hosted-2026-09/surfsense_backend/app/routes/documents_routes.py)). That is the failure to avoid.

## Decisions

1. **One model for both kinds of folder:** `source_roots` → `folders` → `documents.folder_id`, plus `linked_files` for linked roots. Each workspace has one managed root, the *Library*, and any number of linked roots. *Reason:* search, citations, Studio and the agent see only document and folder ids. Six places branch on root kind, and no others.
2. **`documents` gains exactly one column, `folder_id`.** It is added by plain `ALTER TABLE`, `ON DELETE SET NULL` as a backstop. "Linked" is not a document type and "missing" or "trashed" is not a status; that state lives in `linked_files` and `folders`. *Reason:* a CHECK change rebuilds `documents` and cascades into chunks.
3. **Every root has a root folder row, and every constructor files a FILE or NOTE.** The four constructors are named with their default below, and a test checks each. As a backstop, `all` also takes a FILE or NOTE whose `folder_id` is `NULL`, and the tree shows it at the top of the Library. A `NULL` folder otherwise means an unfiled artifact. *Reason:* a missed constructor or the `SET NULL` backstop must never make a source vanish from the tree and from every scope without an error.
4. **Sibling names are unique by `name_key`, folded the way the root folds names.** `name_key` is NFC, plus `casefold()` in Python when the root is case-insensitive; the Library always is. Library folders are capped at 8 levels below the root folder, and moves are checked for cycles. A copied tree deeper than 8 is clamped as the migration clamps. A linked root mirrors whatever depth the disk has. *Reason:* SQLite's `NOCASE` folds ASCII only (checked: `'É' = 'é' COLLATE NOCASE` is false), and on a case-sensitive disk `Data/` and `data/` are two folders. The cap and the cycle check are hosted's numbers, for folders the user makes; the disk is not the app's to refuse.
5. **A delete in the Library goes to a Trash.** Trashed folders and documents leave every scope at once, can be restored intact, and are purged after 30 days (an estimate) or when the user empties the Trash. *Reason:* Explorer's Delete sends files to the Recycle Bin and Finder's moves them to the Trash, so users expect a delete to be undoable. Re-reading a library can take hours at 3 s a page, so a slip should cost one click, not a night of ingest.
6. **The source scope is data, not a list:** `{all, folder_ids, excluded_folder_ids, document_ids, excluded_document_ids}`. A ticked folder is dynamic: a file added later is in scope. *Reason:* it removes the 50-row list, the 1,000-id cap, and the need for the client to load every row. Hosted made the same choice.
7. **The source scope is stored per thread, recorded on every user turn and artifact version, and resolved on the server** for every turn and Studio job. *Reason:* the thread holds the current ticks; the per-turn and per-version records hold what each answer and each artifact actually used. A replay for evals ([`05-model-ladder-and-evals.md`](05-model-ladder-and-evals.md)) re-resolves the recorded scope and can tell from the recorded hash whether the sources are still the same. Regenerate re-resolves the version's scope.
8. **`retrieve()` filters inside the vector KNN** with `rowid IN (chunks of the scope)`. *Reason:* this is verified on 0.1.9. It fixes starvation and the cross-workspace ceiling without rebuilding `chunk_vectors`.
9. **Linked roots are read-only mirrors.** Delete in the app means *exclude* or *unlink*, never touching the disk. *Reason:* 05's "No writes". The redline job depends on untouched originals ([08-b2b-artifact-jobs](../../../plans/community-local/seo/08-b2b-artifact-jobs.md)).
10. **An unavailable root never deletes anything, and a mass vanish asks first.** A file missing from a scan becomes `missing`, leaves the scope, keeps its chunks, and is purged only after a scan of an available root confirms it at least 24 h later (an estimate). When most of a root's files vanish at once, nothing is recorded until the user confirms, while new and changed files keep being indexed. *Reason:* unplugged drives, sleeping NAS boxes and sync clients mid-rename all look like deletion for a while, and a real bulk delete must not freeze the root.
11. **SurfSense never reads a cloud placeholder's data, and says so at the root when most of a folder is online-only.** A file that was indexed and later became cloud-only keeps its text. A root whose supported files are mostly placeholders shows one root-level message with the fix, not one message per file. *Reason:* naive scans have downloaded OneDrive and iCloud trees at 53 MB/s ([hermes-agent #97898](https://github.com/NousResearch/hermes-agent/issues/97898)), and reading truncated stubs led one tool to write them back over users' files ([claude-code #62140](https://github.com/anthropics/claude-code/issues/62140)). Sync clients free space on their own, so a library must not shrink when they do. Organizations move Documents and Desktop into OneDrive with Known Folder Move ([Microsoft](https://learn.microsoft.com/en-us/sharepoint/redirect-known-folders)), so the folder a business user is most likely to link may be mostly online-only, and linking it would index little without saying why.
12. **The watcher runs in the API process, reconcile in its thread pool, and only parsing goes to the ingest queue,** under huey priorities. *Reason:* the API owns the database and the reconcile code, so one watcher stack in one language covers the desktop and the Docker stack ([ADR 0035](../../adr/0035-docker-compose-runs-the-desktop-stack.md)), which runs no Electron. Huey tasks are short-lived, and a reconcile queued behind hours of Docling would leave the tree hours stale.
13. **Identical bytes at two paths are two documents,** in linked roots and Library folders alike. Library uploads are deduplicated per folder, not per workspace. Reusing one parse for the second copy waits until duplicates are measured to cost real Docling time. *Reason:* the tree must match what the user put in it; a copied folder with holes where a file already sat elsewhere is wrong. Per-folder dedup keeps re-copying a folder idempotent.
14. **The agent gets a working folder per thread.** Its `sources/` holds only the thread's scope, flat at first and mirroring the tree once folders exist. *Reason:* nothing else scopes opencode's `read`, `grep` and `glob`. It also gives each tool registration a thread, which MCP calls lack ([`../agent/02-tools.md`](../agent/02-tools.md)).
15. **Engines get originals server-side, by source id, in two steps.** `resolve_original` reads rows inside a transaction; `copy_original` copies and hashes in the worker with no session open. No original enters the working folder under its own name, and no tool takes a path to one. *Reason:* containment, placeholder and freshness checks live in one resolver, a 500 MB hash never holds the write lock, and a linked repository's `AGENTS.md` cannot reach opencode's instruction walk.
16. **An artifact is a source only when the user files it in a folder or ticks it, and never for itself.** Unfiled artifacts stay out of `all` and every folder scope. An artifact's own document is excluded when its own version's sources are resolved. Filing, or a tick, is the only opt-in; there is no `include_outputs` flag, and [`03-editable-artifacts.md`](03-editable-artifacts.md) adds none. *Reason:* [ADR 0003](../../adr/0003-artifacts-as-documents.md) makes artifacts pinnable "because it is a document" and rejects hidden system folders. Filing is one explicit act with one meaning in the tree; a second flag would make a ticked folder use something other than what it shows. Self-exclusion stops a regenerate grounding on its own previous output.
17. **Artifacts cannot be filed into a linked root.** *Reason:* everything under it is a file on disk. Saving a copy to disk is an export owned by 03.
18. **A folder can carry a role.** `folders.role` is a nullable text holding one of [06](06-product-shape.md)'s `Role` values (`evidence`, `target`, `playbook`, `library`). A job's setup or the folder's menu sets it, and it is kept through renames and moves. *Reason:* 06 has one kind of workspace, with jobs as templates, and keeps roles on folders so that a rename does not erase their meaning. A guided job resolves "evidence" or "target" to folder ids on the server with no model call. On a new table the column costs nothing.
19. **The database is snapshotted before any migration.** Before `upgrade_to_head` applies a pending revision to an existing database, it writes a `VACUUM INTO` copy to `<data>/backups/<from>-<to>.db` and keeps the last two. *Reason:* phase 1 and [03](03-editable-artifacts.md)'s phase 1 rewrite users' only database, with a folder backfill, an index swap and a batch rebuild of `artifact_files`. Count checks in tests do not protect a user whose upgrade fails halfway on their own data.

## Design

### Data model

```text
source_roots   id, workspace_id → workspaces CASCADE,
               kind CHECK in ('managed','linked'), name (1–100), name_key,
               disk_path NULL            -- resolved absolute path; NULL for managed
               volume_identity NULL      -- "st_dev:st_ino" of disk_path when linked
               case_sensitive NULL, fs_type NULL,
               grant_id NULL UNIQUE      -- the folder pick that allowed this link
               state CHECK in ('ready','scanning','unavailable','paused','unlinking'),
               unavailable_reason NULL   -- not_found, volume_changed, permission_denied, list_failed
               watch_mode CHECK in ('native','poll') NULL, ignore JSON NULL,
               held_missing NULL, held_since NULL      -- a mass vanish awaiting the user
               scan_notes JSON NULL                    -- skipped entries by reason, with examples
               reconcile_requested_at NULL             -- set by any process; drained by the API
               last_scan_at, last_available_at, created_at, updated_at
               UNIQUE(workspace_id, name_key); partial UNIQUE(workspace_id) WHERE kind='managed'

folders        id, workspace_id → workspaces CASCADE, root_id → source_roots CASCADE,
               parent_id → folders CASCADE NULL      -- NULL only for a root's root folder
               name (1–255), name_key, disk_name NULL, role NULL,
               state CHECK in ('ready','placeholder','trashed','deleting'),
               trash_kind CHECK in ('folder','documents') NULL, trashed_at NULL,
               created_at, updated_at
               partial UNIQUE(parent_id, name_key)
                   WHERE parent_id IS NOT NULL AND state IN ('ready','placeholder')
               partial UNIQUE(root_id) WHERE parent_id IS NULL

documents      + folder_id REFERENCES folders(id) ON DELETE SET NULL   -- plain ALTER
               + INDEX documents_folder(folder_id)
               documents_workspace_dedup_key (workspace_id, dedup_key) becomes
               documents_folder_dedup_key (workspace_id, folder_id, dedup_key),
               same partial WHERE dedup_key IS NOT NULL               -- DROP and CREATE INDEX

linked_files   id, root_id → source_roots CASCADE, folder_id → folders CASCADE,
               relative_path              -- POSIX separators, names as the OS returned them
               path_key                   -- NFC; case-folded when the root is case-insensitive
               size, mtime_ns, file_identity NULL (text), content_sha256 NULL,
               state CHECK in ('queued','indexed','stale','unsupported','placeholder',
                               'too_large','missing','failed'),
               reason NULL                -- unsupported: suffix, legacy_format, name_clash
               indexed_at NULL            -- when its document last became ready
               missing_since NULL, document_id → documents SET NULL, last_seen_scan
               UNIQUE(root_id, path_key); INDEX(document_id); INDEX(content_sha256)

blob_tombstones  id, workspace_id → workspaces CASCADE,
                 kind CHECK in ('document','artifact'), owner_id, created_at

document_text_digests  document_id PRIMARY KEY → documents CASCADE, sha256   -- phase 3a

chat_threads   + source_scope JSON NULL                                  -- plain ALTER
```

- The root folder is depth 0, so Library folders go from 1 to 8. `modules/folders/tree.py` ports hosted's `get_folder_depth`, `get_subtree_max_depth`, `check_no_circular_reference` and `get_folder_subtree_ids` as synchronous CTEs. Hosted's depth CTE starts at `1 AS depth` for a folder whose parent is `NULL`; here that row is the root folder, so the port starts the root folder at 0. Without that, every user folder would be one level deeper than intended and depth 8 would fail.
- `modules/folders/names.py::name_key(name, case_sensitive)` computes the key.
- There is no ordering column. Folders sort first, then by `name_key`. Hosted's fractional `position` would need drag-to-reorder, which file managers lack.
- `role` holds one of 06's `Role` values, validated in code with no CHECK, or `NULL`. A linked root's root folder may carry one too; it is SurfSense's record, never written to disk.
- `documents.content_hash` is declared and never written today. It becomes the SHA-256 of a FILE's original bytes, which equals `dedup_key` for managed files. `copy_original` checks freshness against it, and against `dedup_key` for a managed file whose `content_hash` phase 1 has not filled yet.
- Swapping the dedup index is a plain `DROP INDEX` and `CREATE UNIQUE INDEX`, with no table rebuild. It is weaker than today's index, so no existing row can violate it.

**Migrations** follow [ADR 0005](../../adr/0005-hand-written-migrations.md). Numbers are assigned at merge.

| Revision | Phase | Does |
|---|---|---|
| `thread_scope` | 0 | `ALTER TABLE chat_threads ADD COLUMN source_scope JSON` (plain: `chat_messages` cascades from it) |
| `source_roots_and_folders` | 1 | Creates `source_roots`, `folders` and `blob_tombstones`, and a "Library" root with its root folder per workspace. Adds `documents.folder_id` inline, as `0022` did; inline `REFERENCES … ON DELETE SET NULL` on an added column was checked on SQLite 3.45 with foreign keys on. Creates `documents_folder`. Files every FILE and NOTE, builds chains from `folder_path` (below), copies `dedup_key` into `content_hash`, then swaps the dedup index. Idempotent |
| `linked_files` | 4a | Creates the table |
| `document_text_digests` | 3a | Creates the table and fills it from `content` for every ready FILE and NOTE, in batches of 500 |

The backfill logic is written out in each revision, not imported, as `0022` does with bge's spec. The folder revision's test counts chunks before and after, to catch a cascade.

**Snapshot before migrating** (phase 0). `shared/migrations.py::upgrade_to_head(engine, *, backups_dir: Path | None = None)` gains one step before `command.upgrade`:
1. It reads the current revision with `MigrationContext`, as `is_migrated` does, and the head from `ScriptDirectory`. With nothing pending, or on a new database whose revision is `None`, it writes nothing.
2. Otherwise it runs `VACUUM INTO` to `<backups_dir>/<from>-<to>.db.partial` on a connection outside any transaction, since `VACUUM` cannot run inside one and every session from [`shared/db.py`](../../../surfsense_local/backend/shared/db.py) opens with `BEGIN IMMEDIATE`. On success it renames the file to `<from>-<to>.db`, for example `0023-0025.db`.
3. It deletes all but the two newest snapshots.
4. If the snapshot fails, for example on a full disk, no revision runs and the API start fails with the reason. The app never migrates without a copy to return to.

- The API lifespan passes `get_storage_settings().data_dir / "backups"`. Tests and the retrieval eval pass nothing and take no snapshot.
- `VACUUM INTO` should carry the vec0 and FTS5 tables as their declarations plus shadow-table rows, with no module loaded. The phase 0 test confirms it by opening the snapshot through the app's engine and counting chunks and vectors.
- Restoring: quit SurfSense, replace `surfsense.db` with the snapshot, and start the app. The previous release opens it as it was; the failed release runs the migration again. [data model](../../architecture/data-model.md) and a how-to page in the user docs state these steps.

### Existing documents, imported folder paths, and who sets `folder_id`

- Every FILE and NOTE goes to the top of the Library. Artifacts stay unfiled. Nothing on disk moves.
- A non-empty `folder_path` becomes a chain of folders under the Library root, and the document goes in the deepest one.
  - Segments differing only in case or normalization merge into one folder. Hosted Postgres allowed both, and merging loses no document.
  - Segments past depth 8 are joined with " / " into the eighth.
  - `folder_path` stays in the metadata as provenance.
- Two hosted documents with the same bytes in two hosted folders now both arrive: the import's twin check becomes per folder.
- `modules/source_roots/managed_root.py::ensure_managed_root()` runs from `create_workspace`, `ensure_default_workspace` and `find_or_create_workspaces`, and lazily in every folder route.

Every code path that creates a `Document` sets `folder_id`:

| Constructor | `folder_id` |
|---|---|
| `documents/router.py::create_note` | `NoteCreate.folder_id`, new and optional; the Library root folder when absent |
| `documents/router.py::upload_documents` | the `folder_id` form field, or the chain built from `relative_paths`; the Library root folder when absent |
| `migration/service.py::_import_document` | `modules/folders/ensure_path.py::ensure_folder_path(session, root_folder, segments)` of its `folder_path` |
| `artifacts/service.py::create_artifact_job`, and 03's sweep, revised copies and Save as copy | `NULL`: an artifact starts unfiled |
| `source_roots/scan/reconcile.py` | the mirrored folder |

The folder Known gaps in [documents](../../architecture/documents.md#known-gaps) and [data model](../../architecture/data-model.md#known-gaps) go away.

### Routes

These are under `/workspaces/{workspace_id}` unless noted. Code lives in `modules/folders/` (`models.py`, `names.py`, `tree.py`, `ensure_path.py`, `trash.py`, `purge.py`, `router.py`, `schemas.py`) and `modules/source_roots/` (`models.py`, `managed_root.py`, `link_root.py`, `router.py`, `schemas.py`, `scan/`).

| Method | Path | Does |
|---|---|---|
| `GET` | `/source-roots` | roots with root folder id, state, reason, counts by state, scan notes |
| `POST` | `/source-roots` | link: `{grant_id, name?}`; `201`, state `scanning` |
| `PATCH` | `/source-roots/{id}` | rename; add or remove exclusions; pause or resume |
| `POST` | `/source-roots/{id}/rescan` | reconcile now |
| `POST` | `/source-roots/{id}/confirm-removal` | record a held mass vanish as missing |
| `DELETE` | `/source-roots/{id}` | unlink, which never touches the disk; `409` on the managed root |
| `GET` | `/folders/{id}/children?cursor=&limit=` | one level (limit up to 500): folders with status rollups, documents, and linked files without a document |
| `GET` | `/folders/search?q=&root_id=&limit=` | the tree's name filter: folders, documents and linked files whose name contains `q` (folded as `name_key`), each with its folder chain so the tree can expand to it; limit up to 200 |
| `POST` | `/folders` | `{parent_id, name, role?}` |
| `PATCH` | `/folders/{id}` | rename, move (cycle and depth checks) and/or set `role` |
| `POST` | `/folders/{id}/cancel` | stop all queued or running ingest in the subtree |
| `POST` | `/documents/move` | `{document_ids ≤ 1,000, folder_id}`; a document whose bytes are already in the target folder is skipped and reported |
| `POST` | `/documents/upload` | gains `folder_id` and `relative_paths`: a JSON list, index for index with `files`, as in hosted's `folder_upload` |
| `GET` | `/documents/{id}/location` | for Electron: `{kind, root_path?, relative_path?}`, or `409` with the reason the original cannot be opened |
| `POST` | `/trash` | `{folder_ids, document_ids}`, each at most 1,000: move to the Trash |
| `GET` | `/trash` | trashed entries with counts, size and purge date |
| `POST` | `/trash/{folder_id}/restore` | restore one entry |
| `DELETE` | `/trash/{folder_id}`, `/trash` | purge one entry now, or empty the Trash |
| `PUT` | `/chat/threads/{id}/source-scope` | store a source scope; answers with it and its counts |

- Any write under a linked root answers `409`: "This folder is on disk at {path}. Change it in your file manager." Setting `role` on a linked root's folders is the exception: it changes only SurfSense's row.
- A rollup is one recursive CTE over the subtree joined on `documents_folder`. It runs only for expanded folders.
- `EventKind` ([`modules/events/schemas.py`](../../../surfsense_local/backend/modules/events/schemas.py)) gains `FOLDERS` and `SOURCE_ROOTS`. Events keep carrying `ids`, so the tree refreshes only the rows named ([ADR 0009](../../adr/0009-freshness-by-invalidation.md)).
- `DELETE /documents/{id}` keeps its meaning, permanent with its `409` while processing, for plugins and existing tests. The tree no longer calls it.

### Trash and purge

**Moving to the Trash** (`trash.py`) is one short transaction:
- A folder gets `state='trashed'`, `trash_kind='folder'` and `trashed_at`, where it is. Its subtree leaves every scope and the tree at once.
- Documents deleted on their own are moved into one wrapper folder per folder they came from: `state='trashed'`, `trash_kind='documents'`, named "Deleted {date} {time}", a child of that folder.
- One `UPDATE` cancels the subtree's pending and processing rows, so queued jobs no-op at `begin_job`.
- Filed artifacts go with their folder, and the dialog counts them. Each passes 03's `versions.guard_delete` first, so a running edit answers `409` "Stop the running edit first" and a pending one is cancelled. Unfiled artifacts keep Studio's own delete (03).

**The Trash** is the last row of the Library: "Trash · 3 items · 1.2 GB · emptied after 30 days". It lists only top entries, each with Restore and Delete now; Empty Trash purges all. The delete itself shows no dialog, only a toast with Undo, which calls Restore.

**Restore** sets the entry back to `ready`. A wrapper's documents move back to its parent and the wrapper goes. A name taken in the meantime gets " (restored)". A document whose bytes are now in the target folder stays in the wrapper and is reported. Documents the trash cancelled are re-queued at `PRIORITY_BULK`; nothing records who cancelled them, so a document the user had cancelled is re-queued too.

**Purging** (`purge.py`) serves Delete now, Empty Trash, and entries older than 30 days, which an hourly lifespan task and the API start check:
1. One short transaction sets the subtree's folders to `deleting`. They are already out of scope.
2. Documents go in batches of at most 500, each in its own transaction, so no batch holds SQLite's write lock past the 5 s busy timeout. Each batch writes a `blob_tombstones` row for every `documents/<id>/` and filed `artifacts/<id>/` directory it removes. Chunks cascade, and their triggers clear both indexes.
3. After each commit the batch's directories are removed and their tombstones deleted. A directory that cannot go yet, for example because Docling holds a file open on Windows, keeps its tombstone.
4. Folders go deepest first, after their documents. One event per batch carries the ids.

A Docling job still parsing finds its row gone and stops (`pipeline.run`). A new lifespan step, `modules/documents/orphan_directories.py::sweep_tombstones`, removes at the next start only the directories a tombstone names. A directory with no row and no tombstone is left alone and logged once. A restored backup, a failed migration or a cascade loss therefore never deletes the originals, which are the only copies the app holds.

Unlinking a root runs steps 2 to 4 without tombstones, since a linked root has no bytes in the data directory. Documents always go before their folders, so the `SET NULL` backstop does not fire.

### Source scope

```python
class SourceScope(BaseModel):  # modules/source_scope/schemas.py; each list max_length=1000
    all: bool = False
    folder_ids: list[PositiveInt] = []
    excluded_folder_ids: list[PositiveInt] = []
    document_ids: list[PositiveInt] = []
    excluded_document_ids: list[PositiveInt] = []
```

`modules/source_scope/resolve.py::resolve_scope(session, workspace_id, scope, *, exclude_document_ids=()) -> ResolvedScope` is one recursive-CTE query:

```text
base     = (all ? documents of type FILE or NOTE, or with folder_id NOT NULL : ∅)
           ∪ subtree(folder_ids) − subtree(excluded_folder_ids)
           ∪ document_ids − excluded_document_ids
in scope = base − subtree(folders 'trashed' or 'deleting') − exclude_document_ids
           ∩ (status 'ready' ∪ linked with indexed_at set)
           − linked 'missing' − roots 'unlinking'
```

- Adding `document_ids` back after the folder exclusions lets one file be ticked inside an unticked subfolder.
- A linked document whose file changed keeps its old chunks until `replace_chunks` swaps them, so it stays in scope while it is `pending` or `processing`, and after a failed re-read, as long as it was ready once (`indexed_at`). Its row says so.
- Ids that no longer exist (purged, unlinked, deleted by another route) are dropped and counted as `removed`; the stored scope is pruned at its next write. Ids in the Trash are counted as `in_trash` and kept, so a restore brings the ticks back. Only an id that exists in another workspace answers `422`. A source that is not ready is counted, not refused.
- `exclude_document_ids` carries the artifact's own document when its own version's sources are resolved.
- `ResolvedScope` carries the ids in tree order and the counts `{ready, indexing, failed, cloud_only, missing, in_trash, removed}`. The UI can then say "212 sources in 9 folders; 30 still indexing".
- A thread with no stored scope means `{all: true}`, which is what every thread created before this change gets.
- No file is read while the resolve transaction is open.

**Wire**
- `MessageCreate`, `StudioJobCreate` and `ThreadCreate` gain an optional `source_scope`. The name keeps it apart from 03's `artifact_versions.scope` and `MessageCreate.edit.scope`, which select a passage inside an artifact.
- On a turn, a present `source_scope` is validated, stored on the thread and used, in one `transact`. Ticking a box and pressing Enter therefore cannot race.
- `PUT /source-scope` stores ticks made between turns.
- Each user turn's `chat_messages.content` gains `source_scope` and `resolved: {count, ids_sha256}`, the hash of the sorted resolved ids. The column is JSON, so this needs no migration. A 20,000-id list per turn would not be worth its size; the hash tells a replay whether it ran on the same sources.
- `document_ids` keeps today's meaning and its `409`s for one release and for plugins. The frontend stops sending it.
- The panel shows the open thread's scope. A new chat holds a draft, remembered per workspace in `localStorage` (`surfsense:source-scope:v1`, failures ignored) as the next thread's default. Studio uses the open thread's scope, as it shares the selection today.

**Retrieval.** `retrieve()` gains `scope: ResolvedScope | None`, and `document_ids` stays as is. The ids are bound once as JSON:

```sql
-- keyword leg
AND c.document_id IN (SELECT value FROM json_each(:scope_ids))
-- vector leg, still in its own CTE
WITH knn AS (SELECT rowid, distance FROM chunk_vectors
             WHERE embedding MATCH :vector AND k = :k
               AND rowid IN (SELECT c.id FROM chunks c
                             WHERE c.document_id IN (SELECT value FROM json_each(:scope_ids))))
```

- Even with no scope, the vector leg is prefiltered by workspace. The [search](../../architecture/search.md#ceiling) "Ceiling" retires.
- `search_sources` and `gather()` use the same path.

**Studio at folder scale.**
- `gather(session, scope, query, budget_chars)` takes its budget from the selected model's capability profile in [05](05-model-ladder-and-evals.md), defaulting to today's 24,000. This stream owns the change; 05 decides the numbers.
- It gains a third regime. When the even share would fall below `MIN_SHARE_CHARS = 1,500` (an estimate, about one 480-token chunk), it takes the scope's best passages from one `retrieve(top_k=budget_chars // 1,500)` instead of cutting every document. With no prompt, the query is the format's new `Format.default_focus`.
- The job records `source_scope`, the resolved source ids and `grounded_document_ids`, so the panel can say "Grounded on 14 of 212 sources". Until 03's phase 1 they go in `artifact_metadata`; after it, in the version's `inputs` as `inputs.source_scope`, 03's `inputs.sources` and `inputs.grounded_document_ids`. 03's backfill copies `artifact_metadata` into v1's `inputs`, so nothing is lost between the two.
- **Regenerate** with no body re-resolves the recorded `source_scope`, minus the artifact itself, and records the new list: a ticked folder is dynamic, so files added since are used. An artifact made before this change has no `source_scope`, so its recorded ids replay as today. With a body, 03's `document_ids` or a `source_scope` replace the inputs. When nothing remains it answers `409`: "None of this artifact's sources are left."
- Map-reduce over a whole folder is a model-ladder question for [`03`](03-editable-artifacts.md) and [`05`](05-model-ladder-and-evals.md).

### The tree in the sources panel

The flat list in [`sources-panel.tsx`](../../../surfsense_local/frontend/src/features/sources/sources-panel.tsx) (751 lines) gives way to a `features/sources/tree/` slice:

| File | Owns |
|---|---|
| `use-source-tree.ts` | loading levels and applying events |
| `source-tree.tsx` | the windowed list |
| `folder-row.tsx`, `document-row.tsx`, `linked-file-row.tsx` | one kind of row each |
| `root-header.tsx` | a root's state, reason, scan notes and actions |
| `trash-row.tsx` | the Trash entry and its list |
| `tree-drag.ts` | drag and drop |
| `scope-state.ts` | tri-state ticks derived from the source scope |
| `expanded-folders.ts` | expansion kept per workspace |

- **Rendering.** Rows are windowed with `@tanstack/react-virtual` (MIT, the one new frontend dependency, [`04-runtime-and-packs.md`](04-runtime-and-packs.md)). Expansion is kept per workspace, as hosted did. Children load per level, and an event refetches only the parents of the ids it names. The Library's top level also lists any FILE or NOTE whose folder is `NULL`.
- **Name filter.** A filter box above the tree calls `GET /folders/search` and shows matches with their folder chain expanded, so a file in a 20,000-file linked root can be found without opening folders.
- **Actions.** Library folders offer New folder, Rename, Move to… (a picker) and Delete, which moves to the Trash. Rows move by native HTML5 drag and drop, which needs no library since there is no reordering. Multi-select is Shift and Ctrl click, and Move to Trash acts on the whole selection. That replaces today's unreachable multi-delete path: `selectedDocumentIdSet`, `setDocumentSelected` and `deleteSelected` in `use-sources.ts`, the panel's `onDeleteSelected` prop wired from `dashboard-page.tsx`, and the dialog's `"selected"` branch go together. No test exercises that path today; the harness in `source-upload.test.tsx` that wires `deleteSelected` moves to the tree's `tree/source-tree.test.tsx`, which covers selecting three rows and moving them to the Trash. **Add** offers Files, Folder (copy into Library) and Link a folder on disk.
- **Ticks.** Checkboxes are tri-state, derived from the stored scope rather than from loaded rows, so a collapsed folder of 5,000 files ticks in one click. `SourceCount` ([`chat-composer.tsx`](../../../surfsense_local/frontend/src/features/chat/chat-composer.tsx)) shows the server's counts.

| Row | State | Shows | Tickable |
|---|---|---|---|
| Root | scanning / ready / poll | "Scanning… 1,240 found" / "Watching" / "Checking every 5 min" | yes |
| Root | unavailable | "Drive not connected, last seen {date}", or for `permission_denied` "macOS has not allowed SurfSense to read this folder" with Open Privacy Settings. Its text stays searchable | yes |
| Root | held mass vanish | "612 files are gone from Research. Remove them from SurfSense?" with Remove and Keep | yes |
| Root | paused | "Indexing paused, 312 waiting" | yes |
| Root | mostly online-only | on Windows, "{N} of {M} files are online-only. In OneDrive, choose 'Always keep on this device' for this folder."; elsewhere, "{N} of {M} files are online-only. Make this folder available offline in your sync app." | yes |
| Root | unreadable files | "14 files can't be read yet (.doc, .xls, .ppt)" until 04's RT6; then "14 files need Office support" while it is not installed | – |
| Root | scan notes | "3 files skipped: name is not valid text" | – |
| Folder | rollup | "Ready 812 / 1,240", failed and cloud-only counts | yes |
| Folder | placeholder | "Cloud folder, not downloaded" | no |
| Document | queued, processing, failed | as today, with Retry | when ready |
| Linked document | stale | "Changed on disk, re-reading". The old text is still used | yes |
| Linked document | re-read failed | "Couldn't re-read; using text from {date}", with Retry | yes |
| Linked document | dehydrated | "Cloud-only now; text from {date}" | yes |
| Linked document | missing | struck through, "Not found since {date}". Kept 24 h in case it returns, not used in answers | no |
| Linked file | unsupported / legacy format / placeholder / too large | "Can't read .xyz files" / "Can't read .xls files yet", and after RT6 "Needs Office support" / "Cloud-only: make it available offline in OneDrive" / "Over 500 MB" | no |
| Trash | entries | "Trash · 3 items · 1.2 GB · emptied after 30 days" | no |

The preview still replaces the sidebar ([documents](../../architecture/documents.md#the-original-file)). With a tree, losing your place costs more, so [`../source-preview.md`](../source-preview.md)'s second rail joins phase 2.

### Adding a whole folder (copy)

- **Picker.** `<input type="file" webkitdirectory>` gives `File`s with `webkitRelativePath` ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/webkitdirectory)), with no Electron change.
- **Drop.** `use-file-drop.ts` walks `webkitGetAsEntry()` recursively ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/DataTransferItem/webkitGetAsEntry)) instead of rejecting the folder. A drop on a folder row targets it.
- **Upload.** The client filters by suffix and the default ignores, and sets aside any file over 500 MB from `File.size` before batching, listing it as rejected ("Over 500 MB"). A file over the limit would otherwise fail its whole request with `413` ([documents](../../architecture/documents.md#upload)). It uploads batches of at most 50 files or 200 MB (an estimate). A request with more than 20 files enqueues at `PRIORITY_BULK`.
- **Folders.** The server builds the chains with `ensure_folder_path`. Segments past depth 8 are joined into the eighth, as the migration does, so a deep tree arrives whole rather than half refused.
- **Duplicates.** The dedup check is per folder. A file whose bytes are elsewhere in the Library is created in the new folder too. A file already in that same folder comes back under `duplicates`, so copying a folder again adds only what is new. The dialog says "12 files were already in Research/2024".

### Linking a folder on disk

**Choosing and granting**
- `electron/src/main/linked-roots.ts` adds `sources:pick-folder` (`dialog.showOpenDialog`, `openDirectory`; [dialog](https://www.electronjs.org/docs/latest/api/dialog)).
- The preload adds `surfsense.linkDroppedFolder(file)`, which calls `webUtils.getPathForFile` in the preload's context. A `File` built by page script has no path, so a renderer cannot forge one.
- Main appends `{id, path, picked_at}` with a random `id` to `<data>/linked-root-grants.json` (atomic write), prunes entries older than 10 minutes, and returns the `id`. The API finds the file through `SURFSENSE_LOCAL_LINKED_ROOT_GRANTS` from `pythonEnv()`, the same file hand-off that `opencode.json` uses.
- `POST /source-roots` takes the `grant_id`, not a path. The API links exactly the granted path, never a path below it. It refuses an unknown grant, one older than 10 minutes, and one a live root already used (`source_roots.grant_id` is unique). Unlinking needs no revocation: re-linking later needs a new pick. A source whose HTML ran script in the renderer therefore cannot make the API index `~/.ssh`.
- The Docker stack ([ADR 0035](../../adr/0035-docker-compose-runs-the-desktop-stack.md)) points the variable at a file listing its mount points as standing grants, `{id, path, standing: true}`, with no expiry. Roots under them default to `watch_mode='poll'`, since bind mounts often deliver no inotify events.

**macOS privacy.** Documents, Desktop, Downloads, iCloud Drive and removable and network volumes are protected by macOS's privacy controls, and they are the folders most likely to be linked. The scan runs in the API sidecar, a child process of the app.
- `electron-builder.yml` gains `mac.extendInfo` with `NSDocumentsFolderUsageDescription`, `NSDesktopFolderUsageDescription`, `NSDownloadsFolderUsageDescription`, `NSRemovableVolumesUsageDescription` and `NSNetworkVolumesUsageDescription`: "SurfSense reads the folders you link so it can answer from them. It never changes them." ([Apple](https://developer.apple.com/documentation/bundleresources/information-property-list/nsdocumentsfolderusagedescription)).
- `availability.py` maps `EPERM` or `EACCES` on listing the root to `unavailable_reason='permission_denied'`. The header links to Privacy & Security › Files and Folders (`x-apple.systempreferences:com.apple.preference.security?Privacy_FilesAndFolders`). The root is only unavailable, so nothing is deleted.
- Whether macOS attributes the sidecar's access to SurfSense's bundle, so that the prompt names SurfSense, is checked by phase 4a's packaged-app test (Open questions).

**Validation** (`link_root.py`). The path must be absolute and an existing directory. These are refused:
- a filesystem root;
- a path inside, or containing, the data directory, so `rmtree(workspace_dir)` can never reach user files;
- an already linked path, or one that overlaps a linked root.

What is stored with the root:
- `disk_path`, resolved;
- `volume_identity`;
- `case_sensitive`, from `pathconf(_PC_CASE_SENSITIVE)` on macOS, assumed false on Windows and true on Linux. Nothing is written to probe it;
- `fs_type`, from `statfs` on macOS and `/proc/self/mountinfo` on Linux.

A root on a FUSE file system (`fuse.*`, for example `fuse.rclone`) asks before linking: "SurfSense cannot tell which files in this folder are downloaded. Reading one may download it." It links in `poll` mode.

**Opening a linked original.** `documents:open` and `documents:reveal` in [`document-files.ts`](../../../surfsense_local/electron/src/main/document-files.ts) take `(workspaceId, documentId)` only; the renderer never supplies a path. Main asks the API on the loopback port, as `watchImageModel` already does, through `GET /documents/{id}/location`. For a managed file it applies today's id rule. For a linked file it joins `root_path` and `relative_path`, resolves the result, checks it is still inside `root_path`, and reveals rather than opens any file that is not a supported source type, so a renderer cannot launch an executable.

**Scan** (`modules/source_roots/scan/`: `walk.py`, `ignore_rules.py`, `placeholders.py`, `availability.py`, `long_paths.py`, `reconcile.py`, `purge_missing.py`)
- `os.scandir` runs with `follow_symlinks=False`. Symlinks, junctions (`DirEntry.is_junction()`) and mount points are ignored with the reason "link".
- Default ignores:
  - hidden entries: dot-names, and Windows `HIDDEN` and `SYSTEM`;
  - hosted's six defaults;
  - `~$*`, `.~lock.*#` and `*.tmp`;
  - `Thumbs.db`, `desktop.ini`, `$RECYCLE.BIN` and `System Volume Information`.
- User exclusions are `fnmatch` patterns. `pathspec` would come only if the app reads users' own ignore files.
- Placeholders are detected before anything is opened (table below). File identity comes from `os.stat()`, not `DirEntry.stat()`, which zeroes it on Windows (05).
- Over 500 MB is `too_large`. A suffix nothing parses is `unsupported` with reason `suffix`. Legacy `.doc`, `.xls`, `.ppt`, `.rtf` and `.odt` are `unsupported` with reason `legacy_format`, stay unreadable until [04](04-runtime-and-packs.md)'s RT6, and use 04's wording in the tree. The root header counts them. Once RT6 has shipped and Office support is installed, they are queued and ingest converts them through it first.
- Email files (`.msg`, `.eml`) are not read in v1. They are `unsupported` with reason `suffix`, counted like any other, and left to a follow-up proposal.
- `relative_path` keeps the OS's names so the file can be reopened exactly. `path_key` is NFC, plus `casefold()` on case-insensitive roots. Folder `name_key`s fold the same way, so `Data/` and `data/` on a case-sensitive root are two folders.
- On POSIX, a name that is not valid UTF-8 comes back from Python with surrogate escapes, which a SQLite `TEXT` column cannot hold. Such files and directories get no row; they are counted in `scan_notes` ("name is not valid text"), with up to 20 examples shown with replacement characters.
- Two sibling directories whose names map to one key (NFC and NFD forms on Linux): the second is skipped and counted in `scan_notes` ("name clash"). Two such files: the second is `unsupported` with reason `name_clash`.
- Files are stat-ed and hashed outside any transaction. Rows are then written in transactions of at most 500 (an estimate), so chat and ingest never hit the 5 s busy timeout.

**First scan**
1. One walk creates `folders` and `linked_files` rows, with no hashing.
2. Each supported file gets a pending FILE document: `dedup_key` `NULL`, the file name as its title, and the mirrored folder.
3. Ingest is enqueued after each batch commits, at `PRIORITY_BULK`, cheapest first: text suffixes (no Docling), then by size.
4. The tree is browsable once the walk ends, and chat works on what is ready.
5. Above 20,000 supported files (an estimate), linking asks first, showing a time estimate from 3 s a page.
6. When more than 20% (an estimate) of the root's supported files are placeholders after the walk, the link dialog says so before it closes: "Most of this folder is online-only. SurfSense reads only files that are on this device and never downloads them. In OneDrive, choose 'Always keep on this device' for this folder, and SurfSense indexes each file as it arrives." The root header keeps the "{N} of {M} files are online-only" line while the share stays above the threshold. The Link a folder how-to page carries the same advice. The menu label is OneDrive's own ([Microsoft](https://support.microsoft.com/en-us/office/save-disk-space-with-onedrive-files-on-demand-for-windows-0e6860d3-d9f3-4971-b321-7092438fb38e)).
7. When the first scan's queue drains, the renderer shows an OS notification (`Notification`) if the window is not focused: "Research is ready: 1,240 files indexed."

**Reading an original.** `modules/documents/original_bytes.py` holds both steps:
- `resolve_original(session, document) -> OriginalRef` reads rows only and runs inside the caller's transaction. For a managed file it is today's `original_path()`. For a linked file, `modules/source_roots/linked_original.py::linked_original_path` joins the root and the relative path through `long_paths.extended()` (`\\?\` or `\\?\UNC\` on Windows), checks containment after `resolve()`, and re-checks the placeholder flags with `lstat`, which opens nothing. Anything wrong raises `OriginalUnavailable(reason)`. `OriginalRef` carries the path, `content_hash`, size and `mtime_ns`. The document's root comes through its folder relationship, which every caller's session-bound document can load.
- `copy_original(ref, destination) -> Path` does the file work with no session open: it copies, hashing as it reads, into the destination. If the bytes no longer match `content_hash`, it deletes the copy and raises `OriginalChanged`, whose message is "changed on disk since it was read; re-reading". The caller then sets `source_roots.reconcile_requested_at` in one short transaction. Any process can do that, and the API's tick drains it.
- `original_path()` stays as the managed-only helper. Its three callers move to `resolve_original`:

| Caller | On `OriginalUnavailable` |
|---|---|
| `chat/images/sources.py` | skips the image, as it skips a missing file today; it sends the current bytes and does no hash check, since the image is shown as it is now |
| `documents/router.py` `/original` | `409` with the reason ("This file is online-only…"); `404` stays for a document with no file |
| `worker/ingestion/parsing.py` | the job fails with the reason |

**Ingesting a linked file.**
- The ingest job hashes with `hashlib.file_digest` before parsing and writes `content_hash`. If the hash differs after parsing, the job re-enqueues at `PRIORITY_CHANGED`.
- `pipeline.run` checks the document's root before `begin_job`. A paused root leaves the row as it is and the job ends; Resume re-enqueues every `pending` and `stale` row of the root.
- Success sets `linked_files.state='indexed'` and `indexed_at`.

**The tick** (`modules/source_roots/ticker.py`). One asyncio task in the API lifespan, started after migrations, wakes every 30 s. It reconciles roots whose `reconcile_requested_at` is set, and runs a full reconcile of every root every 15 minutes (an estimate). Full reconciles also run at API start, on watcher errors, on Rescan and after a wake.

**Watching** (`modules/source_roots/watcher.py::watch_linked_roots`). A second lifespan task holds one `watchfiles.awatch` over all native-mode roots.
- watchfiles becomes a direct dependency in `pyproject.toml`, and `api.spec` gains `collect_all("watchfiles")`, so the frozen API does not rely on uvicorn's extra to carry its Rust extension.
- An event is a hint. It schedules `reconcile_path(root_id, rel)` once the path has been stable for 2 s, which covers Office's save-to-temp-then-rename.
- Network roots get `watch_mode='poll'`: no live watcher, and a full reconcile every 5 minutes (an estimate). A root counts as a network root when its path is UNC, its Windows drive is `DRIVE_REMOTE`, or `statfs` reports smbfs, nfs, afpfs or cifs. Cowork does not support raw UNC paths at all ([Cowork local access](https://claude.com/docs/third-party/claude-desktop/local-access)).
- **Wake** is a gap in the tick's own rhythm: when more than 2 minutes of wall time pass between two 30 s ticks, the machine slept or the clock moved, and a full reconcile runs. This holds whether the platform's monotonic clock stops during sleep (Linux) or keeps counting (`GetTickCount64()` on Windows), because wall time always advances. A clock change by the user costs one extra reconcile. The clock is injected for tests.

**Reconcile** (single-flight per root, in `anyio.to_thread`)
1. **Availability first** (`availability.py::root_available`). The path must exist, list without error, and still match its recorded `volume_identity`. Otherwise the root becomes `unavailable` with its reason, and nothing else happens. A different USB stick on the same drive letter fails this check.
2. **Diff by `path_key`.**
   - Size, `mtime_ns` and identity unchanged: nothing is read.
   - Changed: the file is hashed. The same hash updates the stat fields only. A new hash marks it `stale` and enqueues at `PRIORITY_CHANGED`. The document keeps its old chunks, and stays in scope, until the new parse replaces them.
   - Case-only rename: the `path_key` is the same, so `relative_path` is updated in place.
3. **Pair moves.** Vanished and new files are paired by identity and size, then by size and SHA-256. A new file is hashed only when its size matches a vanished one. A paired file keeps its `document_id`, and only its path, folder and title change, so chunks, citations and artifact references survive.
4. **Missing.** Unpaired vanished files become `missing` and leave the scope.
   - **Mass vanish:** if more than half the root's indexed files, or more than 500, vanish in one pass from an available root, they are not recorded. The root stays `ready` and keeps indexing new and changed files. `held_missing` and `held_since` are set, and the header asks once. **Remove** calls `confirm-removal`, which reconciles with the hold lifted, so they become `missing` and the 24 h purge rule applies. **Keep** clears the question; while the same files stay gone the header shows "612 files missing · Review" without asking again, and they stay in scope.
   - **Purge:** `purge_missing.py` deletes a document only when a later reconcile of an available root, at least 24 h after `missing_since`, still finds it absent. It deletes in batches of at most 500.
5. **New files** are handled as in the first scan: `PRIORITY_BULK` above 20 in one pass, `PRIORITY_CHANGED` otherwise. New directories add folders. Emptied mirrored folders are pruned after their files are purged, by hosted's empty-chain rule.

**Cloud placeholders**

| Platform | Detected by | Never |
|---|---|---|
| Windows | `st_file_attributes` from the enumeration, which opens no handle: `RECALL_ON_DATA_ACCESS` 0x00400000, `RECALL_ON_OPEN` 0x00040000, `OFFLINE` 0x00001000 ([constants](https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants), [guidance](https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/placeholders_guidance)) | `os.stat()` or open on such a file. Descending a `RECALL_ON_OPEN` directory, which becomes a `placeholder` folder |
| macOS | `os.lstat().st_flags & 0x40000000` (`SF_DATALESS`; `stat.SF_DATALESS` exists only from Python 3.13) | Listing a dataless directory, which materializes it. The scan thread also turns `IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES` off (05), as a second guard once tested |
| POSIX | `st_blocks == 0 and st_size > 0`, the stub symptom in #62140, only when `fs_type` is one that reports blocks (ext4, xfs, btrfs, zfs, apfs, hfs, tmpfs). On FUSE the rule would mark every file, so a FUSE root links only after the warning above | Parsing it |

- When the user makes a placeholder local, its flags clear. The next reconcile sees a change and ingests it. SurfSense never triggers a download itself (Open questions).
- **Mostly online-only.** `GET /source-roots` already returns counts by state. The header's "online-only" line is derived from them, not stored: `placeholder` rows over the root's supported rows (every row except `unsupported` and `too_large`), above 20% (an estimate, set by the measurement in Open questions). The root stays `ready` and keeps indexing what is local.
- **Dehydration.** Storage Sense, OneDrive's "Free up space" and iCloud's optimised storage make indexed files cloud-only without anyone opening them. A ready document whose file becomes a placeholder keeps its chunks and stays in scope; `linked_files.state` becomes `placeholder` with its `document_id` kept, and the row says "Cloud-only now; text from {indexed_at}". `resolve_original` refuses it with "This file is online-only. Make it available offline to use the original." When it comes back with the same hash, only the stat fields change.

**Exclude, unlink, pause**
- **Exclude** adds an ignore pattern. The next reconcile drops those rows and leaves the disk alone.
- **Unlink** sets `unlinking`, which takes the root out of scope at once, then deletes its documents in batches, then its folders. The dialog says how much indexing the root holds: "Unlinking removes SurfSense's index of 20,412 files. Your files are not touched."
- **Pause** cancels queued ingest with one `UPDATE`, and `pipeline.run` skips the root's documents while it is paused, which covers a changed file still `ready` in the queue. Resume re-enqueues.

**Office support.** When [04](04-runtime-and-packs.md)'s Office support install finishes, it sets `reconcile_requested_at` on every linked root. Reconcile re-examines rows with reason `legacy_format` and queues them.

**Priorities.** The ingest queue stays one thread ([ADR 0008](../../adr/0008-two-job-queues.md)). `modules/documents/tasks.py` defines three constants:

| Constant | Value | Used for |
|---|---|---|
| `PRIORITY_INTERACTIVE` | 100 | a single upload, a note, a note edit, retry |
| `PRIORITY_CHANGED` | 50 | a linked file that changed |
| `PRIORITY_BULK` | 10 | a first scan, a folder copy, a restore |

Callers pass `ingest_document(id, priority=…)`. A note written during a six-hour first scan is ready in seconds.

**Bulk ingest yields to a local model turn.** Docling and llama.cpp share the CPU. Before a `PRIORITY_BULK` job begins, `pipeline.run` checks whether a chat or agent turn on a local model is streaming; if one is, the job re-schedules itself 15 s later (an estimate) and parses nothing. A parse already running finishes. `PRIORITY_INTERACTIVE` and `PRIORITY_CHANGED` jobs do not wait. The signal is a heartbeat the API's local-model relays write while a stream is open, which the worker process can read; its form is settled with the README's whole-stack memory and CPU budget.

### What branches on the kind of root

1. Resolving the original: `resolve_original()` and Electron's opener, through `/location`.
2. Dedup: `dedup_key` per folder for managed files; `(root_id, path_key)` for linked ones.
3. Delete: the Trash and purge for managed; exclude or unlink for linked.
4. Rename and move: allowed for managed; `409` for linked.
5. Freshness: through the API for managed; the watcher and reconcile for linked.
6. The root header.

Nothing else branches.

### Edge cases

| Case | Handling |
|---|---|
| Windows `MAX_PATH` | Linked opens, stats and Docling go through `long_paths.extended()` ([Microsoft](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation)). Managed paths stay id-keyed. Agent mirror paths stay under 259 characters |
| NFC vs NFD | `relative_path` keeps the OS names and `path_key` is NFC. On Linux the two forms are two files; if both map to one key, the second file is `unsupported` ("name clash") and the second directory is skipped and noted |
| Case-only rename | Same `path_key`, so an in-place update; never a delete and create |
| `a.txt` and `A.txt`, or `Data/` and `data/`, on a case-sensitive root | Two documents, or two folders; their mirrored names differ by `[id]` or `[f<id>]` |
| A linked tree 12 levels deep | Mirrored whole; the depth cap is the Library's |
| A copied tree 12 levels deep | Levels past 8 join into the eighth folder |
| A name that is not valid UTF-8 | Skipped and counted in `scan_notes` |
| Symlink or junction leaving the root | Not followed. `linked_original_path` also re-checks containment after `resolve()` |
| A root that is a git repository | `.git` is hidden, so it is ignored. The working folder lives under the data directory, never inside the root ([03-opencode](../agent/03-opencode.md#working-folders)) |
| Same bytes in two Library folders, or linked and uploaded | Two documents, two parses, until phase 6 measures whether reuse is worth it |
| Drive letter reused by another volume | `volume_identity` mismatch, so the root is `unavailable`, not deleted |
| macOS refuses access | `unavailable` with `permission_denied`; nothing deleted |
| A FUSE or Docker bind mount | FUSE asks first; both run in `poll` mode |
| A file freed by the sync client | Keeps its text and scope; the original cannot be opened |
| A database restored from an older backup | Directories with no row and no tombstone are left alone |

### The agent

**Per-thread working folders.** `StorageSettings` gains `thread_working_dir(workspace_id, thread_id)` = `data/workspaces/<ws>/agent/threads/<thread>/`, holding `sources/` and `outputs/`.
- `open_agent_session` creates the session there. `agent_turn` syncs, registers and streams there.
- Thread delete nulls `output_path` on the thread's artifacts in its transaction, and removes the folder after the commit, beside `store.remove_thread`. `forget_sessions` gets the thread's folder.
- Agent threads stay behind the developer switch until M5, which ships phases 3a and 3b and turns the agent on in installers.
- opencode's edit rule today, `*/agent/outputs/*`, matches no per-thread path. It becomes, last match winning:

  ```python
  "edit": {"*": "deny",
           "*/agent/threads/*/outputs/*": "allow",
           # A mirrored folder named "outputs" must not open sources/ to edits.
           "*/agent/threads/*/sources/*": "deny",
           "*AGENTS.md": "deny", "*CLAUDE.md": "deny", "*CONTEXT.md": "deny"}
  ```

  The `sources/` deny is needed because opencode's `*` spans `/`, so `…/threads/7/sources/Research/outputs/a.md` would match the allow. `*/agent/outputs/*` stays allowed only while threads that keep the workspace folder exist (Open questions). [02](02-skills-and-engines.md)'s `permission_for()` uses this set, with the `sources/` deny after the outputs allow.
- What `outputs/` becomes is [`03-editable-artifacts.md`](03-editable-artifacts.md)'s. Its `output_path` is relative to the thread's `outputs/` and unique on `(chat_thread_id, output_path)`, so the same name in two threads is two artifacts.
- There is no separate `artifacts/` view. The agent sees a filed or ticked artifact's head under `sources/` like any source, and reaches artifacts it made by id through 02's engine tools (03).

**Built (2c).** Phases 3a and 3b were built together, as [agent](../../architecture/agent.md#folders) describes.
- **Built.** Each agent thread's session and folder under `agent/threads/<thread>/`; the mirror at the user's folder paths from the start, with no flat stage, under the device-name, instruction-name, collision and length rules above; the hard-link text cache and a sync that writes no file inside a transaction; per-thread tool registration, which removes the per-turn token registry and the shared address two concurrent turns used; scoped `search_sources` labelled by mirrored path; the scope check on `list_images`, `source_pages` and `create_artifact`, now for a thread on every source too; Studio artifacts filed in a ticked folder, mirrored like any source; the edit rules and the prompt; thread delete aborting the session, disposing its instance and removing the folder; and the scope note on every turn not on every source, tagged by id up to 200 and by count past that, which the "Working from" line shows.
- **Legacy threads** (Open question 1): a thread whose session lives in `agent/` is read-only rather than stamped to keep the workspace folder. Its history reads back, a turn answers `409`, and the app shows that refusal with "Start a new chat". `*/agent/outputs/*` is no longer allowed, and `agent/outputs/` stays until the workspace is deleted.
- **Cut.** No `document_text_digests` table and no migration: the cache is keyed by a digest computed at sync time, since the table would save only the ~1.1 s content read at 5,000 sources. Cache files stay writable, since on Windows a read-only hard link cannot be unlinked. The sweep deletes cache files no view links (`st_nlink == 1`) instead of reading the table. `search_sources`' `folder` and `create_artifact`'s `folders` wait for 02's schema order. `require_in_scope` is `TurnScope.refuse_unselected` until 02's engine tools need it. `resolve_original`, `copy_original` and 03's `output_path`, with the delete that nulls it, wait for an engine and the column. No cap disposes idle opencode instances.
- **Still open.** A git repository above the data folder, and opencode's shared tool-output folder, still let an agent read outside its thread's folder (agent Known gaps); closing them needs opencode-side work.

**The mirror.** Phase 3a lays out the resolved scope flat, as `sources/<title> [<id>].md`, today's names. Phase 3b adds folders: `sources_folder.py` gains `mirror_path(document)` = `sources/<root>/<folder>/…/<title> [<id>].md`.
- Each segment passes through the same `_UNSAFE` and is stripped of trailing dots and spaces.
- A segment gets a `_` suffix when it is a Windows device name, an opencode instruction-file name (`AGENTS.md`, `CLAUDE.md` or `CONTEXT.md`) or `outputs`, case-insensitive. On macOS the edit rules match case as written while the disk ignores it, so a mirrored folder named `outputs` under `Sources/` would match the `outputs/` allow and miss the `sources/` deny.
- Two sibling segments that sanitize to the same name both get ` [f<folder id>]`.
- Past 259 characters, segments are cut deepest first, down to 8 characters plus the folder id. `[id]` stays the key that `create_artifact` and citations read.
- The Library mirrors as `sources/Library/`, and each linked root under its own name. Filed artifacts in scope mirror in their folder like any source.
- Only the thread's resolved scope is laid out. Cleanup walks recursively and prunes empty directories.

**Per-turn cost.**
- Text lives once per workspace, in `agent/text/<doc_id>-<digest>.md`, where `digest` is the first 16 hex characters of `document_text_digests.sha256`. Ingest writes that row in the transaction that marks the document ready, from the extracted text of a FILE or the content of a NOTE. A key on content, not on `updated_at`, cannot serve stale text after two changes within one second, since `updated_at` comes from SQLite's `now()`.
- Cache files are read-only, so an approved shell command cannot change the text another thread links to without overriding that first.
- Views hard-link to the cache with `os.link`, or copy where links fail.
- The sync runs in three steps, and none holds the write lock across file work:
  1. One short transaction resolves the scope and reads `(id, title, folder_id, digest)`.
  2. For digests with no cache file, `content` is read in pages of 200 ids, each page in its own short transaction.
  3. After the last commit, `anyio.to_thread.run_sync` writes cache files, lays out links and directories, and cleans up.
- After the sync, a sweep removes cache files whose `<doc_id>-<digest>` no longer matches a row in `document_text_digests`, which covers old versions and deleted documents. It runs at most once every 10 minutes per workspace.
- This closes the agent Known gap "the full-text sync runs on every turn".

**Tools**
- `register_workspace_tools` registers `/agent/tools/workspaces/{ws}/threads/{thread}`. Every tool call therefore knows its thread, and [03](03-editable-artifacts.md) takes a tool-started version's `chat_thread_id` from the URL. Requests on the model endpoint carry no thread, so [05](05-model-ladder-and-evals.md)'s `active_turns` registry (`modules/agent/agent_threads/active_turns.py`, created in its phase P2) still says which turns are streaming, for spend scopes and deferral.
- `search_sources` resolves the thread's scope and labels passages by their mirrored path. Phase 3b gives it an optional flat `folder` string, a path under `sources/`.
- `create_artifact` intersects `source_ids` with the thread's resolved scope through `modules/source_scope/guard.py::require_in_scope(session, thread_id, document_ids)`. An id outside it is a `ToolCallError`: "source 412 is not in this chat's sources". This also stops a document that injects instructions from pointing the agent at unticked sources or at artifacts. Phase 3b adds an optional `folders` array, stored as the artifact's `source_scope`.
- 02's engine tools pass their `source_id` through the same guard.
- Schemas stay flat, and the tool order is owned by [`02-skills-and-engines.md`](02-skills-and-engines.md).

**The prompt.** The agent prompt is 3,178 characters, as `agent_prompt()` strips it, under the 4,000-character test ([`prompts/agent.md`](../../../surfsense_local/backend/modules/agent/prompts/agent.md), `test_opencode_config.py`). This stream adds 112:
- in "Your folder", after the `sources/` bullet, one bullet of 109 characters with its newline: ``- Folders inside `sources/` are the user's folders. Only the sources the user chose for this chat are there.``;
- in step 4, `sources/*.md` becomes `sources/**/*.md`, 3 more.

02 owns the prompt's total (Dependencies).

**Originals.** An engine gets an original only through `resolve_original` and `copy_original`.
- `resolve_original` runs in the tool's short transaction. `copy_original` runs in the engine job in the worker, with no session open, into the job's scratch folder, never into `sources/` or `outputs/`.
- The model names sources by id, never by path. [`02`](02-skills-and-engines.md) owns the engine tool that calls these.

**Instruction injection.**
- When it reads a file, opencode attaches the first of `AGENTS.md`, `CLAUDE.md` (unless `OPENCODE_DISABLE_CLAUDE_CODE` is set) or `CONTEXT.md` found in each directory between that file and the session root, excluding the root itself. `OPENCODE_DISABLE_PROJECT_CONFIG` does not gate this (`Instruction.resolve` and `find` in `session/instruction.ts`, read in `references/opencode-dev`).
- Three rules keep a linked repository's instruction files out of that walk:
  1. Mirrored files are always `<title> [<id>].md`.
  2. Mirrored directories never carry an instruction-file name.
  3. Originals never enter the working folder.
- The remaining path is the agent writing `outputs/AGENTS.md`. The edit rules above deny those names.
- The text of a linked `AGENTS.md` is still a source, and the prompt's "Untrusted text" rule applies to it like any counterparty document.

### Artifacts and folders

- A new artifact is unfiled and shows in Studio's list, as today. It is outside `all` and every folder scope. Each row in Studio's list gets a source tick that adds the artifact to the thread scope's `document_ids`, so an unfiled artifact can be used one at a time. This stream owns that tick; 03 adds no Outputs group and no "include outputs" flag.
- **File in folder…** (Studio's row menu, or dragging the row onto a Library folder) sets `folder_id`. The artifact then shows in the tree with its format badge and is a source wherever that folder is in scope. **Remove from folder** unfiles it.
- An artifact's own document is never among its own sources: `start_version` drops it (03), and `resolve_scope` gets it as `exclude_document_ids` when regenerate re-resolves.
- Filing into a linked root answers `409`.
- There is no automatic Outputs folder. Users make one if they want it, and File in folder… remembers the last folder per workspace.
- Moving a folder to the Trash moves its filed artifacts with it, and the dialog counts them; a purge deletes them and their blob folders.
- `document_type` still earns only its badge, its filter and the read-only guard ([ADR 0003](../../adr/0003-artifacts-as-documents.md)).

### Export, import and sharing

The app is single-user and local, so sharing beyond files is out of scope for v1. A file is the sharing path.
- **Workspace bundle (M6).** The workspace export extends the [export contract](../../contracts/03-export-bundle.md) with `source_roots`, `folders` (name, parent, role, Trash state) and each document's `folder_id`, beside 03's versions and the workspace settings. Import rebuilds the chains with `ensure_folder_path` and keeps roles. A linked root travels as its name, path and exclusions only, never its index, because its files are not the app's; on the new machine it arrives `unavailable` until the user re-links it with a new pick.
- **One Library folder.** "Export folder…" writes the same bundle limited to the folder's subtree, filed artifacts included. A colleague's import adds it as a new folder under their Library, with per-folder dedup, so importing it twice adds nothing.
- **Playbooks.** [02](02-skills-and-engines.md)'s structured playbook is a SurfSense-owned JSON kept beside its source document in the data directory. A `playbook` role folder on a linked root therefore holds the source document on disk and the JSON in SurfSense; nothing is written into the root. The playbook exports with its folder.

## Options considered and rejected

| Option | Why not |
|---|---|
| Materialized paths, on `folders` or `documents` | A rename rewrites every descendant. Name paths bring case and normalization traps. A column on `documents` has nowhere to keep folder state or empty folders |
| A `LINKED` document type or `missing` status | A CHECK change rebuilds `documents` and cascades into chunks |
| `documents.source_root_id` as well | It duplicates what the root folder row already says |
| Labels instead of folders | People keep one location per file and rarely retrieve by tags ([Bergman et al., JASIST 2013](https://onlinelibrary.wiley.com/doi/10.1002/asi.22906)). Gemini Notebook chose AI labels, and extensions with 90k and 40k users sell folders back to its users ([FolderLM](https://chromewebstore.google.com/detail/folderllm-create-folders/nknkgcmodkaiffdnlpmlnegmeamnbioe)). Labels can come later, on top of folders |
| Permanent folder delete behind a counting dialog | A dialog is clicked through; one slip would cost hours of ingest, and every file manager users know makes a delete undoable |
| A trash flag on `documents` | Needs a new column or status on `documents`. Wrapper folders give documents a trash with no change to the table |
| Workspace-wide dedup for folder copies | A copied folder gets holes wherever a file already sat in another folder |
| A client-expanded id list with a higher cap | The client must still load every row, and the scope is not dynamic |
| An `include_outputs` flag on the scope | Two opt-ins for one intent. A ticked folder holding a filed artifact would use something other than what it shows |
| Rebuilding `chunk_vectors` with a `workspace_id` partition key and folder metadata | It works on 0.1.9 (checked), but it needs a full rebuild, and every move rewrites vector metadata. `rowid IN` prefilters the same way without either |
| Only a larger `k` | Still global, so a small folder stays starved at any fixed `k` |
| chokidar in Electron posting hints to the API | A second watcher stack in a second language, and the Docker stack runs the API with no Electron |
| A watch sidecar, or reconcile on the `ingest` queue | The first is another frozen process for one asyncio task. The second waits behind hours of Docling |
| A second ingest queue for bulk work | Two CPU-bound Docling workers contend ([ADR 0008](../../adr/0008-two-job-queues.md)). Priorities give the order without the contention |
| Hosted's finalize-deletes-orphans; downloading placeholders | The first wipes the library when a drive is missing. The second means silent bandwidth use and the Cowork corruption pattern |
| Holding the root `unavailable` on a mass vanish | The next pass sees the same vanish, so a real bulk delete would freeze the root, and its new files, forever |
| Sweeping every id directory with no row at start | A restored backup or a failed migration would delete originals that are the only copies |
| Reusing one parse for identical bytes in the first linked phase | New code in ingest and ranking (ADR 0033's ground) for an uncommon case, before anyone has measured it |
| One agent folder, scope passed only to `search_sources` | `read`, `grep` and `glob` still see everything |
| Originals hard-linked into the working folder | Real names bring `AGENTS.md` into the instruction walk. A hard link *is* the user's file, so a write through it edits the original |
| Scope per workspace in `localStorage` only | Turns could not be replayed, and regenerate could not re-resolve |
| The renderer passing a disk path to Electron's opener | A renderer script could name any file; main can ask the API instead |

## Phases

| # | Phase | Milestone | Scope | Depends on | Size |
|---|---|---|---|---|---|
| 0 | **Source scope on the server** | M0 | the `thread_scope` revision; the snapshot before migrating in `upgrade_to_head`; `modules/source_scope/` without folders (`all` as FILE and NOTE, `document_ids`, `excluded_document_ids`, self-exclusion, `removed` counts); `source_scope` on `MessageCreate`, `StudioJobCreate` and `ThreadCreate`, resolved in `_ground` and `create_artifact_job`; `PUT /source-scope`; the per-turn record; `retrieve(scope=)` with the `json_each` filter and the KNN prefilter; `gather()`'s retrieval regime, `budget_chars` and `grounded_document_ids`; regenerate re-resolves; frontend sends `{all: true, excluded_document_ids}`; `listDocuments` pages at `limit=200`; `SourceCount` from server counts | nothing | **M**: one plain column, one search change, one Studio change, two frontend call sites, one migration-runner step. Fixes the 50-source bug without making Studio worse at 5,000 sources |
| 1 | **Folders in the Library** | M2 | the `source_roots_and_folders` revision with backfill and the dedup index swap; `modules/folders/`; `folders.role`; the managed root; constructors file into the Library; folder scope; the tree slice (virtualized, tri-state, create, rename, drag, picker, name filter, multi-select replacing `deleteSelected`); the Trash, restore, batched purge and tombstone sweep; import writes folders | 0 | **L**: one migration over users' only database and a new UI slice replacing a 751-line component |
| 2 | **Add a whole folder** | M2 | `webkitdirectory` and recursive drop; client-side size filter; batched upload with `relative_paths` and depth clamping; per-folder duplicates; priorities and the bulk yield to local turns; cancel per folder; the preview's second rail | 1 | **M**: standard browser APIs, one route change |
| 3a | **Scoped agent** (built in 2c, with the cuts under [The agent](#the-agent)) | M5 | per-thread folders; the flat mirror of the resolved scope; the per-thread edit rules; `document_text_digests` and the text cache; the sync outside the write lock; per-thread registration; scoped `search_sources`; the `create_artifact` scope guard; the prompt; `resolve_original` and `copy_original` for managed files, always, checking `dedup_key` where `content_hash` is not filled yet | 0; [02](02-skills-and-engines.md) phase A (the edit rules' order, M1) | **M**: contained in `modules/agent/`, after one opencode check. Narrows the agent Known gap "An unticked source is still a file the agent can open" to a git repository above the data folder and opencode's tool-output folder |
| 3b | **Agent mirrors folders** (built in 2c, without `folder` and `folders`) | M5 | `mirror_path`; instruction-name guards for directories; `search_sources`' `folder`; `create_artifact`'s `folders` | 1, 3a | **S** |
| 4a | **Link a folder: scan and reconcile** | M8 | the `linked_files` revision; Electron picker, drop, expiring grants and the `/location` opener; macOS usage strings and `permission_denied`; `link_root`; walk, ignores, placeholders and dehydration, the mostly-online-only header and link-dialog copy, FUSE and Docker modes, non-UTF-8 names, availability, long paths; the tick with reconcile requests; reconcile at start, on demand and every 15 minutes; pairing; missing, the mass-vanish question and purge; the linked branch of `resolve_original`; pause in `pipeline.run`; `legacy_format` and the unreadable count; the first-scan notification; tree states | 1, 2 | **L**: most platform cases; needs Windows and macOS runs from a packaged app, and a Windows VM with OneDrive Known Folder Move |
| 4b | **Live watching** | M8 | watchfiles as a direct dependency and in `api.spec`; `watch_linked_roots`; stability debounce; poll mode; wake detection | 4a | **M** |
| 5 | **Artifacts in folders** | M3 | file and unfile; the Studio row's source tick; artifact rows in the tree; filed artifacts in the mirror | 1; [03](03-editable-artifacts.md) phase 1 for `inputs` | **S** |
| 6 | **Twins, if measured** | unscheduled | `worker/ingestion/twins.py::copy_twin` copying content, chunk rows and vector rows; `_best` keeping one of two hits whose documents share `content_hash` and whose chunks share `position` | 4a, and a measurement showing duplicates take a real share of Docling time on reference libraries | **M** |

Milestones are the README's; durations there are rough.
- Phase 0 ships first, in M0, as a 2.1.x point release that starts now. It does not wait for 02's clean-room work. It is a correctness fix with one plain column, and everything after it builds on it.
- Phases 1 and 2 are M2. They need only M0 and run in parallel with M1 and M3.
- Phase 5 is in M3, which also runs in parallel with M2; it lands once phase 1 is in.
- Phases 3a and 3b are M5, after M2, M3 and M4. Until then agent threads stay behind the developer switch.
- Phases 4a and 4b are M8, beside 04's RT3a, RT3b (Office support) and RT6, in parallel with M5 to M7.
- The workspace and folder bundle (Export, import and sharing) is M6.

## Tests

These are integration tests under `tests/integration/` unless noted. Each lands with its phase, and the failing test is written first.

- **Phase 0**
  - `search/test_retrieve.py`:
    - the existing "neighbour holds every one of the 20 nearest" case now gets a semantic candidate from its own workspace;
    - a one-document scope among 2,000 near chunks finds a paraphrase that shares no keyword.
  - `source_scope/test_resolve_scope.py`: `all` skips unfiled artifacts; non-ready rows are counted, not refused; a foreign id gets `422`; a deleted ticked document is dropped with `removed=1` and the next write prunes it; an artifact is excluded from its own scope.
  - `chat/test_send_scope.py`: with 60 sources, `{all: true}` cites the oldest; the user turn records `source_scope` and `resolved`.
  - `studio/test_gather.py`: 200 and 5,000 documents take the retrieval regime and record `grounded_document_ids`; `budget_chars` is honoured.
  - `artifacts/test_regenerate_scope.py`: regenerate uses a file added after the first run; an artifact with only `source_document_ids` replays them; nothing left gives `409`.
  - Frontend: `sources-stay-fresh.test.tsx` renders 260 rows and sends `source_scope`.
  - `test_migration_snapshot.py`:
    - a populated database one revision behind head gets `backups/<from>-<to>.db` before the revision runs, and the snapshot opens through the app's engine with the same chunk and vector counts;
    - a database at head, and a new database, write no snapshot;
    - after three upgrades only the two newest snapshots remain;
    - a snapshot that cannot be written (read-only backups folder) leaves the database at its revision and fails the start with the reason.
- **Phase 1**
  - `test_migration_*_folders.py`:
    - one Library per workspace;
    - "Research/AI" and "research/ai" become one chain;
    - nine segments clamp to depth 8;
    - a second run is a no-op;
    - the chunk count is unchanged;
    - `content_hash` is filled, and the dedup index is per folder.
  - `folders/test_folder_routes.py`:
    - a cycle gets `400`; eight user levels succeed and a ninth gets `400`;
    - "Été" beside "ÉTÉ" gets `409`;
    - a move into a linked root gets `409`;
    - a move into a folder already holding the same bytes skips and reports that document.
  - `documents/test_every_source_has_a_folder.py`: after `create_note`, `upload_documents` and an import, no FILE or NOTE row has a `NULL` `folder_id`; a row forced to `NULL` still appears at the Library's top and in `all`.
  - `folders/test_trash.py`:
    - a trashed folder leaves scope and the tree at once, and restore brings it back with the same chunk count and the same ticks;
    - a name taken meanwhile restores as " (restored)";
    - an entry older than 30 days is purged (time injected);
    - a concurrent note write succeeds while a 5,000-document folder is purged;
    - a held directory keeps its tombstone and is swept at the next start;
    - a directory with no row and no tombstone is left alone.
  - `source_scope/`: a file added after its folder was ticked is in scope; an excluded subfolder is out; a file re-ticked inside it is in.
  - `folders/test_folder_search.py`: "été" finds "Été.docx" three levels down and returns its chain; a trashed match is not returned.
  - Frontend: `tree/source-tree.test.tsx` selects three rows with Shift and Ctrl and moves them to the Trash in one call, with the Undo toast.
- **Phase 2**
  - `documents/test_upload_folder.py`: `relative_paths` builds chains; a 12-deep tree clamps into the eighth level; a folder holding a file already elsewhere in the Library is copied whole; copying it again reports every file under `duplicates`.
  - Frontend: a 501 MB file is listed as rejected and the other 49 files of its batch are uploaded.
  - `test_ingest_priority.py`: a note queued after 30 bulk jobs runs next; with the local-turn heartbeat set, a bulk job re-schedules without parsing and a note still runs.
  - `test_cancel_folder.py`: queued jobs no-op.
- **Phase 3a** (`agent/test_sources_folder.py`, `test_search_sources.py`, `test_tool_endpoint.py`, and `tests/unit/agent/test_opencode_config.py`)
  - Only scoped files are laid out; two threads keep separate views, and the tool URL's thread limits hits.
  - Unchanged sources load no `content`; two content changes within one second give two cache keys; a deleted document's cache file is swept.
  - A concurrent write succeeds while a 5,000-file scope is laid out.
  - `create_artifact` with an unticked source id, or with an artifact id outside the scope, returns the "not in this chat's sources" error.
  - A per-thread `outputs/` path is writable; `sources/`, and a mirrored folder named `outputs` inside it, are not.
  - Deleting a thread nulls `output_path` on its artifacts and removes its folder.
  - The prompt stays under 4,000 characters.
- **Phase 3b**
  - Files are laid out at mirrored paths; a folder named `AGENTS.md` mirrors as `AGENTS.md_`; deep chains stay under 259 characters.
  - An opencode-in-the-loop test checks that a linked `AGENTS.md` adds no "Instructions from:" reminder.
- **Phase 4a** (`source_roots/`; platform cases run on their platform in CI)
  - Root availability:
    - an unavailable root keeps every document;
    - a different volume at the same path is `unavailable`;
    - an `EPERM` listing gives `permission_denied`;
    - a purge happens only after the 24 h confirming pass (time injected).
  - Mass vanish: a 600-file delete is held; files added during the hold are indexed; Remove records them `missing` and purges after 24 h.
  - Renames:
    - pairing by identity, and by size and hash;
    - a case-only rename keeps its id;
    - NFC and NFD names are two documents on Linux, one on macOS;
    - `Data/` and `data/` on Linux are two folders.
  - Paths: an outward symlink or junction is ignored; a 300-character path ingests on Windows; a 12-deep linked tree mirrors whole; a non-UTF-8 name on Linux is skipped and noted.
  - Placeholders, at the `placeholders.py` seam with a fake enumeration: placeholders open nothing; an indexed file whose attributes gain `RECALL_ON_DATA_ACCESS` keeps its document, stays in scope and opens nothing; the POSIX rule is off on a FUSE `fs_type`; a root with 80 placeholders among 100 supported files reports the online-only counts, stays `ready` and indexes the other 20.
  - Unreadable files: three `.xls` and one `.msg` are counted in the root's unsupported counts by reason and create no document.
  - Freshness: a changed file stays in scope while its re-parse runs and after it fails; `copy_original` on changed bytes raises and sets `reconcile_requested_at`, and the tick reconciles it.
  - Pause: pausing during a burst of changes runs no Docling.
  - Grants: no grant gets `403`; a grant older than 10 minutes gets `403`, so unlink then re-link without a new pick fails; a path inside the data directory gets `422`.
  - Electron: `linked-roots.test.ts` covers grants, and `document-files.test.ts` covers ids-only open, containment, and reveal-not-open for an `.exe`.
  - macOS, manual or CI from the packaged app: linking `~/Documents` shows SurfSense's usage string and indexes after consent.
  - Windows, from the packaged app on a VM with OneDrive Known Folder Move and Files On-Demand: linking Documents with most files online-only shows the online-only line and dialog, hydrates no file (each file's attributes are unchanged after the scan), and indexes files once "Always keep on this device" brings them local.
- **Phase 4b** (`source_roots/test_watcher.py`): a write reconciles after the debounce; a burst of saves becomes one reconcile; a watcher error triggers a full pass; with an injected clock, a 10-minute wall-time gap between ticks triggers a full pass. A packaging test imports `watchfiles._rust_notify` in the frozen API.
- **Phase 6**: twins skip Docling (a converter call counter); a library copy and a linked copy of one file do not both fill the top 5.

## What this changes in existing ADRs and proposals

- **[ADR 0005](../../adr/0005-hand-written-migrations.md):** the decision is unchanged. The consequences should state "`documents` gains columns only by plain `ALTER TABLE`; a CHECK change on it needs an ADR" and "`upgrade_to_head` snapshots the database before any pending revision", and fix the stale count of "twelve" revisions.
- **[ADR 0003](../../adr/0003-artifacts-as-documents.md):** "In the desktop app" gains one point: `Document` owns the folder here too; an artifact is a source only once filed or ticked, and never of itself.
- **[ADR 0006](../../adr/0006-hybrid-retrieval.md) and [search](../../architecture/search.md):** the vector leg is prefiltered inside the KNN, and "Ceiling" is rewritten. New [ADR 0045](README.md#adrs-to-write-or-amend) records "retrieval scope is resolved on the server and applied inside both legs". [ADR 0033](../../adr/0033-every-candidate-is-scored-on-its-own-cosine.md) stands; phase 6 would amend it only if twins land.
- **[ADR 0008](../../adr/0008-two-job-queues.md):** the ingest queue orders by priority.
- **New [ADR 0046](README.md#adrs-to-write-or-amend):** "SurfSense never loses a user's sources by surprise": a Library delete goes to a Trash; linked folders are read-only; an unavailable folder never deletes; a mass vanish asks first; placeholders are never read; a database snapshot is written before every migration (Decisions 5, 9 to 11 and 19). These are promises to users, which belong in an ADR.
- **[documents](../../architecture/documents.md#the-original-file):** the stale "since the main process never calls the backend" sentence goes; the opener asks the API by id. Upload, delete and the original file gain folders, the Trash and linked roots as each phase lands.
- **[`../agent/05-sources-folder.md`](../agent/05-sources-folder.md):** its decisions stand, and its open questions are answered here, so it links here and closes.
- **[`../agent/03-opencode.md`](../agent/03-opencode.md):** "Working folders" becomes per thread and mirrors the scoped tree.
- **[`../agent/README.md`](../agent/README.md):** "Sources on disk" gains "read-only mirror; never deletes on unavailability".
- **[`../source-preview.md`](../source-preview.md):** the second rail moves into phase 2.
- **Architecture docs, as each phase lands:** [data model](../../architecture/data-model.md), [chat](../../architecture/chat.md), [studio](../../architecture/studio.md), [agent](../../architecture/agent.md) (two Known gaps close), [import](../../architecture/import.md), and [overview](../../architecture/overview.md) (the watcher and the tick in the API).

## Dependencies on other streams

- **[`02-skills-and-engines.md`](02-skills-and-engines.md)** needs to:
  - call `resolve_original` in `start_engine_run`'s transaction and `copy_original` in `engine_job`, with no session open; on `OriginalChanged`, fail the version with its message and set `reconcile_requested_at`;
  - pass every `source_id` through `require_in_scope`;
  - take the thread from the tool URL;
  - use the per-thread edit rules above in `permission_for()`, with `*/agent/threads/*/sources/*: deny` after the outputs allow, and run its instruction-name rename backstop over the thread folder;
  - own the agent prompt's total length; this stream's share is the 112 characters above;
  - supply the MCP tool list and order;
  - keep its structured playbooks as SurfSense's files beside their source documents, never inside a linked root.

  This stream gives it the resolver, per-thread registration and the mirror. Managed `resolve_original` and `copy_original` land in phase 3a whatever 02's order, and 02's phase 1 depends on phase 3a.
- **[`03-editable-artifacts.md`](03-editable-artifacts.md)** needs to:
  - store the source scope as `inputs.source_scope` beside `inputs.sources` and `inputs.grounded_document_ids`, keeping its own `scope` column for selections inside an artifact;
  - let regenerate with no body re-resolve `inputs.source_scope`, fall back to `inputs.sources`, and accept a `source_scope` in the body;
  - carry versions and settings in the M6 workspace bundle beside this stream's folders.

  This stream gives it: thread delete nulls `output_path` on the thread's artifacts; moving to the Trash and purging call `versions.guard_delete` for filed artifacts (a linked root holds none); the resolver's `exclude_document_ids` for self-exclusion.
- **[`04-runtime-and-packs.md`](04-runtime-and-packs.md)**: `@tanstack/react-virtual`; watchfiles as a direct dependency and `collect_all("watchfiles")` in `api.spec`, with the frozen-import test; the macOS `extendInfo` strings in `electron-builder.yml`; setting `reconcile_requested_at` on linked roots when Office support installs, and the legacy-format conversion (RT6) that ingest calls. The interface says "Office support". `pathspec` comes only with user ignore files.
- **[`05-model-ladder-and-evals.md`](05-model-ladder-and-evals.md)**: replays and run bundles read the user turn's `source_scope` and `resolved`. The profile supplies Studio's `budget_chars`, and this stream owns the code that takes it, which answers 05's open question 6. Folder-scale grounding and per-turn sync time are matrix metrics; `free_agent_tasks`' 200-file folder case uses this stream's scope and mirror. Small models get a resolved scope, never a tree to browse. 05 keeps the `active_turns` registry for model-endpoint requests, which carry no thread.
- **[`06-product-shape.md`](06-product-shape.md)**: one kind of workspace. `set_up_job()` creates role folders in the Library through `ensure_folder_path` and sets `folders.role`; a role can be set on any folder, a linked root's root folder included, through `PATCH /folders/{id}`. Guided jobs resolve roles to `folder_ids` in a `SourceScope` (`job_scope()`), and the handoff copies the thread's `source_scope` to the new thread. 06 owns the `Role` vocabulary (`evidence`, `target`, `playbook`, `library`) and `workspaces.settings`; this stream owns the column and the route that sets it.
- **The [README](README.md)'s whole-stack memory and CPU budget**: the per-folder opencode instances (Open question 1), the text cache and the scan are measured with the rest of the stack at M5's and M6's exits.

## Open questions

1. ~~Can an opencode 1.18.34 session created in one directory continue in another?~~ Answered: no. Create and fork use the instance directory and `PATCH /session/{id}` takes none, so a thread made before thread folders is read-only: its turns answer `409` "start a new chat", its history still reads back, and `agent/outputs/` stays until the workspace is deleted; `*/agent/outputs/*` is no longer allowed ([agent](../../architecture/agent.md#folders)). An instance is disposed one at a time with `POST /instance/dispose?directory=`, which thread delete calls. One instance holds about 30 MB of opencode's memory after a turn with SurfSense's tools (measured on 1.18.34, `test_thread_isolation.py`), past the 5 MB at which an idle-instance cap was to be revisited; no cap is built yet.
2. Should SurfSense ever trigger a cloud download after per-root consent? A download writes to the user's disk through the sync client, which is close to "no writes".
3. Should the agent learn that unreadable files exist ("questionnaire.xls, not readable yet")? If so, through what? A generated index file must avoid instruction-file names.
4. Should instruction files inside a linked root be ignored by default, or offered later as an opt-in "folder rules" feature?
5. Docling throughput on the reference laptops would set the first-scan threshold and the estimate shown when linking.
6. Do Docling and opencode's Bun-based `read`, `grep` and `glob` handle `\\?\` paths and paths over 260 characters on Windows? The 259-character mirror cap assumes they do not.
7. Does macOS attribute the API sidecar's file access to SurfSense's bundle, so its usage strings show? The packaged-app test in phase 4a answers it, and it needs a notarized build, which failed on 3 Oct 2026 for an expired Apple agreement. If not, the scan would have to start from a process macOS attributes correctly.
8. What share of a real Documents folder under OneDrive Known Folder Move is online-only? Measured in phase 4a on at least one business laptop, it sets the 20% threshold for the root's online-only line and the link dialog.
9. Are 30 days of Trash and the 10-minute grant window right? Both are estimates, and trashed bytes keep using disk until purged.
