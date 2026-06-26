# Phase 4b — Web-search repurposing + source-discovery endpoint

> Part of **Phase 4 — Connector two-type restructure (backend)**. See `00-umbrella-plan.md`.
> Sibling: `04a-connector-category.md`. Best sequenced **after** `04a` (taxonomy in place). Precondition: Phases 1–2 (rename) live.

> **Implementation note.** Citations use **today's** names (`search_space_id`/`SearchSpace`); post Phases 1–2 the live code says `workspace_id`/`Workspace` — map accordingly, and locate code by **symbol/grep**, not the absolute line numbers cited.

## Objective

Retire the five web-search **connector types** and re-cast the survivors as **platform-level providers** that power two things: (1) the existing chat `web_search` tool, and (2) a new **source-discovery endpoint** that, given a topic/competitor, suggests candidate URLs the user can feed into the Universal WebURL Crawler / a pipeline.

Resolved decisions driving this:

- **Drop all 5 search `connector_type` enum values** (`SERPER_API`, `TAVILY_API`, `SEARXNG_API`, `LINKUP_API`, `BAIDU_SEARCH_API`).
- **Tavily + Serper removed entirely** (no provider, no code path).
- **SearXNG / Linkup / Baidu survive as platform providers.** SearXNG is already platform/env-based; **Linkup + Baidu move from per-workspace connector `config` to platform/env config** (one app-wide key set, matching the "single provider app-wide" style from `03b`).

## Current state (cited)

### The 5 search types are first-class connectors today

- Enum members `SERPER_API`/`TAVILY_API`/`SEARXNG_API`/`LINKUP_API`/`BAIDU_SEARCH_API` — `db.py:86–90` (`SERPER_API` is annotated "NOT IMPLEMENTED YET"; SearXNG is already platform-backed despite being an enum value).
- Per-workspace search methods on `ConnectorService` read keys from the connector row's `config`: `search_tavily` (`connector_service.py:481`, key `TAVILY_API_KEY:510`), `search_searxng` (`:587`), `search_baidu` (`:614`), `search_linkup` (`:1968`, key `LINKUP_API_KEY:2000`).
- Query-time routing: `connector_searchable_types.py:_CONNECTOR_TYPE_TO_SEARCHABLE` (`:22–26`) maps `TAVILY_API`/`LINKUP_API`/`BAIDU_SEARCH_API` to the web_search tool ("live search connectors"); the other connector types map to KB pre-search.

### The web_search tool already has a platform/per-workspace split

> **Post-`main`-merge note.** A `main` sync **consolidated web_search to a single tool**: the old research-subagent copy `subagents/builtins/research/tools/web_search.py` was **deleted**, and there is now **one** factory at `app/agents/chat/shared/tools/web_search.py`. The research subagent now imports it (`subagents/builtins/research/tools/index.py:10,24–26`). So everywhere below that said "both variants / mirror" is now **one file**. The same merge also retired the XML result blob in favor of `[n]`-citation rendering (see §3).

`web_search` tool factory `create_web_search_tool(search_space_id, available_connectors)` — the single canonical tool at `app/agents/chat/shared/tools/web_search.py`:
- `_LIVE_SEARCH_CONNECTORS = {TAVILY_API, LINKUP_API, BAIDU_SEARCH_API}` (`:41–45`), `_LIVE_CONNECTOR_SPECS` → `ConnectorService.search_*` (`:47–51`), per-connector dispatch `_search_live_connector` (`:115–151`). The factory picks the active live connectors by intersecting `available_connectors` with `_LIVE_SEARCH_CONNECTORS` (`:163–167`).
- At call time it fans out **in parallel** to platform SearXNG (`web_search_service.is_available()` / `.search()`, `:204–214`) **plus** each active per-workspace live connector (`:216–228`), then dedupes by URL (`:242–250`).
- Platform SearXNG service: `app/services/web_search_service.py` — env-gated by `config.SEARXNG_DEFAULT_HOST`, in-process circuit breaker + Redis result cache; returns the `(result_obj, documents)` shape the tool consumes.

### Config

- `config.SEARXNG_DEFAULT_HOST = os.getenv("SEARXNG_DEFAULT_HOST")` — `config/__init__.py:558`. There are **no** platform env vars for Linkup/Baidu/Tavily today (their keys live in connector `config`).

## Target design

### 1. Platform search-provider config (env)

Add platform env knobs alongside `SEARXNG_DEFAULT_HOST` (`config/__init__.py:~558`):

- `LINKUP_API_KEY = os.getenv("LINKUP_API_KEY")`
- `BAIDU_SEARCH_API_KEY = os.getenv("BAIDU_SEARCH_API_KEY")` (+ the optional knobs `search_baidu` reads from connector `config` today — `BAIDU_MODEL` / `BAIDU_SEARCH_SOURCE` / `BAIDU_ENABLE_DEEP_SEARCH`, per `validators.py:507-514`; the required key is `BAIDU_API_KEY` in the per-workspace config, relocated to this platform env var — port from its current `config` reads).
- (SearXNG unchanged.) Document all three in `.env.example` as optional; each provider self-disables when its key/host is unset (mirrors `web_search_service.is_available()`).

No Tavily/Serper env (removed).

### 2. A platform search-providers service (consolidate the survivors)

Introduce `app/services/web_search_service.py`-level functions (or a small `search_providers/` package) so all three survivors share one platform shape `(result_obj, documents)`:

- `searxng.search(...)` — the existing `web_search_service.search` (unchanged).
- `linkup.search(...)` / `baidu.search(...)` — **port the bodies of `ConnectorService.search_linkup`/`search_baidu`** but source the API key from `config.*` (platform) instead of `connector.config` (per-workspace), and drop the `search_space_id`/connector lookups.
- Each is `is_available()`-gated on its env key. Tavily (`search_tavily`) is deleted.

This removes per-workspace coupling: web search + discovery no longer depend on any connector row.

### 3. Rewire the chat `web_search` tool (single tool)

- Drop the `_LIVE_SEARCH_CONNECTORS` / `_LIVE_CONNECTOR_SPECS` / `_search_live_connector` mechanism in the **single** tool `shared/tools/web_search.py` (`:41–51`, `:115–151`, and the factory's live-connector intersection `:163–167`, plus the per-workspace fan-out `:216–228`). Instead, fan out to the **platform providers** that are `is_available()` (SearXNG + Linkup + Baidu), all keyless from the caller's view.
- Keep the existing parallel-gather + URL-dedupe (`:233–250`). **Note:** the `main` merge replaced the old XML result blob with `[n]`-citation rendering — the tool now builds `RenderableDocument`s (`_to_renderable_web_documents:66–112`) and returns them via `render_web_results` + `load_registry`, persisting the `citation_registry` on state (`:252–281`). Leave that render/registry path **unchanged**; only the *provider sourcing* (SearXNG+Linkup+Baidu, env-keyed) changes.
- **Call-site churn — keep the `available_connectors` parameter in the factory signature but stop using it for provider selection** (providers are now env-derived). This avoids touching every caller: `main_agent/tools/registry.py:24,39`, `subagents/builtins/research/tools/index.py:10,24–26`, and `anonymous_chat/agent.py:127` (passes `available_connectors=None` already). **`deliverables` is no longer a web_search caller** (its KB/web tooling was removed in the `main` merge) — drop it from the churn list. `search_space_id` likewise stays for logging only. (A later cleanup can remove the now-dead params.)
- Net behaviour: web search works platform-wide whenever any provider env key is set; it no longer requires the workspace to have a search connector configured (so anonymous chat gains web search too).

### 4. Source-discovery endpoint (the new capability)

New route (e.g. `routes/source_discovery_routes.py`, mounted under `/api/v1/workspaces/{workspace_id}/...` to match the renamed surface): `POST .../source-discovery` taking `{ query/topic, top_k }` and returning a **ranked list of candidate URLs** (url, title, snippet, provider) for the user to add to the WebURL Crawler / a pipeline.

- Implementation = call the platform providers (§2) in parallel, dedupe by URL (reuse the tool's dedupe), and return URL-centric results (plain `{url,title,snippet,provider}` — **not** the chat tool's `[n]`-cited `render_web_results` output, which is for in-conversation citation, not URL suggestion).
- Auth: standard workspace access check (same dependency as other workspace routes).
- This is **backend-only**; the UX (a "find sources" affordance when configuring a crawler/pipeline) is deferred to the frontend umbrella.
- Optional thin reuse: the chat `web_search` `_web_search_impl` and this endpoint can share a `discover_urls(query, top_k) -> list[UrlCandidate]` core.

### 5. Drop the 5 connector types

- **Remove the enum members** `SERPER_API`/`TAVILY_API`/`SEARXNG_API`/`LINKUP_API`/`BAIDU_SEARCH_API` from `SearchSourceConnectorType` (`db.py:86–90`).
- **Remove their connector code paths**: `ConnectorService.search_tavily` (`:481`, delete) and the per-workspace `search_searxng` (`:587`)/`search_baidu` (`:614`)/`search_linkup` (`:1968`) (replace with the platform service §2; delete the connector-config variants that read `connector.config[...]_API_KEY`, e.g. `:510`, `:2000`). Remove the three search entries from `connector_searchable_types.py:24–26`. Remove the `*_API` entries from the connector-config validation dict (`utils/validators.py:490–514`, the 5 keys in `connector_rules`: `SERPER_API:490`/`TAVILY_API:491`/`SEARXNG_API:492-505`/`LINKUP_API:506`/`BAIDU_SEARCH_API:507-514`) and `04a`'s `HIDDEN` registry entries for these types. **Grep-guard:** no remaining references to the 5 enum names or `search_tavily` anywhere.
- **Migration (this phase is NOT migration-free):** existing connector rows of these 5 types must be handled before/with the enum change:
  - Alembic migration: `DELETE FROM search_source_connectors WHERE connector_type IN ('SERPER_API','TAVILY_API','SEARXNG_API','LINKUP_API','BAIDU_SEARCH_API');` (FKs cascade; these rows only held search API keys, now relocated to env). Self-hosted operators re-add Linkup/Baidu keys via env — call out in the migration docstring + `.env.example`.
  - **PG enum handling:** dropping a value from a Postgres enum type requires a type recreate. Lowest-risk option: after deleting the rows, leave the now-unused labels in the PG enum type (harmless orphans) and just remove them from the Python `StrEnum` so no new rows can use them. If a clean type is wanted, do the standard "create new enum → `ALTER COLUMN ... TYPE` with a `USING` cast → drop old" dance in the migration (heavier; only if desired). Recommend the orphan-label approach for MVP.
  - Also scrub `document.document_type` / search rows that referenced `TAVILY_API`/`LINKUP_API`/`BAIDU_SEARCH_API` as a **doc type** only if such persisted docs exist (live-search results were ephemeral, not indexed — verify; expectation is none).

## Work items

1. **Config**: `LINKUP_API_KEY`, `BAIDU_SEARCH_API_KEY` (+ Baidu host/region) in `Config` + `.env.example`; keep `SEARXNG_DEFAULT_HOST`.
2. **Platform providers**: port Linkup/Baidu search to env-keyed platform functions sharing SearXNG's `(result_obj, documents)` shape; delete Tavily.
3. **Rewire `web_search`** (the single shared tool `shared/tools/web_search.py`) to fan out to platform providers; drop `available_connectors`/live-connector plumbing; keep dedupe + the `[n]`-citation render path.
4. **Source-discovery endpoint**: `POST .../source-discovery` → ranked URL candidates; shared `discover_urls()` core.
5. **Drop the 5 enum values** + remove `search_*` connector methods, `connector_searchable_types` search entries, validators, and `04a` HIDDEN entries.
6. **Migration**: delete the 5 connector types' rows; handle the PG enum (orphan-label approach); docstring notes the env re-keying.
7. **Tests** (below).

## Tests

- **Provider availability**: each of SearXNG/Linkup/Baidu self-disables when its env key/host is unset; `web_search` returns "not available" only when all are unset.
- **web_search rewire**: with `LINKUP_API_KEY` set (no search connector rows), `web_search` still returns Linkup results; results from multiple providers dedupe by URL.
- **No per-workspace dependency**: a workspace with zero connectors still gets web search + source-discovery results.
- **Source-discovery endpoint**: returns URL candidates `{url,title,snippet,provider}`; enforces workspace access; empty when no providers configured.
- **Enum removal**: `SearchSourceConnectorType` no longer has the 5 values; creating one → 422; the migration deletes existing rows; reading remaining connectors is unaffected.
- **Tavily gone**: no import/path references `search_tavily`/`TAVILY_API` remain (grep guard).

## Risks / trade-offs

- **Per-workspace search keys become platform-wide (accepted).** Workspaces can no longer bring their own Linkup/Baidu keys; one app-wide key set serves everyone (matches the single-provider posture). Self-hosted must move keys to env — surfaced in migration docs.
- **Destructive migration.** Deleting the 5 connector types' rows is irreversible (downgrade can recreate rows but not their secrets). Gate behind the standard backup/runbook; the data is just API-key config now living in env.
- **PG enum orphan labels.** Leaving unused enum labels is cosmetically untidy but avoids a risky type-recreate; documented as a deliberate trade-off.
- **Sequencing with 04a.** 04a marks the 5 types `HIDDEN` so the taxonomy stays total in the interim; 04b removes them. If 04b ships first, 04a's HIDDEN bucket is simply never populated — both orders are safe, but `04a → 04b` is the intended order.

## Out of scope (hand-offs)

- Taxonomy/gating/MCP-routing fix → `04a`.
- Using discovered URLs to actually create a pipeline/crawl → Phases 5–7 (this endpoint only *suggests* URLs).
- Source-discovery UX (the "find sources" affordance) → frontend umbrella.
- Crawl billing for any crawl the user starts from a discovered URL → already covered by `03c` (the crawl path bills regardless of how the URL was found).
