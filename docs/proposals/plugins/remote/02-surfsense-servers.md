# Remote plugins: SurfSense's own servers

> Owns: `plugins/remote/`: the plugin host, the server kit, SurfSense's plugins, starting with its scraper plugins in `plugins/remote/proprietary/`.
> The client that reaches them: [`01-mcp-client.md`](01-mcp-client.md). Paid: [`../core/05-paid.md`](../core/05-paid.md). Decision: [ADR 0054](../../../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md).

## SurfSense's own servers

SurfSense publishes plugins as remote MCP servers, like anyone, and lists them in the app's first-party list with `publisher: surfsense` ([`../core/02-registry.md`](../core/02-registry.md#two-lists)). It hosts all of them, free and paid, on one plugin host.

| Where the code lives | License | Example |
|---|---|---|
| `plugins/remote/<id>/` | Apache-2.0 | a free plugin, such as a search of a public API |
| `plugins/remote/proprietary/<id>/` | Business Source License 1.1 ([ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md)) | `reddit`, `google-search` |

The folder decides the license and the plugin's `access` decides the price ([`../core/05-paid.md`](../core/05-paid.md#which-license-a-surfsense-plugin-is-under)). The license check belongs to SurfSense's paid plugins alone: third parties' paid plugins check access on their own service.

## The plugin host

One container, deployed by SurfSense to Azure Container Apps, serves the registry of third-party plugins and every SurfSense plugin at `plugins.surfsense.com`, and runs their long calls as jobs. It runs apart from `surfsense_backend`, imports none of its code and uses none of its services.

```
plugins.surfsense.com ──► the plugin host: one container, one image, as many copies as the load needs
                            /plugins.json, /plugins.json.sig, /icons/*   the signed registry
                            /reddit/mcp, /youtube/mcp, …                 a scraper plugin each
                            /<id>/mcp                                    each other SurfSense plugin
                            /health
                            and its job runner, which runs long calls in the background
                                │ jobs, rate limits, license state, calls in flight, caches
                                ▼
                          Redis, with persistence        Blob Storage: jobs' results, deleted a day after
                          beside it, internal only: SearXNG; secrets from Key Vault
```

- **One container, as the backend runs the scrapers today.** One image carries Python and what its plugins need, their browsers among them, once, and one container runs every plugin and their jobs, so one deploy ships them all. A container per plugin was rejected: each would keep its own copy running while idle and its own spare room for its own peaks, where one shared container lends a quiet plugin's room to a busy one, and the work itself, a browser per scrape, costs the same either way ([below](#scaling)).
- **A plugin is a folder, and its own MCP server.** Its `server.py` returns an MCP server of its own, built on the official MCP Python SDK, whose client the app uses too: its own tools, sessions and license check, at its own path. To the app and to opencode each is a separate server; they only share the process. The folder's name, with underscores as hyphens, is the plugin's `id` and its path: `plugins/remote/proprietary/google_search/` is `id: google-search` at `/google-search/mcp`, since a Python package cannot be named with a hyphen. Adding a plugin adds its entry to the first-party list in the same change, so it reaches users with the next app release.
- **One project.** `host/pyproject.toml` and its `uv.lock` hold every plugin's dependencies. A plugin has no `pyproject.toml` or `Dockerfile` of its own. The import root is `plugins/remote/`, so code imports `mcp_server.progress` or `proprietary.reddit.server`.
- **Nothing blocks the event loop.** The plugins share each process's event loop, so one blocking call would stall every call in it. Blocking work, such as Scrapling's synchronous `StealthyFetcher`, runs in a thread with `asyncio.to_thread`, and network calls use async clients; ruff's `ASYNC` rules fail a blocking call inside an `async def` in CI. Each plugin also has its own limit on browsers and threads, so a busy plugin cannot take them all from the others.
- **Failures stay in their plugin.** A mounted plugin turns its own exceptions into MCP errors, every call runs under a deadline, and a copy failing `/health` is restarted. Each plugin reads only its own settings section, `<ID>_*`; that is a convention, not isolation, acceptable because every plugin here is SurfSense's own code.
- **The registry ships in the image.** The Docker build context is `plugins/`, so the image copies `remote/` and the signed `registry/plugins.json`. Publishing the registry is a deploy of the host ([`../core/02-registry.md`](../core/02-registry.md#how-the-app-gets-the-registry)). If the host is down, apps keep their last copy.
- **The open build.** Without `proprietary/`, the host mounts only the Apache-2.0 plugins, so the tree builds and runs with no Business Source License code in it.
- **Deploys.** A change under `plugins/remote/` or `plugins/registry/` builds the image, pushes it to Azure Container Registry, and deploys a new revision. The previous revision is kept for rollback.

## Layout

```
plugins/
  registry/                    Apache-2.0   third-party plugins, every kind (../core/02-registry.md)
  remote/                      everything the plugin host runs
    host/                      Apache-2.0   the deployable
      pyproject.toml  uv.lock  Dockerfile  compose.yaml (host, Redis, Azurite, SearXNG, for local runs)
      __main__.py              python -m host
      job_runner.py            takes jobs from Redis and runs them in the background, in this container
      app.py                   mounts each plugin at /<id>/mcp, and /health
      mounted_plugins.py       the plugins it serves; skips proprietary/ when absent
      registry_files.py        serves the signed registry and its icons
      config.py                each plugin's settings section
      azure/                   Bicep: the host's Container App and its scale rule, Redis, the results' Blob Storage, SearXNG, Key Vault references
    mcp_server/                Apache-2.0   what every plugin builds its server with
      tools.py                 declaring a tool and its MCP annotations
      progress.py              MCP progress notifications
      jobs.py                  long calls and large results as jobs, and get_job and cancel_job
      access.py                the hook a paid plugin's license check plugs into
    <id>/                      Apache-2.0   a free plugin: server.py, tools.py, tests/
    proprietary/               Business Source License 1.1
      LICENSE
      license_check/           checks "License <key>" with Keygen
      scraping/                what every scraper plugin shares: proxies, captcha, browsers, crawl helpers
      google_search/  web_crawler/  reddit/  youtube/  instagram/  tiktok/
      google_maps/  amazon/  walmart/  indeed/      a scraper plugin each
  bundles/                     deferred (../bundles/README.md)
```

SurfSense's plugins are listed in the app's first-party list, `surfsense_local/backend/modules/plugins/lists/first_party/`, not in `registry/` ([`../core/02-registry.md`](../core/02-registry.md#two-lists)).

`host`, `mcp_server`, `proprietary`, `license_check` and `scraping` are never plugin ids. The check is not `license/`, which would be the same path as `LICENSE` on macOS and Windows. `mcp_server/` holds nothing about scraping or licensing: it is what a free plugin needs too. Code moves into it, or out of a plugin, only when a second plugin needs it.

## Adding a plugin

Every SurfSense plugin, the scrapers and any later one, free or licensed, joins the same way, with no change to the image, the host or the deploy:

| | A free plugin | A licensed plugin |
|---|---|---|
| Its folder, which decides its license | `plugins/remote/<id>/`, Apache-2.0 | `plugins/remote/proprietary/<id>/`, Business Source License 1.1 |
| `access` in its `server.py` | None | `LicenseAccess()` |
| Its first-party list entry | `access: free`, `auth: none` | `access: license`, `auth: license` |
| Who may call it | Anyone, limited per IP address | A valid license, limited per license |

- **What the folder holds:** `server.py`, whose `server()` returns its MCP server; its `config.py`, reading only its own `<ID>_*` settings and secrets; its tests.
- **What it brings to the image, in the change that adds it.** Its Python packages go into `host/pyproject.toml` and its system packages and binaries into `host/Dockerfile`, with its settings in `host/.env.example`. The image holds what the plugins in it need and nothing for one not yet written, so it grows a plugin at a time and an unused binary never ships.
- **What every plugin keeps to:** nothing blocks the event loop, its own limit on threads and browsers, a call that can run past three minutes as a job, and errors returned as MCP errors.
- **One list entry,** in the same change, so the plugin reaches users with the next app release.
- **Free plugins are limited per IP address.** A licensed plugin's caller is known by its license; a free plugin's is anyone on the internet, and SurfSense pays for every call, so the host counts a free plugin's requests per address in Redis and answers `429` past its limit.
- **One container, with two ways out.** A plugin whose load dwarfs the rest, or that needs to be kept apart, runs from the same image in a container of its own, started with `PLUGINS=<id>`. A plugin whose dependencies conflict with another's, or that needs a runtime the image cannot carry, gets its own image too. Either is reached at `/<id>/mcp` on `plugins.surfsense.com` through Container Apps' path routing rules, so the app sees the same host and the same license rules, and nothing in it changes. Every other plugin shares the one container.

## The scraper plugins

SurfSense's first paid plugins: one per platform, each its own MCP server and its own entry in the first-party list, so the user connects, switches off and `@`-mentions each apart.

| Plugin | `id` | Its tools |
|---|---|---|
| Google Search | `google-search` | Search results |
| Web Crawler | `web-crawler` | A page; a site, as a job ([below](#long-calls-run-as-jobs)) |
| Reddit | `reddit` | Posts, comments, a subreddit |
| YouTube | `youtube` | Videos, channels, comments |
| Instagram | `instagram` | Profiles and their posts; a keyword search finds profiles through Google Search, so it follows that plugin |
| TikTok | `tiktok` | Videos, comments, user search, trending |
| Google Maps | `google-maps` | Places and their reviews |
| Amazon | `amazon` | Products and search results |
| Walmart | `walmart` | Products, search results and reviews |
| Indeed | `indeed` | Job listings |

```
plugins/remote/proprietary/
  scraping/          shared by every scraper plugin, never a plugin itself
    proxy/           residential proxy providers and rotation
    captcha/         captcha solving
    crawl/           crawl helpers
    browser_loop.py  the loop that drives Scrapling's stealth browsers
    config.py        their settings, from SCRAPING_* environment variables
  reddit/            one folder per plugin, each laid out alike:
    server.py        its MCP server: its tools, progress, cancel
    fetch.py …       the platform's scraper, its modules as the backend had them
    config.py        its own settings, from REDDIT_* environment variables, if it has any
    tests/
```

A new platform is a new plugin folder and a new list entry. A helper moves into `scraping/` only when a second plugin needs it.

The image starts with what Reddit needs: Chromium for its stealth browsers and the fonts that make them look like a desktop's. Each later plugin adds its own as it is written; from the backend's code, YouTube brings `youtube-transcript-api` and `fake-useragent`, the Web Crawler `trafilatura` and `markdownify`, Indeed Camoufox's Firefox for its Cloudflare-solving session, TikTok Xvfb for its headed browser, and Google Search the captcha solver's settings and SearXNG's address.

- **Tools.** Each declares `readOnlyHint: true` and `openWorldHint: true`, returns a readable summary as text with the items as `structuredContent`, and reports progress with MCP progress notifications. A tool that can run past three minutes, such as a site crawl, is a job ([below](#long-calls-run-as-jobs)), and so is a result too large to return whole. A cancelled call stops its scrape.
- **The license, on the server.** Every request to each plugin needs `Authorization: License <key>`, checked by `proprietary/license_check/` as [`../core/05-paid.md`](../core/05-paid.md) says. The host counts requests per license and limits their rate. All of them are on `plugins.surfsense.com`, so one egress consent covers them, and the key reaches no other host.
- **Their secrets:** the proxy providers' credentials and the captcha solver's key, shared through `scraping/`, from Key Vault. None of them reaches the app.
- **Their dependencies:** Redis for jobs and Google Search's IP pool, Blob Storage for jobs' results, SearXNG as Google Search's fallback, and Scrapling's browsers in the host's image.
- **No database.** The scraping code reads and writes none today; the database in `surfsense_backend` belongs to the scraper API around it. Each of its uses has a replacement here:

  | The scraper API's database | On the plugin host |
  |---|---|
  | Users, workspaces and personal access tokens | The license key, checked with Keygen |
  | Credits per workspace owner | None: a license unlocks the plugin, and contract 2 meters no credits for license callers |
  | The `runs` table, async runs and their events | MCP progress on the call, or a job in Redis |
  | `ToolOutputSpill`, large outputs paged by `read_run` | A finished job's result in Blob Storage, paged by `get_job` |
  | Run history for the hosted logs screen | None: that screen goes with the hosted app ([sunset](../../../architecture/sunset.md)) |

## Long calls run as jobs

A call to a plugin is one HTTP request, and Azure Container Apps' ingress ends a request after 240 seconds. MCP progress resets the caller's own timeout, since opencode calls tools with `resetTimeoutOnProgress`, but it does not lift the ingress limit. A deploy or a replica restart also ends every call in flight. So a call that can run past three minutes is a job.

- **Jobs are ordinary tools.** `crawl_site(...)` queues the job and answers at once with `{job_id, status: "running"}`; `get_job(job_id)` answers its status, progress, and its result or a page of it once done; `cancel_job(job_id)` stops it. The agent calls `get_job` again until it is done, so any MCP client can use them.
- **Not MCP tasks.** Tasks, MCP's own start-now-collect-later calls, are experimental in protocol `2025-11-25` and an extension in `2026-07-28`, and opencode 1.18.34 does not use them: it calls every tool with the SDK's plain `callTool`, which refuses a tool whose `execution.taskSupport` is `required`. No SurfSense tool sets it. Tasks can be added over the same jobs once the clients that call SurfSense's plugins use them.
- **The job runner runs them, in the same container.** A tool queues its job in Redis, and the job runner in any copy of the host takes it and runs it in the background, under the copy's own limit on jobs at once. It records a heartbeat as it runs; a job whose copy stopped, by a deploy or a crash, is run once more by another copy, then fails with a reason.
- **A job is its license's.** It keeps a hash of the license key that queued it, never the key, and `get_job` or `cancel_job` from any other license answers that no such job exists.
- **A large result is a finished job.** A tool whose result is too large to return whole returns a summary and a `job_id`, and `get_job` pages the rest.
- **Kept a day.** A job expires from Redis, and its result from Blob Storage, a day after it ends. After that SurfSense's servers hold nothing of it; the result lives on in the thread's opencode session on the user's computer, and in Sources if the user saved it.

### Redis and Blob Storage, not a database

A job's state is small and changes on every heartbeat; its result can be many megabytes, a site crawl's above all, and is written once. So each goes where it fits, and Redis, which holds everything in memory, stays small:

| Kept | Where | For how long |
|---|---|---|
| Jobs: their queue, status, progress and heartbeat | Redis | A day after the job ends |
| Jobs' results, one blob per job, written by the job runner and paged by `get_job` | Blob Storage, a private container reached with the host's managed identity | A day after the job ends, by a lifecycle rule |
| Requests and rate limits per license, and per IP address for free plugins | Redis | The rate window |
| License answers, and when each key was last valid | Redis | Five minutes, and the 24-hour grace while Keygen is down, shared so a deploy during a Keygen outage locks out no one |
| Stops, passed on a channel to every copy, since any may run the thread's call | Redis | Not kept: each copy keeps its own calls in flight |
| Google Search's warm IP pool and its link cache | Redis | Until they go stale |

Redis runs with persistence on, so a Redis restart loses no job. Everything here expires within a day, is read by its key and never queried, and costs at most a rerun when lost. A database would add migrations and backups for none of it. One would come only for usage kept for months and reported on, such as billing by the call, which nothing in this design does.

## Scaling

No call waits for another to finish. In one copy of the host, calls to every plugin run at once: the event loop interleaves them, blocking work runs in threads, and each scrape drives its own Chromium process. A call would wait only for a copy's room, its CPU, memory or browser slots, so the host adds copies before that room runs out.

- **More copies of the one container.** Container Apps' HTTP scale rule adds a copy once a copy's concurrent requests pass a threshold, and removes it when they fall ([scaling](https://learn.microsoft.com/azure/container-apps/scale-app)). Every copy holds every plugin; a plugin costs little until it is called, since its browsers start per call. At least one copy always runs, because browsers start slowly.
- **Room below the threshold.** Each copy runs at most a set number of browsers at once, and the scale threshold sits below it, so a new copy starts before a call would queue for a browser.
- **Stateless MCP.** A copy keeps no MCP session (`stateless_http`), so any copy answers any request, and a deploy breaks nothing. Kept in one process's memory, a session made a request on another copy fail with `404 Session not found`, and Container Apps' sticky sessions need a cookie opencode's MCP client does not keep. Stateless loses only the server's requests to the client, sampling and elicitation, which these plugins do not use; progress still streams with each call. MCP's `2026-07-28` protocol has no sessions at all.
- **Stop is SurfSense's to send.** opencode 1.18.34 cancels a call by sending `notifications/cancelled` as a request of its own, leaving the call's connection open, and with no session no copy can match it to the call, which then runs to its end. So each turn gives a plugin's server a token for the thread, `X-SurfSense-Calls`, beside the license; each copy keeps its calls in flight under that token and the license, and Stop in the app calls the host's `POST /cancel` with both, which Redis passes on to every copy, so the one running the call stops it within seconds and ends its response with a `Request cancelled` error. A client that cancels by closing the call's connection, as `2026-07-28` does, stops it without this.
- **Splitting a plugin out** is the same image in a container of its own, started with `PLUGINS=<id>`, with a path rule for `/<id>/mcp`: no code changes, in the host or the app.

### Moving the scraping code

The scraping code lives in `surfsense_backend` today: [`app/proprietary/platforms/`](../../../../surfsense_backend/app/proprietary/platforms/) and [`app/proprietary/web_crawler/`](../../../../surfsense_backend/app/proprietary/web_crawler/), about 19,000 lines, and the helpers it imports, [`app/utils/proxy/`](../../../../surfsense_backend/app/utils/proxy/), [`app/utils/captcha/`](../../../../surfsense_backend/app/utils/captcha/), [`app/utils/crawl/`](../../../../surfsense_backend/app/utils/crawl/) and `app/utils/browser_loop.py`, about 1,450 lines, with settings read from `app.config` and progress reported through `app.capabilities.core.progress`.

1. **Copy now.** Each folder in `app/proprietary/platforms/` becomes the plugin of the same name, and `app/proprietary/web_crawler/` becomes `web_crawler/`. The helpers become `scraping/`: `proxy/`, `captcha/`, `crawl/` and `browser_loop.py`. `app.config` splits into `scraping/config.py` and each plugin's `config.py`, and `app.capabilities.core.progress` becomes `mcp_server/progress.py`. The captcha solver, synchronous today, becomes async on the way, since a solve can poll for a minute. The hosted backend keeps its copy, as AGENTS.md requires until the purge on 18 Oct 2026.
2. **Delete the backend's copy when nothing uses it.** The backend's scraper API still serves outside clients, so its copy is deleted once those clients have moved to the plugin host or the scraper API is retired, and never before the purge. Until then a fix to a scraper goes to both copies.
3. **One license for all of it.** Every scraper plugin and `scraping/` are under the Business Source License, including the copies of the helpers that are Apache-2.0 in the backend today ([ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md)).

Outside clients, `surfsense_mcp` and direct users of the scraper API, keep using the backend's scraper API until it is retired; whether they move to the plugin host then is open ([README](../README.md#open-questions)).

## Acceptance

- The plugin host starts and answers `tools/list` at each scraper plugin's path, `/reddit/mcp` among them, with no `surfsense_backend` code, database or service, and its image carries Scrapling's browsers.
- Each scraper plugin lists only its own tools, and switching one off in the app leaves the others' tools in the turn.
- With `proprietary/` removed, the host starts, serves the registry and its free plugins, and has none of the scraper plugins.
- `/plugins.json` and `/plugins.json.sig` are the files CI signed, and the signature verifies with the app's public key.
- A plugin that raises during a call returns an MCP error, and the other plugins keep answering.
- A scraper plugin: a call with a valid trial license returns items; with no key, `401 missing_license`; with an expired one, `403 expired`, each reaching the user as the refusal.
- Stop in the app stops a scraper call within ten seconds, whichever copy of the host runs it.
- A site crawl answers a `job_id` at once; `get_job` reports its progress and then its result, through a deploy of the host during the crawl. `cancel_job` stops it within ten seconds.
- A job whose copy of the host is killed runs once more on another copy, and a second failure ends the job failed, with its reason.
- With two copies of the host, a client's requests answered by either copy all succeed, and under load a new copy starts before a call waits for a browser.
- `get_job` with another license's `job_id` answers that no such job exists.
- No scraper tool declares `execution.taskSupport: required`, and each is called by opencode.
- A free plugin answers without a license, and past its limit an address gets `429`.
- A plugin added as a folder and a list entry is served at its path with no change to the deploy; one split into its own container, or given its own image, is reached at its path on `plugins.surfsense.com` like any other.
- `ruff check` with the `ASYNC` rules passes over `plugins/remote/`, and a call that waits on a slow captcha solve leaves another plugin answering.
