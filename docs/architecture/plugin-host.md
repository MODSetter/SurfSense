# Plugin host

The plugin host is the one server that runs SurfSense's own plugins, free and paid, each an MCP server at `/<id>/mcp`. It is apart from `surfsense_backend` and the desktop app, and imports neither. It serves `/health`, `/cancel` and each plugin folder, and checks the SurfSense license for paid ones. Of the scraper plugins, [Reddit](#the-reddit-plugin) and [YouTube, Amazon, Walmart and Google Maps](#youtube-amazon-walmart-and-google-maps) are written; the others are still in `surfsense_backend`, and the host is not deployed ([proposal](../proposals/plugins/remote/02-surfsense-servers.md)).

**Code:** [`plugins/remote/`](../../plugins/remote/)
**Decisions:** [ADR 0054](../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md), [ADR 0047](../adr/0047-premium-plugins-are-source-available.md)

## Layout

`plugins/remote/` is the import root: code imports `host.app`, `mcp_server.access` or `proprietary.license_check`.

| Folder | License | Holds |
|---|---|---|
| [`host/`](../../plugins/remote/host/) | Apache-2.0 | The server, its `pyproject.toml` and `uv.lock` for every plugin's dependencies, and the tests of the host |
| [`mcp_server/`](../../plugins/remote/mcp_server/) | Apache-2.0 | What a plugin builds on: [`access.py`](../../plugins/remote/mcp_server/access.py), the hook a paid plugin's check plugs into |
| `<id>/` | Apache-2.0 | A free plugin (none yet) |
| [`proprietary/`](../../plugins/remote/proprietary/) | Business Source License 1.1 | Paid plugins: [`reddit/`](../../plugins/remote/proprietary/reddit/), [`youtube/`](../../plugins/remote/proprietary/youtube/), [`amazon/`](../../plugins/remote/proprietary/amazon/), [`walmart/`](../../plugins/remote/proprietary/walmart/) and [`google_maps/`](../../plugins/remote/proprietary/google_maps/); [`license_check/`](../../plugins/remote/proprietary/license_check/); and [`scraping/`](../../plugins/remote/proprietary/scraping/), what the scraper plugins share: the residential proxy vendors' providers and their country rotation, and the loop that drives Scrapling's stealth browsers, with their settings from `SCRAPING_*` ([`config.py`](../../plugins/remote/proprietary/scraping/config.py)) |

The license check is `license_check/`, not `license/`: a `license/` folder beside the `LICENSE` file is one path on macOS and Windows.

## Serving plugins

[`host_app()`](../../plugins/remote/host/app.py) mounts each plugin, answers `GET /health` with `ok`, and takes the app's Stop at `POST /cancel` ([below](#stop)).

- A plugin is a folder with a `server.py` whose `server()` returns its `MCPServer`, from the official MCP Python SDK: its own MCP server at its own path. The folder's name, with underscores as hyphens, is its id and its path: `proprietary/google_search/` would be served at `/google-search/mcp`, since a Python package cannot hold a hyphen ([`mounted_plugins.py`](../../plugins/remote/host/mounted_plugins.py)).
- Folders under the root and under `proprietary/` are both read. Without `proprietary/`, the open build, the host serves the Apache-2.0 plugins and has nothing else missing.
- `host`, `mcp_server`, `proprietary`, `license_check` and `scraping`, the code the scraper plugins will share, are never plugin ids, nor `health` and `cancel`, the host's own routes. Two plugins with one id stop the host from starting.
- A tool that raises returns an MCP error for that call; the other plugins keep answering.
- MCP is served without sessions (`stateless_http`), so any copy of the host answers any request: none issues an `Mcp-Session-Id`, and a request needs no earlier one on the same copy. Progress still streams with each call; the server cannot send the client requests of its own, such as sampling, which no plugin uses.
- The SDK's DNS-rebinding guard is off: it protects servers on a user's loopback, and the host is reached by its public name.

`python -m host`, run from `plugins/remote/`, serves on `PORT`, 8000 by default. `PLUGINS`, ids separated by commas, limits the container to those plugins, as one split out of the shared container runs; an id it does not find stops the host from starting. `REDIS_URL` passes a Stop to the other copies. [`host/.env.example`](../../plugins/remote/host/.env.example) lists every setting the container reads, the scraper plugins' `SCRAPING_PROXY_*` among them; locally, `uv run --project host --env-file host/.env python -m host` reads a copy of it.

## The image

[`host/Dockerfile`](../../plugins/remote/host/Dockerfile) builds the one image every copy of the host runs, from `python:3.12-slim`, with `plugins/` as its build context so the signed registry can join `remote/` later: `docker build -f plugins/remote/host/Dockerfile -t surfsense-plugins plugins`.

- **Python packages** are exported from `host/uv.lock` with no dev tools and installed as locked, so a rebuild never drifts.
- **Browsers:** `scrapling install` adds Playwright's Chromium and the system libraries it needs, and `patchright install chromium` the build Scrapling's stealth fetchers launch, both under `/ms-playwright` (`PLAYWRIGHT_BROWSERS_PATH`) so an unprivileged user can start them.
- **Fonts** for emoji and CJK, Thai and Latin text, so a stealth browser's fingerprints look like a desktop's.
- **Only what Reddit needs.** A plugin adds its own Python packages, system packages and binaries in the change that adds it, so nothing for an unwritten plugin is in the image: not Xvfb, which TikTok's headed browser needs, nor Camoufox, which Indeed's does ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#adding-a-plugin)).
- It runs `python -m host` as an unprivileged user, on `PORT`, with a health check on `/health`. Its settings are environment variables, as [`host/.env.example`](../../plugins/remote/host/.env.example) lists.
- [`Dockerfile.dockerignore`](../../plugins/remote/host/Dockerfile.dockerignore) keeps out the bundles, every `tests/` folder, the host's sample plugins among them, and local state.

## Stop

opencode cancels a call by sending `notifications/cancelled` as a request of its own, leaving the call's connection open, and no copy without sessions can match it to the call. So the app sends each plugin on the plugin host a token for the user's thread, `X-SurfSense-Calls`, and calls `POST /cancel` with it and the license when the user stops the reply ([agent](agent.md#plugins)).

- Each copy runs a call that carries the token where it can be cancelled, under the hash of its `Authorization` and the token ([`calls_in_flight.py`](../../plugins/remote/host/calls_in_flight.py), [`cancellable_calls.py`](../../plugins/remote/host/cancellable_calls.py)). A Stop with another token or another license cancels nothing.
- `POST /cancel` without a token is `400 missing_token`; otherwise `202`, and the Stop is passed to every copy ([`cancel_broadcast.py`](../../plugins/remote/host/cancel_broadcast.py)): on a Redis channel when `REDIS_URL` is set, within the process otherwise.
- The cancelled call's response still ends whole, with a JSON-RPC `-32800` `Request cancelled` error, in its event stream if it had begun one.

## The Reddit plugin

[`reddit/`](../../plugins/remote/proprietary/reddit/) is the backend's anonymous Reddit scraper, copied, behind one MCP tool, `scrape`, at `/reddit/mcp` ([`server.py`](../../plugins/remote/proprietary/reddit/server.py)). It sets `access = LicenseAccess()`.

- **The tool.** `scrape` takes `urls` (a post, subreddit, user or search URL), `search_queries` or `community`, at least one of them and at most 20 URLs or searches, with `sort`, `time_filter`, `include_nsfw`, `skip_comments`, `max_items` (1–100), `max_posts`, `max_comments` and the two date limits. It declares `readOnlyHint` and `openWorldHint`, so the app lets it run without asking.
- **What it returns.** A summary as text, one line per item with its kind, title, community and link, and the items themselves as `structuredContent` under `items`. It reports MCP progress after each item.
- **How it reaches Reddit.** Each proxy session warms once in a stealth Chromium on one sticky residential IP, since Reddit mints its anonymous `loid` cookie only behind a JavaScript challenge, then fetches `.json` pages over plain HTTP on that IP, rotating IP and country on a block ([`fetch.py`](../../plugins/remote/proprietary/reddit/fetch.py)). Independent targets run at once on up to 16 sessions. Only a vendor's provider, `nodemaven` or `dataimpulse` in `SCRAPING_PROXY_PROVIDER`, can pin a session and a country by rewriting the URL's user; unset, scrapes go direct and Reddit refuses them, and any other name is an error rather than a silent fall back to direct ([`registry.py`](../../plugins/remote/proprietary/scraping/proxy/registry.py)).
- **Errors** reach the agent as the tool's error, in words: no source given, a URL that is not http(s), or Reddit refusing every address. A run whose every target Reddit refused raises that refusal rather than answering with no items; one refused target among others still yields the rest.
- Running it for real needs the browsers, `uv run scrapling install` in `host/`, and the proxy settings.

## YouTube, Amazon, Walmart and Google Maps

Each is the backend's scraper, copied with its imports moved and its collectors' progress turned into an `on_item` callback, behind one tool per backend verb, laid out and answering as Reddit's does: read-only and open-world, the backend's own inputs and limits, a summary as text with the items as `structuredContent`, progress per item, and `access = LicenseAccess()`.

| Plugin | Tools | How it reaches the site |
|---|---|---|
| [YouTube](../../plugins/remote/proprietary/youtube/server.py) `/youtube/mcp` | `scrape` (videos, shorts and streams of a channel, video or search, subtitles if asked) and `comments` | InnerTube over plain HTTP on sticky residential IPs, a stealth browser when every proxy fails, and `youtube-transcript-api` for subtitles |
| [Amazon](../../plugins/remote/proprietary/amazon/server.py) `/amazon/mcp` | `scrape` (products, by URL or search, on any Amazon domain) | Plain HTTP, the exit country following the domain |
| [Walmart](../../plugins/remote/proprietary/walmart/server.py) `/walmart/mcp` | `scrape` (products) and `reviews` | Plain HTTP on US exits |
| [Google Maps](../../plugins/remote/proprietary/google_maps/server.py) `/google-maps/mcp` | `scrape` (places, by search, URL or place id) and `reviews` | Plain HTTP with Google's anonymous cookie, a stealth browser for short links and walls; a sign-in wall is the tool's error |

None needs a setting of its own, only the shared `SCRAPING_PROXY_*`, nor anything in the image but Chromium. Unlike Reddit, a block does not end the call with an error: Amazon and Walmart answer with an error item per input they could not reach, as the backend did, and YouTube with no items.

## The license check

A plugin's `server.py` may set `access`, an object with `refusal(headers)` ([`access.py`](../../plugins/remote/mcp_server/access.py)). The host asks it before every request reaches the plugin, and answers a refusal itself with its status and `{"reason": ...}` ([`refused_unless_allowed.py`](../../plugins/remote/host/refused_unless_allowed.py)). A plugin without `access` is open: SurfSense offers no free plugin yet, and nothing limits an open one per IP address ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#adding-a-plugin)).

A paid plugin sets `access = LicenseAccess()` ([`license_access.py`](../../plugins/remote/proprietary/license_check/license_access.py)), which applies [contract 2](../contracts/02-scraper-api-auth.md):

| Request | Answer |
|---|---|
| No `Authorization: License <key>`, another scheme, or an empty key | `401 missing_license`, without asking Keygen |
| Keygen says `VALID` | Through to the plugin |
| `EXPIRED` | `403 expired` |
| `SUSPENDED` or `BANNED` (a refund suspends) | `403 revoked` |
| `NOT_FOUND` or any other code | `403 invalid` |
| Keygen unreachable or answering 5xx, key valid in the last 24 hours | Through to the plugin |
| Keygen unreachable, key not valid in the last 24 hours | `503 license_service_unavailable` |

- Keygen is asked about a key at most once in five minutes; the answer, refusal or not, is kept that long.
- The check uses Keygen's `validate-key` action ([`keygen.py`](../../plugins/remote/proprietary/license_check/keygen.py)), which takes no token: the key is the credential, so the host holds no Keygen secret. Keygen's address and SurfSense's account id are constants in that file, not settings.

## Tests

From `plugins/remote/host`: `uv run pytest`, `uv run ruff check ..` and `uv run ruff format --check ..`. The lint includes ruff's `ASYNC` rules, which fail a blocking call inside an `async def`, since the plugins share each process's event loop. CI runs them in `plugins-pull-request-checks.yml` when `plugins/remote/` changes.

- [`host/tests/`](../../plugins/remote/host/tests/) serve sample plugins on loopback and reach them with the official MCP client: the health check, each plugin at its path, the build without `proprietary/`, a failing tool, an underscored folder at its hyphenated id, and reserved folders. `test_scaling.py` drives a stateless host as opencode's client does: a request answered by a copy that never saw the one before it, `PLUGINS`, and Stop ending the thread's call with a whole response, leaving another thread's or license's alone, and reaching the call on another copy through a real Redis, from `REDIS_URL` in CI or a `redis-server` the test starts.
- [`proprietary/license_check/tests/`](../../plugins/remote/proprietary/license_check/tests/) check the license against a stand-in Keygen on loopback, with the clock passed in: each answer above, the five-minute cache, the 24-hour grace, and a paid sample plugin through the host.
- `proprietary/<plugin>/tests/` hold each plugin's tests from the backend, beside a `test_<plugin>_plugin.py` that serves the real plugin on the host behind a stand-in Keygen, the site faked at its fetch seam: its tools listed read-only and open-world, each tool's results with their summary and progress, a block or sign-in wall, a call naming nothing refused, and no license refused.
- [`proprietary/reddit/tests/`](../../plugins/remote/proprietary/reddit/tests/) run the real plugin on the host behind a stand-in Keygen, with Reddit faked at the scraper's `fetch_json` and its proxy sessions: one read-only, open-world tool; a search's posts with their summary and progress; Reddit refusing every address, and a call naming nothing, as the tool's error; and a request with no license refused. The scraper's own tests, its parsers, URLs, rotation and fan-out, came from the backend with it, as did the proxy providers' tests, in [`proprietary/scraping/tests/`](../../plugins/remote/proprietary/scraping/tests/).

## Known gaps

- `SURFSENSE_ACCOUNT_ID` in `keygen.py` is empty, so a paid plugin's `LicenseAccess()` stops the host from starting until it is set.
- Google Search, the Web Crawler, Instagram, TikTok and Indeed are still in `surfsense_backend` ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#the-scraper-plugins)).
- A block reads as an error item (Amazon, Walmart) or as no items (YouTube), not as the tool's error, so the agent may take it for an empty result.
- 18 of the backend's tests stay skipped, as there, for want of captured responses: 15 of Google Maps', 2 of Reddit's and 1 of YouTube's.
- YouTube's date cutoffs need `dateparser`, which the image lacks; neither tool offers a cutoff yet.
- With `SURFSENSE_ACCOUNT_ID` empty, the host cannot start with Reddit, even locally.
- No limit on threads or browsers per plugin, so Reddit's warm-up browsers are bounded only by its 16 sessions per call; and no per-IP limit for a free plugin, since none exists.
- Requests are not counted or rate-limited per license. License answers and the 24-hour grace are kept per replica, in memory, not in Redis, so a deploy during a Keygen outage refuses keys that were valid.
- No deadline on a plugin's call and no MCP progress. Long calls and large results do not run as jobs, and there is no job runner, Redis or Blob Storage ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#long-calls-run-as-jobs)).
- No scale rule, so copies are not yet added on load ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#scaling)).
- No registry files or Azure deployment, and no workflow builds or pushes the image.
