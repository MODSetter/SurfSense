# Plugin host

The plugin host is the one server that runs SurfSense's own plugins, free and paid, each an MCP server at `/<id>/mcp`. It is apart from `surfsense_backend` and the desktop app, and imports neither. It serves `/health`, `/cancel` and each plugin folder, and checks the SurfSense license for paid ones. All ten scraper plugins are written: [Reddit](#the-reddit-plugin), [YouTube, Amazon, Walmart and Google Maps](#youtube-amazon-walmart-and-google-maps), [Google Search](#the-google-search-plugin), and [Instagram, TikTok, Indeed and Web Crawl](#instagram-tiktok-indeed-and-web-crawl). The host is not deployed ([proposal](../proposals/plugins/remote/02-surfsense-servers.md)).

**Code:** [`plugins/remote/`](../../plugins/remote/)
**Decisions:** [ADR 0054](../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md), [ADR 0047](../adr/0047-premium-plugins-are-source-available.md)

## Layout

`plugins/remote/` is the import root: code imports `host.app`, `mcp_server.access` or `proprietary.license_check`.

| Folder | License | Holds |
|---|---|---|
| [`host/`](../../plugins/remote/host/) | Apache-2.0 | The server, its `pyproject.toml` and `uv.lock` for every plugin's dependencies, and the tests of the host |
| [`mcp_server/`](../../plugins/remote/mcp_server/) | Apache-2.0 | What a plugin builds on: [`access.py`](../../plugins/remote/mcp_server/access.py), the hook a paid plugin's check plugs into |
| `<id>/` | Apache-2.0 | A free plugin (none yet) |
| [`proprietary/`](../../plugins/remote/proprietary/) | Business Source License 1.1 | Paid plugins: [`reddit/`](../../plugins/remote/proprietary/reddit/), [`youtube/`](../../plugins/remote/proprietary/youtube/), [`amazon/`](../../plugins/remote/proprietary/amazon/), [`walmart/`](../../plugins/remote/proprietary/walmart/), [`google_maps/`](../../plugins/remote/proprietary/google_maps/), [`google_search/`](../../plugins/remote/proprietary/google_search/), [`instagram/`](../../plugins/remote/proprietary/instagram/), [`tiktok/`](../../plugins/remote/proprietary/tiktok/), [`indeed/`](../../plugins/remote/proprietary/indeed/) and [`web_crawl/`](../../plugins/remote/proprietary/web_crawl/); [`license_check/`](../../plugins/remote/proprietary/license_check/); and [`scraping/`](../../plugins/remote/proprietary/scraping/), what the scraper plugins share: the residential proxy vendors' providers and their country rotation, the captcha solvers, and the loop that drives Scrapling's stealth browsers, with their settings from `SCRAPING_*` ([`config.py`](../../plugins/remote/proprietary/scraping/config.py)) |

The license check is `license_check/`, not `license/`: a `license/` folder beside the `LICENSE` file is one path on macOS and Windows.

## Serving plugins

[`host_app()`](../../plugins/remote/host/app.py) mounts each plugin, answers `GET /health` with `ok`, and takes the app's Stop at `POST /cancel` ([below](#stop)).

- A plugin is a folder with a `server.py` whose `server()` returns its `MCPServer`, from the official MCP Python SDK: its own MCP server at its own path. The folder's name, with underscores as hyphens, is its id and its path: `proprietary/google_search/` is served at `/google-search/mcp`, since a Python package cannot hold a hyphen ([`mounted_plugins.py`](../../plugins/remote/host/mounted_plugins.py)).
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
- **Xvfb**, a virtual display. [`host/entrypoint.sh`](../../plugins/remote/host/entrypoint.sh) starts it on `:99` and sets `DISPLAY` when `CRAWL_HEADED_XVFB_ENABLED=true`, then `exec`s the host, so the host stays the process that gets the container's signals. TikTok's profile feeds need it: TikTok withholds them from a headless browser.
- **One browser for every plugin.** Indeed's Cloudflare-solving session is Scrapling's stealth session, which in Scrapling 0.4 is the same patchright Chromium, so the image holds no Camoufox. A plugin adds its own packages and binaries in the change that adds it ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#adding-a-plugin)).
- It runs `python -m host` as an unprivileged user, on `PORT`, with a health check on `/health`. Its settings are environment variables, as [`host/.env.example`](../../plugins/remote/host/.env.example) lists.
- [`Dockerfile.dockerignore`](../../plugins/remote/host/Dockerfile.dockerignore) keeps out the bundles, every `tests/` folder, the host's sample plugins among them, and local state.

## Stop

opencode cancels a call by sending `notifications/cancelled` as a request of its own, leaving the call's connection open, and no copy without sessions can match it to the call. So the app sends each plugin on the plugin host a token for the user's thread, `X-SurfSense-Calls`, and calls `POST /cancel` with it and the license when the user stops the reply ([agent](agent.md#plugins)).

- Each copy runs a call that carries the token where it can be cancelled, under the hash of its `Authorization` and the token ([`calls_in_flight.py`](../../plugins/remote/host/calls_in_flight.py), [`cancellable_calls.py`](../../plugins/remote/host/cancellable_calls.py)). A Stop with another token or another license cancels nothing.
- `POST /cancel` without a token is `400 missing_token`; otherwise `202`, and the Stop is passed to every copy ([`cancel_broadcast.py`](../../plugins/remote/host/cancel_broadcast.py)): on a Redis channel when `REDIS_URL` is set, within the process otherwise. A copy starts while Redis is down and reconnects when it returns; a Stop sent while Redis is down still ends the calls on the copy that took it.
- The cancelled call's response still ends whole, with a JSON-RPC `-32800` `Request cancelled` error, in its event stream if it had begun one.

## The Reddit plugin

[`reddit/`](../../plugins/remote/proprietary/reddit/) is the backend's anonymous Reddit scraper, copied, behind one MCP tool, `scrape`, at `/reddit/mcp` ([`server.py`](../../plugins/remote/proprietary/reddit/server.py)). It sets `access = LicenseAccess()`.

- **The tool.** `scrape` takes `urls` (a post, subreddit, user or search URL), `search_queries` or `community`, at least one of them and at most 20 URLs or searches, with `sort`, `time_filter`, `include_nsfw`, `skip_comments`, `max_items` (1–100), `max_posts`, `max_comments` and the two date limits. It declares `readOnlyHint` and `openWorldHint`, so the app lets it run without asking.
- **What it returns.** A summary as text, one line per item with its kind, title, community and link, and the items themselves as `structuredContent` under `items`. It reports MCP progress after each item.
- **How it reaches Reddit.** Each proxy session warms once in a stealth Chromium on one sticky residential IP, since Reddit mints its anonymous `loid` cookie only behind a JavaScript challenge, then fetches `.json` pages over plain HTTP on that IP, rotating IP and country on a block ([`fetch.py`](../../plugins/remote/proprietary/reddit/fetch.py)). Independent targets run at once on up to 16 sessions. Only a vendor's provider, `nodemaven` or `dataimpulse` in `SCRAPING_PROXY_PROVIDER`, can pin a session and a country: NodeMaven by the URL's user, DataImpulse by a country in the user and a sticky port from 10000 to 20000 per session, since it ignores a session id in the user and rotates per request; unset, scrapes go direct and Reddit refuses them, and any other name is an error rather than a silent fall back to direct ([`registry.py`](../../plugins/remote/proprietary/scraping/proxy/registry.py)).
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

## The Google Search plugin

[`google_search/`](../../plugins/remote/proprietary/google_search/) is the backend's Google Search scraper behind one tool, `scrape`, at `/google-search/mcp` ([`server.py`](../../plugins/remote/proprietary/google_search/server.py)), licensed like Reddit.

- **The tool.** `scrape` takes `queries`, 1 to 20 search terms or Google Search URLs, with `max_pages_per_query` (1–10), `country_code`, `language_code` and `site`: the backend's inputs and limits. Each results page is an item, with its organic results, ads, People Also Ask, AI Overview and related searches; the summary lists each page's organic results. Progress is reported per page.
- **How it reaches Google.** Google walls most residential IPs and builds its results with JavaScript, so each page is rendered in a stealth Chromium on a sticky IP that a cheap plain-HTTP check found unwalled, kept in a pool of warm IPs and reused ([`fetch.py`](../../plugins/remote/proprietary/google_search/fetch.py)). Sticky sessions come from the proxy provider, so NodeMaven holds them as DataImpulse does. A page has 180 seconds before it is given up.
- **The reCAPTCHA wall.** A browser on even a clean IP lands on Google's `/sorry` reCAPTCHA Enterprise page. With `SCRAPING_CAPTCHA_API_KEY` set, the solver (`capsolver` or `2captcha`, `SCRAPING_CAPTCHA_PROVIDER`) solves it through the same sticky IP, and the exemption cookie Google returns is reused for every later page on that IP ([`captcha.py`](../../plugins/remote/proprietary/google_search/captcha.py), [`scraping/captcha/`](../../plugins/remote/proprietary/scraping/captcha/)). The solver is async, and an out-of-balance or wrong key stops solving until the host restarts. Without a key nothing is solved.
- **Warm IPs across copies.** With `REDIS_URL`, a solved IP and its cookies are published to Redis for an hour, and another copy adopts it instead of paying for a solve ([`pool_store.py`](../../plugins/remote/proprietary/google_search/pool_store.py)). Without Redis each copy keeps its own pool.
- **Result links.** Google's desktop links are `/goto` redirects whose target is encrypted, so each is followed one hop over the rotating proxy to read its destination; one that will not resolve keeps its redirect ([`goto.py`](../../plugins/remote/proprietary/google_search/goto.py)).
- **The fallback.** When Google walls every IP for a page, `SEARXNG_URL`, if set, answers it with organic results only, marked `resultsProvider: "searxng"`, and the summary says it is not Google's ranking ([`searxng.py`](../../plugins/remote/proprietary/google_search/searxng.py)). The instance must serve JSON.
- **Errors.** A call that got no page at all, every IP walled and no fallback, is the tool's error, not an empty result. A call with no queries is refused, and so is one naming another site's URL: an agent wanting a page's text would otherwise pay a render and a solve to search for the URL, so the error points it at Web Crawl.

## Instagram, TikTok, Indeed and Web Crawl

Each is the backend's scraper, copied as the others were, behind one tool per backend verb, with the backend's inputs and limits, a summary as text with the items as `structuredContent`, progress per item, and the license.

| Plugin | Tools | How it reaches the site |
|---|---|---|
| [Instagram](../../plugins/remote/proprietary/instagram/server.py) `/instagram/mcp` | `scrape` (posts or reels of profiles, posts and reels) and `details` (profiles), each by `urls` or `search_queries`, not both | Plain HTTP on a warmed session holding one IP, Instagram's web API with its anonymous cookies. A keyword finds profiles through the Google Search plugin's scraper, so it costs a Google render |
| [TikTok](../../plugins/remote/proprietary/tiktok/server.py) `/tiktok/mcp` | `scrape` (videos, profiles, hashtags), `comments`, `trending` and `user_search` | A video's page over plain HTTP; feeds, comments, trending and user search by a stealth browser that captures TikTok's own API responses, on country-pinned exits, retried on a fresh country when empty. Profile feeds run headed on Xvfb |
| [Indeed](../../plugins/remote/proprietary/indeed/server.py) `/indeed/mcp` | `scrape` (jobs, by search or URL, in any Indeed country) | A stealth browser that solves Cloudflare and warms on the country's home page, on one sticky IP per session; a session still walled after three new sessions ends the call with the tool's error |
| [Web Crawl](../../plugins/remote/proprietary/web_crawl/server.py) `/web-crawl/mcp` | `crawl` (read pages as markdown, and follow same-site links to a depth of 5 and 200 pages) | Plain HTTP first, then a browser, then a stealth browser that can solve a captcha with the shared solver. One page read puts its text's first 2,000 characters in the summary |

- **Blocks.** Instagram and TikTok refusing every IP is the tool's error; TikTok's withheld feeds and comments are items with an `errorCode` (`no_items`, `no_comments`, `no_users`), as the backend returned them.
- **Web Crawl refuses private addresses**: loopback, private ranges, link-local, carrier-grade NAT, the cloud metadata address and names that do not resolve, before any fetch ([`net_guard.py`](../../plugins/remote/proprietary/web_crawl/net_guard.py)). Its browser tiers run on the shared browser loop, as Google Search's do, so its captcha solve awaits the async solver. It needs `trafilatura`, `markdownify` and `validators`.
- **Settings**, with the backend's names: `CRAWL_HEADED_XVFB_ENABLED` (headed TikTok feeds), `TIKTOK_LISTING_MAX_ATTEMPTS`, and the stealth browser's `CRAWL_GEOIP_MATCH_ENABLED`, `CRAWL_BLOCK_WEBRTC`, `CRAWL_HIDE_CANVAS`, `CRAWL_GOOGLE_SEARCH_REFERER` and `CRAWL_DNS_OVER_HTTPS`. Instagram and Indeed need none of their own.

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
| Keygen unreachable, key not valid in the last 24 hours, or refused since | `503 license_service_unavailable` |

- Keygen is asked about a key at most once in five minutes; the answer, refusal or not, is kept that long.
- The check uses Keygen's `validate-key` action ([`keygen.py`](../../plugins/remote/proprietary/license_check/keygen.py)), which takes no token: the key is the credential, so the host holds no Keygen secret. Keygen's address and SurfSense's account id are constants in that file, not settings.

## Tests

From `plugins/remote/host`: `uv run pytest`, `uv run ruff check ..` and `uv run ruff format --check ..`. The lint includes ruff's `ASYNC` rules, which fail a blocking call inside an `async def`, since the plugins share each process's event loop. CI runs them in `plugins-pull-request-checks.yml` when `plugins/remote/` changes.

- [`host/tests/`](../../plugins/remote/host/tests/) serve sample plugins on loopback and reach them with the official MCP client: the health check, each plugin at its path, the build without `proprietary/`, a failing tool, an underscored folder at its hyphenated id, and reserved folders. `test_scaling.py` drives a stateless host as opencode's client does: a request answered by a copy that never saw the one before it, `PLUGINS`, and Stop ending the thread's call with a whole response, leaving another thread's or license's alone, and reaching the call on another copy through a real Redis, from `REDIS_URL` in CI or a `redis-server` the test starts.
- [`proprietary/license_check/tests/`](../../plugins/remote/proprietary/license_check/tests/) check the license against a stand-in Keygen on loopback, with the clock passed in: each answer above, the five-minute cache, the 24-hour grace and its end once a key is refused, and a paid sample plugin through the host.
- `proprietary/<plugin>/tests/` hold each plugin's tests from the backend, beside a `test_<plugin>_plugin.py` that serves the real plugin on the host behind a stand-in Keygen, the site faked at its fetch seam, Google Search's at its render seam: its tools listed read-only and open-world, each tool's results with their summary and progress, a block or sign-in wall, a call naming nothing refused, and no license refused.
- [`proprietary/reddit/tests/`](../../plugins/remote/proprietary/reddit/tests/) run the real plugin on the host behind a stand-in Keygen, with Reddit faked at the scraper's `fetch_json` and its proxy sessions: one read-only, open-world tool; a search's posts with their summary and progress; Reddit refusing every address, and a call naming nothing, as the tool's error; and a request with no license refused. The scraper's own tests, its parsers, URLs, rotation and fan-out, came from the backend with it, as did the proxy providers' tests, in [`proprietary/scraping/tests/`](../../plugins/remote/proprietary/scraping/tests/), beside the captcha solvers', which solve against a stand-in vendor on loopback.

## Known gaps

- `SURFSENSE_ACCOUNT_ID` in `keygen.py` is empty, so a paid plugin's `LicenseAccess()` stops the host from starting until it is set.
- Instagram's profile API answers `401` to an anonymous session on every IP and country, even with its web app's full headers, so both tools fail on public profiles; the profile page itself still loads with its counts (measured 2026-10-12).
- TikTok returned no comments for a public video, headless or headed, on three exit countries (measured 2026-10-12).
- Web Crawl runs a whole crawl in one call, so a deep crawl of many pages can pass Azure's 240-second request limit; it is to run as a job.
- A block reads as an error item (Amazon, Walmart) or as no items (YouTube), not as the tool's error, so the agent may take it for an empty result.
- 20 of the backend's tests stay skipped, as there, for want of captured responses: 15 of Google Maps', 2 of Reddit's, 2 of Instagram's and 1 of YouTube's.
- YouTube's date cutoffs need `dateparser`, which the image lacks; neither tool offers a cutoff yet.
- With `SURFSENSE_ACCOUNT_ID` empty, the host cannot start with Reddit, even locally.
- No limit on threads or browsers per plugin, so Reddit's warm-up browsers are bounded only by its 16 sessions per call; and no per-IP limit for a free plugin, since none exists.
- Requests are not counted or rate-limited per license. License answers and the 24-hour grace are kept per replica, in memory, not in Redis, so a deploy during a Keygen outage refuses keys that were valid.
- Google Search runs its queries and pages one after another, each page up to 180 seconds, so a call of many queries or pages can pass Azure's 240-second request limit.
- No deadline on a plugin's call and no MCP progress. Long calls and large results do not run as jobs, and there is no job runner or Blob Storage ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#long-calls-run-as-jobs)).
- No scale rule, so copies are not yet added on load ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#scaling)).
- No registry files or Azure deployment, and no workflow builds or pushes the image.
