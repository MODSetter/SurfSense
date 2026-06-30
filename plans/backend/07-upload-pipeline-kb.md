# Phase 7 — File upload as a pipeline + KB-save-secondary

> Part of the **CI Pivot MVP**. See `00-umbrella-plan.md` (Phase 7) — the final backend phase.
> Precondition: Phase 5 (`05-pipelines-model.md`) live (`pipelines`/`pipeline_runs` tables, `PipelineRunTrigger.UPLOAD`, `connector_id` nullable) and Phase 6 (`06-pipelines-exec.md`) live (run engine, which **explicitly fails `connector_id IS NULL` runs**). No sibling ahead — this closes the backend umbrella.

> **Implementation note (post-rename).** Phases 1–2 are **SHIPPED**, so the live code already uses `workspace_id` / `Workspace`. Citations below that still show `search_space_id` / `SearchSpace` are pre-rename — substitute the `workspace_*` equivalent and grep the new name. **New code in this plan uses the canonical `workspace_*` names** (snippets below updated). Locate code by **symbol/grep**, not the absolute line numbers cited here (the rename + Phases 3–6 shift them).

## Objective

Close the loop on the umbrella's positioning — *"User file uploads also do a pipeline entry and register a run that files were uploaded by user; only file uploads are always saved in the knowledge base"* — by:

1. **Uploads-as-pipeline** — give every workspace a singleton **"Uploads" pipeline** (`connector_id = NULL`, `save_to_kb = true`), lazily created, and make each upload request **register a `PipelineRun(trigger=upload)`** so uploads show up in pipeline run history (and in the Phase-6 chat `get_pipeline_runs` tool) exactly like connector fetches.
2. **KB-save-secondary (confirm + close)** — the opt-in `save_to_kb` + `destination_folder_id` machinery for *connector* pipelines already shipped in Phases 5–6; this phase records the **inverse invariant for uploads** (uploads **always** save to KB) and verifies nothing in the pivot accidentally made KB-save the *default* for connector pipelines.

**The core design fact (drives everything):** uploads are **NOT executed by the Phase-6 run engine**. Phase 6's `execute_pipeline_run` fails any `connector_id IS NULL` run with `"uploads pipeline has no fetch executor"` (`06` §1). The existing upload routes remain the executor (they already create `Document`s + dispatch ETL); Phase 7 only **attaches an audit `PipelineRun`** to that flow and ensures the Uploads pipeline row exists. No `run_pipeline` enqueue, no engine change.

## Locked decisions (MVP)

| Concept | Decision |
|---------|----------|
| Uploads pipeline | **One singleton per workspace**, `connector_id = NULL`, `save_to_kb = true`, `schedule_cron = NULL` (never scheduled), `enabled = true`, `name = "Uploads"`. **Lazily get-or-created** on first upload (not at workspace creation — avoids backfilling every existing workspace). |
| Uniqueness / race-safety | A **partial unique index** `ON pipelines (workspace_id) WHERE connector_id IS NULL` makes "one Uploads pipeline per workspace" a DB invariant and lets get-or-create be race-safe via `INSERT … ON CONFLICT DO NOTHING` + re-`SELECT`. (Phase 5 already reserves `connector_id IS NULL` to mean "Uploads", so this index is exactly that semantic.) Small Phase-7 migration. |
| Run lifecycle | **Audit record, created terminal at request time.** The upload route inserts `PipelineRun(trigger=upload, status=succeeded, documents_indexed=<accepted file count>, started_at=finished_at=now())`. Per-file ETL outcomes continue to live on `Document.status` (`pending→ready/failed`, already Zero-synced). Rationale below. |
| Why not track per-file ETL into the run | The `fileupload` path fans out **N independent per-file Celery tasks** (`task_dispatcher.py:44`) with **no batch barrier**, and accurate "which docs belong to this run" needs the **`documents.pipeline_run_id` provenance column that Phase 5 deferred** (`05` §3 "Out of scope (provenance)"). Building a barrier is out of MVP scope; the run is an *upload event* record, matching the umbrella's "register a run that files were uploaded". |
| Billing | **No crawl billing for uploads** — uploads aren't crawls. `charged_micros` / `crawls_*` stay `NULL` on upload runs. Existing ETL/embedding credit behaviour (if any) is unchanged and orthogonal (`03c` only governs `web_crawl`). |
| Folder placement | The Uploads pipeline's `destination_folder_id` stays **NULL** — it is a singleton and cannot encode per-upload folders. Folder placement remains owned by the **existing upload code** (`fileupload` → root; `folder-upload` → its created/declared folder). The run/pipeline is **descriptive**, not the folder driver (unlike connector pipelines, where the engine reads `destination_folder_id`). |
| Surfaces wired | `POST /documents/fileupload` and `POST /documents/folder-upload` (both create `Document`s). The desktop precheck route `POST /documents/folder-mtime-check` (`documents_routes.py:1533`) creates nothing and is **not** wired; `folder-unlink` / `folder-sync-finalize` are delete/sync lifecycle, also out. |
| Connector-pipeline KB default | **Unchanged from Phase 5:** `save_to_kb` defaults `False` (`05` §2 `server_default="false"`). This phase only asserts uploads set it `true`; it does **not** flip the connector default. |

## Current state (cited)

### The upload routes (the executors we attach to)

- **`POST /documents/fileupload`** — `documents_routes.py:126-332`. Permission `DOCUMENTS_CREATE` (`:163-169`). Phase 1: create `Document(search_space_id, document_type=FILE, status=pending, created_by_id, …)` per file, dedup by `unique_identifier_hash` (`:217-266`), `commit` (`:278`). Phase 1.5: `store_document_file(...)` per doc (`:289-297`). Phase 2: `dispatcher.dispatch_file_processing(document_id=…)` per file (`:307-316`). Returns `document_ids` / `skipped_duplicates` (`:318-325`). **Creates no folder (root), no run record today.** `files_to_process` (`:213`) = the accepted (newly-queued) set; `skipped_duplicates` (`:214`) = already-`READY` dupes.
- **`POST /documents/folder-upload`** — `documents_routes.py:1598-1748`. Permission `DOCUMENTS_CREATE` (`:1623-1629`). Creates/reuses a root `Folder` (`:1673-1704`), writes temps, then dispatches **one** batch task `index_uploaded_folder_files_task.delay(...)` (`document_tasks.py:1403`) which has its own notification + heartbeat (`:1446-1457`) — i.e. a **real completion barrier** exists on this path (unlike `fileupload`). Returns `root_folder_id` + `file_count` (`:1743-1748`).
- **Dispatcher** — `task_dispatcher.py:12-52`: `dispatch_file_processing(...)` → `process_file_upload_with_document_task.delay(document_id=…)`, **one task per file**, fire-and-forget (no barrier).

### Phase 5/6 hand-offs this phase consumes

- `Pipeline.connector_id` **nullable**, `NULL = "non-connector pipeline (the Phase-7 Uploads pipeline)"` (`05` §"Pipeline → connector"; model `05` §2 `:105-106`). `PipelineRunTrigger.UPLOAD` already exists (`05` §1). `PipelineRun` has `trigger`, `status`, `documents_indexed`, `started_at`, `finished_at`, `charged_micros` (nullable) (`05` §3).
- **Phase 6 engine refuses uploads**: `if pipeline.connector_id is None: return fail(run, "uploads pipeline has no fetch executor")` (`06` §1) — confirms uploads must be recorded by the route, **not** enqueued to `run_pipeline`.
- **Chat tool** `get_pipeline_runs` (`06` §7) selects `PipelineRun` joined to `Pipeline` by `workspace_id` — so upload runs surface to the agent for free once they exist.
- **De-dup guard** (`06` §6) only touches **connector-backed** pipelines (`when connector_id is set`); the Uploads pipeline (`connector_id NULL`) is untouched by it. The **scheduler** (`06` §5 `_claim_due`) ignores the Uploads pipeline **two ways** — `schedule_cron IS NOT NULL` (NULL cron) **and** `connector_id IS NOT NULL` (the defense-in-depth filter `06` added at Phase 7's request). Both confirmed safe.

### Document model

- `Document` — `db.py:1348`: `document_type` (`:1352`, `DocumentType.FILE`), `unique_identifier_hash` (`:1365`), `folder_id` **nullable** (`:1389`, root/unfiled), `created_by_id` (`:1397`), plus `search_space_id`/`status`. KB membership = a `Document` row exists; uploads always create one ⇒ uploads are always "in the KB" by construction.

## Target design

### 1. `get_or_create_uploads_pipeline(session, workspace_id, created_by_id)` — `app/pipelines/uploads.py`

```python
async def get_or_create_uploads_pipeline(session, *, workspace_id: int, created_by_id) -> Pipeline:
    # fast path
    existing = (await session.execute(
        select(Pipeline).where(Pipeline.workspace_id == workspace_id,
                               Pipeline.connector_id.is_(None)))).scalar_one_or_none()
    if existing:
        return existing
    # race-safe create (partial unique index ux_pipelines_uploads_per_workspace)
    stmt = (pg_insert(Pipeline.__table__)
            .values(workspace_id=workspace_id, connector_id=None, name="Uploads",
                    save_to_kb=True, enabled=True, schedule_cron=None,
                    created_by_id=created_by_id, config={})
            .on_conflict_do_nothing(index_elements=[Pipeline.workspace_id],
                                    index_where=Pipeline.connector_id.is_(None)))
    await session.execute(stmt)
    await session.flush()
    return (await session.execute(
        select(Pipeline).where(Pipeline.workspace_id == workspace_id,
                               Pipeline.connector_id.is_(None)))).scalar_one()
```

- Lazy (first upload), idempotent, race-safe. `created_by_id` = the uploading user (becomes the pipeline's creator metadata; `SET NULL` on member deletion per Phase 5).
- Lives in the `app/pipelines/` package (created in Phase 6) so the upload route imports it without a route↔route dependency.
- **Implementation gotcha — core insert bypasses ORM defaults.** `Pipeline.updated_at`/`created_at` use **Python-side** `default=`/`onupdate=` callables (`05` §2 `:114-115`), which a core `pg_insert` does **not** fire. The `.values(...)` must set `created_at`/`updated_at` explicitly (e.g. `now`) — or implement get-or-create as **ORM-insert + `flush` inside a `session.begin_nested()` SAVEPOINT, catching `IntegrityError` → rollback savepoint → re-`SELECT`** (avoids the core/ORM default mismatch entirely; the SAVEPOINT keeps the route's outer transaction intact). Either is fine; the SAVEPOINT form is closer to the ORM conventions used elsewhere.

### 2. Register an upload run (shared helper) — `app/pipelines/uploads.py`

```python
async def record_upload_run(session, *, workspace_id, created_by_id, documents_indexed: int) -> PipelineRun:
    pipeline = await get_or_create_uploads_pipeline(session, workspace_id=workspace_id,
                                                    created_by_id=created_by_id)
    now = datetime.now(UTC)
    run = PipelineRun(pipeline_id=pipeline.id, trigger=PipelineRunTrigger.UPLOAD,
                      status=PipelineRunStatus.SUCCEEDED,
                      documents_indexed=documents_indexed, started_at=now, finished_at=now)
    session.add(run)
    return run   # caller commits (folds into the route's existing commit)
```

- **Terminal-at-creation** (locked decision): records the upload event with the accepted file count. `crawls_*` / `charged_micros` left NULL (not a crawl).
- Caller does **not** await any Celery task — the run is purely the route's own DB write, folded into the route's existing transaction (no extra round-trips, no new failure mode that could block the upload).

### 3. Wire `POST /documents/fileupload`

After Phase 2 dispatch (`documents_routes.py:307-316`), before building the response, add:

```python
if files_to_process:                              # only when something was actually queued
    await record_upload_run(session, workspace_id=workspace_id,
                            created_by_id=str(user.id),
                            documents_indexed=len(files_to_process))
    await session.commit()
```

- Count = `len(files_to_process)` (the newly-created/re-queued docs), **excluding** `skipped_duplicates` (already-READY no-ops). An all-duplicate upload records **no** run (nothing ingested).
- **Best-effort, non-blocking — and the try/except is mandatory, not cosmetic.** The route has an **outer `except Exception` → `session.rollback()` → HTTP 500** (`documents_routes.py:328-332`). If `record_upload_run` raised unguarded, it would hit that handler and **500 an upload whose documents are already committed + dispatched**. So the call MUST be wrapped in its **own inner `try/except`** that swallows: on failure `await session.rollback()` (discards only the run insert — documents were committed at `:278`/`:304`) + `logger.warning(...)`, then fall through to the response. A run-record write must **never** fail the upload. (Mirrors the `store_document_file` best-effort pattern at `:298-303`.)

### 4. Wire `POST /documents/folder-upload`

Folder-upload dispatches one batch task, so record the run at request time with the file count (`documents_routes.py` before the `return` at `:1743`):

```python
await record_upload_run(session, workspace_id=workspace_id,
                        created_by_id=str(user.id), documents_indexed=len(files))
await session.commit()   # best-effort / logged, same as §3
```

- Uses `len(files)` (folder-upload doesn't pre-dedup in the route; dedup happens inside the batch task).
- **Optional richer accounting (deferred):** because this path *has* a barrier (`index_uploaded_folder_files_task`), a later enhancement could create the run `pending` here and flip it `succeeded`/`failed` from inside the task (it already manages a notification lifecycle). MVP keeps it uniform with `fileupload` (terminal-at-request). Flagged, not built.

### 5. Migration (one small file) — partial unique index

```sql
CREATE UNIQUE INDEX IF NOT EXISTS ux_pipelines_uploads_per_workspace
    ON pipelines (workspace_id) WHERE connector_id IS NULL;
```

- Chain after the then-current head (verify `alembic heads`). Enforces the singleton + powers `ON CONFLICT`. `downgrade()` drops it.
- **Pre-flight (safety):** if any workspace somehow already has >1 `connector_id IS NULL` pipeline (shouldn't, pre-Phase-7), the `CREATE UNIQUE INDEX` fails — the migration docstring notes a dedup step (keep the oldest, delete extras) just in case. Expectation: none exist (uploads pipelines are introduced *here*).

### 6. KB-save-secondary verification (no new code, a guard)

- Uploads pipeline hardcodes `save_to_kb=True` (§1) — uploads always land in the KB (a `Document` row), matching the umbrella invariant.
- Confirm Phase 5's connector-pipeline default is still `save_to_kb=False` (`05` §2) — i.e. KB-save is **opt-in for connectors, mandatory for uploads**. Add a test asserting both defaults so a future change can't silently make connector KB-save the default.

### 7. Guard the generic Phase-5 CRUD against the system Uploads pipeline (the gap)

The Uploads pipeline is a **system-managed** row (`connector_id IS NULL`, auto-created by §1). Phase 5's generic `/pipelines` CRUD doesn't know it's special, which opens three footguns — Phase 7 closes them:

| Phase-5 endpoint | Problem if left generic | Phase-7 guard |
|------------------|-------------------------|---------------|
| `POST /pipelines` | Phase 5 **allows `connector_id=None`** (`05` §7 create + test). A user could hand-create a rogue/duplicate non-connector pipeline. | **Reject `connector_id is None` with 4xx** — non-connector pipelines are system-managed (auto-created on upload), not user-created. This **supersedes** Phase 5's "`connector_id=None` → allowed" create test (update it). The partial unique index (§5) is the DB backstop. |
| `POST /pipelines/{id}/run` | Manual-running the Uploads pipeline enqueues `run_pipeline`, which the Phase-6 engine **fails** (`"uploads pipeline has no fetch executor"`) → a confusing **FAILED** manual run every click. | **Reject `connector_id IS NULL` with 4xx** ("uploads are triggered by uploading files, not a manual run") — before creating the run row / enqueuing. |
| `PUT /pipelines/{id}` | Setting `schedule_cron` on the Uploads pipeline makes the scheduler eligible-by-cron → **perpetually-failing scheduled runs** (engine refuses null-connector). Editing `save_to_kb`/`destination_folder_id` is silently **ineffective** (uploads are route-driven, not engine-driven). | **Reject schedule edits (`schedule_cron`/`schedule_timezone`) on `connector_id IS NULL` pipelines with 4xx.** (`connector_id` is already immutable per Phase 5.) Optionally reject all PUTs to the Uploads pipeline; minimally block the scheduling fields. Belt-and-suspenders: Phase 6's `_claim_due` also filters `connector_id IS NOT NULL` (`06` §5). |
| `DELETE /pipelines/{id}` | Deleting the Uploads pipeline cascades its run history. | **Allowed** (MVP): it is **lazily re-created** on the next upload (§1); only past upload-run history is lost. Note in UI copy later; an optional hard block is a small follow-up. |

Net: after Phase 7, the only non-connector pipeline that can exist is the **system Uploads pipeline**, it is never user-created / manually-run / scheduled, and the scheduler ignores it two ways (NULL cron *and* the `connector_id IS NOT NULL` filter).

## Work items

1. **`app/pipelines/uploads.py`**: `get_or_create_uploads_pipeline` (race-safe via `ON CONFLICT`) + `record_upload_run` (terminal upload run).
2. **Migration**: partial unique index `ux_pipelines_uploads_per_workspace ON pipelines(workspace_id) WHERE connector_id IS NULL`; docstring dedup pre-flight note; `downgrade` drops it.
3. **Wire `fileupload`** (`documents_routes.py:126-332`): call `record_upload_run(documents_indexed=len(files_to_process))` after dispatch, in an **inner** best-effort try/except (must not reach the route's outer 500 handler), only when `files_to_process` non-empty.
4. **Wire `folder-upload`** (`documents_routes.py:1598-1748`): call `record_upload_run(documents_indexed=len(files))` before the response, same inner best-effort guard.
5. **Guard the generic CRUD** (§7): `POST /pipelines` rejects `connector_id is None`; `/run` rejects `connector_id IS NULL`; `PUT` rejects schedule edits on `connector_id IS NULL`. Update Phase 5's "`connector_id=None` → allowed" create test accordingly. (Phase 6's `_claim_due` `connector_id IS NOT NULL` filter is the scheduler backstop.)
6. **Tests** (below).

## Tests

- **First upload creates the pipeline**: `fileupload` into a fresh workspace → exactly one `connector_id IS NULL` pipeline named "Uploads" with `save_to_kb=True`; a `PipelineRun(trigger=upload, status=succeeded, documents_indexed=N)`.
- **Subsequent uploads reuse it**: a second `fileupload` → still one Uploads pipeline, two upload runs. Concurrency: two simultaneous first-uploads (race) → still exactly one pipeline (partial-unique + `ON CONFLICT`), two runs.
- **Duplicate-only upload**: re-uploading already-READY files (`skipped_duplicates == len(files)`, `files_to_process == []`) → **no** run recorded.
- **folder-upload**: records one upload run with `documents_indexed=len(files)`; the existing batch task/folder behaviour is unchanged.
- **No crawl billing**: upload runs have `charged_micros IS NULL`, `crawls_* IS NULL`; no `web_crawl` `TokenUsage` row is written.
- **Engine still refuses uploads**: enqueuing `run_pipeline` for an Uploads pipeline's run (or a NULL-connector pipeline) → Phase-6 engine fails it cleanly (regression guard for `06` §1). Confirms uploads are never engine-executed.
- **Scheduler ignores uploads (two ways)**: the Phase-6 tick never selects the Uploads pipeline — both because `schedule_cron IS NULL` and because `_claim_due` filters `connector_id IS NOT NULL`. Add a case: even with a cron forced onto a NULL-connector row (direct DB), `_claim_due` still skips it.
- **CRUD guards (§7)**: `POST /pipelines` with `connector_id=None` → 4xx; `POST /pipelines/{uploads_id}/run` → 4xx (no FAILED run created); `PUT` setting `schedule_cron` on the Uploads pipeline → 4xx; `DELETE` of the Uploads pipeline → allowed, and the next upload re-creates it.
- **Chat tool surfaces uploads**: `get_pipeline_runs` returns the upload runs for the workspace (trigger=upload), scoped correctly.
- **KB defaults guard**: Uploads pipeline `save_to_kb=True`; a connector pipeline created without `save_to_kb` defaults `False` (§6).
- **Best-effort isolation**: a forced failure inside `record_upload_run` does not fail the upload request (documents still created + dispatched, 2xx returned).

## Risks / trade-offs

- **Run is an upload *event*, not per-file ETL truth.** `status=succeeded` + `documents_indexed=<accepted count>` is stamped at request time; individual files may still fail ETL afterward (visible on `Document.status`, not reflected back onto the run). Accepted for MVP — accurate per-file roll-up needs the deferred `documents.pipeline_run_id` provenance column. Documented; the folder-upload barrier is the natural place to add real status later (§4).
- **Singleton Uploads pipeline ⇒ no per-upload folder on the pipeline.** `destination_folder_id` stays NULL; folder placement stays in the upload code. Fine because the upload run is descriptive, not engine-driven. If product later wants "uploads to folder X" as a first-class pipeline, that's a connector-less pipeline variant (additive).
- **Partial-unique index assumes `connector_id IS NULL ⇔ Uploads`.** True for MVP (Phase 5 reserved NULL for Uploads, and Phase 6 fails NULL-connector runs). If a *second* kind of connector-less pipeline is ever introduced, replace the index predicate with an explicit `kind`/discriminator column (additive migration) — flagged so the NULL-overload doesn't silently block it.
- **Best-effort run write can be skipped on error.** If `record_upload_run` raises (e.g. transient DB error) the upload still succeeds but no run is logged — an audit gap, never a data-loss or user-facing failure. Acceptable: the `Document` rows (the actual KB content) are the source of truth; the run is supplementary history.
- **No backfill for historical uploads.** Pre-Phase-7 uploads have no upload runs (pipeline is created lazily on the next upload). Accepted — run history starts accumulating from rollout; no migration backfills synthetic runs.
- **Upload run doesn't capture the uploader.** `PipelineRun` has no user column (Phase 5), so the run records *what/when/how-many*, not *who* — the per-document uploader is still on `Document.created_by_id`, and the pipeline's `created_by` is just whoever triggered the first-ever upload. If per-run attribution is wanted, add a nullable `triggered_by_id` to `pipeline_runs` (additive Phase-5 model change); deferred.
- **`enabled=True` on a never-scheduled pipeline.** The Uploads pipeline is `enabled=True` with NULL cron — harmless (scheduler ignores it via NULL cron *and* the `connector_id IS NOT NULL` filter); `enabled` only ever gates scheduling, which uploads never use. Left `True` so a future UI can show it as an active pipeline.
- **CRUD-guard coupling to Phase 5.** Phase 7 tightens Phase 5's create contract (`connector_id=None` now rejected) and adds `/run` + `PUT` guards. This is a documented evolution (Phase 7 ships after 5/6); the Phase-5 create test is updated here, not left contradictory.

## Out of scope (hand-offs)

- **`documents.pipeline_run_id` provenance** (per-file → run linkage, accurate ETL roll-up, folder-upload barrier-driven status) → post-MVP (touches `documents`).
- **Engine execution of uploads** — intentionally never; uploads are route-recorded (`06` fails NULL-connector runs by design).
- **Migrating connector periodic indexing into pipelines** — still COEXIST (Phase 5 decision); not revisited here.
- **Public pay-as-you-go API / MCP KB server** → post-MVP (umbrella "Deferred").
- **Frontend** — surfacing the Uploads pipeline + upload runs in the Pipelines UI, "uploads always saved to KB" copy → frontend umbrella.
