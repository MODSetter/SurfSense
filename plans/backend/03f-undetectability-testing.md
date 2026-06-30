# Phase 3f — Undetectability & extraction test harness (manual scorecard)

> Part of **Phase 3 — WebURL Crawler & Crawl Billing**. See `00-umbrella-plan.md`.
> **Status: ACTIVE, sequenced last in Phase 3** (after `03a`–`03e` ship — the harness measures what those built). **Manual-only** — no CI/automated gating for now (resolved decision); it's a dev-run scorecard, not a build gate. Depends on `03a` (the Scrapling tiers + `FetchStrategy`/`CrawlOutcome`), `03b` (proxy provider), `03e` (the stealth levers being tested), and reuses the `page_action` + closure-cell mechanism shared with `03d`.

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
- **Internal JS-object verdicts** (CreepJS `window.Fingerprint`, Castle.js score node) → a **`page_action`** that runs `page.evaluate()` and stashes the result into a **closure cell**, because Scrapling **discards `page_action`'s return value** (sync `_stealth.py:260`, async `:536`). **This is the exact same `page_action`+closure-cell plumbing as `03d`'s token injector** — building the harness de-risks `03d` (and vice-versa); factor it once.

## Suite S — Stealth / anti-bot

### S1. Browser tier (StealthyFetcher — the "undetectable" tier)

| Site | Signal | Extraction | Aspirational bar |
|---|---|---|---|
| `bot.sannysoft.com` | webdriver/chrome/plugins/UA leaks | DOM table | 0 fails |
| `bot.incolumitas.com` | 30+ checks incl. behavioral | JSON-in-body | ≤ `{WEBDRIVER, connectionRTT}` |
| `browserscan.net/bot-detection` | WebDriver/CDP/Navigator | DOM text | 0 Abnormal |
| `deviceandbrowserinfo.com/are_you_a_bot` | fingerprint + behavioral | JSON `isBot` | `isBot=false` |
| `abrahamjuliot.github.io/creepjs` | fingerprint **consistency/lies**, headless% | `window.Fingerprint` (page_action) | headless ≤30%, stealth ≤30% |
| `fingerprint-scan.com` | Castle.js bot-risk + headless signals | DOM node + evaluate | low risk; headless signals 0 |
| `demo.fingerprint.com/web-scraping` | **behavioral block** (click→blocked vs flights) | page_action click + DOM | not blocked |
| `recaptcha-demo.appspot.com/...v3-request-scores.php` | Google server-verified human score | `wait_for_function` + regex (`recaptcha_score.py:22–28`) | score ≥0.7 |

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

## Scorecard & thresholds (resolved)

- **Adopt CloakBrowser's bars as aspirational targets** (above), but the harness's primary output is **our actual measured numbers recorded as the baseline** — a committed `scorecard.md`/JSON snapshot per run (date, tier, proxy on/off, headed/headless, per-site result). Subsequent runs diff against the last baseline so we see drift (ours improving, or a WAF tightening).
- Each row reports: site, tier, verdict, numeric (where applicable), PASS/FAIL vs aspirational bar, and screenshot path.
- A run is summarized as `passed/total` per suite (like `stealth_test.py:314–317`), **never blocking** anything.

## Harness design

- Lives under dev tooling (e.g. `surfsense_backend/scripts/crawler_testbench/` or `tests/manual/` — not collected by the normal pytest run, since it hits the live internet + needs proxies). A thin CLI mirrors `bin/cloaktest`: `python -m ... [--proxy URL] [--headed] [--headless] [--suite S|E|all] [--no-screenshots]`.
- **Reuse split (important — `crawl_url` is *not* a drop-in here):**
  - **Suite E** drives the **real `crawl_url`** end-to-end — extraction correctness *is* the production path (auto-ladder + Trafilatura markdown is exactly what we want to assert).
  - **Suite S** does **not** use `crawl_url`. Two reasons: (1) `crawl_url` auto-ladders and stops at the first `SUCCESS`, so a detection site might be answered by the cheap HTTP tier when we mean to grade the **StealthyFetcher** tier; (2) `crawl_url` returns Trafilatura **markdown** (`_build_result`), but verdict parsing needs the **raw post-JS DOM** (and `window.*` objects need a live page). So Suite S drives the **individual Scrapling fetchers directly**, per tier.
  - **Avoid test-vs-prod drift:** Suite S must construct each fetcher from the **same centralized stealth-config builder** `03e` introduces (the single source of truth for `locale`/`timezone_id`/`hide_canvas`/`block_webrtc`/`impersonate`/profile/headed), **not** a hand-rolled kwargs set — otherwise the scorecard grades a browser we don't ship. (`03e` work item: expose that builder so both the crawler and this harness import it.)
- Outputs: console summary + screenshots + the `scorecard` snapshot.
- Runs with the app-wide proxy provider (`03b`) and `03e` levers on, so the scorecard reflects production fetch behavior — **except captcha solving, which Suite S forces OFF** (`CAPTCHA_SOLVING_ENABLED=false`): we measure the *unaided* stealth/score, and it avoids the `03d` injector firing paid solves against the reCAPTCHA-demo / FingerprintJS rows. Captcha solving is exercised separately (functional `03d` test), not in the stealth scorecard.

## The ceiling-decision loop (why this matters)

The scorecard is the evidence base for the moat strategy: re-run it (a) on a cadence and (b) whenever crawls start failing in the wild. When the **hard** rows (FingerprintJS demo, reCAPTCHA-v3 ≥0.7, and any DataDome/Kasada targets) degrade and `03e` levers can't recover them, that's the documented trigger to flip the **deferred paid-unblocker `FetchStrategy`** (`03e §8`). Without this harness, that decision is guesswork.

## Config / dependencies

- **No new production dependencies** — reuses Scrapling (already pinned) + the crawler. Optionally a tiny dev helper for the scorecard diff (or just stdlib `json`).
- Needs **residential proxy creds** (the `03b` env) to be meaningful; document a "no-proxy" mode that still runs but is expected to fail the harder rows (datacenter IP).
- A results dir (gitignored screenshots; committed `scorecard` snapshots).

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
