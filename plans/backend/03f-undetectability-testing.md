# Phase 3f — Undetectability & extraction test harness (manual scorecard)

> Part of **Phase 3 — WebURL Crawler & Crawl Billing**. See `00-umbrella-plan.md`.
> **Status: ✅ IMPLEMENTED + first baseline run (`ci_mvp`, 2026-06-30).** Harness lives under the **proprietary boundary** at `surfsense_backend/app/proprietary/web_crawler/testbench/` (package: `core.py` scorecard/closure-cell helper, `suite_stealth.py` Suite S, `suite_extraction.py` Suite E, `__main__.py` CLI, `README.md` runbook) — it's the moat's measurement tool, so it carries the `app/proprietary/LICENSE`, not Apache-2. Run: `python -m app.proprietary.web_crawler.testbench --suite all [--proxy URL] [--headed] [--no-screenshots]`. Suite S builds the StealthyFetcher tier from the **shipped** `build_stealthy_kwargs(get_stealth_config())` (no drift); Suite E drives the real `crawl_url` against ToS-safe sandboxes with deterministic assertions. Writes timestamped `scorecard-*.json`/`.md` + diffs the last run; the **whole `results/` tree is gitignored** (run-local: scorecards, `latest.json`, screenshots, dumps). Captcha forced OFF (unaided score). **Not** pytest-collected (live internet + proxy). **Manual-only** — no CI/automated gating (resolved decision); it's a dev-run scorecard, not a build gate. **First baseline: see "First baseline results" below.**
>
> **Post-implementation notes (reconciled to shipped code):** (1) the `03a`/`03e` "`FetchStrategy` seam" never shipped — levers are a centralized kwargs builder, reflected below; (2) **every detection site is now auto-graded from its real DOM verdict** — the initial "INFO + screenshot, read manually" fallback was replaced after a first run by per-site parsers written against actual DOM dumps (reCAPTCHA-v3 reads the server `"score"` JSON, CreepJS the headless-% + boolean spoof tells incl. `hasHeadlessWorkerUA`, incolumitas the fpscanner FAIL keys + `is_datacenter`, fingerprint-scan the `Bot Risk Score`, FingerprintJS the block message, BrowserScan the Normal/Abnormal count, iphey the masthead verdict, Cloudflare the bypass line). `INFO` is now reserved for purely informational rows (TLS JA3/JA4, exit IP) + the manual browserleaks links; screenshots are still captured as a backstop. Each site is one entry in `suite_stealth.py`, so tightening a parser is a one-function change. Depends on `03a` (the Scrapling tier ladder + `CrawlOutcome`), `03b` (proxy provider), `03e` (the stealth levers being tested), and reuses the `page_action` + closure-cell mechanism shared with `03d`.

> **Convention note.** This is **dev/operator tooling**, not a product code path, so it's untouched by the Phase 1–2 rename (no `search_space_id`/`workspace_id` concern). Citations to the gitignored reference checkouts (`references/CloakBrowser/`, `references/Scrapling/`) are pinned to what's on disk; locate code by **symbol/grep** if lines drift.

## Objective

A **manual, repeatable scorecard** that answers one question: *how undetectable (and how correct) is our Universal WebURL Crawler right now?* It drives the real Scrapling tiers against the industry's standard detection + sandbox sites, parses each site's verdict, and prints a pass/fail + numeric scorecard. Its real job is to **quantify the free-stack ceiling** (`03e`) over time so we know — with evidence — when fingerprint maintenance stops being worth it and we should flip the deferred paid-unblocker tier.

It is explicitly **two axes, two suites** (kept separate so each scales independently):

- **Suite S — Stealth / anti-bot** (is the crawler detected?): browser-tier fingerprint/bot tests, HTTP/TLS-tier fingerprint, proxy/leak verification.
- **Suite E — Extraction correctness** (does the crawler get the content right?): scraping sandboxes for the HTTP vs JS (DynamicFetcher) tiers + Trafilatura quality.

## How CloakBrowser tests (the pattern we copy)

CloakBrowser's suite is a **driven-browser verdict-scraper**, not unit tests (`references/CloakBrowser/examples/stealth_test.py`, run via `bin/cloaktest`). The repeated shape:

1. Launch a real page with **proxy + geoip**, toggleable **headed/headless** (`stealth_test.py:231` `launch(headless=…, proxy=…, geoip=True)`).
2. `page.goto(site, wait_until="networkidle")` then **sleep** — scores compute async (Castle.js ~20 s `fingerprint_scan_test.py:31`; CreepJS ~30 s `:96`; reCAPTCHA polls up to 30 s `stealth_test.py:156–164`).
3. `page.evaluate(js)` to **parse the verdict** from the rendered DOM (sannysoft table `stealth_test.py:32–45`) or from internal JS objects (`window.Fingerprint.headless` `fingerprint_scan_test.py:117–127`).
4. Apply an explicit **pass threshold** + screenshot (`stealth_test.py:169–217`).

Their shipped bars (we adopt as **aspirational targets**, see Scorecard): sannysoft **0 fails**; `bot.incolumitas` ≤ `{WEBDRIVER, connectionRTT}` known-FPs; `browserscan` **0 Abnormal**; `deviceandbrowserinfo` `isBot=false`; FingerprintJS demo **not blocked**; reCAPTCHA v3 **≥0.7** (they hit 0.9); CreepJS **headless ≤30% / stealth ≤30%** (`fingerprint_scan_test.py:112–114,166–171`).

## The bridge to our Scrapling crawler

We are **not** a single browser; we're the `03a` tier ladder. The harness therefore tests **per tier**, and extracts verdicts two ways:

- **DOM/JSON-rendered verdicts** → just `StealthyFetcher.fetch(url, …)` (or `Fetcher.get` for JSON endpoints) and parse the **returned post-JS page** with Scrapling's selector (`load_dom` is on by default — `references/Scrapling/scrapling/fetchers/stealth_chrome.py:43`). Covers sannysoft, incolumitas, deviceandbrowserinfo, the reCAPTCHA score text, and every JSON endpoint (`tls.peet.ws/api/all`, `httpbin/headers`).
- **Internal JS-object verdicts** → a **`page_action`** that runs `page.evaluate()` and stashes the result into a **closure cell**, because Scrapling **discards `page_action`'s return value** (sync `_stealth.py:260`, async `:536`). **This is the exact same `page_action`+closure-cell plumbing as `03d`'s token injector** — building the harness de-risks `03d` (and vice-versa); factor it once. *(As-built: CreepJS/fingerprint-scan turned out to render their verdicts into the visible DOM, so their parsers read the post-JS page text directly; the closure-cell `page_action` path is retained as the mechanism for any future `window.*`-only verdict + for the screenshot backstop.)*

## Suite S — Stealth / anti-bot

### S1. Browser tier (StealthyFetcher — the "undetectable" tier)

All rows are **auto-graded** from the post-JS DOM text (no manual screenshot read); the `Extraction` column names the actual marker each parser keys on.

| Site | Signal | Extraction | Aspirational bar |
|---|---|---|---|
| `bot.sannysoft.com` | webdriver/chrome/plugins/UA leaks | `class="failed"` cell count | 0 fails |
| `bot.incolumitas.com` | 30+ checks incl. behavioral + IP class | `"<key>":"FAIL"` keys, `is_datacenter` | 0 fpscanner FAIL |
| `browserscan.net/bot-detection` | WebDriver/CDP/Navigator | `Normal`/`Abnormal` count | 0 Abnormal |
| `deviceandbrowserinfo.com/are_you_a_bot` | fingerprint + behavioral | `"isBot":` JSON | `isBot=false` |
| `abrahamjuliot.github.io/creepjs` | fingerprint **consistency/lies**, headless% | `N% headless` + boolean tells (`hasHeadlessWorkerUA`…) | headless ≤30%, no tells |
| `fingerprint-scan.com` | Castle.js bot-risk + headless signals | `Bot Risk Score: N/100` | risk < 50 |
| `demo.fingerprint.com/web-scraping` | **behavioral block** (FingerprintJS Pro Smart Signals) | block message (`access denied` / `tampering detected`) | not blocked |
| `recaptcha-demo.appspot.com/...v3-request-scores.php` | Google server-verified human score | server verify `"score":` JSON | score ≥0.7 |
| `www.scrapingcourse.com/cloudflare-challenge` | **Cloudflare challenge** (only row exercising `solve_cloudflare`) | `you bypassed the cloudflare challenge` line | bypassed |
| `iphey.com` | cross-layer fingerprint+IP+geo coherence | masthead `Your Digital Identity Looks <verdict>` (async, ~25 s settle) | `Trustworthy` |

### S2. Per-property fingerprint detail (manual/debug — validates `03e` levers directly)

- `browserleaks.com/canvas`, `/webgl`, `/fonts` — confirms `03e` `hide_canvas` + font packages.
- `browserleaks.com/webrtc` + DNS leak — confirms `03e` `block_webrtc` (no real-IP leak through the proxy).

### S3. HTTP/TLS tier (AsyncFetcher / `Fetcher` — curl_cffi impersonation)

Our HTTP tier is `curl_cffi`-based and impersonates a real Chrome TLS stack (`references/Scrapling/scrapling/fetchers/requests.py:29`; `engines/static.py:6–9,36–47`) **only when `impersonate=` is set** — which `03a` **now ships** (`app/proprietary/web_crawler/connector.py`, the `AsyncFetcher.get` call passes `impersonate="chrome"`). This row therefore **validates the shipped parity** rather than driving a fix: confirm the static tier's JA3/JA4 matches a real Chrome (the `03e §2b` lever). If you ever need a before/after, temporarily drop `impersonate=` to reproduce the curl_cffi-default (red) baseline.

- `tls.peet.ws/api/all` (+ `/api/clean`) — JSON **JA3/JA4/Akamai-HTTP2/PeetPrint**; diff against a real-Chrome baseline.
- `httpbin.co/headers` (or httpbingo) — header set/order/UA sanity.

**Recommendation (resolved): TLS parity is a first-class *axis* but an *informational threshold*, not a hard gate.** We record JA3/JA4 and flag drift from the Chrome baseline, but don't "fail" on it — curl_cffi impersonation is strong yet JA-hashes shift across versions, and this is a manual scorecard anyway. Treat a *mismatch* as a tuning signal (pick a closer `impersonate` profile), not a regression.

### S4. Proxy / leak verification

- `httpbin.org/ip` — exit IP == the proxy endpoint actually used (capture-once seam from `03b`/`03e`, not a re-rotated `get_proxy_url()`).
- WebRTC/DNS (S2) — no real-IP leak.

## Suite E — Extraction correctness (separate axis)

Purpose-built, ToS-safe sandboxes — validates the HTTP vs **DynamicFetcher (JS)** tiers and Trafilatura output, independent of stealth:

- `books.toscrape.com` — static catalog + pagination (HTTP tier; baseline extraction).
- `quotes.toscrape.com` — has **`/js`** (JS-rendered), **`/js-delayed`** (`?delay=`), **scroll** (infinite), **login** (CSRF) variants → exercises the DynamicFetcher JS tier + `wait_selector`/`network_idle`.
- `scrapethissite.com` — mixed structures for extraction robustness.

Assertion style: known expected values (e.g. first book title, quote count per page) so extraction regressions are caught deterministically.

## First baseline results (2026-06-30, headless, rotating residential proxy)

First real run of the free stack (patchright-Chromium + curl_cffi `impersonate="chrome"` + `anonymous_proxies` rotating residential), captcha solving OFF, Slice-A levers only (`CRAWL_GEOIP_MATCH_ENABLED=false`). **Suite S: 6 PASS / 4 FAIL across the 10 detection sites** (the other 6 rows are informational: TLS, exit IP, 4 browserleaks manual links).

| Site | Verdict | Observed |
|---|---|---|
| sannysoft | ✅ PASS | 0 failed cells |
| deviceandbrowserinfo | ✅ PASS | `isBot=false` (incl. `isPlaywright=false`, `isAutomatedWithCDP=false`) |
| reCAPTCHA v3 | ✅ PASS | server score **0.9** |
| BrowserScan | ✅ PASS | Test Results: Normal, 0 Abnormal (WebDriver/CDP/Navigator) |
| fingerprint-scan | ✅ PASS | Bot Risk **35/100** (site flags >50) |
| cloudflare_challenge | ✅ PASS | turnstile **solved** → "you bypassed the Cloudflare challenge" |
| **CreepJS** | ❌ FAIL | headless **33%**, **`hasHeadlessWorkerUA: true`** (worker UA leaks `HeadlessChrome`) |
| **incolumitas** | ❌ FAIL | only legacy `fpscanner WEBDRIVER: FAIL`; all modern tests OK |
| **FingerprintJS Pro** | ❌ FAIL | "anti-detect tampering detected, access denied" |
| **iphey** | ❌ FAIL | verdict **Unreliable** |

**Reading the failures (maps directly to the moat roadmap):**
- **FingerprintJS Pro** = the commercial bar (the documented free-stack ceiling). Needs WebGL/GPU + deeper patches (`03e` Slice B/C) or the deferred paid-unblocker (`03e §8`). Hardest.
- **CreepJS `hasHeadlessWorkerUA`** = the **Web Worker** `navigator.userAgent` still reports `HeadlessChrome` (main-thread UA is clean). Known patchright leak, **plausibly fixable** (worker UA override) → concrete `03e` Slice-B candidate.
- **iphey "Unreliable"** = almost certainly **geoip incoherence** (browser tz/locale default `America/Los_Angeles` vs the rotating proxy's exit geo, because `CRAWL_GEOIP_MATCH_ENABLED` is default-off in Slice A). iphey is now a **live regression test for the `03e` geoip-coherence lever** — flipping `CRAWL_GEOIP_MATCH_ENABLED` is the expected fix to validate.
- **incolumitas** = a single 2017-era `fpscanner WEBDRIVER` check that even some real browsers trip; modern checks (webdriverPresent, SELENIUM_DRIVER, HEADCHR_*, CDP) all OK. Lowest priority.

**Proxy-quality note:** incolumitas's IP classifier returned `is_datacenter: true` on one rotation and `false` on another — the `anonymous_proxies` rotating pool **mixes datacenter and residential exits**, a real undetectability variable independent of our code (input to future proxy-provider evaluation).

## Scorecard & thresholds (resolved)

- **Adopt CloakBrowser's bars as aspirational targets** (above), but the harness's primary output is **our actual measured numbers recorded as the baseline** — a `scorecard.md`/JSON snapshot per run (date, tier, proxy on/off, headed/headless, per-site result), written to the **gitignored** `results/` tree. Subsequent runs diff against the last on-disk baseline so we see drift (ours improving, or a WAF tightening).
- Each row reports: site, tier, verdict, numeric (where applicable), PASS/FAIL vs aspirational bar, and screenshot path.
- A run is summarized as `passed/total` per suite (like `stealth_test.py:314–317`), **never blocking** anything.

## Harness design

- Lives under the **proprietary boundary** at `surfsense_backend/app/proprietary/web_crawler/testbench/` (moat measurement tooling — not Apache-2; not collected by the normal pytest run, since it hits the live internet + needs proxies). It is moved here as a coherent package because it can't be cleanly *partially* moved (a proprietary Suite S would otherwise back-import generic scaffolding from `scripts/`, a forbidden app→scripts direction). A thin CLI mirrors `bin/cloaktest`: `python -m app.proprietary.web_crawler.testbench [--proxy URL] [--headed] [--suite S|E|all] [--no-screenshots]`.
- **Reuse split (important — `crawl_url` is *not* a drop-in here):**
  - **Suite E** drives the **real `crawl_url`** end-to-end — extraction correctness *is* the production path (auto-ladder + Trafilatura markdown is exactly what we want to assert).
  - **Suite S** does **not** use `crawl_url`. Two reasons: (1) `crawl_url` auto-ladders and stops at the first `SUCCESS`, so a detection site might be answered by the cheap HTTP tier when we mean to grade the **StealthyFetcher** tier; (2) `crawl_url` returns Trafilatura **markdown** (`_build_result`), but verdict parsing needs the **raw post-JS DOM** (and `window.*` objects need a live page). So Suite S drives the **individual Scrapling fetchers directly**, per tier.
  - **Avoid test-vs-prod drift:** Suite S must construct the StealthyFetcher tier from the **same centralized stealth-config builder** `03e` shipped — `build_stealthy_kwargs(get_stealth_config())` in `app/proprietary/web_crawler/stealth.py` (the single source of truth for `block_webrtc`/`hide_canvas`/`google_search`/`dns_over_https` + geoip `locale`/`timezone_id`) — **not** a hand-rolled kwargs set, otherwise the scorecard grades a browser we don't ship. The static (HTTP) tier's `impersonate="chrome"` anchor stays hardcoded in the connector (`03a` §2b); `real_chrome`/headed/persistent-profile are Slice B/C and **not** yet in the builder, so the harness exercises today's Slice-A browser.
- Outputs: console summary + screenshots + the `scorecard` snapshot.
- Runs with the app-wide proxy provider (`03b`) and `03e` levers on, so the scorecard reflects production fetch behavior — **except captcha solving, which Suite S forces OFF** (`CAPTCHA_SOLVING_ENABLED=false`): we measure the *unaided* stealth/score, and it avoids the `03d` injector firing paid solves against the reCAPTCHA-demo / FingerprintJS rows. Captcha solving is exercised separately (functional `03d` test), not in the stealth scorecard.

## The ceiling-decision loop (why this matters)

The scorecard is the evidence base for the moat strategy: re-run it (a) on a cadence and (b) whenever crawls start failing in the wild. When the **hard** rows (FingerprintJS demo, reCAPTCHA-v3 ≥0.7, and any DataDome/Kasada targets) degrade and `03e` levers can't recover them, that's the documented trigger to flip the **deferred paid-unblocker tier** (`03e §8`). Without this harness, that decision is guesswork.

## Config / dependencies

- **No new production dependencies** — reuses Scrapling (already pinned) + the crawler. Optionally a tiny dev helper for the scorecard diff (or just stdlib `json`).
- Needs **residential proxy creds** (the `03b` env) to be meaningful; document a "no-proxy" mode that still runs but is expected to fail the harder rows (datacenter IP).
- A results dir — **entirely gitignored** (run-local scorecards, `latest.json`, screenshots, dumps); kept tracked only via its `.gitignore`.

## Work items

1. **Shared `page_action`+closure-cell helper** (factored with `03d`) for JS-object verdict extraction.
2. **Suite S runners** (S1 browser, S3 TLS, S4 proxy-leak) with per-site parse + aspirational thresholds; S2 as manual debug links.
3. **Suite E runners** against the toscrape/scrapethissite sandboxes with deterministic assertions.
4. **CLI + scorecard** (snapshot writer + diff vs last baseline) mirroring `bin/cloaktest` ergonomics.
5. **Docs**: a short runbook (how to run, read the scorecard, interpret the ceiling trigger).

## Risks / trade-offs

- **Flaky/rate-limited/changing sites.** Detection sites move DOM and tighten over time; the harness must tolerate parse misses (report `ERROR`, not crash — `stealth_test.py:298–300`) and is **manual** precisely so flakiness never blocks development.
- **Proxy required for realism.** Without residential egress the hard rows fail by design (datacenter IP); document this so a red scorecard isn't misread.
- **ToS.** These are public detection/sandbox sites intended for this purpose; keep volume low and don't hammer.
- **Not a guarantee.** Passing sannysoft/CreepJS ≠ beating DataDome/Kasada; the scorecard's value is *trend + ceiling visibility*, not a green checkmark.

## Out of scope (hand-offs)

- **CI automation** — deferred (resolved: manual-only now). If revisited, it needs tolerant thresholds + proxy creds + nightly cadence; the scorecard JSON is designed to make that easy later.
- The levers themselves (`03e`), captcha solving (`03d`), proxy provider (`03b`), billing (`03c`) — this plan only **measures** them.
- The deferred paid-unblocker integration (`03e §8`) — the harness defines its *trigger*, not its build.
