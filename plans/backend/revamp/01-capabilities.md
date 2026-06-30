# Domain ① — Capabilities (CI pivot revamp · WIP)

> **WIP design doc.** Part of the Phase 4 → end revamp (the old "pipeline").
> **Scope guardrail:** Phases 1–3 are **SHIPPED and FIXED** — the rename, and the proprietary
> crawler/proxy/billing/stealth/captcha stack. This domain *builds on* them and never modifies them.

## Role in the universe

```
FIXED foundation (done):  Acquisition (crawler moat) · Metering (03c) · Identity/Tenancy
OUR scope (this revamp):  ▶ Capabilities ◀ → Access → Intelligence + Timeline → Triggers
```

Capabilities sits directly on the fixed foundation and is consumed by **Access** (the doors) and
the **Intelligence** hot loop. It is the first domain because everything above it calls into it.

## Purpose

Turn the fixed Acquisition engine (+ a new Google Maps actor) into a **small set of typed,
callable verbs** that every door (chat / REST / MCP) and the Intelligence loop consume
**identically**.

This is the core pivot of old Phase 4: **replace "connector that ingests into the KB" with
"capability that returns data."** A capability is a stateless function you *call and get data
back from* — no `SearchSourceConnector` row to configure, no KB write, no schedule attached.

## Foundation it builds on (do not touch)

- `WebCrawlerConnector.crawl_url(url) -> CrawlOutcome` — single-URL fetch; `{content, metadata,
  crawler_type}` on `SUCCESS`; billable predicate single-sourced as `status == SUCCESS`.
  (`app/proprietary/web_crawler/`.)
- `WebCrawlCreditService` (`03c`) — per-success metering + the `bill=` seam.
- Proxy / stealth / captcha tiers — all behind `crawl_url`; callers never see the tier.

## The verb set (MVP) — namespaced, nothing top-level

Two namespaces: **`web.*`** (generic crawler product) and **`maps.*`** (the one platform actor).
Future platforms slot in as their own namespace (`linkedin.*`, `amazon.*`, …).

| Verb | Input → Output | Mode | Executes over | Bills (03c) |
|------|----------------|------|---------------|-------------|
| `web.scrape(urls[])` | → `[{url, status, content, metadata}]` | inline-or-job | loop `crawl_url` | per success |
| `web.discover(query, top_k)` | → `[{url, title, snippet, provider}]` | inline | search providers (SearXNG/Linkup/Baidu) | per search *(or free — open)* |
| `maps.search(query, location)` | → `[place]` | job | Maps actor *(new, proprietary)* | per place |
| `maps.place(place_id\|url)` | → `place` (structured) | inline | Maps actor *(new, proprietary)* | 1 |
| `maps.reviews(place)` | → `[review]` (paged) | job | Maps actor *(new, proprietary)* | per page |

## `web.scrape` — one array-friendly verb (no separate "batch")

Scraping always **welcomes an array of URLs**. There is no separate `scrape_batch`. One verb,
one mental model: "give me URLs, I give you per-URL content."

## Execution mode — a property of the **result**, not two verbs

A capability does **not** split into sync/async variants. Every call returns a **uniform result
envelope**:

```
{ status: "completed" | "pending", job_id?: str, progress?: {done, total}, results?: [...] , error?: ... }
```

- **inline (fast path):** small/fast input → finishes in-request → envelope returns `completed`
  with `results` inline → **zero polling**. (single page, one place, a search)
- **job (slow path):** large/slow input → envelope returns `pending` + `job_id` → caller polls a
  status endpoint until `completed`, then reads `results`. (batch scrape, Maps search/reviews)

So "sync" is simply *a job that finished instantly*. Same verb, same response shape, no magic
branching for the caller to reason about.

- **Threshold** (how many URLs / how heavy before it goes async) is **configurable**.
- A caller may pass `async: true` to **force** a job even for small input (agents that never want
  to block).
- **Only infra this requires:** a thin **job record** (`id, status, progress, result_ref`) + the
  **existing Celery workers**. *Not* a resurrected `pipeline_runs`. Sync verbs need none of it.

## The capability registry — single source of truth

One registry entry per verb:

```
Capability {
  name            # dotted, e.g. "web.scrape", "maps.search"
  input_schema    # Pydantic
  output_schema   # Pydantic
  mode            # can-complete-inline?  +  job-capable?
  executor        # the async fn (wraps Acquisition / Maps actor)
  billing_unit    # how Metering charges this call
}
```

The **three doors are generated from the registry**, not hand-written three times:

- **chat tool** ← entry (tool def + handler)
- **REST route** ← entry (path + request/response models)
- **MCP tool** ← entry (MCP tool schema + handler)

…and the **Intelligence** hot loop calls the *same* `executor` directly. Add a verb once → it
lights up on every surface; the I/O contract cannot drift between surfaces.

## Where it lives / license boundary

- New **Apache-2** package `app/capabilities/` (registry, schemas, executors, the thin job store).
- It **imports from** the proprietary Acquisition engine but never moves into it.
- The **Maps extractor logic is proprietary** (`app/proprietary/...`), consumed by the `maps.*`
  executors — same boundary rule Phase 3 set (Apache code may import *from* proprietary, not move
  *into* it).

## Billing integration — open to the billing service (not hardcoded per verb)

Billing is **not** baked into each verb. A capability only **declares a `billing_unit`** in its
registry entry; charging is delegated to the **billing service**, so adding/repricing a unit is a
billing-service concern, not a capability rewrite. `03c`'s `WebCrawlCreditService` is the **first
provider**; new units register with the same service.

- `web.scrape` → per `SUCCESS` (existing `web_crawl` unit).
- `maps.*` → register a new per-place / per-page unit **with the billing service** (same wallet).
- captcha attempts → existing per-attempt `web_crawl_captcha` unit (unchanged).
- `web.discover` → register a per-search unit (or mark free) **with the billing service**.

The point: the registry says *"this verb bills unit X"*; the **billing service owns what unit X
costs and how it settles.** Verbs stay pure; pricing stays pluggable.

## The Maps actor (clarification)

- **Google-Maps-agnostic** — works for *any* place type (restaurants, gyms, hotels, retail, …).
- Returns **typed structured objects** (`{name, rating, review_count, hours, price_level, …}`),
  not raw markdown — which is exactly what the Intelligence/Timeline layer needs to diff reliably.
- The "restaurant" use case is an **Intelligence-domain wedge** (one Tracker), **not** a constraint
  on the capability. The capability never knows what decision it serves.

## Relationship to the drafted Phase 4

- **04b (source-discovery)** → **absorbed** as `web.discover` + relocating Linkup/Baidu keys from
  per-connector `config` to platform env (SearXNG already env-based). Tavily/Serper dropped.
- **04a (connector taxonomy + MCP routing)** → **demoted to backward-compat hygiene.** The
  capability registry is the new spine, so the Type-1/Type-2 *connector* registry is no longer
  central. 04a's "turn off branded connectors" stays a small, separable cleanup for the legacy
  chat agent; the **BYO-`MCP_CONNECTOR`** routing fix belongs to the **Access/Conversation** domain
  (it lets the agent use the *user's* external tools — a different concept from our capabilities).

## Deferred (not in MVP)

- **Recursive site crawl** (follow links across a whole site) — doesn't exist today; the
  "crawl a topic" story is `web.discover` → `web.scrape`.
- A generic **`web.extract`** (LLM-structured extraction as a standalone verb) — structured
  extraction lives in the Intelligence loop for MVP; promote to a capability later if devs want it.
- Additional platform namespaces (`linkedin.*`, `amazon.*`, …).

## Locked decisions

1. Verbs: `web.scrape` · `web.discover` · `maps.search` · `maps.place` · `maps.reviews`. Namespaced; nothing top-level.
2. One array-friendly `web.scrape` (no separate batch verb).
3. Execution mode = result property (uniform `completed`/`pending` envelope), not separate verbs.
4. Build the thin job model now (Maps search / batch scrape force it).
5. One capability registry → generates chat/REST/MCP doors + feeds the Intelligence executor.
6. `app/capabilities/` Apache-2; Maps extractor proprietary; billing **delegated to the billing
   service** (verbs declare a `billing_unit`; `03c` is the first provider, new units register there).
7. Connector → capability is a **replacement** for these data sources, not an extension.

## Open questions (carry forward)

- Default async threshold for `web.scrape`.
- The **Google Maps actor** is **net-new** (not part of shipped Phases 1–3) — designed/built as a
  **separate effort** (incl. sourcing legality). `maps.*` verbs are contracts against it; this domain
  doesn't block on it.
