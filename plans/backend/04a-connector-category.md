# Phase 4a — Connector taxonomy (Type-1/Type-2) + availability gating + MCP routing fix

> ## ↪ REDIRECT / DEMOTED (2026-06-30) — superseded by the revamp
> **The canonical Phase 4 is now [`revamp phases 4-7/04a-capabilities.md`](revamp%20phases%204-7/04a-capabilities.md) + [`04b-access.md`](revamp%20phases%204-7/04b-access.md)** (typed capability verbs + generated doors — see `00-umbrella-plan.md`). This file's connector-taxonomy work is **demoted to backward-compat hygiene**: it is **not** the core of Phase 4. Read the revamp first.
>
> What survives from this doc, and where it goes:
> - **The one genuinely useful piece — the `MCP_CONNECTOR` (BYO MCP) routing-gap fix — moves to `revamp/04b`** (the "consume-user-MCP" work). That's the actionable carry-over.
> - **Keeping legacy branded natives `MIGRATING` (off) + existing indexed KB docs searchable, and Obsidian/Circleback `DISABLED`** — still true; a small hygiene task, no longer a headline phase.
> - **`is_pipeline_eligible` is dropped** (no pipelines); **Type-1 = file/KB-input only** (Drive/Dropbox/OneDrive + uploads → input-only KB); **`WEBCRAWLER_CONNECTOR` is RETIRED** (native `scrape_webpage` tool, now a `web.scrape` capability verb).
>
> The static-registry design below is retained for reference, but do not treat "connector two-type restructure" as the Phase 4 deliverable — the deliverable is the **capability registry** in `revamp/04a`.

> Part of **Phase 4 — Connector two-type restructure (backend)**. See `00-umbrella-plan.md`.
> Sibling: `04b-source-discovery.md` (web-search repurposing). Precondition: Phases 1–2 (rename) live.

> **Implementation note.** Phases 1–2 are **SHIPPED**, so the live code already says `workspace_id`/`Workspace` — substitute for the old `search_space_*`/`SearchSpace` names in citations below and grep the new name. Locate code by **symbol/grep**, not the absolute line numbers cited here, since the rename shifted them.

## Objective

Give connectors a first-class **Type-1 (Data Source) / Type-2 (MCP Tool)** taxonomy and an **availability** state, then gate creation, indexing, chat-subagent build, and (forward-compat) pipeline-eligibility off it — without a DB migration. Also fix the long-standing bug where generic `MCP_CONNECTOR` tools are discovered but dropped.

The taxonomy is **fully determined by `connector_type`** (every Notion row is the same category), so it is modeled as a **static code registry**, not a per-row column (resolved decision — avoids a migration + backfill drift across ~20 connector-create sites). `is_indexable` is **kept** (it is an orthogonal per-row capability that still gates the real `/index` + periodic machinery — e.g. Notion is `is_indexable=True` yet is a Type-2 tool).

## Locked model (MVP)

| Bucket | `category` | `availability` | Members | Behaviour |
|--------|-----------|----------------|---------|-----------|
| Functional data sources | `DATA_SOURCE` | `AVAILABLE` | `WEBCRAWLER_CONNECTOR`, `GOOGLE_DRIVE_CONNECTOR`, `COMPOSIO_GOOGLE_DRIVE_CONNECTOR`, `ONEDRIVE_CONNECTOR`, `DROPBOX_CONNECTOR` | create OK, `/index`+periodic OK, **pipeline-eligible** |
| Functional tool | `MCP_TOOL` | `AVAILABLE` | `MCP_CONNECTOR` (generic BYO MCP server) | create OK, acts in chat, **no pipelines** |
| Deprecated branded (indexers) | `MCP_TOOL` | `MIGRATING` | `NOTION_CONNECTOR`, `GITHUB_CONNECTOR`, `CONFLUENCE_CONNECTOR`, `BOOKSTACK_CONNECTOR`, `ELASTICSEARCH_CONNECTOR` | block new create, **disable `/index`+periodic**; disable subagent **only for Notion/Confluence** (GitHub/BookStack/Elasticsearch have no subagent); keep existing rows + already-indexed KB docs searchable |
| Deprecated branded (act-only) | `MCP_TOOL` | `MIGRATING` | `SLACK_CONNECTOR`, `TEAMS_CONNECTOR`, `LINEAR_CONNECTOR`, `JIRA_CONNECTOR`, `CLICKUP_CONNECTOR`, `AIRTABLE_CONNECTOR`, `DISCORD_CONNECTOR`, `GOOGLE_GMAIL_CONNECTOR`, `GOOGLE_CALENDAR_CONNECTOR`, `LUMA_CONNECTOR`, `COMPOSIO_GMAIL_CONNECTOR`, `COMPOSIO_GOOGLE_CALENDAR_CONNECTOR` | block new create, **disable subagent** (no KB data to keep) |
| Disabled | `DATA_SOURCE` | `DISABLED` | `OBSIDIAN_CONNECTOR`, `CIRCLEBACK_CONNECTOR` | block new create + subagent; not MCP-bound (distinct from MIGRATING). Obsidian is self-hosted-only today |
| Removed → `04b` | n/a | n/a | `SERPER_API`, `TAVILY_API`, `SEARXNG_API`, `LINKUP_API`, `BAIDU_SEARCH_API` | enum values dropped + repurposed in `04b`. **04a treats them as `HIDDEN`** (excluded from taxonomy) so the registry is total until `04b` removes them |

**"Migrating" UX:** existing `MIGRATING` rows remain in the DB and (for the indexers) their already-indexed documents stay searchable via the always-on `knowledge_base` subagent; only the connector's own management (re-index, periodic, live subagent) is turned off, with a "Migrating to MCP soon" status surfaced by the API.

## Current state (cited)

### The enum + model

- `class SearchSourceConnectorType(StrEnum)` — `db.py:85–117` (all **30** values, incl. the 5 search APIs `:86–90`, `MCP_CONNECTOR:113`, Composio variants `:115–117`). The registry's totality test must cover all 30.
- `class SearchSourceConnector` — `db.py:1829`. Columns: `connector_type` (`:1867`), `is_indexable` (`:1868`, `Boolean default False`), periodic fields `periodic_indexing_enabled`/`indexing_frequency_minutes`/`next_scheduled_at` (`:1880–1882`).
- Schema: `schemas/search_source_connector.py` — `is_indexable: bool` (`:16`), validator "periodic only if indexable" (`:42–45`), `Update.is_indexable` (`:66`).

### Where indexability is currently set (per connector, scattered)

Create routes hardcode `is_indexable` per type: `True` for Notion (`notion_add_connector_route.py:409`), Confluence (`:376`), Google Drive (`:420`), Dropbox (`:373`), OneDrive (`:380`); `False` for Slack/Teams/Discord/Gmail/Calendar/Linear/Jira/ClickUp/Airtable/Luma (their `*_add_connector_route.py`), MCP (`search_source_connectors_routes.py:2696`). Composio uses `INDEXABLE_TOOLKITS` (`composio_routes.py:289,400`, `composio_service.py:99`). `oauth_connector_base.py:59,598` defaults `True`. **This scatter is exactly why category lives in a registry, not duplicated at each create site.**

### The `/index` dispatch (the indexable set, today)

`index_connector_content()` — `search_source_connectors_routes.py:717` — is an `if/elif` chain on `connector_type` that dispatches to a Celery task for: Notion (`:850`), GitHub (`:861`), Confluence (`:872`), BookStack (`:885`), Google Drive (`:898`), OneDrive (`:948`), Dropbox (`:995`), Elasticsearch (`~:1050`), WebCrawler (`:1058`). **Movers** (Notion/GitHub/Confluence/BookStack/Elasticsearch) lose this branch; the file-based + WebCrawler branches stay.

### The chat subagent maps + the routing gap

- `multi_agent_chat/constants.py` (the chat-package root `constants.py`, **not** under `subagents/`) — `CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS` (`:5–24`, connector_type → subagent name; **note GitHub/BookStack/Elasticsearch have NO entry** — they are index-only, no chat subagent) and `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP` (`:26–44`, subagent → required tokens; `deliverables`/`knowledge_base` require `frozenset()` = always built). The required tokens are a **mix of connector types and doc types** (e.g. `notion`→`NOTION_CONNECTOR`, but `dropbox`→`DROPBOX_FILE`, `google_drive`→`GOOGLE_DRIVE_FILE`, `onedrive`→`ONEDRIVE_FILE`).
- Subagent exclusion: `subagents/registry.py` `get_subagents_to_exclude(available_connectors)` (`:136–152`) excludes a builder in **two** cases: (a) it is **absent from** `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP` (`required_tokens is None`, `:145–147`) → excluded; (b) it has non-empty required tokens that don't intersect the available set (`:150–151`) → excluded. An **empty** `frozenset()` (deliverables/knowledge_base) is always kept (`:148–149`). `build_subagents(..., exclude=...)` (`:182–220`) additionally hard-skips `memory`/`research` (`:195`) and the names in `exclude`, then calls each builder with `mcp_tools=mcp.get(name)` (`:209`). `SUBAGENT_BUILDERS_BY_NAME` (`:92–112`) has **no `mcp` builder** today. **Consequence for §5:** adding an `mcp` builder *without* a `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP["mcp"]` entry would hit case (a) and exclude it forever — so §5's map entry is mandatory, not optional.
- **CRITICAL — `available_connectors` is NOT raw connector types.** `factory.py:102–105` computes `connector_types = get_available_connectors(...)` then `available_connectors = map_connectors_to_searchable_types(connector_types)`. This **shared, already-mapped** list of searchable-type tokens feeds *multiple* consumers: `get_subagents_to_exclude` (`factory.py:253`, `main_agent/middleware/stack.py:202`), the on-demand KB-search tool (`subagents/builtins/knowledge_base/tools/search_knowledge_base.py:_search_types:53–63` does `types.update(available_connectors)` at `:61–62` — this is the post-`main`-merge replacement for the now-deleted `shared/middleware/knowledge_search.py`, which used to do the same in `_resolve_search_types`), `web_search`'s live-connector filter (`shared/tools/web_search.py`), and the `deliverables` `report` tool. **Filtering this list would break legacy KB-doc searchability and web search** — see Target §4.
- `map_connectors_to_searchable_types` (`connector_searchable_types.py:65–100`) maps each configured connector type to a searchable token; **`MCP_CONNECTOR` is absent from `_CONNECTOR_TYPE_TO_SEARCHABLE` (`:22–54`)**, so MCP connectors never produce a token in `available_connectors`.
- **The bug:** `subagents/mcp_tools/index.py` `partition_mcp_tools_by_connector` (`:55–99`) routes each MCP tool via `CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS.get(connector_type)`; `MCP_CONNECTOR` has **no entry**, so it hits the `connector_agent is None` branch and is **skipped with a warning** (`:88–95`). Generic user MCP servers therefore contribute zero tools today. (The bucket key is the agent name, e.g. `"mcp"`, consumed by `build_subagents` via `mcp.get("mcp")`.)

### Query-time searchable mapping (keeps legacy docs visible)

`main_agent/runtime/connector_searchable_types.py` `_CONNECTOR_TYPE_TO_SEARCHABLE` (`:22–54`, unchanged by the `main` merge) maps connector types → searchable doc-types that scope the KB-search tool (via `available_connectors` → `search_knowledge_base.py:_search_types`). The MIGRATING indexers' entries (NOTION→`NOTION_CONNECTOR`, etc.) **stay** so already-indexed docs remain searchable. (WebCrawler→`CRAWLED_URL`, file connectors→`*_FILE` stay too.)

## Target design

### 1. The static registry (single source of truth)

New `app/connectors/connector_registry.py` (or `app/utils/connector_registry.py`):

```python
class ConnectorCategory(StrEnum):
    DATA_SOURCE = "DATA_SOURCE"
    MCP_TOOL = "MCP_TOOL"

class ConnectorAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"    # usable now
    MIGRATING = "MIGRATING"    # branded native, "moving to MCP soon"
    DISABLED  = "DISABLED"     # off for MVP, not MCP-bound (Obsidian/Circleback)
    HIDDEN    = "HIDDEN"       # not a real connector in the taxonomy (search APIs, until 04b removes them)

# connector_type -> (category, availability). Total over SearchSourceConnectorType.
CONNECTOR_REGISTRY: dict[SearchSourceConnectorType, tuple[ConnectorCategory, ConnectorAvailability]] = { ... }

def get_category(ct) -> ConnectorCategory | None
def get_availability(ct) -> ConnectorAvailability
def is_creatable(ct) -> bool          # availability == AVAILABLE
def is_pipeline_eligible(ct) -> bool  # category == DATA_SOURCE and availability == AVAILABLE
def is_indexable_type(ct) -> bool     # the file/web data sources that own a Celery indexer
```

- **Totality guard (test):** assert every `SearchSourceConnectorType` member has a registry entry, so a newly added connector can't silently fall through gating.
- Exposed on the connector read schema as **computed fields** (`category`, `availability`) so the API/frontend can label and filter without a DB column. (Promote to a column later only if Zero/SQL filtering needs it — see umbrella resolved log.)

### 2. Create gating

In the generic create handler `create_search_source_connector` (`search_source_connectors_routes.py:172`, `@router.post("/search-source-connectors")`) **and** the per-service add/OAuth routes (e.g. `notion_add_connector_route.py`, `luma_add_connector_route.py:51`, the Composio routes) reject when `not is_creatable(connector_type)` with a clear 4xx ("This connector is migrating to MCP and can't be added yet" / "disabled for MVP"). The existing per-type duplicate check (`:198–212`) is unaffected. Because the per-service routes each build their own connector, the gate must be applied in each (or in a shared helper they all call) — verify by grepping the `*_add_connector_route.py` set. This is the behavioural change that blocks new branded connectors; existing rows are untouched.

### 3. Index gating

Guard `index_connector_content` (`:717`) up front: if `not is_indexable_type(connector_type)`, return a 4xx/no-op ("indexing disabled — migrating to MCP"). This neutralizes the Notion/GitHub/Confluence/BookStack/Elasticsearch branches without deleting their (now-dead) code paths.

**Periodic path (must also be gated).** Create-gating blocks *new* MIGRATING rows, but **existing** MIGRATING connectors with `periodic_indexing_enabled=True` already have a `next_scheduled_at` and would keep firing via the meta-scheduler Beat task that polls `next_scheduled_at` every minute: `tasks/celery_tasks/schedule_checker_task.py` (due query `next_scheduled_at <= now` `:36`, dispatch loop `:88`, `task = task_map.get(connector.connector_type)` then `.delay(...)` `:118`). The first-run trigger is `create_periodic_schedule` (`utils/periodic_scheduler.py:30`, `task.delay(...)` `:97`). **Both paths re-dispatch through the same per-type Celery tasks** (`index_crawled_urls_task`, `index_notion_pages_task`, …), so the robust single chokepoint is to **gate the Celery index tasks at entry** by `is_indexable_type(connector_type)` — this covers the manual `/index` route, the first-run trigger, and the recurring meta-scheduler pass at once (a no-op early-return for MIGRATING types). (Aside: `schedule_checker_task` already auto-disables a `LIVE_CONNECTOR_TYPES` set at `:74-77` — an existing precedent for turning periodic off per type.) The schema validator "periodic only if indexable" (`schemas/search_source_connector.py:42–45`) is unchanged and unaffected (it keys off the per-row `is_indexable` bool, not the registry).

Note: **update** (`PUT /search-source-connectors/{id}`, `search_source_connectors_routes.py:371`) is intentionally **left allowed** for MIGRATING rows so existing users can still edit/disable them; only create + index are gated.

### 4. Subagent gating (turns off branded chat tools) — by NAME, not by token

> **Do NOT filter `available_connectors`.** It is a shared, already-mapped searchable-type list (see Current State). Stripping MIGRATING entries from it would (a) remove `NOTION_CONNECTOR`/etc. from the KB-search tool's doc-type scope (`search_knowledge_base.py:_search_types`) → **break the very legacy-doc searchability this plan promises**, and (b) remove the live-search tokens → break `web_search` before 04b. The token list must stay intact.

Instead, **exclude the deprecated subagents by NAME**, derived from the registry. Extend `get_subagents_to_exclude` (`registry.py:136`) so that, in addition to its current token check, it also excludes any subagent whose mapped connector type(s) are all non-`AVAILABLE`:

- Build the reverse of `CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS` (subagent_name → set of connector types). For each `SUBAGENT_BUILDERS_BY_NAME` entry, if it has connector type(s) and **every** one is non-`AVAILABLE` in the registry, add it to the excluded set unconditionally (regardless of tokens).
- This is the single chokepoint used by both `factory.py:253` and `stack.py:202`, and feeds `main_prompt_registry_subagent_lines(exclude)`, so the deprecated specialists disappear from both the build and the prompt.

Net effect for MVP:

- **Excluded (MIGRATING):** `notion`, `confluence`, `slack`, `teams`, `linear`, `jira`, `clickup`, `airtable`, `discord`, `gmail`, `calendar`, `luma`. (GitHub/BookStack/Elasticsearch have no subagent — they are handled purely by §3 index gating; their indexed docs stay searchable via the untouched token list.)
- **Kept (AVAILABLE):** `knowledge_base`, `deliverables`, `research`, `memory` (builtins), the new `mcp` subagent, **and the file-source specialists `google_drive`, `dropbox`, `onedrive`** — these map to `AVAILABLE` Type-1 connectors, so by the registry rule they are NOT deprecation-excluded; they remain token-gated as today (built only when that file connector is configured). **Decision:** keep them — a Type-1 data source can still own a chat specialist over its indexed files; the two-type split governs pipeline-eligibility + the MCP migration, not whether an AVAILABLE connector may have a subagent. (If we later want pure-ingestion file connectors with no specialist, flip them by adding a `subagent_chat` flag to the registry — out of scope here.)

### 5. MCP_CONNECTOR routing-gap fix (makes generic Type-2 work)

Two changes are needed — the routing map AND surfacing the token, or the subagent will still never build:

1. **Routing map** (`multi_agent_chat/constants.py`): add `"MCP_CONNECTOR": "mcp"` to `CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS` (so `partition_mcp_tools_by_connector` stops hitting the `connector_agent is None` skip at `mcp_tools/index.py:88–95`), and `"mcp": frozenset({"MCP_CONNECTOR"})` to `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP`.
2. **Builder**: add a generic `mcp` entry to `SUBAGENT_BUILDERS_BY_NAME` (`registry.py:92`); `build_subagents` will call it with `mcp_tools=mcp.get("mcp")` (the bucket key from step 1's map value).
3. **Surface the token** (the gap step 4's predecessor missed): `MCP_CONNECTOR` is **not** in `_CONNECTOR_TYPE_TO_SEARCHABLE`, so `available_connectors` never contains it and the `mcp` subagent's required token `{MCP_CONNECTOR}` would never intersect → it would be excluded forever. Fix by adding `"MCP_CONNECTOR": "MCP_CONNECTOR"` to `_CONNECTOR_TYPE_TO_SEARCHABLE` (`connector_searchable_types.py:22`). Side effect: `MCP_CONNECTOR` joins the KB-search tool's doc-type scope (`search_knowledge_base.py:_search_types`), where it matches zero indexed docs — harmless no-op. (Alternative if the no-op is undesirable: special-case `mcp` in `get_subagents_to_exclude` to include it whenever any configured connector is an `AVAILABLE` `MCP_TOOL`, passing the raw `connector_types` alongside. The searchable-map entry is simpler and preferred.)

### 6. Keep `is_indexable` semantics intact

No change to the column or its validator. `is_indexable` continues to gate the real `/index`+periodic machinery for the data sources; the registry's `is_indexable_type` is a **type-level** allowlist layered on top (a row must be both an indexable type AND `is_indexable=True`). This avoids reinterpreting historical rows.

## Work items

1. **Registry module** + `ConnectorCategory`/`ConnectorAvailability` enums + the total `CONNECTOR_REGISTRY` map + helper predicates (incl. reverse subagent-name→types helper for §4).
2. **Schema**: add computed `category`/`availability` to the connector read schema (`schemas/search_source_connector.py`).
3. **Create gating** in the generic create handler (`:172`) + every per-service add route (reject non-`AVAILABLE`).
4. **Index gating** at the Celery index-task entry (`is_indexable_type`) — covers manual `/index`, first-run trigger, and meta-scheduler.
5. **Subagent gating by name**: extend `get_subagents_to_exclude` to also exclude subagents whose mapped connector types are all non-`AVAILABLE` (do **not** filter the shared `available_connectors` token list).
6. **MCP routing-gap fix**: `multi_agent_chat/constants.py` map entries + generic `mcp` builder in `SUBAGENT_BUILDERS_BY_NAME` + `MCP_CONNECTOR` token in `_CONNECTOR_TYPE_TO_SEARCHABLE` (so the subagent actually builds).
7. **Tests** (below).

## Tests

- **Registry totality**: every `SearchSourceConnectorType` has an entry (guards future additions).
- **Create gating**: creating any `MIGRATING`/`DISABLED` type → 4xx; `WEBCRAWLER`/file/`MCP_CONNECTOR` → OK; MCP multi-instance still works.
- **Index gating**: index task entry for Notion/GitHub/Confluence/BookStack/Elasticsearch → no-op; WebCrawler/GDrive/OneDrive/Dropbox → runs. Include a case for an **existing** MIGRATING row with `periodic_indexing_enabled=True` + due `next_scheduled_at` → meta-scheduler triggers a no-op (does not re-index).
- **Subagent gating by name**: with a (legacy) Notion + Slack connector configured, `get_subagents_to_exclude` excludes `notion`/`slack`; `knowledge_base`/`deliverables` always built; a configured `google_drive`/`dropbox`/`onedrive` (AVAILABLE) is **not** excluded (still token-gated).
- **No collateral damage to the token list**: gating subagents must NOT change `available_connectors` — assert the KB-search tool still resolves the `NOTION_CONNECTOR` doc type (via `_search_types`) for the legacy connector (guards against the "filter the shared list" regression).
- **MCP gap (two-part)**: (a) a configured `MCP_CONNECTOR` produces a `"mcp"` token in `map_connectors_to_searchable_types`; (b) its tools land in the `mcp` bucket and the `mcp` subagent is actually built (regression for both `mcp_tools/index.py:88–95` and the missing-token exclusion).
- **Legacy searchability**: a search space with an existing (now-MIGRATING) Notion connector + indexed docs still returns those docs via the KB-search tool (`connector_searchable_types` Notion entry unchanged).

## Risks / trade-offs

- **Breaks current branded chat tooling (accepted).** Deprecating act-only natives removes their live chat subagents for existing users mid-pivot. Per the umbrella's "DB migrations carry users; backend behaviour can change" posture, this is acceptable; the "migrating to MCP soon" status sets expectations.
- **Dead code paths left in place.** The Notion/GitHub/Confluence/BookStack/Elasticsearch `/index` branches + indexers remain but are gated off (not deleted) to keep the diff small and reversible; delete when the real MCP migration lands.
- **No column = not SQL/Zero-filterable.** Frontend (deferred) filters via the API's computed fields. If Zero needs server-side filtering later, promoting the registry to a denormalized column is additive.
- **Registry/`is_indexable` dual-gate.** Two truths (type-level allowlist + per-row bool) must agree; the totality test + index-gating test cover the seam.
- **Shared `available_connectors` is a footgun.** It feeds subagent-exclusion, the KB-search tool's doc-type scope, web_search, and the deliverables `report` tool simultaneously. Subagent gating is therefore done by *name* (registry-driven), never by mutating that list; the "no collateral damage" test pins this. This also removes any 04a→04b sequencing hazard (04a no longer touches the live-search tokens that 04b later retires).
- **File-source specialists kept.** `google_drive`/`dropbox`/`onedrive` stay as AVAILABLE chat specialists (decision in §4). If product wants pure-ingestion file connectors, that's an additive registry flag later.

## Out of scope (hand-offs)

- Search-API enum removal, key relocation, and the source-discovery endpoint → `04b`.
- Pipeline tables + actually creating pipelines from Type-1 connectors → Phases 5–7 (`is_pipeline_eligible` is defined here for them to consume).
- Real MCP migration of the branded connectors (re-point to MCP servers) → post-MVP.
- Frontend connector UI restructure → frontend umbrella.
