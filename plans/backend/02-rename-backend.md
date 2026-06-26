# Subplan 02 — Rename backend (code + API)

Part of [00-umbrella-plan.md](00-umbrella-plan.md), Phase 2. Backend only (`surfsense_backend`).

## Goal

Remove the Phase 1 shim and complete the SYMBOLIC rename `SearchSpace -> Workspace` / `search_space_id -> workspace_id` across the ~150 backend files, then consolidate the three live URL spellings (`/searchspaces`, `/search-spaces`, `/search-space`) onto a single canonical `/workspaces`. After this phase the physical DB (Phase 1) and the Python/API surface speak the same name.

Precondition: [01-rename-db.md](01-rename-db.md) is merged and live. Phase 1 left the Python attribute as `search_space_id` mapped to the physical column via `Column("workspace_id", ...)`; Phase 2 flips the attribute itself and drops that explicit-name shim.

## Surface area (cited; counts are current-tree, will shift after Phase 1)

Measured over `surfsense_backend/app` (Grep, case-insensitive `search.?space`):

- `search_space` — ~150 files, ~2,800 line matches (dominated by ORM attribute access).
- `SearchSpace` (class/relationship target) — ~38 files, ~450 matches.
- Heaviest files: [services/connector_service.py](surfsense_backend/app/services/connector_service.py) (158), [routes/search_source_connectors_routes.py](surfsense_backend/app/routes/search_source_connectors_routes.py) (138), [routes/rbac_routes.py](surfsense_backend/app/routes/rbac_routes.py) (142), [routes/model_connections_routes.py](surfsense_backend/app/routes/model_connections_routes.py) (132), [routes/new_chat_routes.py](surfsense_backend/app/routes/new_chat_routes.py) (133), [routes/documents_routes.py](surfsense_backend/app/routes/documents_routes.py) (121), [db.py](surfsense_backend/app/db.py) (119).
- Plus ~120 test files under `surfsense_backend/tests` mirror these patterns (rename in the same release).

This is mostly mechanical (an automated symbol rename handles the bulk), but a fixed set of STRING-LITERAL contracts and EXTERNAL contracts are NOT safe to blind-replace — they get explicit decisions in this plan (see "String-literal & external contracts").

## Transition policy: HARD CUTOVER (confirmed)

The umbrella defers all frontend/client work, and the frontend will be (re)built against the corrected backend in its own umbrella rather than kept alive in lockstep. So this phase HARD-CUTS the external API — no backward-compat aliases.

- URL paths: rename `/api/v1/searchspaces...`, `/api/v1/search-spaces/...`, `/api/v1/...search-space...` outright to the canonical `/api/v1/workspaces...` ([routes/search_spaces_routes.py](surfsense_backend/app/routes/search_spaces_routes.py) 73-373; mount at [app.py](surfsense_backend/app/app.py) 993, `crud_router` under `/api/v1`).
- JSON field names: rename `search_space_id` -> `workspace_id` in request/response bodies outright (e.g. [schemas/new_chat.py](surfsense_backend/app/schemas/new_chat.py), [schemas/rbac_schemas.py](surfsense_backend/app/schemas/rbac_schemas.py), [schemas/documents.py](surfsense_backend/app/schemas/documents.py)). No `populate_by_name` alias plumbing.

CONSEQUENCE (accepted): the existing deployed frontend breaks against the renamed API until its umbrella lands. Backend correctness is therefore verified INDEPENDENTLY of the old UI — via the test suite, OpenAPI/`/docs`, and direct API calls — not by clicking through the current frontend. (Alias/dual-serve was considered and rejected: it adds plumbing to keep a frontend alive that is being redesigned anyway.)

## Rename waves (order matters)

### Wave A — ORM core in [db.py](surfsense_backend/app/db.py)

1. Classes: `SearchSpace` (1688), `SearchSpaceRole` (2021/2027), `SearchSpaceMembership` (2058/2064), `SearchSpaceInvite` (2107/2113) -> `Workspace`, `WorkspaceRole`, `WorkspaceMembership`, `WorkspaceInvite`.
2. Drop the Phase 1 shim on every column: `search_space_id = Column("workspace_id", Integer, ForeignKey("workspaces.id", ...))` -> `workspace_id = Column(Integer, ForeignKey("workspaces.id", ...))` (the explicit `"workspace_id"` first arg is now redundant because attribute name == column name). Same for `owner_search_space_id` -> `owner_workspace_id` (785-787).
3. INVERSE OF PHASE-1 FINDING 1: now that the attribute `.key` becomes `workspace_id`, the `__table_args__` inner column-reference strings MUST flip to `"workspace_id"` to match — `UniqueConstraint("search_space_id", ...)` -> `UniqueConstraint("workspace_id", ...)` at 1826-1832 (`uq_workspace_user_connector_type_name`), 2029-2033 (`uq_workspace_role_name`), 2066-2070 (`uq_user_workspace_membership`), and the `Index(... "search_space_id" ...)` at 978-979. (Phase 1 deliberately left these as `search_space_id`; Phase 2 completes them. Getting this wrong = config-time boot failure, same failure mode as Phase 1 finding 1, just mirrored.)
4. Relationships (~35 pairs): rename the attribute names and both ends of `back_populates`, and the target-class strings:
   - Child side: `search_space = relationship("SearchSpace", back_populates="...")` -> `workspace = relationship("Workspace", back_populates="...")` (e.g. Folder 1340, Document 1421, Connection 948).
   - Hub side on `Workspace`: `back_populates="search_space"` -> `"workspace"` for folders (1726-1728), documents, threads, podcasts, video_presentations, reports, image_generations, logs, notifications, connectors, connections, automations, roles, memberships, invites.
   - User side (both auth branches ~2205 and ~2337): `search_spaces = relationship("SearchSpace", ...)` -> `workspaces = relationship("Workspace", ...)`; `search_space_memberships` -> `workspace_memberships`; invites likewise.
   - External chat: `owner_search_space = relationship("SearchSpace", foreign_keys=[owner_search_space_id])` (819-820) -> `owner_workspace = relationship("Workspace", foreign_keys=[owner_workspace_id])`.
5. CHECK text on `connections`: `ck_connections_scope_owner` (1578-1581) `search_space_id` -> `workspace_id` in the SQL string. (Phase 1 already did this if shipped; re-confirm. The scope literal `'SEARCH_SPACE'` stays — see enum carve-out.)
6. Runtime index DDL in `_INDEX_DEFINITIONS` (2820-2830): already renamed to `workspace_id`/`idx_documents_workspace_id` in Phase 1 — confirm no `search_space` remains.

### Wave B — satellite ORM modules (mirror Wave A; drop shim, flip strings)

- [automations/persistence/models/automation.py](surfsense_backend/app/automations/persistence/models/automation.py) (27-29 column, 68 relationship).
- [file_storage/persistence/models.py](surfsense_backend/app/file_storage/persistence/models.py) (32-34).
- [notifications/persistence/models.py](surfsense_backend/app/notifications/persistence/models.py) (50-52 column, 72 relationship, plus the index `ix_notifications_user_space_created` 36-41 — definition auto-follows; rename only if you want the name clean).
- [podcasts/persistence/models.py](surfsense_backend/app/podcasts/persistence/models.py) (71-72).

### Wave C — Pydantic schemas

- Dedicated module [schemas/search_space.py](surfsense_backend/app/schemas/search_space.py): classes `SearchSpaceBase/Create/Update/Read/WithStats` -> `Workspace*`. Rename file to `schemas/workspace.py`. Update re-exports in [schemas/__init__.py](surfsense_backend/app/schemas/__init__.py) (106-111, and `UserSearchSpaceAccess` ~87).
- Field `search_space_id` -> `workspace_id` across: new_chat, rbac_schemas (+ `search_space_name`, `UserSearchSpaceAccess`), documents, folders, image_generation, model_connections, search_source_connector, logs, stripe, prompts, chat_comments, video_presentations, reports, obsidian_plugin, podcasts/api/schemas, automations schemas, notifications/api/schemas.
- Under hard cutover the serialized JSON key changes outright to `workspace_id` (no alias). Update fixtures/contract tests accordingly.

### Wave D — services / utils / tasks / agents / gateway / event_bus (the mechanical bulk)

Pure attribute/param/function symbol rename `search_space_id -> workspace_id`, `search_space -> workspace`, plus function renames:
- RBAC helpers [utils/rbac.py](surfsense_backend/app/utils/rbac.py): `check_search_space_access` (129), `is_search_space_owner` (160), `get_search_space_with_access_check` (180) -> `*_workspace_*`.
- Validator [utils/validators.py](surfsense_backend/app/utils/validators.py): `validate_search_space_id` (16).
- Retrievers [retriever/documents_hybrid_search.py](surfsense_backend/app/retriever/documents_hybrid_search.py), [retriever/chunks_hybrid_search.py](surfsense_backend/app/retriever/chunks_hybrid_search.py) (~26 each, filter clauses).
- Connector service [services/connector_service.py](surfsense_backend/app/services/connector_service.py) (ctor param + `self.search_space_id`, + the in-process caches keyed by id — see literals).
- Indexers under `app/tasks/connector_indexers/*`, `indexing_pipeline/*`, `services/*/kb_sync_service.py`.
- Agents: dep-dict KEYS like `"search_space_id": d["search_space_id"]` (e.g. [agents/.../subagents/connectors/google_drive/tools/index.py](surfsense_backend/app/agents/chat/multi_agent_chat/subagents/connectors/google_drive/tools/index.py) 28; `main_agent/runtime/factory.py` 137); class `SearchSpaceSkillsBackend` (`.../main_agent/skills/backends.py` 184).
- Gateway: [gateway/inbox_processor.py](surfsense_backend/app/gateway/inbox_processor.py), [gateway/agent_invoke.py](surfsense_backend/app/gateway/agent_invoke.py), [gateway/auth_invariant.py](surfsense_backend/app/gateway/auth_invariant.py).
- Event bus: `Event.search_space_id` field ([event_bus/event.py](surfsense_backend/app/event_bus/event.py) 36), `publish(... search_space_id=...)` ([event_bus/bus.py](surfsense_backend/app/event_bus/bus.py) 43-49), payload-dict key in [event_bus/events/document_entered_folder.py](surfsense_backend/app/event_bus/events/document_entered_folder.py) 74-76 — see literals decision.

### Wave E — routes: rename handlers + consolidate the three URL spellings

Canonical: `/workspaces` (umbrella decision). Current spellings to retire:
- `/searchspaces` (no hyphen): [search_spaces_routes.py](surfsense_backend/app/routes/search_spaces_routes.py) (73-373), [rbac_routes.py](surfsense_backend/app/routes/rbac_routes.py), [agent_permissions_route.py](surfsense_backend/app/routes/agent_permissions_route.py), [team_memory_routes.py](surfsense_backend/app/routes/team_memory_routes.py).
- `/search-spaces` (hyphen, plural): [editor_routes.py](surfsense_backend/app/routes/editor_routes.py), [notes_routes.py](surfsense_backend/app/routes/notes_routes.py), [export_routes.py](surfsense_backend/app/routes/export_routes.py), [model_connections_routes.py](surfsense_backend/app/routes/model_connections_routes.py) (`/model-roles`).
- `/search-space` (hyphen, singular): [logs_routes.py](surfsense_backend/app/routes/logs_routes.py) 252, [gateway_webhook_routes.py](surfsense_backend/app/routes/gateway_webhook_routes.py) 992/1022, webhook path `{search_space_id}` in [circleback_webhook_route.py](surfsense_backend/app/routes/circleback_webhook_route.py) 215/315.
- Rename the route files (`search_spaces_routes.py` -> `workspaces_routes.py`) and handler fns (`create_search_space` etc.) and the import/include in [routes/__init__.py](surfsense_backend/app/routes/__init__.py) (63, 73).

Mechanism: routers use `APIRouter()` with the path fully spelled in each decorator (no per-router prefix), mounted under `/api/v1` at [app.py](surfsense_backend/app/app.py) 993. So consolidation = edit each decorator string to `/workspaces/{workspace_id}/...` outright (hard cutover; no alias routers).

### Wave F — tests + fixtures

Rename `surfsense_backend/tests/**`; watch for fixtures that hardcode the table name `searchspaces`/JSON key `search_space_id` (those depend on the transition policy for API tests).

## String-literal & external contracts (explicit decisions — NOT blind-replace)

These do not move with a symbol rename; each is decided here.

1. Enum VALUES `'SEARCH_SPACE'` — `ConnectionScope.SEARCH_SPACE` ([db.py](surfsense_backend/app/db.py) 204-207, stored in `connections.scope` via `SQLAlchemyEnum`, line 1558) and `ChatVisibility.SEARCH_SPACE` (510-520, stored in `new_chat_threads.visibility`, 596-597). DECISION: KEEP the enum value strings as-is. They are persisted in Postgres and exposed in JSON; renaming the value needs a data migration + PG enum-type alter for zero benefit. This matches Phase 1's decision to keep the `'SEARCH_SPACE'` CHECK literal. (Optionally rename only the Python member to `WORKSPACE` while keeping `= "SEARCH_SPACE"` — deferred; not worth the churn for MVP.)
2. Celery task `name=` strings — `"delete_search_space_background"` ([tasks/celery_tasks/document_tasks.py](surfsense_backend/app/tasks/celery_tasks/document_tasks.py) 206), `"ai_sort_search_space"` (1546). These are the WIRE NAME between producer and worker; tasks dispatch via `.delay()`/`send_task` (e.g. event trigger `send_task(TASK_NAME, ...)` in [automations/triggers/builtin/event/source.py](surfsense_backend/app/automations/triggers/builtin/event/source.py) 19). DECISION: KEEP the `name=` strings unchanged; freely rename the Python function symbols (`ai_sort_search_space_task` etc.). A rolling deploy with renamed wire names would orphan in-flight messages. (If a cosmetic rename is wanted later, do it with a dual-register + queue-drain, out of scope here.)
3. Redis key literals — `surfsense:spawn_paused:{search_space_id}` (`tasks/.../spawn_paused.py`) and `ai_sort:search_space:{search_space_id}:lock` ([document_tasks.py](surfsense_backend/app/tasks/celery_tasks/document_tasks.py) 1542). DECISION: rename literals to `workspace` (these hold short-lived locks / an ops toggle). Accept that any in-flight lock / paused-flag resets at deploy (locks are seconds-long; paused-flag is an ops action). UPDATE the runbook in `.env.example` (the `redis-cli SET surfsense:spawn_paused:<id>` doc, ~503-504).
4. Event payload key `search_space_id` — `Event` is `model_dump`ed and sent to Celery for automation event triggers, and trigger filters read the key. DECISION: rename the field to `workspace_id` (internal, and triggers are re-evaluated continuously); accept transient loss of any event enqueued across the deploy boundary (fire-and-forget). Drain the event queue during the maintenance window to be safe.
5. OpenTelemetry attribute `search_space.id` + metric label ([observability/otel.py](surfsense_backend/app/observability/otel.py) 263-264/305-306, [observability/metrics.py](surfsense_backend/app/observability/metrics.py) 537-542). DECISION: KEEP the OTel/metric KEY `search_space.id` for now (dashboards/alerts depend on it); rename only the Python params. Schedule the observability-key rename as a separate, announced change. (Carve-out to avoid silently breaking alerting.)
6. Notification dedup/operation IDs embedding `{search_space_id}` (e.g. `doc_..._{search_space_id}_...`, `insufficient_credits_{search_space_id}_...`) and frontend deep-link strings like `/dashboard/{search_space_id}/buy-more`. DECISION: the ID is a numeric value, not the literal word — leave format strings as-is functionally; the embedded VALUE is unchanged. The `/dashboard/{id}/...` deep link points at a FRONTEND route still named `[search_space_id]` (deferred umbrella) — KEEP it until the frontend segment renames, else links 404.
7. Storage path builders — `documents/{search_space_id}/...` ([file_storage/keys.py](surfsense_backend/app/file_storage/keys.py) 20-26) and `podcasts/{search_space_id}/...` ([podcasts/storage.py](surfsense_backend/app/podcasts/storage.py) 22-25). The path segment is the numeric ID; the literal word `search_space` is NOT in stored object keys. DECISION: rename the param only; NO blob migration needed; existing objects keep resolving.
8. `SearchSourceConnector` — contains "search" but is the connectors table, a different concept (the word "search" here is unrelated to `SearchSpace`). OUT OF SCOPE: this rename does NOT touch it, and Phase 4 does not rename the class either — Phase 4 adds a Type-1/Type-2 taxonomy via a static `connector_type`→(category, availability) registry (no new column) and KEEPS `is_indexable` (`db.py:1868`). Leave `SearchSourceConnector` as-is.
9. Historical Alembic migrations (`surfsense_backend/alembic/versions/*`) — ~20 files embed `searchspaces` / `search_space_id` as raw-SQL string literals (e.g. `23_associate_connectors_with_search_spaces.py`, `41_backfill_rbac_for_existing_searchspaces.py`, `40_move_llm_preferences_to_searchspace.py`). DECISION: NEVER rewrite these. They are an immutable replay log that intentionally references the schema as it existed at that revision; rewriting them corrupts history and breaks a clean `alembic upgrade` from zero. Verified safe: no migration imports the ORM classes (only `from app.db import Base` in `env.py` / `0_initial_schema.py`), so the class rename does not touch them. Phase 1's rename migration (the next integer after the live head — `170` at time of writing, since `main` advanced the head to `169`, but chain by actual `alembic heads`) is the single transition point; migrations after it use the new names. The scripted rename scope is `app/` + `tests/` ONLY.
10. LangGraph persisted state channel key `search_space_id` — `input_state = {..., "search_space_id": search_space_id, ...}` ([tasks/chat/streaming/flows/new_chat/input_state.py](surfsense_backend/app/tasks/chat/streaming/flows/new_chat/input_state.py) 131) is a CHECKPOINTED state channel. The resume_chat flow reads persisted state (`agent.aget_state({"configurable": {"thread_id": ...}})`, [flows/resume_chat/resume_routing.py](surfsense_backend/app/tasks/chat/streaming/flows/resume_chat/resume_routing.py) 50) and HITL interrupts (`surfsense_resume_value`, `HumanReview`) can sit pending across a deploy. DECISION: rename the channel key to `workspace_id` for consistency, and ACCEPT that any chat thread paused at a HITL interrupt BEFORE the cutover must be restarted after (the old checkpoint carries `search_space_id`, the new graph reads `workspace_id`). Operationally: drain/resolve pending interrupts before deploy if practical. (Alternative — keep the channel key as a carve-out — rejected: leaves a lone `search_space_id` in otherwise-renamed agent state for a transient, conversation-scoped value. The `configurable` keys are `thread_id` / `surfsense_resume_value`, not `search_space_id`, so only this state channel is affected.)
11. User-facing default literal — `users.py` seeds the default workspace `name="My Search Space"` (line 158, persisted + shown to users) and logs "Created default search space" (207). DECISION: rename the default name to "My Workspace" (backend-created seed value, not caught by a symbol rename); log strings are cosmetic. Also update the Redis-key assertion in `tests/unit/services/test_ai_sort_task_dedupe.py:14` when literal 3 is renamed.

## Execution approach

- Automate the safe bulk: a scripted symbol rename (IDE rename / `ast-grep`-style) for `search_space_id -> workspace_id`, `search_space -> workspace`, `SearchSpace -> Workspace`. SCOPE STRICTLY to `app/` + `tests/` — NEVER `alembic/versions/` (carve-out 9: immutable replay log). EXCLUDE the other carve-outs above (enum values, Celery `name=`, OTel keys, frontend deep-links, default-name literal). Run per-wave, not all at once, so review is tractable.
- Then hand-apply the carve-outs and the routing consolidation.
- One atomic release (same coupling rule as Phase 1): ORM + schemas + routes + literals ship together; there is no half-renamed steady state.

## Verification & rollout

- `alembic revision --autogenerate` must produce an EMPTY diff: confirms the renamed ORM (classes/attrs/constraint inner-strings) still matches the Phase 1 physical schema. A diff means a missed attribute flip or a stale `__table_args__` string.
- Boot API + Celery worker; verify via OpenAPI/`/docs` + direct API calls (NOT the old frontend): create workspace, chat, document upload, an RBAC invite/membership op, an automation event trigger, and a podcast — exercising the renamed relationships (`workspace`, `workspaces`), tasks, and event payloads.
- Hard-cutover contract check: confirm `/workspaces...` resolves and the three legacy spellings now 404; confirm bodies use `workspace_id` only.
- Full backend test suite green; grep `surfsense_backend/app` for residual `search_space`/`SearchSpace` and confirm every remaining hit is an intentional carve-out (enum value, Celery `name=`, OTel key, frontend deep-link).
- Confirm `alembic/versions/*` was NOT modified by the rename (git diff shows zero changes under that path) — guard against carve-out 9.
- Resume check (carve-out 10): start a chat, trigger a HITL interrupt, deploy/rename, then verify NEW interrupts resume on `workspace_id`; accept that pre-cutover pending interrupts are restarted. Ideally drain pending interrupts before deploy.
- Observability check: `search_space.id` OTel attribute still emitted (carve-out 5) so dashboards keep working.

## Risks

- Stale `__table_args__` inner string after attribute flip (Wave A.3) — config-time boot failure; mirror of Phase 1 finding 1. Mitigated by the autogenerate empty-diff gate + boot smoke test.
- Relationship rename misses one `back_populates` end — mapper-config error at startup; the pair list in Wave A.4 is the checklist.
- Hard cutover breaks the existing frontend in the interim (accepted) — mitigated by verifying the backend via tests/OpenAPI/API calls, and by (re)building the frontend against the new contract in its umbrella. Do not rely on the old UI to smoke-test during this window.
- Renaming a Celery `name=` or the event payload key without a drain — orphaned/dropped in-flight messages; mitigated by the carve-out (keep task names) + queue-drain for events.
- Enum value migration scope creep — explicitly OUT (carve-out 1); keep `'SEARCH_SPACE'` values.
- Scripted rename corrupting historical Alembic migrations (carve-out 9) — would break `alembic upgrade` from zero / replay history; mitigated by scoping the rename to `app/`+`tests/` and the git-diff guard on `alembic/versions/`.
- Renaming the persisted LangGraph state channel key (carve-out 10) — breaks resume of threads paused at a HITL interrupt across the cutover; mitigated by draining interrupts pre-deploy and accepting restart of any stragglers (state is conversation-scoped/ephemeral).
- Sheer size (~150 app + ~120 test files) — mitigated by per-wave scripted rename + the empty-diff and residual-grep gates.

## Out of scope (later phases / umbrella)

- Frontend route segment `[search_space_id] -> [workspace_id]`, `search-space-settings/`, TS types, atoms, i18n, frontend Zero schema — deferred frontend umbrella.
- Satellite apps (desktop, Obsidian, browser extension, evals) + docs — deferred.
- Connector `category` discriminator and `SearchSourceConnector` handling — Phase 4 ([04a-connector-category.md](04a-connector-category.md)).
- Enum VALUE migration and observability-key rename — deliberately deferred announced changes.
