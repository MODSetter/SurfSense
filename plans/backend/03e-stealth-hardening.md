# Phase 3e — Stealth hardening (the in-house "undetectable" moat)

> Part of **Phase 3 — WebURL Crawler & Crawl Billing**. See `00-umbrella-plan.md`.
> Depends on `03a` (Scrapling StealthyFetcher tier + `FetchStrategy` seam + `CrawlOutcome`) and `03b` (app-wide proxy provider). Precedes `03d` (captcha) in the escalation order — hardening **avoids** challenges; captcha solving is the paid last resort for the ones we can't avoid. Touches `03c` only via the deferred paid-unblocker tier (its own billing, decided if/when built).

> **Implementation note.** Same convention as `03a`–`03d`: citations use **today's** names (`search_space_id`/`SearchSpace`) and predate `03a`'s `crawl_url` refactor; locate code by **symbol/grep**, not absolute lines. Scrapling references point at the on-disk (gitignored) `references/Scrapling/` checkout pinned to `scrapling[fetchers]>=0.4.9` (`pyproject.toml:91`).

## Objective

Push the Universal WebURL Crawler as far toward "undetectable" as the **free / in-house stack** allows, so we hold a scraping moat for the next ~4–6 months **without** a third-party unblocker (ZenRows/ScrapFly/Bright Data) or a source-patched browser (CloakBrowser — rejected on licensing). Everything here is **runtime/config-level** stealth layered on Scrapling's patchright-Chromium (`03a` engine note): geoip fingerprint coherence, persistent profiles, headed execution, real fonts, and behavioral humanization — plus a **block classifier** + **per-domain strategy memory** so the ladder learns and the cheap tiers get skipped once a domain's working strategy is known. The paid-unblocker tier is defined here as a **deferred** `FetchStrategy` (the explicit escape hatch for when in-house maintenance gets too costly), not built now.

## The realistic ceiling (be honest with downstream devs)

Scrapling already ships strong **runtime** stealth by default: `DEFAULT_ARGS + STEALTH_ARGS` (`references/Scrapling/scrapling/engines/constants.py:24–99`, incl. `--disable-blink-features=AutomationControlled` `:94`), a persistent context (`_browsers/_stealth.py:91–93,366–368`), and `navigator.webdriver` masking via patchright. With `03b` residential proxies + this plan's coherence/humanization on top, the crawler reliably handles **Cloudflare** (via `03a` `solve_cloudflare`) and the long tail of **moderate** anti-bot.

What the free stack does **not** reliably beat: **DataDome, Kasada, reCAPTCHA-Enterprise**, and other behavioral/device-fingerprint systems. Those generally require C++ source-level browser patches (CloakBrowser's 58-patch approach — out on licensing) or a commercial unblocker. For **competitive-intelligence targets** these top-tier defenses are the exception, not the rule, so the in-house moat is a sound 4–6 month bet — with the deferred paid tier (§8) as the pre-wired escape hatch. **Do not promise "beats everything."**

## Levers (all behind the `03a` `FetchStrategy` seam — callers stay outcome-only)

### 1. Geoip fingerprint coherence (match the browser to the proxy exit IP)

A residential IP in Berlin behind an `en-US`/`America/New_York` browser is an instant tell. Make the fingerprint cohere with the proxy's exit geo:

- Resolve the proxy exit IP → country/locale/timezone (lightweight geoip; e.g. a bundled MaxmindLite/`geoip2` DB or the proxy provider's location knob `RESIDENTIAL_PROXY_LOCATION` from `03b`).
- Pass the matched values into StealthyFetcher: `locale=` (drives `navigator.language` + `Accept-Language` — `stealth_chrome.py:34–35`) and `timezone_id=` (`:36`). These flow into the Playwright context (`_browsers/_base.py:440–441`).
- This needs the crawl's **chosen proxy endpoint** surfaced into the strategy (the same seam `03d` needs for IP-bound solves) — capture it once in `03a`'s strategy context, don't re-call `get_proxy_url()` (which rotates on a pool-backed provider, `03b`).

### 2. Fingerprint flags Scrapling already exposes (turn them on)

- `hide_canvas=True` — random noise on canvas ops to defeat canvas fingerprinting (`stealth_chrome.py:40`).
- `block_webrtc=True` — forces WebRTC to respect the proxy, preventing the **real local IP leak** that unmasks proxied browsers (`:41`).
- `google_search=True` (default) — sets a Google referer so the first hit looks like organic arrival (`:45`); override per-need via `extra_headers` (`:46`).
- `additional_args=` — last-priority Playwright context overrides for anything not surfaced as a first-class param (`:51`).

### 2b. HTTP-tier TLS fingerprint (the AsyncFetcher tier — `impersonate`)

The cheap static tier (`03a` tier 1) is the **first** thing every crawl hits, yet it currently sets `stealthy_headers=True` but **no** `impersonate` (`webcrawler_connector.py:284–289`), so its TLS ClientHello is curl_cffi's default JA3 — a non-browser signature that fingerprinting WAFs flag before the body even loads. Pass an `impersonate="chrome"` profile (Scrapling's static engine selects a matching curl_cffi browser profile — `references/Scrapling/scrapling/engines/static.py:36–47`) so the HTTP tier's **JA3/JA4/HTTP-2** matches a real Chrome and coheres with the browser tiers' UA. Cheap, safe, default-on. `03f §S3` is the test that validates parity against `tls.peet.ws`.

### 3. Persistent per-domain profiles (look like a returning human)

Scrapling defaults to a **temporary** user-data dir (fresh = suspicious). Use `user_data_dir=` (`stealth_chrome.py:48`; `launch_persistent_context` `_stealth.py:93,366–368`) to keep a **persistent profile per domain** (or per domain+proxy-geo), so cookies/localStorage/site-trust carry across crawls and the browser presents as a returning visitor rather than a brand-new incognito session. Store profiles under a configured dir (`shared_tmp`-style volume so API + worker share them).

### 4. Headed execution under Xvfb (defeat headless tells)

`headless` defaults to hidden (`stealth_chrome.py:19/71`). Many WAFs flag headless Chromium. Run **headful** (`headless=False`) inside a virtual framebuffer (**Xvfb**) in the Docker worker so the browser is "visible" to itself but needs no real display. Gate behind a config flag (off by default for self-hosted, on for hosted workers that have Xvfb installed).

### 5. Real fonts (canvas/emoji hash realism)

A minimal container has almost no fonts, making canvas/emoji fingerprint hashes obviously synthetic. Install real font packages (DejaVu, Liberation, Noto incl. CJK + emoji) in the worker image so font-enumeration + canvas hashes resemble a real desktop. `Dockerfile` change only (`apt-get install fonts-*`).

### 6. Behavioral humanization (DIY — Scrapling has no `humanize` for the Chromium engine)

Unlike Camoufox, the patchright-Chromium StealthyFetcher exposes **no built-in `humanize`** (verified: zero matches in the StealthyFetcher param set). So humanization is custom, injected via the existing hooks:

- `page_action=` (runs after navigation, `stealth_chrome.py:30`; engine `_stealth.py:258–262`) — randomized mouse moves/curves, scrolls, hover-before-click, and small think-time delays before extraction. This is the **same hook `03d` uses** for token injection, so the two compose (humanize → optional captcha solve).
- `init_script=` (JS executed on page creation, `:33`) — early shims for any residual JS tells not covered by patchright.
- Tunable `wait`/`network_idle` (`:29,27`) so dwell time isn't robotically constant.

### 7. Block classifier + per-domain strategy memory (the "learning ladder")

Two small in-house pieces make the ladder smart instead of brute-force:

- **Block classifier** — inspect each `Response` (status + body/cookie markers) and label the outcome: `OK` / `CLOUDFLARE` / `CAPTCHA_RECAPTCHA` / `CAPTCHA_HCAPTCHA` / `DATADOME` / `KASADA` / `RATE_LIMITED` / `EMPTY`. (Markers: `"Just a moment"` + `cf-mitigated` → Cloudflare; `datadome` cookie/script → DataDome; `g-recaptcha`/`h-captcha` sitekeys → captcha; etc.) The label drives escalation (which tier/lever next), routes captcha types to `03d`, and feeds the memory below. It also makes `CrawlOutcome.status` decisions principled instead of "empty == fail".
- **Per-domain strategy memory** — cache the **strategy that last succeeded per domain** (e.g. Redis key `crawl:strategy:{domain}` with TTL, reusing the existing Redis the indexer already uses for `indexing_locks`). Next crawl of that domain starts at the known-good tier/lever set, skipping cheaper tiers that always fail there — fewer requests, lower latency, less proxy/captcha spend. No DB migration (Redis, best-effort, self-healing on miss).

## 8. Deferred: paid-unblocker tier (the escape hatch, NOT built now)

The moat strategy is explicit: **maintain in-house bypass for ~4–6 months, then move hostile targets to a paid unblocker if demand/maintenance justifies it.** That switch is **evidence-driven, not a guess** — `03f`'s manual scorecard quantifies the free-stack ceiling over time and is the documented trigger for flipping this tier. Pre-wire the seam so the switch is a config flip, not a refactor:

- Define (but do not implement) a `PaidUnblockerStrategy` that satisfies the `03a` `FetchStrategy` contract `(url, ctx) -> CrawlOutcome`, appended **last** in the ladder and active only when an env flag + API key are set.
- It would call an external unblocker (ZenRows/ScrapFly/Bright Data Web Unlocker) for the residual `DATADOME`/`KASADA`/`reCAPTCHA-Enterprise` domains the block classifier flags as unreachable in-house.
- **Its own billing** (cost-plus pass-through, decided at build time) — separate from `03c`'s flat crawl unit and `03d`'s per-solve unit, because unblocker pricing is per-request and provider-specific.
- Until built, those domains simply return non-`SUCCESS` (free under `03c`). This keeps the umbrella's "WebURL Crawler is the moat" honest while bounding our maintenance risk.

## Config / env changes

Add (all default OFF / conservative; next to the `03b`/`03c` knobs in `config/__init__.py` + `.env.example`):

- `CRAWL_GEOIP_MATCH_ENABLED` (default FALSE) + optional geoip DB path.
- `CRAWL_HIDE_CANVAS` / `CRAWL_BLOCK_WEBRTC` (default TRUE — cheap, safe).
- `CRAWL_PERSISTENT_PROFILES_DIR` (unset → Scrapling's temp default; set → per-domain profiles).
- `CRAWL_HEADED_XVFB_ENABLED` (default FALSE; requires Xvfb in the image).
- `CRAWL_HUMANIZE_ENABLED` (default TRUE) + dwell/jitter bounds.
- `CRAWL_STRATEGY_MEMORY_TTL_S` (default e.g. `86400`; 0 → disabled).
- `CRAWL_PAID_UNBLOCKER_ENABLED` (default FALSE) + provider/key (deferred tier).

## Docker changes (`surfsense_backend/Dockerfile`)

- Install **Xvfb** + a font set (`fonts-dejavu`, `fonts-liberation`, `fonts-noto`, `fonts-noto-cjk`, `fonts-noto-color-emoji`) in the worker image. (Note from `03a`: also drop the stale "+ Camoufox" comment near `:112`; `scrapling install` only fetches Chromium.)
- Headed runs need the browser launched under `xvfb-run` (or an Xvfb display in the worker entrypoint), gated by `CRAWL_HEADED_XVFB_ENABLED`.

## Work items

1. **Geoip coherence** — resolve proxy exit geo → `locale`/`timezone_id`; thread the crawl's chosen endpoint into the strategy context (shared seam with `03d`).
2. **Fingerprint flags** — wire `hide_canvas`/`block_webrtc`/`google_search`/`extra_headers`/`additional_args` from config into the StealthyFetcher tier. Also add `impersonate="chrome"` to the AsyncFetcher (HTTP) tier (§2b) so its TLS coheres. **Centralize this into a single per-tier kwargs builder** (one function that returns the StealthyFetcher / AsyncFetcher kwargs from config) — the crawler *and* `03f`'s harness both import it, so the scorecard grades the exact browser we ship (no test-vs-prod drift).
3. **Persistent profiles** — per-domain `user_data_dir` under `CRAWL_PERSISTENT_PROFILES_DIR` (shared volume).
4. **Headed + Xvfb** — `headless=False` path gated by flag; Xvfb + fonts in the worker image.
5. **Humanization** — a `page_action` humanizer (mouse/scroll/dwell) composing with `03d`'s injector; optional `init_script` shims.
6. **Block classifier** — `classify(response) -> BlockType`, used by the ladder + `CrawlOutcome.status` + `03d` routing.
7. **Per-domain strategy memory** — Redis read/write around the ladder; start at known-good tier; self-heal on miss.
8. **Paid-unblocker seam** — define the deferred `FetchStrategy` + config flag only (no provider integration).
9. **Instrumentation** — log `(domain, block_type, winning_strategy, attempts, latency)` for tuning the ladder.
10. **Config + Docker + tests**.

## Risks / trade-offs

- **Arms race / maintenance.** Fingerprint bypasses rot as WAFs update; this is exactly the cost the deferred paid tier (§8) hedges. Instrumentation (work item 9) plus **`03f`'s scorecard** are what tell us when in-house upkeep stops being worth it.
- **Headed/Xvfb cost.** Headful browsers use more CPU/RAM than headless; gate per-flag and only escalate to headed when the block classifier says cheaper tiers fail for a domain (per-domain memory keeps it from being the default).
- **Profile growth.** Persistent profiles accumulate disk; add a size/TTL cap and periodic prune.
- **Geoip accuracy.** A coarse country→locale map is fine; over-fitting per-city tz isn't worth it. Wrong-but-coherent beats default-mismatched.
- **No silver bullet.** Reiterate the ceiling (§"realistic ceiling") in any user-facing copy: the crawler is "best-effort undetectable," not guaranteed.

## Out of scope (hand-offs)

- Cloudflare solving (`03a`), reCAPTCHA/hCaptcha solving + its per-solve billing (`03d`), proxy rotation (`03b`), flat crawl billing (`03c`).
- **Logged-in / account-based bypass** (sticky/static proxies + credential management) — deferred to the platform-actor work (umbrella Phase 8 + `03b` static-proxy hand-off). Public data only this MVP.
- Building the paid-unblocker provider integration — deferred (§8 leaves only the seam + flag).
- **Measuring** undetectability (the scorecard that grades these levers) → `03f` (manual harness). This plan *builds* the levers; `03f` *tests* them.
- Platform-specific structured extractors (Google Maps, LinkedIn public, …) — these sit **on top** of this hardened fetch core as Phase-8 actors; this plan only delivers the core they depend on.
