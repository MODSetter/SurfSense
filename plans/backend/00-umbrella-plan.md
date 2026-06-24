# CI Pivot MVP — Umbrella Plan

> Master roadmap for the Competitive Intelligence pivot. Each phase becomes its own subplan saved in this folder (`content_research/pivot/`).

This is the high-level roadmap. It is sequenced to match the agreed order: rename first, then connector restructure, then Pipelines.

> SCOPE: This umbrella currently covers the BACKEND only (`surfsense_backend`). Frontend (`surfsense_web`) and client apps (desktop, Obsidian, browser extension) will get their own umbrella/subplans LATER, once the backend is fully working as expected. Frontend-facing decisions (URL segment, TS types, i18n copy) are recorded below where relevant but are out of scope for the active phases.

## Positioning

"NotebookLM for Competitive Intelligence" — each WorkSpace acts as a workspace for setting up competitive-intelligence-optimised notebooks.

## Target architecture

```mermaid
flowchart TD
  WS[WorkSpace] --> CONN[Connectors]
  WS --> PIPE[Pipelines]
  WS --> KB[(Knowledge Base: documents + chunks)]
  CONN --> T1[Type 1: Data Sources - pull]
  CONN --> T2[Type 2: MCP Tools - act]
  T1 --> WEB[Universal WebURL Crawler - functional]
  T1 --> PLAT[Platform connectors - coming soon]
  T1 --> UP[File Upload]
  PIPE --> RUN[PipelineRun history]
  PIPE -->|"save_to_kb + destination folder"| KB
  RUN -->|"manual or cron"| T1
  T2 --> CHAT[Chat / Automations]
  CHAT --> DELIV[Deliverables: audio/video/report/image]
  RUN -->|"read-only context"| CHAT
```

## Decisions locked

- Full rename SearchSpace -> WorkSpace across DB, API, URLs, code, satellite apps.
- Canonical names (proposed defaults): DB table `workspaces`, column `workspace_id`, RBAC tables `workspace_roles` / `workspace_memberships` / `workspace_invites`, API base `/workspaces` (consolidating today's `/searchspaces` vs `/search-spaces` split), URL segment `[workspace_id]`, settings folder `workspace-settings`, TS type `Workspace`.
- Connectors get a `category` discriminator: `DATA_SOURCE` (Type 1) vs `MCP_TOOL` (Type 2). Type 1 keeps only file/cloud data sources (WebURL crawler, Google Drive, OneDrive, Dropbox, YouTube, file uploads) plus deferred platform connectors. Everything else moves to MCP. Artifacts stay in the existing `deliverables` agent system (not routed through MCP).
- Web search APIs (Tavily, SearXNG, Linkup, Baidu, Serper) are repurposed as a SOURCE-DISCOVERY helper: they suggest URLs the user can add to the Universal WebURL Crawler when setting up pipelines (they are not a standalone connector type and do not index data).
- Obsidian and Circleback (push/webhook sources) are DISABLED for the MVP.
- MCP-availability audit complete: BookStack (community MCP servers), Elasticsearch (official Elastic Agent Builder MCP), and Luma (community MCP servers) all have MCP available, so none are disabled — they migrate to Type-2.
- `Pipeline` and `PipelineRun` are new first-class tables. A Pipeline references a connector + config + schedule + KB destination. File upload creates/uses a pipeline and registers a run; uploads always save to KB.
- The chat agent gets read-only access to pipeline run history (pipelines + their recent runs/status) as context, so it can reason about what was fetched, when, and whether runs succeeded — even for data not saved to the KB.
- Deferred (post-MVP): platform scraper implementations, public pay-as-you-go API for Type-1 connectors, public MCP server exposing the KB.

## Platform connector research list (deferred build, MVP = "coming soon")

- LinkedIn — people profiles (discovery by keyword/company), company info, job listings.
- Amazon — product (ASIN), search (keyword), pricing; reviews secondary.
- Google — Web Search (organic SERP), AI Overviews, Maps/Local (discover by location).
- Instagram — profiles first, then posts; discover profiles by username/keyword.
- Zillow / Redfin — full property listings (discover by search URL/filters); Zillow price history.
- Walmart — product, search; zipcode-localized pricing premium variant.
- eBay — search by keyword/category; price-comparison/resale feeds.
- Crunchbase — company info, search by keyword (B2B lead-gen / investor research).
- TikTok / YouTube — profiles/channels, posts/videos; discover by keyword/hashtag; TikTok Shop.
- Indeed / Glassdoor — job listings (discover by keyword in location), company reviews.

## Backend phases (active — this umbrella)

### Phase 1 — Rename foundation (DB) [`subplan: 01-rename-db.md`]

- Alembic migration: rename `searchspaces` -> `workspaces`; rename `search_space_id` -> `workspace_id` on ~20 child tables; rename RBAC tables and their FKs; rename indexes/constraints (`uq_searchspace_*`, `idx_documents_search_space_id`, etc.); update Rocicorp Zero publication column lists (backend-owned `publication` definition; frontend Zero schema rename happens in the later frontend umbrella).
- Decide transition strategy: hard cutover (simplest for MVP) vs temporary API aliases for clients.
- Key files: `surfsense_backend/app/db.py`, `surfsense_backend/alembic/versions/` (new migration).

### Phase 2 — Rename backend (code + API) [`subplan: 02-rename-backend.md`]

- Rename models/schemas/services/routes/agents/tasks identifiers: `SearchSpace*` -> `Workspace*`, `search_space_id` -> `workspace_id`.
- Consolidate API to `/workspaces` and fix the `/searchspaces` vs `/search-spaces` inconsistency.
- High-touch files: `routes/search_spaces_routes.py`, `routes/rbac_routes.py`, `utils/rbac.py` (`check_search_space_access`), `schemas/search_space.py`, plus `search_space_id` threading through agents/Redis keys/storage paths (`documents/{id}/...`).

### Phase 3 — Connector two-type restructure (backend) [`subplan: 03-connector-two-type-backend.md`]

- Add `category` (`DATA_SOURCE` / `MCP_TOOL`) to `SearchSourceConnector` (replaces ad hoc `is_indexable`): `db.py` enum/model, schema, Alembic migration + data backfill that tags existing rows.
- Adjust backend routing/indexing so only Type-1 keeps the `/index` + Celery path; Type-2 resolves via MCP tools.
- Add a backend source-discovery endpoint for the WebURL Crawler (reuses existing web-search services); UI surfacing is deferred to the frontend umbrella.
- Frontend connector UI restructure is DEFERRED.

**Type 1 — Data Sources (pull -> feed pipelines/KB).** Keep only:

- Universal WebURL Crawler (functional for MVP; from current `WEBCRAWLER_CONNECTOR`). Gets a source-discovery assist powered by the web search APIs (see below) to suggest URLs for pipelines.
- Google Drive (native + Composio) — `google_drive_indexer.py`.
- OneDrive — `onedrive_indexer.py`.
- Dropbox — `dropbox_indexer.py`.
- YouTube — promote from frontend-only/document handling to a real Type-1 connector (extra work: no backend connector today).
- File uploads.
- Platform connectors (coming soon, not built): LinkedIn, Amazon, Google, Instagram, Zillow/Redfin, Walmart, eBay, Crunchbase, TikTok, Indeed/Glassdoor.

**Type 2 — MCP Tools (act in chat/automations).** Migrate existing connectors to MCP (all audited services have an MCP available):

- Notion, GitHub, Confluence, Slack, Teams, Linear, Jira, ClickUp, Airtable, Discord, Gmail, Google Calendar. (Linear/Jira/ClickUp/Slack/Airtable already store MCP server URL + OAuth in `config`.)
- BookStack (community MCP), Elasticsearch (official Elastic Agent Builder MCP, 9.2+), Luma (community MCP) — confirmed MCP available, migrate rather than disable.
- Fix known gap: `MCP_CONNECTOR` is missing from the subagent routing map (`constants.py`) — generic MCP tools get discovered but skipped.

**Web search APIs — repurposed (not a connector type):**

- Tavily, SearXNG, Linkup, Baidu, Serper become a source-discovery helper for the Universal WebURL Crawler: given a topic/competitor, suggest candidate URLs the user can add to a pipeline. Reuses the existing web-search services; backend endpoint here, UX deferred to frontend umbrella.

**Disabled for MVP:**

- Obsidian (plugin push) and Circleback (meeting webhook) — disabled for the pivot MVP.

### Phase 4 — Pipelines data model [`subplan: 04-pipelines-model.md`]

- New tables: `pipelines` (workspace_id, user_id, connector_id, name, config JSON, schedule/cron, `save_to_kb` bool, `destination_folder_id` nullable, enabled, next_scheduled_at) and `pipeline_runs` (pipeline_id, status, trigger = manual/scheduled/upload, timestamps, doc counts, error, optional raw-result blob ref).
- Models + Pydantic schemas + Alembic migration + backend Zero publication entry.
- Pipelines API routes: CRUD + manual run trigger + list runs.

### Phase 5 — Pipeline execution + scheduling [`subplan: 05-pipelines-exec.md`]

- Run engine: pipeline run -> invoke connector fetch (WebURL crawler for MVP) -> if `save_to_kb`, route through `IndexingPipelineService` into the destination folder -> write `PipelineRun` record.
- Scheduling: reuse the Celery Beat meta-scheduler pattern (`schedule_checker_task.py`, `periodic_scheduler.py`) for cron + manual triggers.
- When `save_to_kb` is off, persist the raw fetch result on the run (blob via `file_storage`) so it is retrievable without indexing.
- Chat agent context: expose pipeline run history to the `multi_agent_chat` agent (read-only) — via a tool (e.g. `list_pipelines` / `get_pipeline_runs`) and/or a context middleware injection (similar to `KnowledgeTreeMiddleware`). Scope strictly to the active workspace. Gives the agent awareness of recent runs, statuses, schedules, and last-fetched timestamps.

### Phase 6 — File upload as a pipeline + KB-save-secondary [`subplan: 06-upload-pipeline-kb.md`]

- Wire file upload (`documents_routes.py` fileupload flow) to create/use an "Uploads" pipeline and register a `PipelineRun`; uploads always `save_to_kb = true`.
- Generalize KB saving to be opt-in for non-upload pipelines via `save_to_kb` + destination folder.

## Deferred — Frontend & client phases (separate umbrella, planned LATER)

These are recorded for continuity but are NOT planned in this umbrella. They start once the backend phases above are working.

- Frontend rename + i18n: route segment `[search_space_id]` -> `[workspace_id]`, `search-space-settings/` -> `workspace-settings/`, TS types, api services, Jotai atoms, components, cache keys, and "Workspace" copy across 5 locales (`messages/{en,zh,es,pt,hi}.json`), plus frontend Zero schema rename.
- Satellite/client apps + docs rename: `surfsense_desktop`, `surfsense_obsidian`, `surfsense_browser_extension`, `surfsense_evals`, README/docs.
- Connector two-type UI: restructure `connector-popup` and `connector-constants.ts` into the two labeled types.
- Pipelines UI + positioning: Pipelines section (list/create/configure/run-history/manual run), WebURL source-discovery UX, file-upload-as-pipeline surfacing, "coming soon" platform cards, "NotebookLM for Competitive Intelligence" copy.

## Open items to confirm during subplanning

- ~~Rename transition: hard cutover vs temporary API aliases~~ RESOLVED: HARD CUTOVER (see resolved log + 02-rename-backend.md). The frontend is rebuilt against the corrected backend in its own umbrella; backend is verified via tests/OpenAPI, not the old UI.
- Whether existing connector periodic-indexing config is migrated into Pipelines or coexists during MVP.
- Chat agent run-history access: tool vs middleware injection vs both (default: tool).
- Type-2 MCP migration depth: actually re-point native connectors (Notion/GitHub/Gmail/etc.) to MCP servers now, vs keep their existing native integration and just re-tag them under the MCP-Tools category for MVP.

## Resolved decisions log

- Web search APIs (Tavily/SearXNG/Linkup/Baidu/Serper): repurposed as source-discovery helper for the WebURL Crawler (suggest URLs for pipelines); not a standalone connector type.
- Obsidian + Circleback: disabled for MVP.
- MCP-availability audit: BookStack, Elasticsearch, Luma all have MCP available -> migrate to Type-2, none disabled.
- Rename transition policy: HARD CUTOVER of the external API (paths + JSON field names) in Phase 2 — no backward-compat aliases. Rationale: the frontend is (re)built against the corrected backend later, so there is no old client to keep alive; backend correctness is verified via the test suite + OpenAPI rather than the existing UI.

## Subplan index (backend)

| Phase | Subplan file | Status |
|-------|--------------|--------|
| 1 | `01-rename-db.md` | drafted |
| 2 | `02-rename-backend.md` | drafted |
| 3 | `03-connector-two-type-backend.md` | not started |
| 4 | `04-pipelines-model.md` | not started |
| 5 | `05-pipelines-exec.md` | not started |
| 6 | `06-upload-pipeline-kb.md` | not started |

Frontend & client subplans will be added under a separate umbrella later (see "Deferred — Frontend & client phases").
