# Remote plugins: SurfSense's own servers

> Owns: the plugin servers SurfSense publishes and hosts, in `plugins/<id>/` and `plugins/proprietary/<id>/`, starting with `plugins/proprietary/surfsense-scrapers/`.
> The client that reaches them: [`01-mcp-client.md`](01-mcp-client.md). Paid: [`../core/05-paid.md`](../core/05-paid.md).

## SurfSense's own servers

SurfSense publishes plugins the same way anyone does, as remote MCP servers listed in the registry with `publisher: surfsense`, and hosts them.

| Where the server's code lives | License | Example |
|---|---|---|
| `plugins/<id>/` | Apache-2.0 | a free plugin, such as a search of a public API |
| `plugins/proprietary/<id>/` | Business Source License 1.1 ([ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md)) | `surfsense-scrapers` |

A server is a Python project with its own `pyproject.toml`, tests and `Dockerfile`, built on the official MCP Python SDK: unlike the app, a hosted server has no size limit worth the cost of a client of our own. Each runs as its own container, deployed by SurfSense, apart from `surfsense_backend`: it imports none of the backend's code and uses none of its services. A paid one checks the license itself ([`../core/05-paid.md`](../core/05-paid.md)). `surfsense_mcp` is not reused; it stays the server outside clients such as Claude and Cursor connect to with a personal key.

### SurfSense Scrapers

The first paid plugin, and a container of its own. It shares no code, process, database or deployment with `surfsense_backend`.

```
plugins/proprietary/surfsense-scrapers/      Business Source License 1.1
  server/        the MCP server: one tool per platform verb, progress, cancel
  license/       checks "License <key>" with Keygen on every call
  platforms/     the scrapers: Amazon, Google Maps, Google Search, Indeed, Instagram,
                 Reddit, TikTok, Walmart, YouTube
  web_crawler/   the site crawler
  proxy/         residential proxy providers and rotation
  captcha/       captcha solving
  browser/       Scrapling's stealth browsers and the loop that drives them
  config.py      its own settings, from environment variables
  Dockerfile     Python, Scrapling's browsers and Xvfb
  compose.yaml   the server, Redis and SearXNG, as deployed
```

- **Tools.** One per scraper verb: web crawl, Google Search, Reddit, YouTube and its comments, Instagram and its details, TikTok and its comments, user search and trending, Google Maps and its reviews, Indeed, Amazon, Walmart and its reviews. Each declares `readOnlyHint: true` and `openWorldHint: true`, returns a readable summary as text with the items as `structuredContent`, and reports progress with MCP progress notifications. A result too large to return whole is kept for a day and paged with a `get_scraper_result` tool. A cancelled call stops its scrape.
- **The license, on the server.** Every request needs `Authorization: License <key>`. The container validates it with Keygen itself, by contract 2's producer rules: a result cached for five minutes, a key validated in the last 24 hours still accepted while Keygen is unreachable, and the `401` and `403` reasons the contract defines ([`../core/05-paid.md`](../core/05-paid.md)). It counts requests per license and limits their rate.
- **Its own secrets:** the proxy providers' credentials, the captcha solver's key, and Keygen access, all as environment variables of the deployment. None of them reaches the app.
- **Its own dependencies:** Redis for Google Search's IP pool, SearXNG as Google Search's fallback, and Scrapling's browsers, all inside its deployment.
- **No database.** The scraper API's `runs` table and async-run events are replaced by MCP progress and a short-lived result store in Redis.

#### Moving the scraping code

The scraping code lives in `surfsense_backend` today: [`app/proprietary/platforms/`](../../../../surfsense_backend/app/proprietary/platforms/) and [`app/proprietary/web_crawler/`](../../../../surfsense_backend/app/proprietary/web_crawler/), about 19,000 lines, and the helpers it imports, [`app/utils/proxy/`](../../../../surfsense_backend/app/utils/proxy/), [`app/utils/captcha/`](../../../../surfsense_backend/app/utils/captcha/), [`app/utils/crawl/`](../../../../surfsense_backend/app/utils/crawl/) and `app/utils/browser_loop.py`, with settings read from `app.config` and progress reported through `app.capabilities`.

1. **Copy now.** The container starts as a copy of that code, with every `app.*` import replaced by the container's own `config.py`, helpers and progress reporting. The hosted backend keeps its copy, as AGENTS.md requires until the purge on 18 Oct 2026.
2. **Delete the backend's copy when nothing uses it.** The backend's scraper API still serves outside clients, so its copy is deleted once those clients have moved to the container or the scraper API is retired, and never before the purge. Then the container is the one home of the scraping code. Until then a fix to a scraper goes to both copies.
3. **One license for all of it.** Everything the scrapers container holds is under the Business Source License, including the copies of `app/utils/proxy/`, `app/utils/captcha/` and `app/utils/crawl/`, which are Apache-2.0 in the backend today. Every commit to that code and to the scrapers is by a SurfSense maintainer, so SurfSense holds the rights to all of it and no file keeps a separate Apache-2.0 notice.

Outside clients, `surfsense_mcp` and direct users of the scraper API, keep using the backend's scraper API until it is retired; whether they move to this container then is open ([README](../README.md#open-questions)).

## Acceptance

- SurfSense Scrapers: a call with a valid trial license returns items; with no key, `401 missing_license`; with an expired one, `403 expired`, each reaching the user as the refusal.
- The scrapers container starts and answers `tools/list` with no `surfsense_backend` code, database or service, and its image carries Scrapling's browsers.
- A cancelled scraper call stops its scrape within ten seconds.
