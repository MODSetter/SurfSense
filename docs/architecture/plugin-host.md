# Plugin host

The plugin host is the one server that runs SurfSense's own plugins, free and paid, each an MCP server at `/<id>/mcp`. It is apart from `surfsense_backend` and the desktop app, and imports neither. It serves `/health`, `/cancel`, `/license` and each plugin folder, checks the SurfSense license for paid ones, and counts each plugin's tool calls per license ([usage meter](#usage-meter)). All ten scraper plugins are written: [Reddit](#the-reddit-plugin), [YouTube, Amazon, Walmart and Google Maps](#youtube-amazon-walmart-and-google-maps), [Google Search](#the-google-search-plugin), and [Instagram, TikTok, Indeed and Web Crawl](#instagram-tiktok-indeed-and-web-crawl). The app's first-party list offers all ten. The [registry](plugin-registry.md#the-container) is served on the same hostname by a container of its own; the host does not serve it. Both are deployed at `plugins.surfsense.com`.

**Code:** [`plugins/remote/`](../../plugins/remote/)
**Decisions:** [ADR 0054](../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md), [ADR 0047](../adr/0047-premium-plugins-are-source-available.md)

## Layout

`plugins/remote/` is the import root: code imports `host.app`, `mcp_server.access` or `proprietary.license_check`.

| Folder | License | Holds |
|---|---|---|
| [`host/`](../../plugins/remote/host/) | Apache-2.0 | The server, its [usage meter](#usage-meter), its `pyproject.toml` and `uv.lock` for every plugin's dependencies, and the tests of the host |
| [`mcp_server/`](../../plugins/remote/mcp_server/) | Apache-2.0 | What a plugin builds on: [`access.py`](../../plugins/remote/mcp_server/access.py), the hook a paid plugin's check plugs into; [`results.py`](../../plugins/remote/mcp_server/results.py), a tool's result as the agent reads it; and [`progress.py`](../../plugins/remote/mcp_server/progress.py), a call's progress at each stage ([below](#results-and-progress)) |
| `<id>/` | Apache-2.0 | A free plugin (none yet) |
| [`proprietary/`](../../plugins/remote/proprietary/) | Business Source License 1.1 | Paid plugins: [`reddit/`](../../plugins/remote/proprietary/reddit/), [`youtube/`](../../plugins/remote/proprietary/youtube/), [`amazon/`](../../plugins/remote/proprietary/amazon/), [`walmart/`](../../plugins/remote/proprietary/walmart/), [`google_maps/`](../../plugins/remote/proprietary/google_maps/), [`google_search/`](../../plugins/remote/proprietary/google_search/), [`instagram/`](../../plugins/remote/proprietary/instagram/), [`tiktok/`](../../plugins/remote/proprietary/tiktok/), [`indeed/`](../../plugins/remote/proprietary/indeed/) and [`web_crawl/`](../../plugins/remote/proprietary/web_crawl/); [`license_check/`](../../plugins/remote/proprietary/license_check/); and [`scraping/`](../../plugins/remote/proprietary/scraping/), what the scraper plugins share: the residential proxy vendors' providers and their country rotation, the captcha solvers, and the loop that drives Scrapling's stealth browsers, with their settings from `SCRAPING_*` ([`config.py`](../../plugins/remote/proprietary/scraping/config.py)) |

The license check is `license_check/`, not `license/`: a `license/` folder beside the `LICENSE` file is one path on macOS and Windows.

- **The folder decides the license.** `plugins/remote/proprietary/` is under the Business Source License 1.1 by its own [`LICENSE`](../../plugins/remote/proprietary/LICENSE), which names the folder as its scope and turns each version into Apache-2.0 four years after its release. The root `LICENSE` is the plain Apache-2.0 text, so GitHub recognises it ([ADR 0047](../adr/0047-premium-plugins-are-source-available.md)).
- **Only maintainers change `proprietary/`,** so SurfSense holds all of its copyright: code-quality's Proprietary Code job fails a pull request from anyone else that touches it, and CODEOWNERS names them.
- **The open build runs without it.** `test_without_proprietary_the_free_plugins_still_run` deletes `proprietary/` and serves the rest, so Apache-2.0 code never imports from it.
- **The backend keeps its copy.** The scrapers and `scraping/` were copied from `surfsense_backend/app/proprietary/` and `app/utils/` (`proxy/`, `captcha/`, `crawl/`, `browser_loop.py`), which still serve the backend's scraper API, `surfsense_mcp` and outside clients. A fix to a scraper goes to both copies until that API is retired, never before the purge on 18 Oct 2026. The helpers that are Apache-2.0 in the backend are BSL here.

## Adding a plugin

Every plugin joins the same way, with no change to the host, the image's layout or the app:

| | A free plugin | A paid plugin |
|---|---|---|
| Its folder | `plugins/remote/<id>/`, Apache-2.0 | `plugins/remote/proprietary/<id>/`, BSL 1.1 |
| `access` in its `server.py` | None | `shared_access()` ([the license check](#the-license-check)) |
| Its first-party list entry | `access: free`, `auth: none` | `access: license`, `auth: license` |

- The folder holds `server.py`, whose `server()` returns its `MCPServer`, and its tests.
- In the same change: its Python packages in `host/pyproject.toml`, its system packages and binaries in `host/Dockerfile`, its settings in `host/.env.example`, and its entry in the app's [first-party list](plugins.md#surfsenses-own-plugins), whose `tools` `test_first_party_list.py` checks against the server.
- Nothing blocks the event loop (ruff's `ASYNC` rules), and a tool's failure is returned as its MCP error.
- A plugin that must run apart is the same image started with `PLUGINS=<id>`, reached at the same `/<id>/mcp` through a path rule in front.

## Serving plugins

[`host_app()`](../../plugins/remote/host/app.py) mounts each plugin, answers `GET /health` with `ok`, and takes the app's Stop at `POST /cancel` ([below](#stop)).

- A plugin is a folder with a `server.py` whose `server()` returns its `MCPServer`, from the official MCP Python SDK: its own MCP server at its own path. The folder's name, with underscores as hyphens, is its id and its path: `proprietary/google_search/` is served at `/google-search/mcp`, since a Python package cannot hold a hyphen ([`mounted_plugins.py`](../../plugins/remote/host/mounted_plugins.py)).
- Folders under the root and under `proprietary/` are both read. Without `proprietary/`, the open build, the host serves the Apache-2.0 plugins and has nothing else missing.
- `host`, `mcp_server`, `proprietary`, `license_check` and `scraping`, the code the scraper plugins will share, are never plugin ids, nor `health`, `cancel`, `license` and `admin`, the host's own routes. Two plugins with one id stop the host from starting.
- A tool that raises returns an MCP error for that call; the other plugins keep answering.
- MCP is served without sessions (`stateless_http`), so any copy of the host answers any request: none issues an `Mcp-Session-Id`, and a request needs no earlier one on the same copy. Progress still streams with each call; the server cannot send the client requests of its own, such as sampling, which no plugin uses.
- `/<id>/mcp` takes `POST` only: `GET` and `DELETE` are `405` with `Allow: POST`, before any license check ([`post_only.py`](../../plugins/remote/host/post_only.py)). Without sessions, the SDK answered the client's `GET` with an event stream that never carries a message, holding a connection, a task and a ping every 15 seconds per plugin per agent; opencode's client reads `405` as no stream, and there is no session to `DELETE`.
- A plugin's `server.py` may define `lifespan`, a function taking nothing that returns an async context manager, for what it keeps from startup to shutdown, such as warm browsers, kept clients and extractors warmed in advance ([`mounted_plugins.py`](../../plugins/remote/host/mounted_plugins.py), [`app.py`](../../plugins/remote/host/app.py)). It is not `MCPServer(lifespan=...)`, which, without sessions, runs for every request.
  - The host holds each one open in a task of its own: startup waits for none, so a warm-up awaited before the `yield` never delays `/health`, and a lifespan that raises is logged while its plugin is still served. `PLUGIN_LIFESPANS=off` (or `0`, `false`, `no`) holds none, so a warm-up gone wrong is stopped without a release.
  - At shutdown the MCP servers stop first, ending the calls still running, and then each lifespan is left, last mounted first. One that takes over 10 seconds (`CLOSE_SECONDS`) is cancelled; one still starting is cancelled at once.
  - The scraper plugins' lifespans enter [`scraping/lifecycle.py`](../../plugins/remote/proprietary/scraping/lifecycle.py)'s `lifespan()`, counted across plugins. Each shared pool registers its close with `at_shutdown` on first use, and the last plugin to leave closes them all at once, within 15 seconds in all, even when its own exit is cut short: the host's 10 seconds do not cut that close short.
- The SDK's DNS-rebinding guard is off: it protects servers on a user's loopback, and the host is reached by its public name.

`python -m host`, run from `plugins/remote/`, serves on `PORT`, 8000 by default. `PLUGINS`, ids separated by commas, limits the container to those plugins, as one split out of the shared container runs; an id it does not find stops the host from starting. `REDIS_URL` passes a Stop to the other copies. `USAGE_DB_PATH`, `USAGE_ADMIN_TOKEN`, `POSTHOG_API_KEY` and `POSTHOG_HOST` set the [usage meter](#usage-meter). [`host/.env.example`](../../plugins/remote/host/.env.example) lists every setting the container reads, the scraper plugins' `SCRAPING_PROXY_*` among them; locally, `uv run --project host --env-file host/.env python -m host` reads a copy of it.

Before it loads a plugin, `python -m host` redacts every log record as it is made, its message, arguments and traceback, so no logger or handler writes a credential: a URL's `user:password@`, a proxy in the captcha solvers' `user:password@host:port` form, and a `password` or a solver's `key` as a field ([`redacted_logs.py`](../../plugins/remote/host/redacted_logs.py)). Scrapling would otherwise log a failed proxy with its user and password.

## The image

[`host/Dockerfile`](../../plugins/remote/host/Dockerfile) builds the one image every copy of the host runs, from `python:3.12-slim`, with `plugins/` as its build context: `docker build -f plugins/remote/host/Dockerfile -t surfsense-plugins plugins`.

- **Python packages** are exported from `host/uv.lock` with no dev tools and installed as locked, so a rebuild never drifts.
- **Browsers:** `scrapling install` adds Playwright's Chromium and the system libraries it needs, and `patchright install chromium` the build Scrapling's stealth fetchers launch, both under `/ms-playwright` (`PLAYWRIGHT_BROWSERS_PATH`) so an unprivileged user can start them.
- **Fonts** for emoji and CJK, Thai and Latin text, so a stealth browser's fingerprints look like a desktop's.
- **Xvfb**, a virtual display. [`host/entrypoint.sh`](../../plugins/remote/host/entrypoint.sh) starts it on `:99` and sets `DISPLAY` when `CRAWL_HEADED_XVFB_ENABLED=true`, then `exec`s the host, so the host stays the process that gets the container's signals. TikTok's profile feeds need it: TikTok withholds them from a headless browser.
- **One browser for every plugin.** Indeed's Cloudflare-solving session is Scrapling's stealth session, which in Scrapling 0.4 is the same patchright Chromium, so the image holds no Camoufox. A plugin adds its own packages and binaries in the change that adds it ([adding a plugin](#adding-a-plugin)).
- It runs `python -m host` as an unprivileged user, on `PORT`, with a health check on `/health`. `/srv/remote/usage/`, owned by that user, holds the usage meter's file; production mounts a persistent volume there, which takes the folder's owner when new. Its settings are environment variables, as [`host/.env.example`](../../plugins/remote/host/.env.example) lists.
- [`Dockerfile.dockerignore`](../../plugins/remote/host/Dockerfile.dockerignore) keeps out the bundles, every `tests/` folder, the host's sample plugins among them, and local state.

## Stop

opencode cancels a call by sending `notifications/cancelled` as a request of its own, leaving the call's connection open, and no copy without sessions can match it to the call. So the app sends each plugin on the plugin host a token for the user's thread, `X-SurfSense-Calls`, and calls `POST /cancel` with it and the license when the user stops the reply ([agent](agent.md#plugins)).

- Each copy runs a call that carries the token where it can be cancelled, under the hash of its `Authorization` and the token ([`calls_in_flight.py`](../../plugins/remote/host/calls_in_flight.py), [`cancellable_calls.py`](../../plugins/remote/host/cancellable_calls.py)). A Stop with another token or another license cancels nothing.
- `POST /cancel` without a token is `400 missing_token`; otherwise `202`, and the Stop is passed to every copy ([`cancel_broadcast.py`](../../plugins/remote/host/cancel_broadcast.py)): on a Redis channel when `REDIS_URL` is set, within the process otherwise. A copy starts while Redis is down and reconnects when it returns; a Stop sent while Redis is down still ends the calls on the copy that took it.
- The cancelled call's response still ends whole, with a JSON-RPC `-32800` `Request cancelled` error, in its event stream if it had begun one.

## The Reddit plugin

[`reddit/`](../../plugins/remote/proprietary/reddit/) is the backend's anonymous Reddit scraper, copied, behind one MCP tool, `scrape`, at `/reddit/mcp` ([`server.py`](../../plugins/remote/proprietary/reddit/server.py)). It sets `access = shared_access()`.

- **The tool.** `scrape` takes `urls` (a post, subreddit, user or search URL), `search_queries` or `community`, at least one of them and at most 20 URLs or searches, with `sort` (unset, a search orders by relevance, or by newest under a post date limit, and a listing by newest), `time_filter`, `include_nsfw`, `skip_comments`, `max_items` (1–100), `max_posts`, `max_comments` and the two date limits. It declares `readOnlyHint` and `openWorldHint`, so the app lets it run without asking.
- **What it returns.** A summary as text, one line per item with its kind, title, community and link, and the items themselves as `structuredContent` under `items`. It reports MCP progress after each item.
- **How it reaches Reddit.** Reddit closed logged-out `.json` on 2026-10-13, so the plugin reads the HTML Reddit renders for a logged-out visitor, over plain HTTP with no browser ([`fetch.py`](../../plugins/remote/proprietary/reddit/fetch.py)). Each proxy session first asks for one listing with the `over18` cookie, which sets the anonymous `loid` jar on its sticky residential IP; asked with no cookie, Reddit answers a reCAPTCHA page and then a JavaScript check on that IP's full pages. Later pages replay the jar at least 2 seconds apart, and a 403 or either challenge page rotates IP and country rather than being solved. [`pages/`](../../plugins/remote/proprietary/reddit/pages/) reads each page into the `.json` shape the scraper always paged through: a subreddit's posts from `/svc/shreddit/community-more-posts/<sort>/`, a post and its comments from `/comments/<id>/`, whose comment tree streams in after `</html>`, then further top-level comments by the page's own POST to `/svc/shreddit/more-comments/` until `max_comments`, a user's feeds from `/svc/shreddit/profiles/profile_<feed>-more-posts/new/`, and search from `/svc/shreddit/search/` or `/svc/shreddit/r/<sub>/search/`. A subreddit's details come from the header on its top post's page, since its own pages often serve the JavaScript check. Each route is asked for as Reddit spells it: `more-comments` with a trailing slash, or POSTed with the stealth headers' Google referer, is a 403. Independent targets run at once on up to 16 sessions. Only a vendor's provider, `nodemaven` or `dataimpulse` in `SCRAPING_PROXY_PROVIDER`, can pin a session and a country: NodeMaven by the URL's user, DataImpulse by a country in the user and a sticky port from 10000 to 20000 per session, since it ignores a session id in the user and rotates per request; unset, scrapes go direct and Reddit refuses them, and any other name is an error rather than a silent fall back to direct ([`registry.py`](../../plugins/remote/proprietary/scraping/proxy/registry.py)).
- **Errors** reach the agent as the tool's error, in words: no source given, a URL that is not http(s), or Reddit refusing every address. A run whose every target Reddit refused raises that refusal rather than answering with no items; one refused target among others still yields the rest.
- Running it for real needs the browsers, `uv run scrapling install` in `host/`, and the proxy settings.

## YouTube, Amazon, Walmart and Google Maps

Each is the backend's scraper, copied with its imports moved and its collectors' progress turned into an `on_item` callback, behind one tool per backend verb, laid out and answering as Reddit's does: read-only and open-world, the backend's own inputs and limits, a summary as text with the items as `structuredContent`, progress per item, and `access = shared_access()`.

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
| [Instagram](../../plugins/remote/proprietary/instagram/server.py) `/instagram/mcp` | `scrape` (posts or reels of profiles, posts and reels) and `details` (profiles), each by `urls` or `search_queries`, not both | Plain HTTP on a warmed session holding one IP, reading the pages a logged-out visitor sees, since `web_profile_info` answers `require_login` ([`pages/`](../../plugins/remote/proprietary/instagram/pages/)). A profile's details join its page (bio, following, link) with its embed, `/<user>/embed/` (exact follower and post counts, its newest posts in full). Its posts feed is its page's grid, each post taken in full from the embed, with its product type and alt text from the grid and its owner's name from the profile, or else from its own `/p/<code>/` page; the grid lists pinned posts first and the embed leaves them out, which marks them. Its reels feed is its `/reels/` tab, whose nodes say which are pinned and count plays, each reel read from its own page for its video; it asks for no embed. A post taken from the embed carries no video URL: `scrape`'s description tells the agent to scrape that post's URL for it, which reads the post's own page when the file is needed, since the URL is signed and expires within hours to days. A login-page redirect flagged `is_from_rle` is a rate limit and rotates the exit. A keyword finds profiles through the Google Search plugin's scraper, so it costs a Google render |
| [TikTok](../../plugins/remote/proprietary/tiktok/server.py) `/tiktok/mcp` | `scrape` (videos, profiles, hashtags), `comments`, `trending` and `user_search` | A video's page over plain HTTP; feeds, comments, trending and user search by a stealth browser that captures TikTok's own API responses, on country-pinned exits, retried on a fresh country when empty. Profile feeds run headed on Xvfb |
| [Indeed](../../plugins/remote/proprietary/indeed/server.py) `/indeed/mcp` | `scrape` (jobs, by search or URL, in any Indeed country) | A stealth browser context kept per Indeed country on a sticky exit in that country, so its Cloudflare clearance carries across calls, with job details from Indeed's own `spa=1` JSON ([`fetch.py`](../../plugins/remote/proprietary/indeed/fetch.py)); a session still walled after three new sessions ends the call with the tool's error |
| [Web Crawl](../../plugins/remote/proprietary/web_crawl/server.py) `/web-crawl/mcp` | `crawl` (read pages as markdown, and follow same-site links to a depth of 5 and 200 pages) | Plain HTTP first, then a browser, then a stealth browser that can solve a captcha with the shared solver. One page read puts its text's first 2,000 characters in the summary |

- **Blocks.** Instagram and TikTok refusing every IP is the tool's error; TikTok's withheld feeds and comments are items with an `errorCode` (`no_items`, `no_comments`, `no_users`), as the backend returned them.
- **Web Crawl refuses private addresses**: loopback, private ranges, link-local, carrier-grade NAT, the cloud metadata address and names that do not resolve, before any fetch ([`net_guard.py`](../../plugins/remote/proprietary/web_crawl/net_guard.py)). Its browser tiers run on the shared browser loop, as Google Search's do, so its captcha solve awaits the async solver. It needs `trafilatura`, `markdownify` and `validators`.
- **Settings**, with the backend's names: `CRAWL_HEADED_XVFB_ENABLED` (headed TikTok feeds), `TIKTOK_LISTING_MAX_ATTEMPTS`, and the stealth browser's `CRAWL_GEOIP_MATCH_ENABLED`, `CRAWL_BLOCK_WEBRTC`, `CRAWL_HIDE_CANVAS`, `CRAWL_GOOGLE_SEARCH_REFERER` and `CRAWL_DNS_OVER_HTTPS`. Instagram's one is its login wall's memory ([known gaps](#known-gaps)); Indeed needs none of its own.

## The license check

A plugin's `server.py` may set `access`, an object with `refusal(headers)` ([`access.py`](../../plugins/remote/mcp_server/access.py)). The host asks it before every request reaches the plugin, and answers a refusal itself with its status and `{"reason": ...}` ([`refused_unless_allowed.py`](../../plugins/remote/host/refused_unless_allowed.py)). A plugin without `access` is open: SurfSense offers no free plugin yet, and nothing limits an open one per IP address ([Known gaps](#known-gaps)).

A paid plugin sets `access = shared_access()` ([`license_access.py`](../../plugins/remote/proprietary/license_check/license_access.py)): one `LicenseAccess` for the process, shared by every paid plugin, so a key is asked about once for all of them. It applies [contract 2](../contracts/02-scraper-api-auth.md):

| Request | Answer |
|---|---|
| No `Authorization: License <key>`, another scheme, or an empty key | `401 missing_license`, without asking Keygen |
| Keygen says `VALID` | Through to the plugin |
| `EXPIRED` | `403 expired` |
| `SUSPENDED` or `BANNED` (a refund suspends) | `403 revoked` |
| `NOT_FOUND` or any other code | `403 invalid` |
| Keygen answers 4xx or a redirect | `403 invalid`, and a warning in the log: a wrong account id or address answers so for every key |
| Keygen unreachable, answering 5xx or with no code, key valid in the last 24 hours | Through to the plugin |
| Keygen unreachable, answering 5xx or with no code, key not valid in the last 24 hours, or refused since | `503 license_service_unavailable` |

- Keygen is asked about a key at most once in five minutes; the answer, refusal or not, is kept that long.
- After five minutes a key Keygen last called `VALID` still passes at once, while Keygen is asked again in the background for the next request, for up to 24 hours since that answer; past that the request waits for Keygen. A refused key always waits for Keygen's new answer, so a renewed key passes on its first request after five minutes. A key refused since its last check still makes one more call, or the few that arrive before Keygen's answer.
- Keygen is asked about a key once at a time: every request carrying it, on any plugin, waits for the same answer, and one giving up leaves it to the others.
- Keygen is asked on one kept client, which reuses its connection ([`scraping/api_clients.py`](../../plugins/remote/proprietary/scraping/api_clients.py)), as the captcha solvers are; they poll CapSolver every second.
- The check uses Keygen's `validate-key` action ([`keygen.py`](../../plugins/remote/proprietary/license_check/keygen.py)), which takes no token: the key is the credential, so the host holds no Keygen secret.
- Its settings are the backend's, under the same names and meanings, so a deployment gives both the same values: `KEYGEN_API_URL`, the accounts endpoint, Keygen Cloud's `https://api.keygen.sh/v1/accounts` unless set; `KEYGEN_ACCOUNT_ID`, SurfSense's account, without which a paid plugin stops the host from starting; and `KEYGEN_HOST`, a self-hosted Keygen CE's hostname, sent as `Host` with `X-Forwarded-Proto: https`, since CE finds the account from `Host` and redirects plain HTTP unless a proxy vouches for it ([portal](license/portal.md)). Production's CE is reached inside the deployment, at `http://keygen-web:3000/v1/accounts` with `KEYGEN_HOST=keygen.internal`, as the backend reaches it.


`GET /license` answers whether a request's license unlocks the paid plugins, once for all of them, so the app need not list each paid plugin to learn it ([`license_route.py`](../../plugins/remote/host/license_route.py)). It is the first mounted paid plugin's own check, so its answers, cache and grace are the table's: `200 {"status": "valid"}`, or the refusal's status and `reason`. A host without a paid plugin, the open build, has no `/license`.

## Usage meter

The host counts each plugin's tool calls per license ([`usage_meter/`](../../plugins/remote/host/usage_meter/)), so SurfSense can detect abuse, plan fair-use limits and see which plugins and tools to improve, the purposes section 4.4 of the website's [privacy policy](../../surfsense_web/app/(home)/privacy/page.tsx) names. The license is a flat price, so nothing is billed from these counts. [ADR 0016](../adr/0016-no-telemetry.md) keeps such counts on the server, never in the app, and the app sends nothing new for them.

- **What is counted.** Only JSON-RPC `tools/call` requests to `/<id>/mcp`, per UTC day, license, plugin, tool and outcome, each with a call count and the calls' total milliseconds. `initialize`, `tools/list`, `GET /license`, `/cancel` and `/health` are not counted.

  | Outcome | When |
  |---|---|
  | `ok` | The tool answered |
  | `tool_error` | The tool answered with its MCP error (`isError`) |
  | `refused` | The license check refused the request |
  | `cancelled` | A Stop ended the call |
  | `error` | Anything else: a JSON-RPC error, another HTTP status, or no answer |

- **The license** is Keygen's license id, `data.id` in the same `validate-key` answer the check already asks for, so counting costs no Keygen call. The check sets it as `checked_license` ([`access.py`](../../plugins/remote/mcp_server/access.py)) for the request, allowed or refused. A call with no key or a key Keygen does not know, and any free plugin's call, counts as `unlicensed`.
- **Never read or kept:** the tool's arguments, the license key, the `X-SurfSense-Calls` token and the IP address. Only the tool's name is read from the request, and a name the plugin has no tool for is kept as `unknown`, since the caller chose it. Of the response, only the outcome is kept.
- **Where it sits.** `MeteredCalls` wraps each plugin inside `PostOnly` and outside the license check, so refusals are counted ([`metered_calls.py`](../../plugins/remote/host/usage_meter/metered_calls.py)). It reads at most 1 MiB of a body before that check, so no caller can make the host hold more; a longer call reaches the plugin whole, uncounted. It is best effort: a failure in the meter is logged once and never fails, blocks or slows a call.
- **Storage.** Counts are kept in memory and written every 60 seconds, and at shutdown after the last call, to SQLite at `USAGE_DB_PATH`, off the event loop ([`usage_store.py`](../../plugins/remote/host/usage_meter/usage_store.py)). It defaults to `usage/plugin-usage.sqlite3` under the working directory, `/srv/remote/usage/` in the image. A write that fails keeps its counts for the next one. Each license's first day with a call, whatever its outcome, is kept too, for the license cohort report.
- **Retention.** Once a day the host deletes the rows older than 13 months, and a license's first day once the license has no row left, as section 8 of the website's [privacy policy](../../surfsense_web/app/(home)/privacy/page.tsx) says.
- **Daily rollup.** With `POSTHOG_API_KEY` set, yesterday's totals go to PostHog (`POSTHOG_HOST`, `https://us.i.posthog.com` by default) as personless events, with no license id ([`rollup.py`](../../plugins/remote/host/usage_meter/rollup.py)): `plugin_usage_daily` per plugin, tool and outcome, with `day`, `plugin`, `tool`, `outcome`, `calls`, `total_ms` and `distinct_licences`; and `plugin_licences_daily`, with `day`, `active_licences` (licenses with a call that day) and `new_licences` (licenses whose first call was that day). The host checks every hour and sends each day once, so a restart or a failed send is caught up within the hour. `python -m host.usage_meter.rollup --day YYYY-MM-DD`, run from `plugins/remote/`, sends one day by hand, even one already sent. Each event's `uuid` is made from its name, day, plugin, tool and outcome, so a day sent again carries the same ids and PostHog keeps one copy instead of counting it twice.
- **Admin routes.** With `USAGE_ADMIN_TOKEN` set, two routes serve the records to `Authorization: Bearer <token>`, compared in constant time, and answer `401` without it; unset, both are `404` ([`admin_routes.py`](../../plugins/remote/host/usage_meter/admin_routes.py)). Each writes the counts so far before it reads.

  | Route | Answer |
  |---|---|
  | `GET /admin/usage/first-seen` | `{"licences": {"<license id>": "YYYY-MM-DD"}}`: each license's first day with a call |
  | `GET /admin/usage/daily?day=YYYY-MM-DD` | That day's totals as the rollup sends them, with no license id; `400 invalid_day` for any other date form |

## Results and progress

opencode keeps only a tool result's text when it has any, so whatever the text leaves out the agent never sees: a summary of titles hid prices, page text, reviews and answers, and the agent called again for them. A plugin returns `tool_result(summary, items, project=...)` ([`results.py`](../../plugins/remote/mcp_server/results.py)):

- The text is the summary, then each item as one compact line of JSON, with the fields `project` picks. Nulls, empty strings and empty lists or objects are dropped, and a string over 2,000 characters (`clip_chars`) is cut with an ellipsis.
- The text stays within 32,000 bytes (`max_text_bytes`), about 8,000 tokens. The items that do not fit are left out in order and counted on the last line: `N more items not shown: this reply is full`. A first item too long on its own is cut to fit: its one long string, such as a page's text, when that is enough, and otherwise its line, so the agent still reads its start, such as a place's first reviews. Items past the cap are never serialised.
- `structured_content` holds the items whole, as before, unless the request carries `x-surfsense-text-only: 1` (`wants_text_only(ctx)`).

A client gives up on a call after a silence, 200 seconds for opencode, and only a progress notification resets it. `stage(ctx, message, done=..., total=...)` ([`progress.py`](../../plugins/remote/mcp_server/progress.py)) reports each stage of a call, such as an attempt started or a page fetched, not only each item done: at most once a second per call, always the item that first reaches the total, the value rising with every notification as MCP requires, from the browser loop too, and never raising.

## Tests

From `plugins/remote/host`: `uv run pytest`, `uv run ruff check ..` and `uv run ruff format --check ..`. The lint includes ruff's `ASYNC` rules, which fail a blocking call inside an `async def`, since the plugins share each process's event loop. CI runs them in `plugins-pull-request-checks.yml` when `plugins/remote/` changes.

- [`test_first_party_list.py`](../../plugins/remote/host/tests/test_first_party_list.py) checks that each entry in the app's first-party list names exactly the tools its `server.py` registers, read from the source, since building a licensed plugin needs the license server's account.
- [`host/tests/`](../../plugins/remote/host/tests/) serve sample plugins on loopback and reach them with the official MCP client: the health check, each plugin at its path, the build without `proprietary/`, a failing tool, an underscored folder at its hyphenated id, and reserved folders. `test_plugin_lifespans.py` checks the lifespans held while serving and left last mounted first after the calls end, a failing one, a warm-up that never ends delaying neither startup nor shutdown, and a close cut short; `test_post_only.py` the `405`s, before any license check; `test_results.py` and `test_progress.py` the text results, their byte cap and count line, a first item too long on its own, text only, and progress once a second and always rising, through the host too. `test_scaling.py` drives a stateless host as opencode's client does: a request answered by a copy that never saw the one before it, `PLUGINS`, and Stop ending the thread's call with a whole response, leaving another thread's or license's alone, and reaching the call on another copy through a real Redis, from `REDIS_URL` in CI or a `redis-server` the test starts.
- [`proprietary/license_check/tests/`](../../plugins/remote/proprietary/license_check/tests/) check the license against a stand-in Keygen on loopback, with the clock passed in: each answer above, the five-minute cache, a valid key answered at once and asked about again in the background, one check per key however many requests wait on it, one access per process shared by two paid plugins, the 24-hour grace and its end once a key is refused, a 4xx refusing the key as invalid, a reply with no code read as no answer, `Host` and `X-Forwarded-Proto` sent only with `KEYGEN_HOST`, the settings read from the environment, a paid sample plugin through the host, and `/license` answering once for every paid plugin.
- [`test_redacted_logs.py`](../../plugins/remote/host/tests/test_redacted_logs.py) checks each credential form hidden, text without one left alone, and every record redacted before a handler formats it, its traceback included.
- `proprietary/<plugin>/tests/` hold each plugin's tests from the backend, beside a `test_<plugin>_plugin.py` that serves the real plugin on the host behind a stand-in Keygen, the site faked at its fetch seam, Google Search's at its render seam: its tools listed read-only and open-world, each tool's results with their summary and progress, a block or sign-in wall, a call naming nothing refused, and no license refused.
- [`proprietary/license_check/tests/`](../../plugins/remote/proprietary/license_check/tests/) also check that the license id is taken from Keygen's answer with no extra call, and `test_license_metering.py` counts calls through the host under that id, a refused key's included, and checks that the key never reaches the meter's file.
- [`test_usage_meter.py`](../../plugins/remote/host/tests/test_usage_meter.py) counts calls through the host by plugin, tool and outcome, a Stop's included, and nothing but `tools/call`; checks that a canary in a call's arguments, key and thread token never reaches the SQLite file, the rollup or the admin route; that a meter that raises, or a store that cannot be written, fails no call and loses no count; a body over 1 MiB passed whole and uncounted; the admin routes' token and answers; and the 13-month retention. [`test_usage_rollup.py`](../../plugins/remote/host/tests/test_usage_rollup.py) checks yesterday's events sent once to a stand-in PostHog with no license id, nothing sent without a key, a refused send retried, the rollup command, and the same event ids for a day sent again.
- [`proprietary/reddit/tests/`](../../plugins/remote/proprietary/reddit/tests/) run the real plugin on the host behind a stand-in Keygen, with Reddit faked at the scraper's `read_listing` and its proxy sessions: one read-only, open-world tool; a search's posts with their summary and progress; Reddit refusing every address, and a call naming nothing, as the tool's error; and a request with no license refused. [`test_pages.py`](../../plugins/remote/proprietary/reddit/tests/test_pages.py) fakes Reddit one step lower, at `fetch_page`, with pages cut to the shape Reddit serves: a subreddit's listing, its details from a post page's header, a post with its comment tree and later batches, search site-wide and in one subreddit, and a user's overview, comments and posts with each feed's cursor. The fetch tests hold the warm's `over18` cookie, a challenge page rotating, routes spelled as Reddit spells them and a POST's Reddit referer. The scraper's own tests, its parsers, URLs, rotation and fan-out, came from the backend with it, as did the proxy providers' tests, in [`proprietary/scraping/tests/`](../../plugins/remote/proprietary/scraping/tests/), beside the captcha solvers', which solve against a stand-in vendor on loopback.
- [`proprietary/instagram/tests/test_pages.py`](../../plugins/remote/proprietary/instagram/tests/test_pages.py) fakes Instagram at the scraper's `fetch_html` with pages cut to the shape Instagram serves logged out: a profile's details from its page and embed, its posts in full with the pinned one first, skipping pinned posts, and its reels from the reels tab with their play counts. The fetch tests hold a rate-limit redirect to the login page rotating the exit.

## Known gaps

- Reddit's nested "more replies" are not followed, as the `.json` read stopped at its `more` stubs: a post gives its first batch of comments and further top-level ones, not every reply deep in a thread.
- Reddit's 403 page reads "blocked by network security" for a closed endpoint and for a route spelled wrong alike, so a route Reddit renames would trip the closed latch: once two countries' warmed sessions get that page every call fails for 30 minutes (`REDDIT_CLOSED_LATCH_S`, `REDDIT_CLOSED_QUORUM`) before one asks again.
- An Instagram profile's feeds stop at what a logged-out visitor sees, its latest 12 posts or 12 reels: the page's own next-page query answers `null` logged out (2026-10-22). A video in the posts feed has no view count, which only the reels tab gives.
- TikTok returned no comments for a public video, headless or headed, on three exit countries (measured 2026-10-12).
- Web Crawl runs a whole crawl in one call, so a deep crawl of many pages can pass the request limit of the proxies in front of the host; it is to run as a job.
- A block reads as an error item (Amazon, Walmart) or as no items (YouTube), not as the tool's error, so the agent may take it for an empty result.
- 20 of the backend's tests stay skipped, as there, for want of captured responses: 15 of Google Maps', 2 of Reddit's, 2 of Instagram's and 1 of YouTube's.
- YouTube's date cutoffs need `dateparser`, which the image lacks; neither tool offers a cutoff yet.
- Indeed, TikTok and Web Crawl open their pages in the shared browser pool, at most `SCRAPING_MAX_BROWSERS` browsers (3) and `SCRAPING_MAX_BROWSER_PAGES` pages (6) in all ([`browser_pool.py`](../../plugins/remote/proprietary/scraping/browser_pool.py)); Google Search and Google Maps still launch their own. No per-IP limit for a free plugin, since none exists.
- Calls are counted per license ([usage meter](#usage-meter)) but not rate-limited. License answers and the 24-hour grace are kept per replica, in memory, not in Redis, so a deploy during a Keygen outage refuses keys that were valid.
- Google Search renders a call's pages side by side only as far as its warm IPs allow (`GOOGLE_SEARCH_MAX_CONCURRENT_PAGES`, 4), each page up to 180 seconds, so a call of many queries or pages can still pass the request limit of the proxies in front of the host.
- No deadline on a plugin's call. Long calls and large results do not run as jobs, and there is no job runner or object storage ([proposal](../proposals/plugins/README.md#long-calls-as-jobs-on-the-plugin-host)).
- Each copy of the host keeps its own usage file and sends its own rollup, so a second copy needs a shared store first; until then its counts and rollups would be split.
- No scale rule, so copies are not yet added on load ([proposal](../proposals/plugins/README.md#scaling-the-plugin-host)).
- No workflow builds or deploys the image; the host is deployed outside CI.
