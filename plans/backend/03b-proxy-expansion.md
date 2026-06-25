# Phase 3b — Proxy provider expansion + rotation

> Part of **Phase 3 — WebURL Crawler & Crawl Billing**. See `00-umbrella-plan.md`.
> Depends on `03a-crawler-core.md` (Scrapling-only crawler). Siblings: `03c-crawl-billing.md`, `03d-captcha-solving.md` (deferred).

> **Implementation note.** Same convention as `03a`: citations use **today's** names (`search_space_id`/`SearchSpace`) — map to `workspace_id`/`Workspace` post Phases 1–2. Crucially, the `webcrawler_connector.py` line numbers below (e.g. the three tiers at 287/329/359) and the `scrape_webpage.py` lines **predate `03a`'s Firecrawl removal + `crawl_url` refactor**, so they will have moved by the time `03b` is implemented. Locate code by **symbol/grep**, not absolute lines.

## Objective

Let the WebURL Crawler (and every other proxy consumer) run behind **either** the existing `anonymous_proxies` gateway **or** a new BYO `CustomProxyProvider`, chosen by a **single, app-wide** `Config.PROXY_PROVIDER`. When the active provider is backed by a **pool of endpoints**, rotate across them client-side with a bounded retry. **No branded vendors and no per-connector/per-crawl provider divergence** (resolved decisions): the whole app uses one provider.

The provider abstraction already exists and is clean; the real gaps are just (1) only `anonymous_proxies` is registered (no BYO option), and (2) there is **no client-side rotation/retry** when a provider exposes multiple endpoints. The "process-global, env-only" shape is exactly what we want for a single-provider app, so we keep it.

## Current state (cited)

### A clean but process-global abstraction

`app/utils/proxy/` is already a "subclass + register" provider package:

- `base.py` — `ProxyProvider` ABC: `get_proxy_url()` (canonical `http://user:pass@host:port` for Scrapling/curl_cffi), `get_playwright_proxy()`, `get_requests_proxies()` (built from the URL by default).
- `registry.py` — `_PROVIDERS` dict keyed by provider `name`; `get_active_provider()` resolves `Config.PROXY_PROVIDER` and **caches a single instance process-wide** (`_active_provider`, lines 23, 26–44). Only `AnonymousProxiesProvider` is registered (lines 17–19).
- `__init__.py` — zero-arg module helpers `get_proxy_url()` / `get_playwright_proxy()` / `get_requests_proxies()` + a `get_residential_proxy_url()` back-compat alias, all delegating to `get_active_provider()`.
- `providers/anonymous_proxies.py` — the one vendor. Note it's a **server-side rotating gateway**: host is `rotating.dnsproxifier.com:PORT` and the rotation `type`/location are encoded into a base64 "password" dict (lines 23–51). So per-request IP rotation already happens **upstream**; the client sends one static endpoint.
- `app/utils/proxy_config.py` — a thin back-compat shim re-exporting the package (kept for old import paths).

Config knobs: `Config.PROXY_PROVIDER` (default `"anonymous_proxies"`) + `RESIDENTIAL_PROXY_{USERNAME,PASSWORD,HOSTNAME,LOCATION,TYPE}` (`config/__init__.py:983–992`; documented commented-out in `.env.example:300–309`).

### Who consumes the proxy (blast radius)

The zero-arg getters are used in **more than just the crawler**, so any signature change must stay backward-compatible:

| Consumer | File:line | Uses |
|----------|-----------|------|
| WebURL crawler (all 3 Scrapling tiers) | `connectors/webcrawler_connector.py` (287, 329, 359) | `get_proxy_url()` |
| YouTube transcript route | `routes/youtube_routes.py` (78, 119) | `get_proxy_url()` |
| YouTube processor (indexing) | `tasks/document_processors/youtube_processor.py` (223, 229) | `get_requests_proxies()`, `get_proxy_url()` |
| Chat scrape tools (YouTube branch) | `main_agent/tools/scrape_webpage.py` (80, 93), `research/tools/scrape_webpage.py` (74, 87) | `get_requests_proxies()`, `get_proxy_url()` |

**Implication:** the whole app shares **one** global provider, so every consumer keeps calling the zero-arg getters **unchanged**. The only behavior change is (a) *which* provider class those getters resolve to (selected by `Config.PROXY_PROVIDER`) and (b) optional client-side rotation when that provider is pool-backed. No caller passes a key; no signatures change.

**Shape note (verified):** `get_playwright_proxy()` has **no consumers** anywhere — only the ABC/impl/exports define it. All three crawler tiers and YouTube's `AsyncFetcher.get` consume the **string** form (`get_proxy_url`); browser fetchers accept a string proxy (`references/Scrapling/.../stealth_chrome.py:47` — "it can be a string or a dictionary"). The dict form (`get_requests_proxies`) is consumed only by YouTube-transcript fetches (`youtube_processor.py:223`, plus the chat tools' YouTube branch `main_agent/tools/scrape_webpage.py:80` and `research/tools/scrape_webpage.py:74`) — none of which are crawler tiers. **Conclusion:** rotation only needs the **string** shape; the playwright dict can be ignored (or left as-is on providers) rather than threaded through rotation.

### Scrapling's rotation primitive

`ProxyRotator(proxies: list, strategy=cyclic_rotation)` is a thread-safe cycler over a **static list** of proxy URLs/dicts (`get_proxy()`, `proxy_rotation.py:88–92`) plus `is_proxy_error(exc)` (`:27–30`) that matches proxy failure strings (`net::err_proxy`, `connection refused`, …). It does **not** manage credentials or sessions — it just hands out the next endpoint. So it's only useful when we have a **pool of distinct endpoints**; it adds nothing for a single server-side-rotating gateway like `anonymous_proxies`.

Both are **publicly importable**: `from scrapling.engines.toolbelt import ProxyRotator, is_proxy_error` (re-exported in `engines/toolbelt/__init__.py:1–3`). The thread-safe `Lock` (`:71,90`) makes `ProxyRotator` safe to call from the browser tiers that `03a` runs via `asyncio.to_thread`. Version is guaranteed: the pinned floor is `scrapling[fetchers]>=0.4.9` (`pyproject.toml:91`) and these APIs exist as of `0.4.9` (`scrapling/__init__.py:2`).

## Selection scope (resolved)

The user expects a **single proxy provider across the entire app**, so 03b's selection scope is simply the **global, env-configured provider** — no per-connector or per-crawl override is built now. That is both the fastest path and, with one thin seam, the most scalable later:

- All resolution stays behind today's `get_active_provider()` (env-selected, process-cached). One provider, app-wide.
- "Scalable in future": if per-pipeline proxying is ever wanted (Phase 5+), it layers on as an **optional argument** to a resolver (`resolve_proxy(override=pipeline.config)`) with **zero** changes to existing call sites — but it is explicitly **not** implemented in 03b (YAGNI for a single-provider app).

## Target design

### 1. Registry: register the BYO provider; keep single-provider selection

The existing `get_active_provider()` (env-selected via `Config.PROXY_PROVIDER`, cached process-wide in `_active_provider` — `registry.py:23,26–44`) is exactly the single-provider model we want — keep it. The only change is to **register `CustomProxyProvider`** so `PROXY_PROVIDER` can select it:

- `_PROVIDERS["anonymous_proxies"] = AnonymousProxiesProvider` (existing) + `_PROVIDERS["custom"] = CustomProxyProvider` (new).
- `get_active_provider()` resolves the **one** active provider from env and caches it — **no keyed multi-provider coexistence** (`get_provider(key)` is intentionally NOT added; YAGNI for a single-provider app).
- Unknown `PROXY_PROVIDER` → existing warn-and-fallback path (`registry.py:35–41`) is unchanged.

### 2. Provider config source: env only

Credentials come from **env**, full stop (single global provider):

- `anonymous_proxies` → existing `RESIDENTIAL_PROXY_*`. Unchanged.
- `custom` → new env knobs (one URL or a pool): `CUSTOM_PROXY_URLS` (comma-separated) and/or `CUSTOM_PROXY_URL`.

No per-connector proxy keys, and **no** connector-config validator changes (that was the per-connector path, now dropped).

### 3. New provider: `CustomProxyProvider` (BYO) — the only addition

- Accepts a raw proxy URL **or** a list of URLs from env. Covers "bring your own proxy / our own pool" with no vendor-specific auth assumptions.
- Implements just `get_proxy_url()`; the base derives `get_requests_proxies()` from it (`base.py:37–46`). When configured with a **pool**, `get_proxy_url()` returns the *next* endpoint from an internal `ProxyRotator` (see §4) — so rotation is transparent to every caller of the zero-arg getter.
- **No branded vendors** (resolved): Webshare/BrightData/Smartproxy/etc. are not shipped. A user who wants any specific vendor points `CustomProxyProvider` at that vendor's endpoint(s) via `CUSTOM_PROXY_URLS`.

### 4. Rotation + retry (only when the active provider is pool-backed)

- If `CustomProxyProvider` is configured with **multiple** URLs, it wraps them in Scrapling's `ProxyRotator` (cyclic default, thread-safe `Lock` — `proxy_rotation.py:71,88–92`) and returns the next endpoint per `get_proxy_url()` call. Because `03a`'s browser tiers run under `asyncio.to_thread`, the rotator's lock keeps this safe.
- The crawler adds a **bounded** client-side retry: on a tier failure where `is_proxy_error(exc)` is true (`proxy_rotation.py:27–30`), it re-reads `get_proxy_url()` (next endpoint) and retries **that tier once** before falling through. One rotation-retry per tier — no unbounded fan-out on billable crawls.
- Single-endpoint providers (`anonymous_proxies`, already server-side rotating; or `custom` with one URL) return the same endpoint every call, so the retry is a harmless no-op for them.

### 5. Crawler stays on the zero-arg getter (no injection needed)

Because there is one global provider and rotation lives **inside** it, the crawler does **not** need a proxy injected per crawl:

- All three Scrapling tiers keep calling `get_proxy_url()` (which yields the rotating value when pool-backed). The only crawler edit is the bounded `is_proxy_error` retry from §4.
- **No change** to YouTube/chat-tool consumers — same zero-arg getters, same global provider.
- Future seam (NOT built): if per-pipeline proxying is ever needed, resolve a provider from `pipeline.config` and pass its `get_proxy_url` into the crawl — an additive optional arg, no change to today's call sites.

## Config / env changes

- `config/__init__.py:983–992` + `.env.example:300–309`: add `CUSTOM_PROXY_URLS` (comma-separated pool) and/or `CUSTOM_PROXY_URL` for the `custom` provider; keep all existing `RESIDENTIAL_PROXY_*` working unchanged. `PROXY_PROVIDER` now accepts `"custom"` in addition to `"anonymous_proxies"`.
- **No** connector-config validator changes (the per-connector proxy path is dropped — single global provider).

## Work items

1. **`CustomProxyProvider`**: BYO single-URL or pool-of-URLs provider (reads `CUSTOM_PROXY_URL(S)`); internal `ProxyRotator` when pool-backed; register as `"custom"` in `_PROVIDERS`.
2. **Rotation retry**: add a bounded (one-per-tier) `is_proxy_error` retry to the crawler's Scrapling tiers; single-endpoint providers no-op.
3. **Config + docs**: `CUSTOM_PROXY_URL(S)` in `Config` + `.env.example`; document `PROXY_PROVIDER="custom"`.
4. **Tests**: `CustomProxyProvider` single-URL vs pool; `ProxyRotator` cyclic order; `get_active_provider()` resolves `"custom"` and still warn-falls-back on unknown; crawler rotates once on `is_proxy_error` then falls through; `anonymous_proxies` + YouTube path unchanged (same endpoint each call).

## Risks / trade-offs

- **Backward compatibility of the getters.** The zero-arg `get_proxy_url()` contract is consumed in 4+ places; the design keeps it **completely intact** — no signature changes, no per-caller keys. Only the cached active provider's *implementation* changes when `PROXY_PROVIDER="custom"`.
- **Over-rotation cost.** Rotation-retry is bounded to one extra attempt per tier so a billable crawl can't silently multiply upstream proxy usage.
- **Single provider is a deliberate constraint.** One global provider app-wide (resolved). Per-pipeline/per-connector selection is intentionally deferred behind a no-op seam (§5); not built now.
- **Pool rotation under `to_thread`.** `ProxyRotator`'s `Lock` makes the rotating `get_proxy_url()` safe to call from the browser tiers `03a` offloads via `asyncio.to_thread`.

## Resolved decisions

- **Branded vendors → NONE.** Ship `CustomProxyProvider` (BYO) only; no Webshare/BrightData/Smartproxy/etc. subclasses. A user who wants a specific vendor points `CUSTOM_PROXY_URLS` at it.
- **Selection scope → single global provider, app-wide.** No per-connector/per-crawl override is built; resolution is env-only via `Config.PROXY_PROVIDER`. A future per-pipeline override is left as a no-op seam (§5) so it stays "scalable + fast to add later."
- **Client-side rotation → built, but only active for a pool-backed `CustomProxyProvider`.** `anonymous_proxies` (server-side rotating) and single-URL custom configs skip it automatically. Rotation lives inside the provider so it's transparent to all callers.

## Out of scope (hand-offs)

- Per-**pipeline** / per-connector proxy selection → deferred (Phases 5–7 *if ever needed*); §5 leaves a no-op seam, nothing is wired now.
- Branded-vendor provider subclasses → not planned (use `CustomProxyProvider`).
- **Static / sticky-session proxies (future).** A later capability will add **static proxy** support — sticky IPs held for the duration of a session — most likely paired with **authenticated/account-based scraping** to bypass logged-in platforms (the deferred platform connectors: LinkedIn, Instagram, etc.). This is a *different axis* from the rotating pool here: rotation maximizes IP diversity, whereas account bypass needs IP **stability** so a session/cookie stays bound to one IP. It is additive to this design — a new `ProxyProvider` (or a "sticky" mode/flag on `CustomProxyProvider`) registered under a new `PROXY_PROVIDER` key, with no change to the zero-arg getter contract — and stays consistent with the single-provider model (the active provider would be the static one when that workflow is selected). Build it alongside the platform connectors, not in Phase 3.
- Crawl credit metering (proxy cost is absorbed into the flat `$1 / 1000 successful` price, **not** metered separately) → `03c`.
- Captcha solving → `03d` (deferred).
