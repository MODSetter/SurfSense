# Phase 3d — Captcha solving (DEFERRED — sequenced last, non-MVP-blocking)

> Part of **Phase 3 — WebURL Crawler & Crawl Billing**. See `00-umbrella-plan.md`.
> **Status: deferred.** Build only after `03a`/`03b`/`03c` ship and there's a real need. Depends on `03a` (the StealthyFetcher tier) and the per-crawl proxy from `03b`. Touches the crawl billing model from `03c`.

## Why deferred

Scrapling already solves **Cloudflare Turnstile/Interstitial** via `solve_cloudflare=True` on the StealthyFetcher tier (`03a`; `references/Scrapling/scrapling/fetchers/stealth_chrome.py:38,90`). That covers the most common interstitial. The remaining captcha types (reCAPTCHA v2/v3, hCaptcha, image) need a **paid third-party solver**, add latency (10–60s/solve), have <100% success, and carry target-ToS/legal considerations. None of that is MVP-blocking, so it's sequenced last.

## Scope boundary

| Challenge | Handled by | Where |
| --- | --- | --- |
| Cloudflare Turnstile / Interstitial | Scrapling `solve_cloudflare=True` | `03a`, StealthyFetcher tier |
| reCAPTCHA v2/v3, hCaptcha, image | **`captchatools`** (this subplan) | StealthyFetcher `page_action` |

## Grounding (libraries verified)

- **`captchatools` is itself the provider registry.** `new_harvester(api_key, solving_site, sitekey, captcha_url, captcha_type="v2"|"v3"|"hcaptcha"|"image", ...)` → `.get_token(proxy=…, proxy_type=…, user_agent=…, b64_img=…)` returns a **token string** (`references/Captcha-Tools/README.md:28–47`). `solving_site` ∈ {`capmonster`,`2captcha`,`anticaptcha`,`capsolver`,`captchaai`} (`:113–127`). Errors: `ErrNoBalance`, `ErrWrongAPIKey`, `ErrWrongSitekey`, … via `captchatools.exceptions` (`:136–155`). **Implication:** we do **not** rebuild a multi-provider class hierarchy (unlike `03b`'s proxy registry) — `captchatools` already dispatches across the 5 services. Our layer is thin: config resolution + page detection/injection glue.
- **`captchatools` only harvests a token; it does not inject it.** The caller must drop the token into the page (`g-recaptcha-response` / `h-captcha-response` textarea, or invoke the JS callback) and submit.
- **Injection requires a browser page**, so this only works on the **StealthyFetcher** tier. Scrapling exposes `page_action`: "a function that takes the `page` object, runs after navigation, and does the automation you need" (`stealth_chrome.py:30,82`). AsyncFetcher (HTTP) and DynamicFetcher cannot solve interactive captchas — a captcha hit there must escalate to StealthyFetcher.

## Sketch (when built)

1. **Config layer** (`app/utils/captcha/`, mirroring `app/utils/proxy/`'s config resolution from `03b`):
   - `CaptchaConfig` = `(enabled, solving_site, api_key)`, resolved from env defaults or per-connector config (same `resolve_*` pattern as proxy in `03b`).
   - Env: `CAPTCHA_SOLVING_ENABLED` (default FALSE), `CAPTCHA_SOLVER_PROVIDER`, `CAPTCHA_SOLVER_API_KEY`. Off by default → zero captcha attempts (and zero solver cost).
2. **Detection + injection `page_action` factory** — builds a callback passed to `StealthyFetcher.async_fetch(..., page_action=…)`:
   - Detect sitekey in DOM (`.g-recaptcha[data-sitekey]`, `.h-captcha[data-sitekey]`, reCAPTCHA-v3 via `grecaptcha.execute`).
   - Harvest: `new_harvester(solving_site, api_key, sitekey, captcha_url=page.url, captcha_type=…).get_token(proxy=<the 03b per-crawl proxy>, user_agent=<page UA>)`.
   - Inject token + dispatch events / invoke callback; submit; wait for navigation.
3. **Crawler escalation**: only the StealthyFetcher tier attempts solving; a captcha detected on a lower tier escalates to StealthyFetcher (the ladder already ends there per `03a`).
4. **Dependency**: add `captchatools` to `pyproject.toml` (build-time only).

## The billing asymmetry (the hard part — decide at build time)

`03c` bills the workspace owner **per successful crawl** (`CrawlOutcomeStatus.SUCCESS`), and absorbs proxy cost into the flat $1/1000. **Captcha is different**: the solver charges **per attempt** (~$1–3 / 1000, type-dependent) **regardless of whether the crawl ultimately succeeds**. So a failed solve = real upstream cost with **no billable success** — proxy's absorb-it model doesn't transfer cleanly.

Options (resolve when this is actually built):
- **(a) Separate per-solve charge** — meter each solve attempt as its own unit (e.g. `web_crawl_captcha` usage_type, its own `*_MICROS_PER_*` knob), independent of crawl SUCCESS. Most cost-honest; bills even on failed solves (matching the upstream charge).
- **(b) Higher crawl price when captcha enabled** — absorb into a fatter flat rate; simplest UX, but cross-subsidizes failed solves and easy-vs-hard pages unevenly.
- **(c) Cost-plus pass-through** — meter the solver's reported cost × margin.

Recommendation leaning **(a)** (separate per-attempt unit) because the upstream cost is per-attempt and significant, but defer the final call.

## Risks / considerations

- **Solver-tier only.** No captcha solving on the HTTP/DynamicFetcher tiers; must escalate to StealthyFetcher (slower, browser-backed).
- **Latency & flakiness.** Solves take 10–60s and aren't guaranteed; tune timeouts and a max-attempts cap so a single URL can't burn unbounded solver credit.
- **Solver-account balance.** `ErrNoBalance`/`ErrWrongAPIKey` (`README.md:136–155`) must surface clearly and disable solving rather than loop.
- **Proxy coherence.** Pass the **same** per-crawl proxy (`03b`) to `get_token(proxy=…)` so the solve happens from the same IP as the crawl (some captchas IP-bind the token).
- **Policy / ToS.** Automated captcha solving may violate a target site's terms; gate behind the explicit `CAPTCHA_SOLVING_ENABLED` flag and treat as an opt-in, owner-acknowledged capability.

## Out of scope

- Anything in `03a`/`03b`/`03c`.
- Cloudflare Turnstile (already handled by Scrapling in `03a`).
- Final captcha billing model — chosen at build time (see options above).
