# Phase 4a — Capabilities (typed verbs over Acquisition)

> Part of **Phase 4 — Capabilities & Access** (the CI-pivot revamp of the old "pipeline" Phases 4–7).
> Sibling: `04b-access.md` (the doors that expose these verbs). **Build first** — everything above
> calls into it.
> **Depends on** Phases 3a/3b/3c (SHIPPED): the `WebCrawlerConnector.crawl_url -> CrawlOutcome`
> contract, the proxy provider, and the `WebCrawlCreditService` billing seam.
> **Scope guardrail:** Phases 1–3 are SHIPPED/FIXED. This domain *builds on* them and never modifies
> them. Locate foundation code by **symbol/grep**, not the line numbers cited.

## Objective

Turn the fixed Acquisition engine (+ a new Google Maps actor) into a **small set of typed, callable
verbs** that every door (chat / REST / MCP) and the Intelligence hot loop (`05b`) consume
**identically**. This is the core pivot of the old Phase 4: **replace "connector that ingests into the
KB" with "capability that returns data."** A capability is a stateless function you *call and get data
back from* — no `SearchSourceConnector` row to configure, no KB write, no schedule attached.

## Current state (cited)

- `WebCrawlerConnector.crawl_url(url) -> CrawlOutcome` — single-URL fetch returning `{content,
  metadata, crawler_type}` on `SUCCESS`. `CrawlOutcomeStatus.SUCCESS` documents the billable signal, but
  **operationally every caller checks `status == SUCCESS and outcome.result`** (see `scrape_webpage.py` and
  `webcrawler_indexer.py`) — the predicate is duplicated, not one helper. **The executor (below) should
  single-source it** in a shared `is_billable(outcome)` helper (`app/proprietary/web_crawler/`).
- `WebCrawlCreditService` (`03c`) — per-success metering with the static `billing_enabled()` /
  `successes_to_micros()` seam (`app/services/web_crawl_credit_service.py`).
- Proxy / stealth / captcha tiers — all behind `crawl_url`; callers never see the tier (`03b`/`03d`/`03e`).
- Web-search providers (SearXNG/Linkup/Baidu) and the source-discovery core from old `04b` — the
  substrate for `web.discover`.
- **No Maps actor exists** — it is net-new, proprietary, and built as a separate effort (see Out of scope).

## Target design

### The verb set (MVP) — namespaced, nothing top-level

Two namespaces: **`web.*`** (generic crawler product) and **`<platform>.*`** (per-platform scrapers).
Future platforms slot in as their own namespace (`maps.*`, `linkedin.*`, `amazon.*`, …).

> **Scope clarification (2026-06-30).** Platform-specific scrapers are a **family of individual scraping
> endpoints**, **not** one committed integration — **no specific platform (incl. Google Maps) is committed
> for MVP**; `maps.*` below is an **illustrative example** of the pattern. Each such scraper is *just
> another capability verb*: adding one lights up (a) an **agent tool** (chat) and (b) a **dev-callable REST
> endpoint behind the platform API key** — same executor, same billing, zero new machinery. **The MVP
> builds only `web.scrape` + `web.discover` executors**; every `<platform>.*` row is a **contract stub**
> demonstrating that the registry + generated doors (`04b`) make per-platform endpoints a drop-in.

| Verb | Input → Output | Mode | Executes over | Bills (03c) |
|------|----------------|------|---------------|-------------|
| `web.scrape(urls[])` | → `[{url, status, content, metadata}]` | inline-or-job | loop `crawl_url` | per success |
| `web.discover(query, top_k)` | → `[{url, title, snippet, provider}]` | inline | search providers (SearXNG/Linkup/Baidu) | per search *(or free — open)* |
| `maps.search(query, location)` | → `[place]` | job | Maps actor *(new, proprietary)* | per place |
| `maps.place(place_id\|url)` | → `place` (structured) | inline | Maps actor *(new, proprietary)* | 1 |
| `maps.reviews(place)` | → `[review]` (paged) | job | Maps actor *(new, proprietary)* | per page |

### `web.scrape` — one array-friendly verb (no separate "batch")

Scraping always **welcomes an array of URLs**. There is no `scrape_batch`. One verb, one mental model:
"give me URLs, I give you per-URL content."

### Execution mode — a property of the **result**, not two verbs

A capability does **not** split into sync/async variants. Every call returns a **uniform envelope**:

```
{ status: "completed" | "pending", job_id?: str, progress?: {done, total}, results?: [...], error?: ... }
```

- **inline (fast path):** small/fast input finishes in-request → `completed` with `results` inline →
  zero polling. (single page, one place, a search)
- **job (slow path):** large/slow input → `pending` + `job_id` → caller polls a status endpoint until
  `completed`. (batch scrape, Maps search/reviews)

So "sync" is simply *a job that finished instantly*. Same verb, same shape, no branching for the caller.

- **Threshold** (how many URLs / how heavy before async) is **configurable**.
- A caller may pass `async: true` to **force** a job even for small input (agents that never block).
- **Only infra this requires:** a thin **job record** (`id, status, progress, result_ref`) + the
  **existing Celery workers**. *Not* a resurrected `pipeline_runs`. Sync verbs need none of it.

### The capability registry — single source of truth

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

The **three doors are generated from the registry** (`04b`), not hand-written three times — chat tool,
REST route, MCP tool — and the **Intelligence** hot loop (`05b`) calls the *same* `executor` directly.
Add a verb once → it lights up on every surface; the I/O contract cannot drift between surfaces.

### Billing — open to the billing service (not hardcoded per verb)

A capability only **declares a `billing_unit`** in its registry entry; charging is delegated to the
**billing service**, so adding/repricing a unit is a billing-service concern, not a capability rewrite.
`03c`'s `WebCrawlCreditService` is the **first provider**; new units register with the same service.

- `web.scrape` → per `SUCCESS` (existing `web_crawl` unit).
- `maps.*` → register a new per-place / per-page unit **with the billing service** (same wallet).
- captcha attempts → existing per-attempt `web_crawl_captcha` unit (`03d`, unchanged).
- `web.discover` → register a per-search unit (or mark free) **with the billing service**.

The registry says *"this verb bills unit X"*; the **billing service owns what unit X costs.** Verbs
stay pure; pricing stays pluggable.

> **Charge at the executor, not the turn accumulator (locked 2026-06-30).** The billable charge fires
> **inside the capability executor** (this phase), so *every* caller meters identically — chat,
> **automation/recurring**, REST, MCP, external-cron. This is deliberate: a code review confirmed the
> automation path (`run_agent_task` → `agent_task`) establishes **no chat turn accumulator**, so the
> existing `scrape_webpage` billing (which no-ops when `get_current_accumulator()` is `None`) would let
> **automation-run crawls bill nothing**. The interactive chat **turn accumulator stays only as an
> optional presentation fold** (so a chat turn still shows the crawl line on its bill) — it is **not** the
> charging mechanism. Billing idempotency is **per capability call** (+ the `05b` content-hash pre-check),
> not per run.

### Platform scrapers (illustrated with a Maps actor — example only, not committed)

- Each platform scraper is a **standalone endpoint**; the one shown here (a hypothetical Maps actor) is
  **Google-Maps-agnostic** — works for *any* place type (restaurants, gyms, hotels, retail, …).
- Returns **typed structured objects** (`{name, rating, review_count, hours, price_level, …}`), not raw
  markdown — exactly what the Intelligence/Timeline layer needs to diff reliably.
- The "restaurant" use case is an **Intelligence-domain wedge** (one Tracker), **not** a constraint on
  the capability. The capability never knows what decision it serves.

### Where it lives / license boundary

- New **Apache-2** package `app/capabilities/` (registry, schemas, executors, the thin job store).
- It **imports from** the proprietary Acquisition engine but never moves into it.
- The **Maps extractor logic is proprietary** (`app/proprietary/...`), consumed by the `maps.*`
  executors — same boundary rule Phase 3 set.

## Work items

1. **Registry**: `app/capabilities/` package — `Capability` dataclass + a registry that other domains import.
2. **`web.scrape` executor**: loop `crawl_url` over a URL array; map each `CrawlOutcome` to the per-URL
   result shape; declare the `web_crawl` `billing_unit`.
3. **`web.discover` executor**: wrap the `04b` source-discovery core (SearXNG/Linkup/Baidu, env-keyed);
   declare its `billing_unit` (or free).
4. **Job store**: thin job record (`id, status, progress, result_ref`) + Celery dispatch for job-mode verbs.
5. **Uniform envelope**: shared `completed|pending` result type returned by every executor.
6. **`maps.*` contracts**: input/output schemas + executor stubs against the (separate) Maps actor.
7. **Billing seam**: `billing_unit` declaration honored via the billing service (no per-verb price code).

## Tests

- **Envelope**: a small `web.scrape` returns `completed` inline; a large/`async:true` one returns
  `pending` + `job_id`; the job completes to `results`.
- **Array semantics**: `web.scrape([a, b, c])` returns one per-URL row each; partial failures don't fail
  the batch.
- **Billing**: each `SUCCESS` bills exactly one `web_crawl` unit via the billing service; `EMPTY`/`FAILED`
  free; disabling the billing flag makes it a no-op.
- **Registry → executor parity**: the Intelligence loop and a door hit the *same* executor for the same verb.
- **`web.discover`**: returns `{url,title,snippet,provider}`; self-disables when no provider env key is set.

## Risks / trade-offs

- **Maps actor is a hard external dependency** for `maps.*` — contracts ship now, executors light up when
  the actor lands (doesn't block `web.*`).
- **Job store vs no store**: a thin job record is unavoidable for slow verbs; keep it minimal so it never
  grows back into `pipeline_runs`.
- **Per-success billing on batches** can exhaust a wallet mid-run — pre-check is an upper bound; exact
  mid-run behavior is an implementation-time call.

## Resolved decisions

1. Verbs: `web.scrape` · `web.discover` · `maps.search` · `maps.place` · `maps.reviews`. Namespaced; nothing top-level.
2. One array-friendly `web.scrape` (no separate batch verb).
3. Execution mode = result property (uniform `completed`/`pending` envelope), not separate verbs.
4. Build the thin job model now (Maps search / batch scrape force it).
5. One capability registry → generates chat/REST/MCP doors (`04b`) + feeds the Intelligence executor (`05b`).
6. `app/capabilities/` Apache-2; Maps extractor proprietary; billing **delegated to the billing service**
   (verbs declare a `billing_unit`; `03c` is the first provider, new units register there).
7. Connector → capability is a **replacement** for these data sources, not an extension.

## Out of scope (hand-offs)

- **The doors** (chat/REST/MCP adapters, auth, metering gate) → `04b`.
- **Stateful accumulation** (Tracker/Timeline) → `05a`/`05b`; capabilities stay stateless.
- **The Google Maps actor** is **net-new** (not part of shipped Phases 1–3) — designed/built as a
  **separate effort** (incl. sourcing legality). `maps.*` verbs are contracts against it; this domain
  doesn't block on it.
- **Recursive site crawl**, a generic **`web.extract`** verb, and additional platform namespaces
  (`linkedin.*`, `amazon.*`) — deferred.
- **04a (old, connector taxonomy)** → demoted to backward-compat hygiene; the BYO-`MCP_CONNECTOR` routing
  fix belongs to `04b` (consume-user-MCP). **04b (old, source-discovery)** → absorbed here as `web.discover`.

## Open questions (carry forward)

- Default async threshold for `web.scrape`.
- Whether `web.discover` is metered or free.
