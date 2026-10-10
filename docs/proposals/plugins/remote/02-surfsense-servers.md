# Remote plugins: SurfSense's own servers

> Owns: `plugins/remote/`: the plugin host, the server kit, SurfSense's plugins, starting with `plugins/remote/proprietary/scrapers/`.
> The client that reaches them: [`01-mcp-client.md`](01-mcp-client.md). Paid: [`../core/05-paid.md`](../core/05-paid.md). Decision: [ADR 0054](../../../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md).

## SurfSense's own servers

SurfSense publishes plugins as remote MCP servers, like anyone, and lists them in the app's built-in list with `publisher: surfsense` ([`../core/02-registry.md`](../core/02-registry.md#two-lists)). It hosts all of them, free and paid, on one plugin host.

| Where the code lives | License | Example |
|---|---|---|
| `plugins/remote/<id>/` | Apache-2.0 | a free plugin, such as a search of a public API |
| `plugins/remote/proprietary/<id>/` | Business Source License 1.1 ([ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md)) | `scrapers` |

The folder decides the license and the plugin's `access` decides the price ([`../core/05-paid.md`](../core/05-paid.md#which-license-a-surfsense-plugin-is-under)). The license check belongs to SurfSense's paid plugins alone: third parties' paid plugins check access on their own service.

## The plugin host

One container, deployed by SurfSense to Azure Container Apps at `plugins.surfsense.com`, serves the registry of other publishers' plugins and every SurfSense plugin. It runs apart from `surfsense_backend`, imports none of its code and uses none of its services.

```
plugins.surfsense.com ──► the plugin host (one Container App, at least one replica: browsers start slowly)
                            /plugins.json, /plugins.json.sig, /icons/*   the signed registry
                            /scrapers/mcp                                SurfSense Scrapers
                            /<id>/mcp                                    each other SurfSense plugin
                            /health
                          beside it, internal only: Redis, SearXNG; secrets from Key Vault
```

- **One container, as the backend runs the scrapers today.** One image carries Python, Xvfb and the browsers once; one deploy ships every plugin. A container per plugin was rejected: it multiplies images, deployments and routing for plugins that are mostly small.
- **A plugin is a folder** whose `server.py` returns its MCP server, built on the official MCP Python SDK: unlike the app, a hosted server has no size limit worth the cost of a client of our own. The folder name is the plugin's `id` and its path: `plugins/remote/proprietary/scrapers/` is `id: scrapers` at `/scrapers/mcp`. Adding a plugin adds its entry to the built-in list in the same change, so it reaches users with the next app release.
- **One project.** `host/pyproject.toml` and its `uv.lock` hold every plugin's dependencies. A plugin has no `pyproject.toml` or `Dockerfile` of its own. The import root is `plugins/remote/`, so code imports `mcp_server.progress` or `proprietary.scrapers.server`.
- **Failures stay in their plugin.** A mounted plugin turns its own exceptions into MCP errors, every call runs under a deadline, and a replica failing `/health` is restarted. Each plugin reads only its own settings section, `<ID>_*`; that is a convention, not isolation, acceptable because every plugin here is SurfSense's own code.
- **The registry ships in the image.** The Docker build context is `plugins/`, so the image copies `remote/` and the signed `registry/plugins.json`. Publishing the registry is a deploy of the host ([`../core/02-registry.md`](../core/02-registry.md#how-the-app-gets-the-registry)). If the host is down, apps keep their last copy.
- **The open build.** Without `proprietary/`, the host mounts only the Apache-2.0 plugins, so the tree builds and runs with no Business Source License code in it.
- **Deploys.** A change under `plugins/remote/` or `plugins/registry/` builds the image, pushes it to Azure Container Registry, and deploys a new revision. The previous revision is kept for rollback.

## Layout

```
plugins/
  registry/                    Apache-2.0   other publishers' plugins, every kind (../core/02-registry.md)
  remote/                      everything the plugin host runs
    host/                      Apache-2.0   the deployable
      pyproject.toml  uv.lock  Dockerfile  compose.yaml (host, Redis, SearXNG, for local runs)
      __main__.py              python -m host
      app.py                   mounts each plugin at /<id>/mcp, and /health
      mounted_plugins.py       the plugins it serves; skips proprietary/ when absent
      registry_files.py        serves the signed registry and its icons
      config.py                each plugin's settings section
      azure/                   Bicep: the Container App, Redis, SearXNG, Key Vault references
    mcp_server/                Apache-2.0   what every plugin builds its server with
      tools.py                 declaring a tool and its MCP annotations
      progress.py              MCP progress notifications
      result_store.py          a result too large to return whole, kept a day and paged
      access.py                the hook a paid plugin's license check plugs into
    <id>/                      Apache-2.0   a free plugin: server.py, tools.py, tests/
    proprietary/               Business Source License 1.1
      LICENSE
      license/                 checks "License <key>" with Keygen
      scrapers/                SurfSense Scrapers
  bundles/                     deferred (../bundles/README.md)
```

SurfSense's plugins are listed in the app's built-in list, `surfsense_local/backend/modules/plugins/lists/built_in/`, not in `registry/` ([`../core/02-registry.md`](../core/02-registry.md#two-lists)).

`host`, `mcp_server`, `proprietary` and `license` are never plugin ids. `mcp_server/` holds nothing about scraping or licensing: it is what a free plugin needs too. Code moves into it, or out of a plugin, only when a second plugin needs it.

## SurfSense Scrapers

The first paid plugin, `id: scrapers`.

```
plugins/remote/proprietary/scrapers/
  server.py        the MCP server: every platform's tools, progress, cancel
  config.py        its settings, from SCRAPERS_* environment variables
  platforms/       one folder per platform, its scraper and its tools.py: Amazon, Google Maps,
                   Google Search, Indeed, Instagram, Reddit, TikTok, Walmart, YouTube
  web_crawler/     the site crawler, and its tools.py
  proxy/           residential proxy providers and rotation
  captcha/         captcha solving
  crawl/           crawl helpers
  browser_loop.py  the loop that drives Scrapling's stealth browsers
  tests/
```

A new platform is one folder in `platforms/`. Proxy, captcha and crawl stay private to this plugin until a second plugin needs them.

- **Tools.** One per scraper verb: web crawl, Google Search, Reddit, YouTube and its comments, Instagram and its details, TikTok and its comments, user search and trending, Google Maps and its reviews, Indeed, Amazon, Walmart and its reviews. Each declares `readOnlyHint: true` and `openWorldHint: true`, returns a readable summary as text with the items as `structuredContent`, and reports progress with MCP progress notifications. A result too large to return whole is kept for a day and paged with a `get_scraper_result` tool. A cancelled call stops its scrape.
- **The license, on the server.** Every request needs `Authorization: License <key>`, checked by `proprietary/license/` as [`../core/05-paid.md`](../core/05-paid.md) says. The host counts requests per license and limits their rate.
- **Its own secrets:** the proxy providers' credentials, the captcha solver's key, and Keygen access, from Key Vault. None of them reaches the app.
- **Its own dependencies:** Redis for Google Search's IP pool and the result store, SearXNG as Google Search's fallback, and Scrapling's browsers in the host's image.
- **No database.** The scraper API's `runs` table and async-run events are replaced by MCP progress and the short-lived result store in Redis.

### Moving the scraping code

The scraping code lives in `surfsense_backend` today: [`app/proprietary/platforms/`](../../../../surfsense_backend/app/proprietary/platforms/) and [`app/proprietary/web_crawler/`](../../../../surfsense_backend/app/proprietary/web_crawler/), about 19,000 lines, and the helpers it imports, [`app/utils/proxy/`](../../../../surfsense_backend/app/utils/proxy/), [`app/utils/captcha/`](../../../../surfsense_backend/app/utils/captcha/), [`app/utils/crawl/`](../../../../surfsense_backend/app/utils/crawl/) and `app/utils/browser_loop.py`, about 1,450 lines, with settings read from `app.config` and progress reported through `app.capabilities.core.progress`.

1. **Copy now.** `scrapers/` starts as a copy of that code. `app.config` becomes `scrapers/config.py`, `app.capabilities.core.progress` becomes `mcp_server/progress.py`, and the helpers become `proxy/`, `captcha/`, `crawl/` and `browser_loop.py` inside `scrapers/`. The hosted backend keeps its copy, as AGENTS.md requires until the purge on 18 Oct 2026.
2. **Delete the backend's copy when nothing uses it.** The backend's scraper API still serves outside clients, so its copy is deleted once those clients have moved to the plugin host or the scraper API is retired, and never before the purge. Until then a fix to a scraper goes to both copies.
3. **One license for the plugin.** Everything under `scrapers/` is under the Business Source License, including the copies of the helpers that are Apache-2.0 in the backend today ([ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md)).

Outside clients, `surfsense_mcp` and direct users of the scraper API, keep using the backend's scraper API until it is retired; whether they move to the plugin host then is open ([README](../README.md#open-questions)).

## Acceptance

- The plugin host starts and answers `tools/list` at `/scrapers/mcp` with no `surfsense_backend` code, database or service, and its image carries Scrapling's browsers.
- With `proprietary/` removed, the host starts, serves the registry and its free plugins, and has no `/scrapers/mcp`.
- `/plugins.json` and `/plugins.json.sig` are the files CI signed, and the signature verifies with the app's public key.
- A plugin that raises during a call returns an MCP error, and the other plugins keep answering.
- SurfSense Scrapers: a call with a valid trial license returns items; with no key, `401 missing_license`; with an expired one, `403 expired`, each reaching the user as the refusal.
- A cancelled scraper call stops its scrape within ten seconds.
