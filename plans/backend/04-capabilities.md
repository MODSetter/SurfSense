# Phase 4 — Capabilities (the scraper APIs)

> Build first; every other phase calls this registry. Sibling: `05-access.md` (the doors).
> Reuses Phases 3a/3b/3c (shipped): `WebCrawlerConnector.crawl_url -> CrawlOutcome`, the proxy/stealth/
> captcha tiers, and the `WebCrawlCreditService` billing seam. Locate code by symbol/grep.

## Objective

Expose the Acquisition engine as a small set of typed, stateless scraper verbs (`web.*`, `maps.*`) that
return cleaned, AI-ready structured data. One capability = one function you call and get data back from.

## Verb set (MVP)

Two namespaces: `web.*` (generic crawler) and `maps.*` (Google Maps actor). Future platforms slot in as
their own namespace.

| Verb | Input → Output (cleaned) | Executes over | Billing unit |
|------|--------------------------|---------------|--------------|
| `web.scrape(urls[])` | `[{url, status, content, metadata}]` | loop `crawl_url` | per success |
| `web.discover(query, top_k)` | `[{url, title, snippet, provider}]` | search providers | per search / free |
| `maps.search(query, location)` | `[place]` | Maps actor | per place |
| `maps.place(place_id\|url)` | `place` | Maps actor | 1 |
| `maps.reviews(place)` | `[review]` (paged) | Maps actor | per page |

`maps.*` returns typed structured objects (`{name, rating, review_count, hours, price_level, …}`).
`web.scrape` takes a URL array.

## Execution

Each verb is a direct async call that returns its cleaned result. Slow verbs (large `web.scrape` arrays,
`maps.reviews` paging) are bounded/streamed at the endpoint.

## Registry

One entry per verb, and the single source of truth the doors (`05`) and the agent (`07`) read from:

```
Capability {
  name            # dotted, e.g. "web.scrape", "maps.search"
  input_schema    # Pydantic
  output_schema   # Pydantic (cleaned, AI-ready)
  executor        # async fn; wraps Acquisition / Maps actor; returns data directly
  billing_unit    # how the billing service charges this call
}
```

Adding a verb once lights it up on every door.

## Billing

A verb declares a `billing_unit`; charging is delegated to the billing service (`03c` first provider).

- `web.scrape` → per `SUCCESS` (`web_crawl` unit).
- `maps.*` → new per-place / per-page unit registered with the billing service.
- captcha attempts → existing per-attempt `web_crawl_captcha` unit (`03d`).
- `web.discover` → per-search unit (or free).

## Location

New Apache-2 package `app/capabilities/` (registry, schemas, executors) — open-source and self-hostable.
Executors import the proprietary Acquisition engine and Maps extractor (`app/proprietary/…`).

## Work items

1. Registry package: `Capability` dataclass + registry, imported by `05` and `07`.
2. `web.scrape` executor: loop `crawl_url` over the URL array → per-URL cleaned rows; `web_crawl` unit.
3. `web.discover` executor: wrap the search-provider core (SearXNG/Linkup/Baidu, env-keyed); its unit.
4. `maps.*` contracts: input/output schemas + executor stubs against the Maps actor.
5. Output normalization: each executor returns AI-ready structured output.
6. Billing seam: honor `billing_unit` via the billing service.

## Tests

- `web.scrape([a,b,c])` returns one cleaned row per URL inline; partial failures don't fail the batch.
- Each `SUCCESS` bills one `web_crawl` unit; `EMPTY`/`FAILED` free; disabling the flag no-ops.
- A door and the agent hit the same executor for a verb.
- `web.discover` returns `{url,title,snippet,provider}`; self-disables when no provider key is set.
- `maps.*` returns typed structured objects against fixtures.

## Out of scope

- Doors → `05`. Keep-watching mode → `06`. Agent → `07`.
- Google Maps actor build (incl. sourcing legality) — net-new, separate effort; `maps.*` are contracts.
- Additional platform namespaces; recursive site crawl; a generic `web.extract` verb.

## Open questions

- `web.discover` metered vs free.
- How large `web.scrape` / `maps.reviews` responses are bounded/streamed.
