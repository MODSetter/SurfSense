# Phase 5 — Pipelines data model (tables, schemas, migration, Zero, CRUD + run routes)

> Part of the **CI Pivot MVP**. See `00-umbrella-plan.md` (Phase 5).
> Precondition: Phases 1–2 (rename) live, Phase 4a (connector registry) live. Siblings ahead: `06-pipelines-exec.md` (run engine + scheduling), `07-upload-pipeline-kb.md` (uploads-as-pipeline).

> **Implementation note (post-rename).** This phase adds **brand-new** tables, created *after* the rename, so they use the canonical names natively: table `workspaces`, column `workspace_id`, ORM class `Workspace`. Phases 1–2 are now **SHIPPED**, so the live code uses the `workspace_*` names. Existing code cited below that still shows the **pre-rename** names (`searchspaces`/`search_space_id`/`SearchSpace`) was captured pre-rename — substitute the `workspace_*` equivalent and grep the new name. Locate code by **symbol/grep**, not the absolute line numbers cited here (the rename + Phase 3/4 migrations shift them).

## Objective

Introduce two first-class tables — `pipelines` and `pipeline_runs` — plus their enums, Pydantic schemas, one Alembic migration, the backend Zero-publication entries, and the HTTP routes (CRUD + manual-run trigger + list/get runs). **This phase is data-model + API surface only.** The actual run **engine** (invoke connector fetch → optional KB save → write run record), scheduling tick, crawl-billing wiring, and chat-agent context exposure are **Phase 6**; wiring file upload onto an "Uploads" pipeline is **Phase 7**. The manual-run endpoint here **creates a `PipelineRun` row and enqueues the Phase-6 task** (which is a stub until Phase 6 lands), so the surface is testable end-to-end without the engine.

A **Pipeline** = a saved, runnable fetch over a Type-1 data source: it references a connector + per-pipeline config + an optional cron schedule + a KB destination (`save_to_kb` + `destination_folder_id`). A **PipelineRun** = one immutable execution record (manual / scheduled / upload), carrying status, timing, doc counts, error, an optional raw-result blob ref, and a billing idempotency field.

## Locked model (MVP)

| Concept | Decision |
|---------|----------|
| Tables | `pipelines` (mutable definition) + `pipeline_runs` (append-only execution record). Mirrors the `automations` / `automation_runs` split. |
| Where the ORM lives | In **`app/db.py`** alongside `Folder`/`Document`/`SearchSourceConnector`/`Log` (the other core, Zero-published, cross-referenced entities), **not** a separate package. Rationale: needs `back_populates` on `Workspace`/`User`/`SearchSourceConnector`/`Folder`, a Zero entry, and a `schemas/` Pydantic mirror — all lowest-friction in `db.py`. (The `automations` package avoided `db.py` but pays for it with string-relationships + import-time model registration; pipelines are more core, like connectors.) |
| Pipeline → connector | `connector_id` **nullable**, FK `ON DELETE CASCADE`. A connector-backed pipeline points at a Type-1 source; **`NULL` = a non-connector pipeline** (the Phase-7 "Uploads" pipeline). Eligibility (`DATA_SOURCE` + `AVAILABLE`) is enforced at create via Phase 4a's `is_pipeline_eligible` (app-level, not a DB constraint — the registry is code) **and re-checked at run time in Phase 6** (the static registry can flip a type to `MIGRATING` on deploy, stranding existing pipelines). |
| Ownership | `created_by_id` FK `ON DELETE SET NULL`, **nullable** — creator metadata only (workspace-shared, like `Folder`/`Automation`), not an owner. Billing targets the workspace owner (03c). |
| Schedule representation | `schedule_cron VARCHAR NULL` (NULL = manual-only) + `schedule_timezone VARCHAR NOT NULL DEFAULT 'UTC'` + `enabled BOOLEAN` + `next_scheduled_at TIMESTAMPTZ NULL` (computed by Phase 6's tick). Chosen over a bare `frequency_minutes` int to match the **automations** schedule model and reuse its cron util (`automations/triggers/builtin/schedule/cron.py`), which takes **both** a cron and a timezone (`compute_next_fire_at(cron, timezone, …)`). |
| KB destination | `save_to_kb BOOLEAN` + `destination_folder_id` FK `ON DELETE SET NULL` (nullable). `save_to_kb=true` with NULL folder ⇒ index to workspace root (`documents.folder_id` is nullable). No DB CHECK couples them (an FK `SET NULL` would violate a conditional CHECK); the pairing is validated at the API only. |
| Run status enum | `pipeline_run_status`: `pending`, `running`, `succeeded`, `failed`, `cancelled` (mirrors `automation_run_status` minus `timed_out`). |
| Run trigger enum | `pipeline_run_trigger`: `manual`, `scheduled`, `upload`. |
| Periodic coexistence | **COEXIST, do not migrate** (resolves umbrella open item §2 — see "Periodic-indexing coexistence" below). |
| Zero publication | Publish **both tables full-row** (`None`), mirroring `folders` / `search_source_connectors`. Avoids the column-list `_0_version` seam entirely; neither table has a bulky column. |
| Naming | The CI **`Pipeline`** entity (a saved, runnable fetch) is distinct from the existing **`IndexingPipelineService`** (`app/indexing_pipeline/`, the KB-ingest service). They coexist but do **not** share a code path for the MVP: Phase 6's WebURL executor reuses the crawler's own KB-write path (`index_crawled_urls`, extended with `folder_id`), **not** `IndexingPipelineService` (which is the file/Composio ingest path — and is what Phase 7's uploads flow builds on). Name routes/services `pipeline_*` (not `indexing_pipeline_*`) to keep the two legible. |

## Current state (cited)

### The precedent: `automations` / `automation_runs`

The cleanest existing analogue to model against.

- Editable parent: `Automation` — `automations/persistence/models/automation.py:24`. Pattern: `BaseModel, TimestampMixin`; `search_space_id` FK CASCADE (`:27`), `created_by_user_id` FK SET NULL (`:34`), a native enum `status` with `values_callable=lambda x: [e.value for e in x]` (`:44–54`), a JSONB `definition` (`:56`), an explicit `updated_at` with `onupdate` (`:60–66`), and `runs = relationship(..., cascade="all, delete-orphan", passive_deletes=True)` (`:76–81`).
- Append-only child: `AutomationRun` — `automations/persistence/models/run.py:20`. `automation_id` FK CASCADE (`:23`), native enum `status` default `pending` (`:37–47`), JSONB `error` (`:60`), nullable `started_at`/`finished_at` (`:62–63`).
- Enums: `automations/persistence/enums/run_status.py:8` (`RunStatus(StrEnum)` = pending/running/succeeded/failed/cancelled/timed_out).
- Migration: `alembic/versions/144_add_automation_tables.py` — the **exact template** for this phase: idempotent `CREATE TYPE ... DO $$ IF NOT EXISTS` guards (`:31–76`), `CREATE TABLE IF NOT EXISTS` with inline FKs (`:79–96`), `CREATE INDEX IF NOT EXISTS` per FK/status/created_at (`:97–111`), a **partial "due" index** for the schedule scan (`ix_automation_triggers_due`, `:144–152`), and symmetric `downgrade()` dropping indexes→tables→types (`:190–213`).
- Run routes: `automations/api/run.py` — `GET /automations/{id}/runs` (list, paginated `limit/offset`, `:13–30`) + `GET /automations/{id}/runs/{run_id}` (detail, `:33–44`). The exact shape to mirror for pipeline runs.

### The other core tables (relationship + column conventions)

- Base: `TimestampMixin` (gives `created_at`, `db.py:487`) + `BaseModel` (`id SERIAL PK`, `db.py:498`). Tables wanting a mutable `updated_at` declare it explicitly (see `Folder.updated_at` `db.py:1333–1339`, with `onupdate` + `index=True`).
- `SearchSourceConnector` — `db.py:1829`. `connector_type` native enum (`:1867`), `is_indexable` (`:1868`), periodic fields `periodic_indexing_enabled`/`indexing_frequency_minutes`/`next_scheduled_at` (`:1880–1882`), `search_space_id` FK CASCADE (`:1884`), `user_id` FK CASCADE (`:1891`), `documents = relationship(...)` (`:1897`). **Pipelines FK this table** (`connector_id`).
- `Folder` — `db.py:1310`. `search_space_id` FK CASCADE (`:1321`), `created_by_id` FK SET NULL (`:1327`). **Pipelines FK this table** (`destination_folder_id`, SET NULL).
- `Document.folder_id` is nullable (root/unfiled docs exist) — confirmed by `DOCUMENT_COLS` including `folder_id` (`zero_publication.py:32`) and `Document.folder` `passive_deletes=True` (`db.py:1345`). Lets `save_to_kb` work with a NULL destination.
- `Permission` enum has `CONNECTORS_CREATE/READ/UPDATE/DELETE` (`db.py:345–348`); routes authz via `check_permission(session, auth, search_space_id, Permission.X.value, msg)` (`folders_routes.py:42–48`) with `auth = Depends(get_auth_context)` + `session = Depends(get_async_session)` (`folders_routes.py:36–37`). **Reuse the `CONNECTORS_*` permissions** for pipelines (no new permission needed for MVP).

### Schema conventions

- `schemas/base.py`: `IDModel` (`id:int`, `:11`) + `TimestampModel` (`created_at`, `:6`), both `ConfigDict(from_attributes=True)`.
- `schemas/search_source_connector.py`: `Base` → `Create(Base)` → `Update(BaseModel, all-Optional)` → `Read(Base, IDModel, TimestampModel)` with `model_config = ConfigDict(from_attributes=True)` and `field_validator`/`model_validator` for config consistency (`:24–56`). The shape to mirror for `schemas/pipeline.py`.

### Zero publication mechanics

- `zero_publication.py`: `ZERO_PUBLICATION` map (`:81–94`; line numbers post-`main`-merge, which added `automations`/`new_chat_threads` entries) is the single source of truth; `None` ⇒ publish full row (e.g. `folders`, `search_source_connectors`), a list ⇒ column subset (e.g. `AUTOMATION_RUN_COLS` `:44–53`). `apply_publication(conn)` (`:163`) reconciles via `ALTER PUBLICATION ... SET TABLE`; a migration just calls it (template: `159_publish_podcasts_to_zero.py:21–22`). `_format_table_entry` omits a table until it physically exists with all its canonical columns (`:125–152`), so the migration **must create the tables before** calling `apply_publication`. The `_0_version` allowlist (`{"documents","user","podcasts"}`, `:118`) applies **only to column-list tables** — irrelevant here since we publish full-row.

### The meta-scheduler we coexist with (Phase-6 reuse target)

- `tasks/celery_tasks/schedule_checker_task.py:17` — `check_periodic_schedules_task`, runs every minute, scans `SearchSourceConnector` where `periodic_indexing_enabled AND next_scheduled_at <= now` (`:33–39`) and dispatches per-type Celery tasks. This is the **connector-level** periodic path and is **untouched** by Phase 5. Phase 6 adds a sibling scan over `pipelines.next_scheduled_at`.
- `utils/periodic_scheduler.py:30` — `create_periodic_schedule` (first-run trigger helper). Reference for Phase 6's pipeline scheduler.

### Alembic head

As of the latest `main` sync the head is **`169`** (`alembic/versions/169_migrate_google_oauth_account_ids_to_sub.py`; chain `166→167→168→169`, sequential integer-prefixed files). By the time Phase 5 is implemented, Phase 1 (rename) and Phase 4b (search-enum drop) have each added a migration ahead of `169`. **Set `down_revision` to the then-current head** — verify with `alembic heads`; do not hardcode a number.

## Target design

### 1. Enums (`db.py`, near the other `StrEnum`s)

```python
class PipelineRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PipelineRunTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    UPLOAD = "upload"
```

Mapped with native PG enum types `pipeline_run_status` / `pipeline_run_trigger` using the `values_callable=lambda x: [e.value for e in x]` convention (matches `Automation.status` `automation.py:46–49`, so the DB stores lowercase values, not the Python member names).

### 2. `pipelines` table (`db.py`)

```python
class Pipeline(BaseModel, TimestampMixin):
    __tablename__ = "pipelines"

    name = Column(String(200), nullable=False, index=True)
    config = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))  # per-pipeline overrides (URL list, crawl opts, proxy override seam)

    save_to_kb = Column(Boolean, nullable=False, default=False, server_default="false")

    # Schedule (NULL cron = manual-only). next_scheduled_at is owned/written by Phase 6's tick.
    schedule_cron = Column(String(120), nullable=True)
    schedule_timezone = Column(String(64), nullable=False, default="UTC", server_default="UTC")  # cron util needs a tz (compute_next_fire_at)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    next_scheduled_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # NULL connector_id = non-connector pipeline (Phase-7 Uploads).
    connector_id = Column(Integer, ForeignKey("search_source_connectors.id", ondelete="CASCADE"), nullable=True, index=True)
    destination_folder_id = Column(Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    # Creator metadata, NOT owner: pipelines are workspace-shared (like folders/automations),
    # so member deletion must NOT nuke them — SET NULL, nullable. Billing targets the workspace
    # owner (03c), not this field. Phase 6 resolves the acting user as created_by ?? workspace owner.
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)

    updated_at = Column(TIMESTAMP(timezone=True), nullable=False,
                        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True)

    connector = relationship("SearchSourceConnector", back_populates="pipelines")
    destination_folder = relationship("Folder")
    workspace = relationship("Workspace", back_populates="pipelines")
    created_by = relationship("User", back_populates="pipelines")
    runs = relationship("PipelineRun", back_populates="pipeline", cascade="all, delete-orphan", passive_deletes=True)
```

Add the inverse `pipelines = relationship("Pipeline", back_populates=...)` on **`Workspace`**, **`User`**, and **`SearchSourceConnector`** (mirror how `SearchSpace.search_source_connectors` / `User.search_source_connectors` are declared at `db.py:1887–1894`; the `created_by`/SET-NULL side mirrors `Folder.created_by` `db.py:1344` and `Automation.created_by` `automation.py:69`). `destination_folder` is intentionally one-directional (no back_populates on `Folder`) to keep the folder model lean.

> **Ownership decision (review).** Earlier draft used connector-style `user_id NOT NULL CASCADE`. Corrected to `created_by_id … SET NULL` because pipelines are **workspace-shared** content (closer to `Folder`/`Automation` than to the per-user `SearchSourceConnector`): removing a member must not delete the workspace's pipelines or erase run-history audit. For *connector-backed* pipelines this also avoids surprising double-cascade (the connector's own `user_id CASCADE` would already drop them on member deletion via `connector_id`); for the Phase-7 Uploads pipeline (`connector_id` NULL) it's the only thing keeping the pipeline alive after its creator leaves.

> **FK target naming:** Phases 1–2 are **SHIPPED**, so the table is `workspaces` and the column `workspace_id` — author the FK against `workspaces` / `workspace_id`. (The earlier "if sequencing slips before the rename" caveat is now moot.)

### 3. `pipeline_runs` table (`db.py`)

```python
class PipelineRun(BaseModel, TimestampMixin):
    __tablename__ = "pipeline_runs"

    pipeline_id = Column(Integer, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(SQLAlchemyEnum(PipelineRunStatus, name="pipeline_run_status",
                    values_callable=lambda x: [e.value for e in x]),
                    nullable=False, default=PipelineRunStatus.PENDING,
                    server_default=PipelineRunStatus.PENDING.value, index=True)
    trigger = Column(SQLAlchemyEnum(PipelineRunTrigger, name="pipeline_run_trigger",
                     values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)

    # Result accounting (written by Phase 6).
    documents_indexed = Column(Integer, nullable=True)
    crawls_attempted = Column(Integer, nullable=True)
    crawls_succeeded = Column(Integer, nullable=True)
    error = Column(JSONB, nullable=True)

    # Raw fetch blob ref for save_to_kb=false runs (Phase 6 writes via file_storage). Just a key/path string.
    result_blob_key = Column(String, nullable=True)

    # Crawl-billing idempotency (carry-over from 03c / umbrella Phase 6 §105): micro-USD charged for this run.
    charged_micros = Column(BigInteger, nullable=True)

    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)

    pipeline = relationship("Pipeline", back_populates="runs")
```

These extra columns (`crawls_*`, `result_blob_key`, `charged_micros`) are added **now** so Phase 6 needs **no second migration** — they sit unused until the engine writes them. (`charged_micros` directly satisfies umbrella Phase 6 line 105's "record `charged_micros` on the `PipelineRun` for idempotency".)

> **Out of scope (provenance):** linking individual `documents` back to the `pipeline_run` that produced them (a `documents.pipeline_run_id` column) is **not** in this phase — it would touch the existing `documents` table. Defer to Phase 6/7 if run-level provenance is wanted.

### 4. Migration (one file, `144`-shaped)

Chain after the then-current head. In `upgrade()`:

1. `CREATE TYPE pipeline_run_status` + `pipeline_run_trigger` behind `DO $$ IF NOT EXISTS` guards (copy `144:31–76`).
2. `CREATE TABLE IF NOT EXISTS pipelines (...)` with inline FKs: `workspace_id → workspaces(id) ON DELETE CASCADE` (NOT NULL), `connector_id → search_source_connectors(id) ON DELETE CASCADE` (nullable), `destination_folder_id → folders(id) ON DELETE SET NULL` (nullable), `created_by_id → "user"(id) ON DELETE SET NULL` (nullable; note the quoted `"user"` table). `id SERIAL PK`, `created_at`/`updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `config JSONB NOT NULL DEFAULT '{}'::jsonb`, `schedule_timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'`.
3. `CREATE TABLE IF NOT EXISTS pipeline_runs (...)`.
4. Indexes (`CREATE INDEX IF NOT EXISTS`): per FK (`workspace_id`, `created_by_id`, `connector_id`, `destination_folder_id`, `pipeline_id`), plus `status`, `created_at`, `updated_at`, `name`, `trigger`. Add the **partial "due" index** for Phase 6's tick:

```sql
CREATE INDEX IF NOT EXISTS ix_pipelines_due
    ON pipelines (next_scheduled_at)
    WHERE enabled = true AND next_scheduled_at IS NOT NULL;
```

5. `from app.zero_publication import apply_publication; apply_publication(op.get_bind())` **after** the tables exist (so `_format_table_entry` includes them). Requires the `ZERO_PUBLICATION` code change (§6) to be in the tree.

`downgrade()`: drop indexes → `pipeline_runs` → `pipelines` → both types (symmetric to `144:190–213`). (The publication reconcile is intentionally not reversed — historical publication shapes are immutable, per `159:25–27`.)

### 5. Pydantic schemas (`app/schemas/pipeline.py`, exported via `app/schemas/__init__.py`)

```python
class PipelineBase(BaseModel):
    name: str
    connector_id: int | None = None
    config: dict[str, Any] = {}
    save_to_kb: bool = False
    destination_folder_id: int | None = None
    schedule_cron: str | None = None
    schedule_timezone: str = "UTC"
    enabled: bool = True

class PipelineCreate(PipelineBase):
    workspace_id: int          # required on create (path/body), like FolderCreate.search_space_id

class PipelineUpdate(BaseModel):  # all-Optional, like SearchSourceConnectorUpdate
    name: str | None = None
    config: dict[str, Any] | None = None
    save_to_kb: bool | None = None
    destination_folder_id: int | None = None
    schedule_cron: str | None = None
    schedule_timezone: str | None = None
    enabled: bool | None = None
    # connector_id is immutable after create (re-create to re-point); not in Update.

class PipelineRead(PipelineBase, IDModel, TimestampModel):
    workspace_id: int
    created_by_id: uuid.UUID | None = None
    next_scheduled_at: datetime | None = None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PipelineRunRead(IDModel, TimestampModel):
    pipeline_id: int
    status: PipelineRunStatus
    trigger: PipelineRunTrigger
    documents_indexed: int | None = None
    crawls_attempted: int | None = None
    crawls_succeeded: int | None = None
    error: dict[str, Any] | None = None
    charged_micros: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

class PipelineRunList(BaseModel):
    items: list[PipelineRunRead]
    total: int
```

**Validators:**

- `schedule_cron` + `schedule_timezone` (when cron not None): validate together with the existing automations cron util `validate_cron(cron, timezone)` (`automations/triggers/builtin/schedule/cron.py:15`) so a bad expression **or** bad IANA timezone 422s at create, not at the Phase-6 tick. (`schedule_timezone` is consumed by Phase 6's `compute_next_fire_at`; default `"UTC"`.)
- The `save_to_kb` ⇄ `destination_folder_id` pairing and **connector eligibility** are validated in the **route** (they need a DB session: folder-in-workspace check + `is_pipeline_eligible(connector.connector_type)`), not in the pure schema validator — mirroring how `folders_routes` validates parent-in-search-space in the handler (`folders_routes.py:54–58`).

### 6. Zero publication (`zero_publication.py`)

Add to `ZERO_PUBLICATION` (`:81–94`), both **full-row**:

```python
    "pipelines": None,
    "pipeline_runs": None,
```

Full-row (like `folders`/`search_source_connectors`) — no `_0_version` allowlist edit needed, no column-drift migrations later. (If a bulky column is ever added and must be excluded, switch that table to an explicit COLS list and handle the `_0_version` seam at `:118` then.) `verify_publication` will then expect both tables; the migration's `apply_publication` call (§4) reconciles them.

> **Client sync is not live until the frontend lands (safe).** Publishing backend-side only makes the rows *available* to Zero; nothing syncs to a client until the (deferred) frontend Zero schema + permissions include these tables. Publishing now is harmless and matches the existing pattern (e.g. `automation_runs` was published by migration before/independent of its UI). This entry exists so the chat-agent run-history context (Phase 6) and a later Pipelines UI get push for free.

### 7. Routes (`app/routes/pipelines_routes.py`, registered in `routes/__init__.py`)

Follow `folders_routes` for authz (`check_permission` + `get_auth_context` + `get_async_session`) and `automations/api/run.py` for the run-list shape. Register the router in `routes/__init__.py` near `search_source_connectors_router` (`:105`).

| Method + path | Behaviour | AuthZ |
|---------------|-----------|-------|
| `POST /pipelines` | Create. Validate: workspace access; if `connector_id`, load it, assert same workspace + `is_pipeline_eligible` (4xx otherwise); if `destination_folder_id`, assert folder in same workspace; `save_to_kb=true` allowed with NULL folder (→ root). Set `created_by_id = auth.user.id`. Persist; return `PipelineRead`. | `CONNECTORS_CREATE` |
| `GET /pipelines?workspace_id=` | List pipelines in a workspace. | `CONNECTORS_READ` |
| `GET /pipelines/{id}` | Read one. | `CONNECTORS_READ` |
| `PUT /pipelines/{id}` | Update (all-optional). Re-validate folder-in-workspace + cron if changed. | `CONNECTORS_UPDATE` |
| `DELETE /pipelines/{id}` | Delete (runs cascade). | `CONNECTORS_DELETE` |
| `POST /pipelines/{id}/run` | **Manual trigger.** Insert a `PipelineRun(status=pending, trigger=manual)`, enqueue the Phase-6 Celery task with the run id, return the run. Until Phase 6, the task is a stub (no-op/marks failed) — the row + enqueue path are what this phase delivers. (Concurrency control — block a second run while one is in flight — is deferred to Phase 6, reusing the connector indexing Redis locks `utils/indexing_locks.py`.) | `CONNECTORS_UPDATE` |
| `GET /pipelines/{id}/runs?limit=&offset=` | List runs newest-first, paginated (`limit` 1–200 default 50, `offset` ≥0) → `PipelineRunList`. Mirror `automations/api/run.py:13–30`. | `CONNECTORS_READ` |
| `GET /pipelines/{id}/runs/{run_id}` | Run detail. | `CONNECTORS_READ` |

All handlers scope by the pipeline's `workspace_id` and 404 on cross-workspace access. A thin `PipelineService` (mirroring `automations` `RunService`) is optional; for MVP, inline session logic in the routes (as `folders_routes` does) is acceptable.

## Periodic-indexing coexistence (resolves umbrella open item §2)

**Decision: COEXIST for MVP — do NOT migrate connector periodic config into pipelines.**

- The existing `SearchSourceConnector.periodic_indexing_enabled` / `next_scheduled_at` path and its meta-scheduler (`schedule_checker_task.py`) **stay fully functional and untouched** in Phases 5–6. Pipelines are **purely additive**: a new `pipelines.next_scheduled_at` scan (Phase 6) runs **alongside** the connector scan.
- **Rationale:** (a) lowest risk + smallest diff (no backfill of existing connector schedules into pipeline rows, no data migration of live schedules); (b) only the WebURL crawler is the MVP pipeline executor (Phase 6) — file sources keep using their connector-level periodic path; (c) consistent with the umbrella posture "DB migrations carry users; backend behaviour can change incrementally."
- **Known overlap (flagged for Phase 6, not solved here):** a single `WEBCRAWLER_CONNECTOR` could have BOTH connector-level periodic indexing AND a pipeline wrapping it → double crawl + **double bill**. The data model permits it; the *guard* is Phase 6's responsibility. **Recommendation for Phase 6:** when a pipeline is created/enabled over a connector, treat the **pipeline as authoritative** and set that connector's `periodic_indexing_enabled=False` (single scheduler owns each connector). Recorded here so Phase 6 implements the de-dup; Phase 5 only needs the columns to support either path.

## Work items

1. **Enums** `PipelineRunStatus` + `PipelineRunTrigger` in `db.py`.
2. **ORM** `Pipeline` + `PipelineRun` in `db.py`; inverse `pipelines` relationships on `Workspace`, `User`, `SearchSourceConnector`.
3. **Migration**: 2 types + 2 tables + indexes (incl. `ix_pipelines_due`) + `apply_publication`; symmetric downgrade.
4. **Schemas** `app/schemas/pipeline.py` (+ export in `schemas/__init__.py`); cron syntactic validator.
5. **Zero**: add `pipelines`/`pipeline_runs` (full-row) to `ZERO_PUBLICATION`.
6. **Routes** `pipelines_routes.py` (CRUD + `/run` + `/runs` list/detail); register in `routes/__init__.py`; reuse `CONNECTORS_*` permissions.
7. **Phase-6 task stub**: a named Celery task `run_pipeline(run_id)` in **`app/pipelines/tasks.py`** (the module Phase 6 fleshes out) that `/run` enqueues — no-op/marks the run `failed` with an "engine not implemented" error until Phase 6 fills it in (keeps the endpoint honest and testable). Register it so it's dispatchable: add `"app.pipelines.tasks"` to the Celery `include` list (`celery_app.py`). Phase 6 replaces the stub body in-place (same task name + module → `/run`'s import is stable) and adds the scheduler task + Beat entry + queue routing.
8. **Tests** (below).

## Tests

- **Migration round-trip**: upgrade creates both tables + both enum types + `ix_pipelines_due`; `zero_publication --verify` reports no mismatch (both tables published full-row); downgrade drops cleanly.
- **Create gating (cross-link to 04a)**: `POST /pipelines` with an `AVAILABLE` `DATA_SOURCE` connector (WebURL/GDrive/OneDrive/Dropbox) → 201; with a `MIGRATING`/`MCP_TOOL`/`DISABLED` connector → 4xx (`is_pipeline_eligible` false); with `connector_id=None` → allowed (Uploads case). **(Superseded in Phase 7: once the system-managed Uploads pipeline exists, user `POST` with `connector_id=None` is rejected 4xx and the Uploads row is auto-created on upload — see `07` §7. Update this test in Phase 7.)**
- **Folder validation**: `destination_folder_id` in another workspace → 4xx; `save_to_kb=true` with NULL folder → allowed.
- **Cron validation**: invalid `schedule_cron` → 422; NULL cron → allowed (manual-only).
- **Cascade**: deleting a connector deletes its pipelines + their runs; deleting a folder SET-NULLs `destination_folder_id` (pipeline survives); deleting a workspace removes pipelines + runs.
- **Manual run**: `POST /pipelines/{id}/run` inserts a `pending`/`manual` run and enqueues the task; `GET /pipelines/{id}/runs` returns it newest-first with correct `total`.
- **AuthZ**: cross-workspace access to any pipeline/run route → 404; missing `CONNECTORS_*` permission → 403.
- **Zero shape**: `expected_publication_shape` includes `pipelines`/`pipeline_runs` as full-row.

## Risks / trade-offs

- **`db.py` growth.** Adds two more models to an already-large module. Accepted for relationship/Zero/schema ergonomics + consistency with the other core tables; a later extraction to a `pipelines` package is additive.
- **Coexisting schedulers (double-bill window).** Until Phase 6 adds the de-dup guard, a connector with both its own periodic indexing and a wrapping pipeline can crawl/bill twice. Documented above; Phase 6 owns the fix. MVP exposure is small (operator-created overlap only).
- **Eligibility enforced in code, not SQL.** `is_pipeline_eligible` is a registry (04a) check at the route, so a direct DB insert could bypass it. Same trade-off 04a already accepted (no DB column for the taxonomy).
- **Pre-built unused columns.** `crawls_*` / `result_blob_key` / `charged_micros` ship empty in Phase 5. Deliberate — avoids a second migration in Phase 6.
- **`connector_id` CASCADE drops run history.** Deleting a connector erases its pipelines' audit trail. If audit retention becomes a requirement, switch to `SET NULL` + a discriminator to distinguish Uploads from orphaned (additive change).
- **`created_by_id` nullable shifts work to Phase 6.** SET-NULL preserves shared pipelines past member deletion (the goal) but means the run engine cannot assume a creator — it must resolve `created_by ?? workspace owner` for the indexing actor + billing target. Flagged in the Phase-6 handoff; harmless until then (no engine).
- **Static-registry strand.** A pipeline created over an `AVAILABLE` connector can later reference a type the registry flips to `MIGRATING` on a deploy (create-time check passed; the row persists). Phase 6 must re-check `is_pipeline_eligible` at run time and fail the run cleanly. The data model intentionally does not encode eligibility, so no migration is needed when the registry changes.

## Out of scope (hand-offs)

- Run **engine**, scheduling tick over `pipelines.next_scheduled_at`, crawl-billing wiring (write `charged_micros`/`crawls_*`), raw-blob persistence, and chat-agent run-history context → **Phase 6** (`06-pipelines-exec.md`). Phase 6 also owns three guards this model only *enables*: (a) **run-time eligibility re-check** (`is_pipeline_eligible` — a deploy can flip a connector type to `MIGRATING`, stranding existing pipelines → fail the run cleanly, don't crash); (b) **acting-user resolution** (`created_by_id` can be NULL after member deletion → resolve `created_by ?? workspace owner` for indexing + billing); (c) **concurrency** (Redis indexing lock per pipeline/connector).
- File upload creating/using an "Uploads" pipeline (`connector_id=NULL`, `trigger=upload`, always `save_to_kb`) + generalizing opt-in KB save → **Phase 7** (`07-upload-pipeline-kb.md`).
- Document→run provenance column → deferred (Phase 6/7 if needed).
- Frontend Pipelines UI (list/create/configure/run-history/manual run) → frontend umbrella.
- Public pay-as-you-go API over Type-1 pipelines → post-MVP (umbrella "Deferred").
