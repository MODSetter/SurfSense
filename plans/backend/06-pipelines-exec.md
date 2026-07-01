# Phase 6 — Pipeline execution + scheduling (run engine, crawl billing, blob, chat context)

> # ❌ SUPERSEDED (2026-06-30)
> **This entire phase is dropped.** Per the **Architecture correction** in `00-umbrella-plan.md`, there is no pipeline run engine or scheduler. The existing **automations** system already runs the full chat agent (with the native `web_search`/`scrape_webpage` tools) on **cron/event** triggers and persists **`automation_runs`** — which is exactly what this phase was building. Retained **for historical context only** — do **not** implement it. **Its still-relevant ideas survive in the canonical revamp:** (1) **billing crawls done outside chat** → now handled at the **capability executor** ([`revamp/04a`](revamp%20phases%204-7/04a-capabilities.md)), so recurring/automation runs meter correctly; (2) the refresh **hot loop** (crawl → diff → judge → append) → [`revamp/05b-intelligence.md`](revamp%20phases%204-7/05b-intelligence.md), writing the **Timeline** ([`revamp/05a`](revamp%20phases%204-7/05a-timeline.md)) — not `automation_runs.output`; (3) **recurrence + "run now"** → [`revamp/06-triggers.md`](revamp%20phases%204-7/06-triggers.md) (reuse automations via a CI action). The `bill=False` seam and `index_crawled_urls` `folder_id`/`stats` params described below are **not needed** (no pipeline path).

> Part of the **CI Pivot MVP**. See `00-umbrella-plan.md` (Phase 6).
> Precondition: Phase 5 (`05-pipelines-model.md`) live — `pipelines` / `pipeline_runs` tables, schemas, Zero, CRUD + `/run` (currently enqueues a **stub** `run_pipeline(run_id)`). Depends on `03a-crawler-core.md` (`crawl_url` SUCCESS signal + `crawls_succeeded` counter) and `03c-crawl-billing.md` (`WebCrawlCreditService`). Sibling ahead: `07-upload-pipeline-kb.md` (uploads-as-pipeline).

> **Implementation note (post-rename).** Phases 1–2 are **SHIPPED**, so the live code already uses `workspace_id` / `Workspace` / `workspaces`. Citations below that still show `search_space_id` / `SearchSpace` / `searchspaces` are pre-rename — substitute the `workspace_*` equivalent and grep the new name. **New code in this plan uses the canonical `workspace_*` names** (snippets below updated; e.g. the `get_pipeline_runs` tool's dep key is `workspace_id`, matching the renamed deps dict). Locate code by **symbol/grep**, not the absolute line numbers cited here (the rename + Phases 3–5 shift them).

## Objective

Make pipelines actually **run**. Phase 5 shipped the data model + a stub task; this phase fills in:

1. **Run engine** — turn a `PipelineRun` row into work: resolve the pipeline + connector, re-check eligibility, acquire a lock, crawl the source (WebURL crawler = the only MVP executor), optionally save to the KB destination folder, persist a raw-result blob otherwise, write the run record (status/timing/counts/error).
2. **Crawl billing wiring** (carry-over from `03c`) — bill `crawls_succeeded` to the **workspace owner** via `WebCrawlCreditService` for **both** KB-save branches (a `save_to_kb=false` run must not crawl for free); record `charged_micros` on the run for idempotency.
3. **Scheduling** — a Celery Beat tick that fires due `pipelines.next_scheduled_at` (cron), modeled on the **automations** schedule selector (cron + `FOR UPDATE SKIP LOCKED` + self-heal). Plus the **de-dup guard** Phase 5 deferred (a pipeline over a connector disables that connector's own periodic indexing).
4. **Chat-agent context** — a read-only main-agent **tool** (`get_pipeline_runs`) exposing recent run history scoped to the active workspace (umbrella default = tool).

This is backend-only; the Pipelines UI is deferred to the frontend umbrella.

## Locked decisions (MVP)

| Concept | Decision |
|---------|----------|
| MVP executor | **WebURL crawler only.** `connector.connector_type == WEBCRAWLER_CONNECTOR`. Any other Type-1 type (GDrive/OneDrive/Dropbox) → run fails cleanly with `"executor not implemented for <type>"` (their connector-level periodic path still works; pipelines over them are a Phase-7+ concern). `connector_id IS NULL` (Phase-7 Uploads) → not run by this engine (uploads register their own run in Phase 7). |
| Run-engine shape | Mirror **automations**: thin Celery task → `run_async_celery_task` → async `execute_pipeline_run(session, run_id)` (`automations/tasks/execute_run.py:19-33`). PENDING-gated + idempotent terminal no-op (`automations/runtime/executor.py:29-30`). Status lifecycle `pending → running → succeeded/failed` with `started_at`/`finished_at` (mirrors `repository.mark_running/mark_succeeded/mark_failed`). |
| KB-save path | **Reuse `index_crawled_urls`** (the battle-tested 2-phase indexer) for `save_to_kb=true`, extended with a `folder_id` param (set on created/updated `Document`s → destination folder). `save_to_kb=true` + NULL folder → root (existing behaviour; `documents.folder_id` nullable). |
| Non-KB path | `save_to_kb=false` → a **fetch-only** crawl loop (no `Document` rows): crawl each URL, collect `{url, content, metadata}`, persist as **one JSON blob** via `file_storage` backend, store `result_blob_key` on the run. (The 2-phase indexer is `Document`-centric and cannot "not persist"; a separate small loop is cleaner than bending it.) |
| Billing ownership | **Run engine owns billing for the pipeline path** (pre-check on `len(urls)` + charge on `crawls_succeeded` + record `charged_micros`), calling the crawler with **billing suppressed** (`bill=False`). The connector `/index` + connector-periodic paths keep `03c`'s in-indexer billing (`bill=True`). This keeps `charged_micros` run-idempotency clean and bills both KB branches identically. **(03c coordination — see below.)** |
| Scheduler | New `pipeline_schedule_select` Beat task modeled on `automations/triggers/builtin/schedule/selector.py` (cron, `FOR UPDATE SKIP LOCKED`, self-heal of NULL `next_scheduled_at`), **not** the simpler connector `frequency_minutes` checker — because Phase 5 chose `schedule_cron`. Reuses the existing `croniter` util (`automations/triggers/builtin/schedule/cron.py`). |
| Schedule timezone | Cron needs a timezone (`compute_next_fire_at(cron, timezone, …)`). Phase 5's model has only `schedule_cron`. **Add `schedule_timezone VARCHAR NOT NULL DEFAULT 'UTC'` to `pipelines`** (small additive amendment to `05` — see "Required 05 amendment"). Matches how automations store cron **and** timezone (`schedule/selector.py:86-89`). |
| Concurrency | Per-pipeline Redis lock + (when connector-backed) the **existing connector lock** `utils/indexing_locks.py` so a pipeline run and any residual connector index can't double-crawl the same connector. |
| Chat context | A main-agent **tool** `get_pipeline_runs` (registry pattern, `main_agent/tools/registry.py:85-102`), opening its own `shielded_async_session()` (like `KnowledgeTreeMiddleware`) and scoping to the build-time `workspace_id`. Always-on middleware injection is **deferred** (token cost; tool is on-demand). |
| Code location | New `app/pipelines/` package: `engine.py` (`execute_pipeline_run`), `tasks.py` (Celery `run_pipeline` + `pipeline_schedule_select`), `scheduler.py` (the tick), `storage.py` (blob key). The Phase-5 stub `run_pipeline` is **replaced** by the real task here; the `/run` route + scheduler enqueue it. (ORM stays in `db.py` per Phase 5; only the *engine* is a package, mirroring `app/automations/`.) |

## Current state (cited)

### Run-engine precedent (automations)

- **Task wrapper**: `automations/tasks/execute_run.py:19-33` — `@celery_app.task(name=..., bind=True)` → `run_async_celery_task(lambda: _impl(run_id))`; `_impl` opens `get_celery_session_maker()()` and calls `execute_run(session, run_id)`, rolling back + re-raising on failure.
- **Launch**: `automations/dispatch/launch.py:43-60` — create the child row `status=PENDING`, `session.add` + `commit` + `refresh`, then `task.apply_async(args=[run.id], time_limit=…)`. (Phase 5's `/run` already does the create+enqueue; this phase makes the task real.)
- **Executor lifecycle**: `automations/runtime/executor.py:23-75` — `load run; if run.status != PENDING: return` (idempotent terminal no-op, `:29-30`); `mark_running` + `commit` (`:46-47`); on bad snapshot → `mark_failed` + commit (`:35-44`); terminal `mark_succeeded`/`mark_failed` each `commit`.

### The MVP executor: `webcrawler_indexer.index_crawled_urls`

- Signature `webcrawler_indexer.py:44-53`: `(session, connector_id, search_space_id, user_id, start_date=None, end_date=None, update_last_indexed=True, on_heartbeat_callback=None) -> (int, str|None)`.
- Reads URLs from `connector.config["INITIAL_URLS"]` via `parse_webcrawler_urls` (`:118-119`).
- **Creates `Document` rows with NO `folder_id`** (`:222-239`) → today everything lands at workspace root. Updates existing docs in place. Crawls via `crawler.crawl_url(url)` (`:297`; `03a` changes this signature/return). Tracks `documents_indexed` / `documents_updated` / counts; final commit at `:432`; returns `(total_processed, error)` (`:477`).
- **No billing today** — `03c` adds the owner pre-check + `charge_credits` inside this function (`03c` §2). **This phase adds a `bill: bool = True` seam** so the pipeline path can suppress it (plus `folder_id` / `urls` params + a `stats` out-param — see "Crawler changes"; the positional return is left unchanged so the shared wrapper keeps working).
- Connector entrypoint chain (the path the pipeline engine **bypasses**, because it's notification-centric, not run-centric): `connector_tasks.py:418-454` (`index_crawled_urls_task` → `_index_crawled_urls` → `run_web_page_indexing`) → a `_run_indexing_with_notifications(...)` **call site** (e.g. the WebCrawler one at `search_source_connectors_routes.py:~2524`). The wrapper itself is **defined at `:1296`** (acquires the connector lock at `:1334`, length-unpacks the indexer return at `:1503`).

### KB-ingest service (folder support already exists there)

- `IndexingPipelineService` (`indexing_pipeline/indexing_pipeline_service.py:82`) already threads a destination folder via `ConnectorDocument.folder_id` (`:273-274`, `:301-302`, `:326`). **But the webcrawler indexer does not use this service** — it writes `Document`s directly. So the umbrella's "route through `IndexingPipelineService` into the destination folder" is accurate for **file/Composio** sources, **not** the crawler. For the WebURL MVP, the minimal correct move is to thread `folder_id` into `index_crawled_urls` (not refactor the crawler onto `IndexingPipelineService`). Unifying them is a post-MVP cleanup.

### Scheduler precedent (cron) + Beat registration

- **Selector** `automations/triggers/builtin/schedule/selector.py`: tick (`:47-65`) → self-heal NULL `next_fire_at` (`:68-98`) → claim due rows `FOR UPDATE SKIP LOCKED` + advance via `compute_next_fire_at` + set `last_fired_at` (`:101-150`) → `_start_one` launches each (`:153-183`). `_TICK_BATCH=200` cap (`:35`).
- **Cron util** `automations/triggers/builtin/schedule/cron.py`: `validate_cron(cron, timezone)` (`:15`) and `compute_next_fire_at(cron, timezone, *, after)` (`:28`, returns UTC). **Requires a timezone** → drives the 05 amendment.
- **Beat source** `automations/triggers/builtin/schedule/source.py:14-20` — a `BEAT_SCHEDULE` dict (`crontab(minute="*")`) merged into the app at `celery_app.py:323` (`**SCHEDULE_BEAT_SCHEDULE`). The app's beat dict is `celery_app.py:268-324`; the worker `include` list is `:180-198`; task routing (`index_crawled_urls → CONNECTORS_QUEUE`) is `:237-255` (`:246`).
- **Connector meta-scheduler we coexist with**: `schedule_checker_task.py:17` scans `SearchSourceConnector` where `periodic_indexing_enabled AND next_scheduled_at <= now` (`:33-39`), with a Redis-lock guard `is_connector_indexing_locked` (`:93`). Untouched; the pipeline tick is a sibling.

### Locks, storage, chat tooling

- **Locks** `utils/indexing_locks.py`: `acquire_connector_indexing_lock(connector_id)->bool` (`:24`), `release_…` (`:37`), `is_…_locked` (`:43`), keyed `indexing:connector_lock:{id}`, TTL `CONNECTOR_INDEXING_LOCK_TTL_SECONDS`.
- **Storage** `file_storage/service.py:39,46`: `get_storage_backend()` (from `file_storage/factory.py`) → `backend.put(key, data, content_type=…)` / `open_stream(key)` / `delete(key)`. Keys are built per-purpose (`file_storage/keys.py:11`, `build_document_file_key`). For runs we add a sibling key builder (no `document_files` row — runs aren't documents).
- **Tool registry** `main_agent/tools/registry.py:85-102` — `_MAIN_AGENT_TOOL_FACTORIES: {name: (factory, required_dep_names)}`; `build_main_agent_tools(deps, …)` resolves deps + builds (`:105-147`). Display metadata lives in `shared/tools/catalog`; the main-agent name list in `main_agent/tools/index` (per the registry docstring `:1-14`). Read-only DB pattern for a chat surface: `KnowledgeTreeMiddleware` opens `shielded_async_session()` and filters by its build-time `search_space_id` (`knowledge_tree/middleware.py:199-206`).
- **Workspace owner** (billing target): `SearchSpace.user_id` (`03c` §2.1 resolves the owner with a direct `select SearchSpace.user_id where id == search_space_id`).

## Target design

### 1. `execute_pipeline_run(session, run_id)` — the engine (`app/pipelines/engine.py`)

```
load run (pipeline + connector eager); if run is None: raise
if run.status != PENDING: return            # status gate; also no-ops acks_late redelivery (executor.py:29-30)
pipeline = run.pipeline
mark_running(run): status=RUNNING, started_at=now; commit
# ^ committed BEFORE any crawl/charge → a redelivered/duplicate task sees RUNNING and returns (executor.py:46-47)

pipeline_lock = connector_lock = False
connector = None
try:
    # --- guards: fail cleanly, never crash the worker (Phase-5 hand-offs (a)/(b)) ---
    if pipeline.connector_id is None:                  # Uploads pipeline — Phase 7, not here
        return fail(run, "uploads pipeline has no fetch executor")
    connector = pipeline.connector
    if not is_pipeline_eligible(connector.connector_type):   # 04a runtime re-check (strand guard)
        return fail(run, f"connector type {connector.connector_type} no longer eligible")
    if connector.connector_type != WEBCRAWLER_CONNECTOR:
        return fail(run, f"executor not implemented for {connector.connector_type}")

    owner_id = workspace_owner_id(session, pipeline.workspace_id)   # select Workspace.user_id (03c §2.1)
    actor_user_id = str(pipeline.created_by_id or owner_id)         # Phase-5 hand-off (b)
    urls = parse_webcrawler_urls(pipeline.config.get("INITIAL_URLS") or connector.config.get("INITIAL_URLS"))
    if not urls:
        return fail(run, "no URLs to crawl")

    # --- concurrency: take both; release only what we took (Phase-5 hand-off (c)) ---
    pipeline_lock = acquire_pipeline_indexing_lock(pipeline.id)
    if not pipeline_lock:
        return fail(run, "a run for this pipeline is already in progress")
    connector_lock = acquire_connector_indexing_lock(connector.id)
    if not connector_lock:
        return fail(run, "connector is currently indexing; retry later")

    # --- billing pre-flight (run-level; 03c statics). len(urls) is a safe upper bound. ---
    svc = WebCrawlCreditService(session)
    if WebCrawlCreditService.billing_enabled() and run.charged_micros is None:
        await svc.check_credits(owner_id, len(urls))   # InsufficientCreditsError → except → fail("out of crawl credit")

    # --- fetch ---
    if pipeline.save_to_kb:
        stats = {}                                     # out-param sink — NON-breaking (see §3)
        await index_crawled_urls(session, connector.id, pipeline.workspace_id, actor_user_id,
                                 urls=urls, folder_id=pipeline.destination_folder_id,
                                 bill=False, stats=stats, update_last_indexed=True)
        documents_indexed = stats["documents_indexed"]
        crawls_attempted  = stats["crawls_attempted"]
        crawls_succeeded  = stats["crawls_succeeded"]
        result_blob_key   = None
    else:
        outcomes = await crawl_urls_fetch_only(urls)   # list[dict] from CrawlOutcome (03a)
        crawls_attempted  = len(urls)
        crawls_succeeded  = sum(1 for o in outcomes if o["status"] == "success")
        documents_indexed = 0
        result_blob_key  = await persist_run_blob(run, outcomes)

    # --- charge: stamp run + add audit, THEN charge (its single commit flushes all three atomically) ---
    if WebCrawlCreditService.billing_enabled() and crawls_succeeded > 0 and run.charged_micros is None:
        run.charged_micros = WebCrawlCreditService.successes_to_micros(crawls_succeeded)
        record_token_usage(session, usage_type="web_crawl", workspace_id=pipeline.workspace_id,
                           user_id=owner_id, cost_micros=run.charged_micros,
                           call_details={"urls": len(urls), "successes": crawls_succeeded,
                                         "pipeline_id": pipeline.id, "run_id": run.id},
                           message_id=None)             # add only — does not commit (03c §2.3)
        await svc.charge_credits(owner_id, crawls_succeeded)   # debits + COMMITS run+audit+balance (03c §2.4)

    mark_succeeded(run): status=SUCCEEDED, finished_at=now,
                         documents_indexed, crawls_attempted, crawls_succeeded, result_blob_key; commit
except InsufficientCreditsError:
    return fail(run, "out of crawl credit")            # run is RUNNING→FAILED; no debit happened
except Exception as e:
    return fail(run, {"message": str(e), "type": type(e).__name__})
finally:
    if connector_lock: release_connector_indexing_lock(connector.id)
    if pipeline_lock:  release_pipeline_indexing_lock(pipeline.id)
```

`fail(run, err)` = set `status=FAILED`, `finished_at=now`, `error={...}`, `commit`, return — so the `finally` still runs and releases only the locks actually taken. `connector.id` in `finally` is reached only when `connector_lock is True`, which implies `connector` was resolved. **Idempotency rests on the status gate**, not `charged_micros`: `mark_running` commits `RUNNING` before any crawl/charge, so an `acks_late` redelivery (`celery_app.py:228-229`) or a manual re-enqueue sees `RUNNING`/terminal and returns. `charged_micros` is the belt-and-suspenders guard reserved for a future stuck-`RUNNING` re-driver (none in MVP).

Notes:
- **`workspace_owner_id`** = `select Workspace.user_id where id == workspace_id` (`03c` §2.1 pattern).
- **`is_pipeline_eligible`** is the 04a registry helper — re-checked here at run time (a deploy can flip a type to `MIGRATING`; the create-time check in Phase 5 doesn't protect the row forever).
- **URL source**: per-pipeline `config["INITIAL_URLS"]` overrides the connector's (the `config` JSONB "per-pipeline overrides" Phase 5 reserved); fall back to the connector's `INITIAL_URLS`.

### 2. Celery tasks (`app/pipelines/tasks.py`)

```python
@celery_app.task(name="run_pipeline", bind=True)
def run_pipeline(self, run_id: int) -> None:
    return run_async_celery_task(lambda: _run(run_id))   # execute_run.py:19-22 shape

async def _run(run_id: int) -> None:
    async with get_celery_session_maker()() as session:
        try:
            await execute_pipeline_run(session, run_id)
        except Exception:
            logger.exception("pipeline run %d failed unexpectedly", run_id)
            await session.rollback(); raise
```

- `run_pipeline` **replaces** the Phase-5 stub of the same name; Phase 5's `/run` route already enqueues `run_pipeline(run.id)` (no route change needed).
- **Routing/registration**: ensure `"app.pipelines.tasks"` is in the `include` list (`celery_app.py:180-198`) — Phase 5 already added it for the stub; no-op if present — and route `"run_pipeline": {"queue": CONNECTORS_QUEUE}` (it crawls — same queue as `index_crawled_urls`, `celery_app.py:246`). Give the `apply_async`/`delay` a `time_limit` (the connectors queue already has an 8h hard cap, `celery_app.py:219`).

### 3. Crawler changes — `index_crawled_urls` (coordination with `03a`/`03c`)

Four additive params, **all default-compatible** with the existing connector path:

1. **`folder_id: int | None = None`** — set on each created `Document` (`:222-239`) and on the existing-doc update branch, so KB-save lands in the destination folder. Default `None` = root (today's behaviour).
2. **`urls: list[str] | None = None`** — when provided, crawl this list instead of re-reading `connector.config["INITIAL_URLS"]` (`:118-119`). **Required** for the per-pipeline `config["INITIAL_URLS"]` override (a Phase-5 `config` capability) and to keep the engine's `len(urls)` billing pre-check consistent with what's actually crawled. Default `None` = read connector config (today's behaviour).
3. **`bill: bool = True`** — gate `03c`'s in-indexer `check_credits` + `charge_credits` + `record_token_usage`. The pipeline engine calls `bill=False` and bills at the run level; the connector `/index` + periodic paths keep `bill=True`. *(Small addition to `03c`'s §2 wiring — see "Cross-plan coordination".)*
4. **`stats: dict | None = None`** — an **out-param sink**, NOT a return-shape change. When provided, the indexer populates `stats["documents_indexed"|"crawls_attempted"|"crawls_succeeded"]`. **Do NOT widen the return tuple:** the shared `_run_indexing_with_notifications` wrapper unpacks every indexer's return **by length** (`search_source_connectors_routes.py:1499-1507`: `if len(result) == 3: a,b,c = result else: a,b = result`), so a 4-tuple would raise `ValueError` for *every* connector. The 2-/3-tuple return stays exactly as-is (wrapper untouched); the engine passes a fresh `stats` dict and reads it after the call (the wrapper passes none → `None` → no-op). `03a` work-item 3 already reflects this (it exposes `crawls_succeeded` via **task metadata** only, with this `stats` sink owned by Phase 6 — not via the positional return).

The engine **bypasses** `_run_indexing_with_notifications` (it acquires the connector lock itself at `:1334` — going through the wrapper would self-deadlock on that same lock, and the wrapper's connector-`Notification` UI is the wrong surface for a pipeline run, which has its own `PipelineRun` record). It calls `index_crawled_urls` directly with no heartbeat callback. (Consequence: pipeline runs don't emit connector-indexing notifications and aren't touched by `cleanup_stale_indexing_notifications` — fine; run status lives on `pipeline_runs`.)

### 4. Fetch-only path + blob (`app/pipelines/engine.py` + `app/pipelines/storage.py`)

For `save_to_kb=false`:

```python
async def crawl_urls_fetch_only(urls):
    crawler = WebCrawlerConnector()                       # 03a: no firecrawl ctor arg
    out = []
    for url in urls:
        outcome = await crawler.crawl_url(url)            # 03a: CrawlOutcome(status, result, error, tier)
        out.append({
            "url": url,
            "status": outcome.status.value,               # CrawlOutcomeStatus: success | empty | failed
            "content": (outcome.result or {}).get("content", ""),
            "metadata": (outcome.result or {}).get("metadata", {}),
            "error": outcome.error,
        })
    return out
```

> **03a return shape.** `03a` is **committed to the `CrawlOutcome` dataclass** (`status`/`result`/`error`/`tier`) — the tuple option was dropped precisely because this fetch-only path consumes `.status`/`.result`/`.error` as attributes. So the unpack above is the firm contract; no adaptation needed.

```python
# storage.py
def build_pipeline_run_result_key(*, workspace_id: int, run_id: int) -> str:
    return f"pipeline_runs/{workspace_id}/{run_id}/result.json"

async def persist_run_blob(run, outcomes) -> str:
    key = build_pipeline_run_result_key(workspace_id=run.pipeline.workspace_id, run_id=run.id)
    data = json.dumps({"runs": outcomes}).encode()
    await get_storage_backend().put(key, data, content_type="application/json")
    return key                                            # → run.result_blob_key
```

- One blob per run (single configured backend, like document files). `result_blob_key` (Phase 5 column) stores the key; reads resolve via `get_storage_backend()`.
- **Billing still applies** here — `crawls_succeeded` is counted from `outcomes`, so non-KB runs cost exactly the same as KB runs (umbrella line 105). This is the whole reason the run engine, not the indexer, owns pipeline billing.

### 5. Scheduler tick (`app/pipelines/scheduler.py` + `tasks.py`)

A near-copy of the automations selector, retargeted at `pipelines`:

```python
@celery_app.task(name="pipeline_schedule_select")
def pipeline_schedule_select() -> None:
    return run_async_celery_task(_tick)

async def _tick():
    async with get_celery_session_maker()() as session:
        now = datetime.now(UTC)
        await _self_heal_null_next(session, now)          # enabled + cron + next_scheduled_at IS NULL → compute
        claims = await _claim_due(session, now)           # enabled + next_scheduled_at <= now, FOR UPDATE SKIP LOCKED, advance
        for c in claims:
            await _start_run(session, c)                  # create PipelineRun(trigger=scheduled, status=pending) + run_pipeline.apply_async
```

- **`_claim_due`**: `select Pipeline where enabled AND connector_id IS NOT NULL AND schedule_cron IS NOT NULL AND next_scheduled_at IS NOT NULL AND next_scheduled_at <= now ORDER BY next_scheduled_at LIMIT 200 FOR UPDATE SKIP LOCKED` (uses Phase 5's partial `ix_pipelines_due`). The `connector_id IS NOT NULL` filter is **defense-in-depth** so a non-connector pipeline (the Phase-7 Uploads pipeline) can **never** be scheduled into perpetually-failing runs even if a cron is somehow set on it — the engine would `fail` every such run (`§1`); this stops them at the selector. (Phase 7 also guards the API; this is the belt to that suspenders.) Advance `next_scheduled_at = compute_next_fire_at(schedule_cron, schedule_timezone, after=now)`; on `InvalidCronError` → `enabled=False` (self-disable, like `selector.py:90-96,131-137`). Commit, then create the run + enqueue (mirror `_start_one` reload-after-commit, `selector.py:153-183`).
- **`_self_heal_null_next`**: backfills `next_scheduled_at` for enabled cron pipelines missing it (fresh inserts, restored rows) — so Phase 5's create can leave it NULL and the tick fills it within ≤1 min.
- **Duplicate suppression**: in `_start_run`, skip creating a scheduled run if the pipeline already has a non-terminal run (`status IN (pending, running)`) — mirrors the connector checker's in-progress guard (`schedule_checker_task.py:100-116`). Without it, a pipeline whose run outlasts its cron interval piles up `scheduled` runs that immediately `fail` on the lock (noisy, though harmless). `next_scheduled_at` is still advanced (the fire isn't retried — `catchup=False`, like the automations selector).
- **Beat entry**: add `"pipeline-schedule-select": {"task": "pipeline_schedule_select", "schedule": crontab(minute="*"), "options": {"expires": 50}}` to `celery_app.py:268-324` (default fast queue, like `check_periodic_schedules`). (`"app.pipelines.tasks"` is already in `include` from Phase 5's stub, so `pipeline_schedule_select` in the same module is auto-registered.)
- **`schedule_cron` edits** (Phase 5 `PUT`): when `schedule_cron` (or timezone) changes, **null `next_scheduled_at`** so the tick recomputes (small `PUT`-handler addition — see Required 05 amendment). NULL cron ⇒ manual-only (tick ignores it).

### 6. De-dup guard (resolves Phase-5 deferred double-bill)

When a pipeline that **wraps a connector** is created or enabled (Phase 5 routes), set that connector's `periodic_indexing_enabled = False` (+ `next_scheduled_at = None`) so a single scheduler owns each connector (the **pipeline is authoritative**, per Phase 5's recommendation). Two touch points:

- Phase 6 owns the rule; implement it in the Phase-5 `POST /pipelines` and `PUT /pipelines/{id}` handlers (when `connector_id` is set and `enabled`). This is a tiny handler addition (Phase 5 explicitly handed it here).
- Belt-and-suspenders: the run engine already takes the **connector lock** during a run, so even if both scan, only one crawl proceeds at a time (the connector checker skips on a held lock, `schedule_checker_task.py:93`).

### 7. Chat-agent run-history tool (`main_agent/tools/pipeline_runs.py`)

A read-only tool registered in the main-agent registry (umbrella default = tool):

```python
def create_get_pipeline_runs_tool(*, workspace_id: int) -> BaseTool:
    @tool
    async def get_pipeline_runs(pipeline_id: int | None = None, limit: int = 20) -> str:
        """Recent pipeline run history for THIS workspace: name, status, trigger,
        schedule, counts, started/finished. Read-only."""
        async with shielded_async_session() as session:     # knowledge_tree/middleware.py:199 pattern
            q = (select(PipelineRun, Pipeline.name, Pipeline.schedule_cron)
                 .join(Pipeline, PipelineRun.pipeline_id == Pipeline.id)
                 .where(Pipeline.workspace_id == workspace_id))
            if pipeline_id is not None:
                q = q.where(Pipeline.id == pipeline_id)
            rows = (await session.execute(
                q.order_by(PipelineRun.created_at.desc()).limit(min(limit, 100)))).all()
        return render_compact(rows)   # name • status • trigger • finished_at • docs/crawls
    return get_pipeline_runs
```

- **Registration**: add `"get_pipeline_runs": (_build_get_pipeline_runs_tool, ("workspace_id",))` to `_MAIN_AGENT_TOOL_FACTORIES` (`registry.py:85-102`) — the dep key is `workspace_id`, matching the post-rename deps dict; add the name to `main_agent/tools/index`; add display metadata to `shared/tools/catalog`.
- **Workspace scope is structural** — the tool only ever sees its build-time `workspace_id`; no cross-workspace leakage (same guarantee `KnowledgeTreeMiddleware` relies on).
- **Anonymous / no-workspace turns**: exclude the tool when there's no `workspace_id` (anonymous chat has no workspace/pipelines), the same way `KnowledgeTreeMiddleware` is CLOUD-only (`knowledge_tree/middleware.py:130-131`). The registry factory requires `workspace_id`, so just don't enable it in the anonymous tool set.
- The tool reads `pipelines`/`pipeline_runs` directly (no Zero dependency), so it works server-side immediately even though client Zero sync is dormant until the frontend lands (Phase 5 note).
- **Deferred**: an always-on `<pipeline_activity>` middleware injection (à la `KnowledgeTreeMiddleware`) — adds per-turn token cost; revisit if the agent under-uses the tool.

### 8. (Optional) blob read endpoint

Phase 5 stores `result_blob_key` but exposes no reader. Add `GET /pipelines/{id}/runs/{run_id}/result` → stream the blob via `get_storage_backend().open_stream(run.result_blob_key)` (404 if NULL), `CONNECTORS_READ`, workspace-scoped — mirroring `file_storage/api.py:69-90`. Lets API consumers + the chat tool fetch non-KB results. (Small; include if cheap, else defer to the public-API phase.)

## Required `05` amendment (timezone + recompute)

Small, additive. **Items 1–3 (the `schedule_timezone` column) are already folded into `05`** (model/migration/schema/validator) — listed here for traceability. **Item 4 is Phase-6 route logic** added on top of Phase 5's handlers (Work items 5–6):

1. *(done in `05` §2)* **Model**: `schedule_timezone = Column(String(64), nullable=False, default="UTC", server_default="UTC")` on `Pipeline`.
2. *(done in `05` §4)* **Migration**: `schedule_timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'` in `CREATE TABLE pipelines`.
3. *(done in `05` §5)* **Schema**: `schedule_timezone: str = "UTC"` on `PipelineBase` + `PipelineUpdate`; `(schedule_cron, schedule_timezone)` validated together via `validate_cron(cron, tz)` (`cron.py:15`).
4. **Routes** (Phase 6 adds to `05` §7 handlers): on `PUT` when `schedule_cron`/`schedule_timezone` changes, set `next_scheduled_at = None` (tick self-heals). On `POST`/`PUT` with `connector_id` + `enabled`, apply the §6 de-dup guard.

(If we'd rather not touch `05`: hardcode `"UTC"` everywhere in Phase 6 and skip the column — but that loses operator-meaningful local schedules and diverges from automations. The column is the right call.)

## Cross-plan coordination

- **`03a`** — Phase 6 calls `WebCrawlerConnector.crawl_url(url)` directly in the fetch-only path and relies on `03a`'s `CrawlOutcome.status` (`SUCCESS`/`EMPTY`/`FAILED`, dataclass form — already locked in `03a`). `03a` work-item 3 is **already aligned**: it surfaces the `crawls_succeeded` counter via **task metadata** only (not by widening `index_crawled_urls`'s positional return — the shared `_run_indexing_with_notifications` wrapper unpacks by tuple length, `:1499-1507`). Phase 6 owns the `folder_id`/`urls`/`stats` params; `03a` owns the counter + `CrawlOutcome`.
- **`03c`** — add the **`bill: bool = True`** parameter to the in-indexer billing (so the pipeline path can suppress it). `03c`'s `WebCrawlCreditService` statics (`billing_enabled()`, `successes_to_micros(n)`, `check_credits`, `charge_credits`) are reused verbatim by the run engine. `03c`'s risk note already anticipated this: *"Phase 5's `PipelineRun` can persist `charged_micros` for stronger idempotency"* — Phase 6 is where that lands.
- **`05`** — the four amendments above; `run_pipeline` task name + `/run` enqueue already exist (stub → real); `charged_micros`/`crawls_*`/`result_blob_key` columns already exist (pre-built in Phase 5).
- **`04a`** — `is_pipeline_eligible(connector_type)` is imported for the run-time re-check.

## Work items

1. **`app/pipelines/` package**: `engine.py` (`execute_pipeline_run` + `mark_running/succeeded/fail` helpers + `workspace_owner_id` + `crawl_urls_fetch_only`), `tasks.py` (`run_pipeline`, `pipeline_schedule_select`), `scheduler.py` (`_tick`/`_self_heal_null_next`/`_claim_due`/`_start_run`), `storage.py` (blob key + `persist_run_blob`).
2. **Pipeline lock helpers**: add `acquire_pipeline_indexing_lock(id)` / `release_pipeline_indexing_lock(id)` to `utils/indexing_locks.py` (key `indexing:pipeline_lock:{id}`), mirroring the connector lock (`:19-40`).
3. **Crawler changes**: `index_crawled_urls` gains `folder_id` + `urls` + `bill` + a `stats` **out-param** (populates `documents_indexed`/`crawls_attempted`/`crawls_succeeded`). **No return-shape change → no caller changes** (the shared wrapper's 2-/3-tuple unpack stays valid). Coordinate with `03a`/`03c` (see "Cross-plan coordination").
4. **Celery wiring** (`celery_app.py`): ensure `"app.pipelines.tasks"` is in `include` (added in Phase 5 for the stub); route `run_pipeline → CONNECTORS_QUEUE`; add the `pipeline-schedule-select` Beat entry.
5. **De-dup guard** in Phase-5 `POST`/`PUT /pipelines` (disable wrapped connector's periodic indexing).
6. **`05` amendment**: `schedule_timezone` column/migration/schema/validator + `next_scheduled_at` reset on cron edit.
7. **Chat tool** `get_pipeline_runs` + registry/index/catalog registration.
8. **(Optional)** `GET …/runs/{run_id}/result` blob reader.
9. **Tests** (below).

## Tests

- **Manual run, KB-save**: WebURL pipeline `save_to_kb=true` + `destination_folder_id` → run goes `pending→running→succeeded`, `Document`s created **in that folder**, `documents_indexed`/`crawls_*` set, `finished_at` set.
- **Manual run, non-KB**: `save_to_kb=false` → **no** `Document`s, `result_blob_key` set + blob readable, `crawls_*` set. Billing **still** charges `crawls_succeeded` (parity with KB run).
- **Billing**: enabled + sufficient → owner debited `crawls_succeeded * 1000`, `charged_micros` stamped, one `web_crawl` `TokenUsage`; **insufficient → run fails pre-crawl (FAILED), no debit**; disabled (self-hosted) → no charge, no `web_crawl` row, `charged_micros` stays NULL.
- **Idempotency / lifecycle**: re-enqueuing a `RUNNING` or terminal run → immediate no-op (`status != PENDING` gate) → **no second charge** (the primary guard; `mark_running` commits before any charge); engine never raises out of `fail()` paths (bad type / NULL connector / no URLs / ineligible / lock contention) — all land the run in `FAILED` and release locks.
- **Eligibility re-check**: pipeline over a connector whose type is now `MIGRATING` → run fails cleanly (not crash).
- **Scheduler**: a due cron pipeline → tick creates a `scheduled` run + advances `next_scheduled_at` to the next cron match (in `schedule_timezone`); NULL `next_scheduled_at` self-heals; invalid cron self-disables (`enabled=False`); manual-only (NULL cron) never fires.
- **De-dup**: creating/enabling a pipeline over a connector flips that connector's `periodic_indexing_enabled=False`; concurrent connector-checker tick skips on the held lock.
- **Concurrency**: a second run while one is in-flight → fails with "already in progress" (locks held).
- **Chat tool**: `get_pipeline_runs` returns this workspace's runs only; another workspace's runs never appear; respects `limit`.
- **Counts contract (regression-critical)**: `index_crawled_urls` keeps its existing 2-/3-tuple return (the shared `_run_indexing_with_notifications` length-unpack still works for *all* connectors); when a `stats` dict is passed it's populated with `documents_indexed`/`crawls_attempted`/`crawls_succeeded`; `bill=False` suppresses in-indexer billing; connector path (`bill=True`, no `stats`) behaves byte-for-byte as before. Add a wrapper test asserting webcrawler indexing through `_run_indexing_with_notifications` still unpacks cleanly.

## Risks / trade-offs

- **Billing split across two call sites** (indexer for connector path, run engine for pipeline path), unified only by `03c`'s shared statics. Accepted: it's what makes `charged_micros` run-idempotency clean and keeps both KB branches billed identically. The `bill` flag is the single seam.
- **Stuck `RUNNING` runs.** A crash *after* `mark_running` but *before* terminal leaves `status=RUNNING` forever (the `status != PENDING` gate then no-ops any redelivery — same property as automations). No double-charge (gate + `charged_micros`), but the run never completes and its locks rely on Redis TTL to free. A stale-run sweeper (à la `cleanup_stale_indexing_notifications`, `celery_app.py:279-285`) is deferred; MVP exposure is a rare worker crash.
- **Two crawl code paths** (`index_crawled_urls` for KB vs `crawl_urls_fetch_only` for non-KB). Minor duplication of the crawl loop; deliberate, since forcing the `Document`-centric 2-phase indexer into a "don't persist" mode is messier. Both share `WebCrawlerConnector.crawl_url` + the same billing math.
- **WebURL-only executor.** A pipeline over GDrive/OneDrive/Dropbox is creatable (Phase 5 lets `AVAILABLE DATA_SOURCE`) but fails at run time ("executor not implemented"). Acceptable for MVP (those keep their connector-periodic path); generalize the executor in Phase 7+.
- **De-dup guard is one-way.** Creating/enabling a pipeline disables the wrapped connector's `periodic_indexing_enabled`, but **disabling or deleting that pipeline does NOT restore it** — so a connector can end up indexed by *neither* path (data goes stale) until the user re-enables connector periodic indexing manually. MVP-acceptable (operator action); a symmetric restore-on-disable is a small follow-up. Flag in the (deferred) UI copy.
- **Blob backend assumption.** `result_blob_key` stores only the key (no backend name, unlike `document_files.storage_backend`). Fine for the single configured backend; if multi-backend ever lands, add a backend column to `pipeline_runs` (additive).
- **Non-KB blob built in memory.** `crawl_urls_fetch_only` accumulates every URL's extracted content into one JSON blob before upload — a large URL list (or huge pages) inflates worker memory. Acceptable for MVP URL counts; if it bites, stream to the backend or cap per-run URLs (a `config` knob). Also: non-KB runs have **no dedup** (every run re-crawls + re-bills all URLs) — that's inherent to "don't persist", and the user opted out of KB.
- **Lock lifetime vs run length.** The Redis locks use `CONNECTOR_INDEXING_LOCK_TTL_SECONDS`; a crawl run longer than the TTL could let a second run start. Pre-existing property of the connector lock (the connectors queue caps at 8h); revisit the TTL if pipeline runs routinely exceed it.
- **Two minute-level Beat scans** (connector checker + pipeline tick) now run every minute. Both are indexed (`ix_pipelines_due` partial index; connector scan on its own predicate) + batch-capped (200), so cost is negligible.

## Out of scope (hand-offs)

- **Uploads pipeline execution** (`connector_id=NULL`, `trigger=upload`, always `save_to_kb`) → **Phase 7** (`07-upload-pipeline-kb.md`). This engine explicitly fails NULL-connector runs.
- **Non-WebURL executors** (GDrive/OneDrive/Dropbox pipelines) → Phase 7+.
- **Always-on chat context middleware** (`<pipeline_activity>` injection) → deferred (tool-only for MVP).
- **Document→run provenance** (`documents.pipeline_run_id`) → deferred (touches `documents`).
- **Public pay-as-you-go API over pipelines** + **public MCP KB server** → post-MVP (umbrella "Deferred").
- **Frontend** Pipelines UI (run-history, manual run, schedule editor) → frontend umbrella.
