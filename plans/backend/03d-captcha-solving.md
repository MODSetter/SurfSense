# Phase 3d — Captcha solving (reCAPTCHA / hCaptcha / image)

> Part of **Phase 3 — WebURL Crawler & Crawl Billing**. See `00-umbrella-plan.md`.
> **Status: ACTIVE (sequenced last in Phase 3).** No longer deferred — captcha bypass is now an explicit goal of the "undetectable, captcha-bypassing universal WebURL crawler." Build **after** `03a` (StealthyFetcher tier + `FetchStrategy` seam + `CrawlOutcome`), `03b` (app-wide proxy provider, accessed via the zero-arg `get_proxy_url()`), `03c` (crawl wallet), and `03e` (stealth-hardening — solving is the *last* resort once humanization + fingerprint coherence have minimized challenges).
> **Decision recap (this pass):** Cloudflare stays in-framework (free, `03a`); reCAPTCHA/hCaptcha/image use a **paid** solver via `captchatools`, **opt-in + off by default**, and are billed as a **separate per-attempt unit** (option (a) below — now decided, not deferred). Logged-in/account-gated captcha flows are **out of scope** (no authenticated scraping in this MVP — see umbrella Phase 8 / `03b` static-proxy hand-off).

## Why this is the last tier, not the first

A solve is the **most expensive and least reliable** move available (paid per attempt, 10–60 s latency, <100% success, ToS-sensitive). So the crawler must exhaust the cheaper, in-house levers first; captcha solving only fires when everything else has already failed:

1. `03e` humanization + fingerprint coherence (geoip locale/tz, persistent profile, headed/Xvfb) → **avoid** triggering a challenge at all.
2. `03a` `solve_cloudflare=True` on StealthyFetcher → free Cloudflare Turnstile/Interstitial.
3. **This subplan** → only the residual reCAPTCHA v2/v3 + hCaptcha + image challenges, and only when `CAPTCHA_SOLVING_ENABLED`.

## Scope boundary

| Challenge | Handled by | Where |
| --- | --- | --- |
| Cloudflare Turnstile / Interstitial | Scrapling `solve_cloudflare=True` | `03a`, StealthyFetcher tier |
| reCAPTCHA v2/v3, hCaptcha, image | **`captchatools`** (this subplan) | StealthyFetcher `page_action` |
| DataDome / Kasada / reCAPTCHA-**Enterprise** | **none in the free stack** | deferred paid-unblocker tier (`03e`) |

## Grounding (libraries verified)

- **`captchatools` is itself the provider registry.** `new_harvester(api_key, solving_site, sitekey, captcha_url, captcha_type="v2"|"v3"|"hcaptcha"|"image", invisible_captcha=…, min_score=…, action=…)` → `.get_token(proxy=…, proxy_type=…, user_agent=…, b64_img=…)` returns a **token string** (`references/Captcha-Tools/README.md:28–47`). `solving_site` ∈ {`capmonster`,`2captcha`,`anticaptcha`,`capsolver`,`captchaai`} (`:113–127`). Errors: `ErrNoBalance`, `ErrWrongAPIKey`, `ErrWrongSitekey`, `ErrIncorrectCapType`, `ErrNoHarvester` via `captchatools.exceptions` (`:136–155`). **Implication:** we do **not** rebuild a multi-provider class hierarchy (unlike `03b`'s proxy registry) — `captchatools` already dispatches across the 5 services. Our layer is thin: config resolution + page detection/injection glue + billing.
- **`captchatools` only harvests a token; it does not inject it.** The caller must drop the token into the page (`g-recaptcha-response` / `h-captcha-response` textarea, or invoke the JS callback) and submit.
- **Injection requires a live browser page**, so this only works on the **StealthyFetcher** tier. Scrapling exposes `page_action`: "a function that takes the `page` object, runs after navigation, and does the automation you need" (`references/Scrapling/scrapling/fetchers/stealth_chrome.py:30,82`; engine docstrings `_browsers/_stealth.py:50,191,326,466`). The HTTP (`AsyncFetcher`) and `DynamicFetcher` tiers cannot solve interactive captchas — a captcha hit there must **escalate to StealthyFetcher** (`FetchStrategy` seam from `03a`; the ladder already ends there).
- **Ordering is already correct in Scrapling.** `solve_cloudflare` runs **before** `page_action` (sync `_stealth.py:253–254` then `:258–260`; async `:529–530` then `:534–536`). So Cloudflare is cleared first, *then* our injector runs — exactly the tier order we want. `page_action` exceptions are caught + logged by Scrapling (`:262` / `:538`), so our factory must also return a clear signal (it can't rely on raising to abort the fetch).

## Target design

### 1. Config layer (`app/utils/captcha/`, mirroring `app/utils/proxy/` from `03b`)

- `CaptchaConfig = (enabled, solving_site, api_key, captcha_type_default, min_score, max_attempts, timeout_s)`, resolved from **env only** — one app-wide config, mirroring `03b`'s env-only single-provider model (`get_active_provider()`); **no per-connector config** (that path was dropped in `03b`).
- Env knobs (next to the proxy + crawl-billing knobs in `config/__init__.py`):
  - `CAPTCHA_SOLVING_ENABLED` (default `FALSE`) — off ⇒ zero solve attempts and zero solver cost.
  - `CAPTCHA_SOLVER_PROVIDER` (e.g. `capsolver`), `CAPTCHA_SOLVER_API_KEY`.
  - `CAPTCHA_MAX_ATTEMPTS_PER_URL` (default `1`), `CAPTCHA_SOLVE_TIMEOUT_S` (default `120`).
- A `captcha_enabled()` static (mirrors `WebCrawlCreditService.billing_enabled()`) so callers gate cheaply before constructing anything.

### 2. Detection + injection `page_action` factory

Builds the **sync** callable passed to `StealthyFetcher.fetch(..., page_action=…)` (03a runs StealthyFetcher via `asyncio.to_thread`, so the sync engine path `_stealth.py:258–262` applies — the factory returns a plain `def(page): ...`, not a coroutine):

1. **Detect** the challenge + sitekey in the DOM:
   - reCAPTCHA v2: `.g-recaptcha[data-sitekey]` (or iframe `src*="recaptcha"`).
   - hCaptcha: `.h-captcha[data-sitekey]` (or iframe `src*="hcaptcha"`).
   - reCAPTCHA v3: presence of `grecaptcha.execute` + a known `action` (config/site-mapped).
   - If no sitekey found → **no-op return** (nothing to solve; let `wait_selector`/extraction proceed).
2. **Bind the proxy/UA** (the IP-coherence caveat below): harvest with the **exact endpoint used for this crawl tier** —
   `new_harvester(solving_site, api_key, sitekey, captcha_url=page.url, captcha_type=…, min_score=…, action=…).get_token(proxy=<this crawl's endpoint, reformatted ip:port:user:pass>, proxy_type="HTTP", user_agent=<page UA>)` (`README.md:44–46,107–110`).
3. **Inject + submit**: set the response token into `g-recaptcha-response` / `h-captcha-response` (make textarea visible if needed), dispatch `input`/`change`, invoke the JS callback when present (`grecaptcha.getResponse` flows / `___grecaptcha_cfg` callbacks), then submit the form and `page.wait_for_load_state`. For v3 (no widget) the token is consumed by the site's own `execute()` flow.
4. **Signal outcome** via a mutable closure cell (since Scrapling swallows `page_action` exceptions at `:262` **and discards its return value** at `:260`/`:536`): record `solved: bool` + `attempts: int` into a captured `dict` the crawler reads after `fetch()` returns, so billing (§4) and the retry cap can act on it. **This `page_action`+closure-cell helper is shared with `03f`'s test harness** (which uses the same mechanism to read JS-object verdicts like CreepJS `window.Fingerprint`) — factor it once.

### 3. Crawler escalation (uses the `03a` `FetchStrategy` seam)

- Only the **StealthyFetcher** strategy attempts solving. A captcha detected on a lower tier (HTTP/DynamicFetcher) returns non-`SUCCESS`, and the ladder already escalates to StealthyFetcher (`03a`), which this time is constructed with the captcha `page_action` when `captcha_enabled()`.
- **Attempt cap:** at most `CAPTCHA_MAX_ATTEMPTS_PER_URL` solves per URL so one hostile page can't burn unbounded solver credit. The closure cell's `attempts` enforces it.
- No new caller *contract*: the strategy still returns `CrawlOutcome` (`03a` invariant). Captcha is a *parameterization* of the last tier, not a new return shape.
- **But billing needs the attempt count to escape the closure cell.** §4 charges per attempt on **both** the indexer and chat paths, so the count can't stay buried inside `page_action`'s closure — the crawler must copy it onto the outcome. Add **`captcha_attempts: int = 0`** (and `captcha_solved: bool = False`) as **dataclass fields on `CrawlOutcome`** (`03a`). This is safe: `03a`'s "don't widen the return" rule is about the *indexer's* positional `(total_processed, error)` tuple unpacked by length, **not** about `crawl_url`'s dataclass — adding fields to a dataclass breaks no consumer. The indexer sums `outcome.captcha_attempts`; the chat tool reads it off the same outcome.

### 4. Billing — separate per-attempt unit (option (a), DECIDED)

`03c` bills per **successful crawl** (`CrawlOutcomeStatus.SUCCESS`) and absorbs proxy cost into the flat $1/1000. **Captcha can't ride that model**: the solver charges **per attempt regardless of whether the crawl ultimately succeeds**, so a failed solve = real upstream cost with no billable crawl success. We therefore meter solves **independently**:

- New static on `WebCrawlCreditService` (defined in `03c`, knobs added here): `captcha_solves_to_micros(n) = n * config.WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE`.
- Each **attempt** (not each success) is charged when `CAPTCHA_SOLVING_ENABLED` **and** `WEB_CRAWL_CAPTCHA_BILLING_ENABLED`:
  - **Indexer/pipeline path:** after the crawl loop, debit `captcha_solves_to_micros(total_attempts)` — where `total_attempts = Σ outcome.captcha_attempts` over the batch — from the **workspace owner** (same owner resolution as `03c §2`) and `record_token_usage(usage_type="web_crawl_captcha", …, cost_micros=…, call_details={"attempts": n, "solved": k})`. Added before the charge commit, same one-transaction pattern as `03c`.
  - **Chat-scrape path:** fold `captcha_solves_to_micros(outcome.captcha_attempts)` into the turn accumulator with `call_kind="web_crawl_captcha"` (same mechanism as `03c §3`), so it settles with the premium turn; non-premium/anonymous turns record-but-don't-debit.
- **No pre-block on solves** (unlike the crawl batch): attempts are bounded by `CAPTCHA_MAX_ATTEMPTS_PER_URL × len(urls)`, an upper bound the indexer can optionally pre-check against the wallet if we want symmetry with `03c §2` (recommended: pre-check the combined crawl + worst-case captcha estimate so a run can't strand mid-batch on solver insolvency).
- New env (next to `03c`'s knobs): `WEB_CRAWL_CAPTCHA_BILLING_ENABLED` (default `FALSE`), `WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE` (default e.g. `3000` = $3/1000 attempts; type-dependent, set with margin over the solver's per-attempt price). **No DB migration** — `web_crawl_captcha` is just another free-form `TokenUsage.usage_type` value (`db.py` `usage_type String(50)`).

### 5. Dependency + Docker

- Add `captchatools` to `pyproject.toml` (build-time only). It's a thin HTTP client for the solver services — no browser binaries.
- No `Dockerfile` change beyond the dependency (browser already installed by `03a`/`03e`).

## Error handling (must not loop or silently burn credit)

- `ErrNoBalance` / `ErrWrongAPIKey` (`README.md:134,136–143`) → **stop solving for the rest of the run** (set a process/run flag), surface a clear "captcha solver out of balance / misconfigured" message via `log_task_failure`, and fall through to a non-`SUCCESS` `CrawlOutcome`. The README explicitly warns balance-exhausted loops can get the **IP temporarily banned** (`:132–134`) — never retry on `ErrNoBalance`.
- `ErrWrongSitekey` / `ErrIncorrectCapType` → log + skip this URL's solve (likely detection bug, not transient); count the attempt for billing only if the solver actually charged.
- Timeout (`CAPTCHA_SOLVE_TIMEOUT_S`) → abort the solve, count one attempt, return non-`SUCCESS`.

## Risks / considerations

- **Solver-tier only.** No captcha solving on the HTTP/DynamicFetcher tiers; must escalate to StealthyFetcher (slower, browser-backed).
- **Latency & flakiness.** Solves take 10–60 s and aren't guaranteed; the `CAPTCHA_MAX_ATTEMPTS_PER_URL` + `CAPTCHA_SOLVE_TIMEOUT_S` caps keep a single URL from burning unbounded solver credit.
- **Proxy coherence (rotating-pool caveat).** Many captchas IP-bind the token, so the solver must egress from the **same IP** as the crawl. Under `03b`'s single app-wide provider this is automatic for single-endpoint providers (`anonymous_proxies`, single-URL `custom`). But a **pool-backed `CustomProxyProvider`** returns the *next* endpoint on each zero-arg `get_proxy_url()` call — so the `page_action` must **reuse the endpoint actually used for this crawl tier** (the crawler captures it once and passes it into the factory), NOT call `get_proxy_url()` again (which would rotate to a different IP). This is the same "surface the chosen endpoint" seam `03e`/`03d` both rely on — build it once in `03a`'s strategy context.
- **Enterprise captchas are out of reach.** reCAPTCHA **Enterprise**, DataDome, and Kasada use behavioral + device signals the token-injection model doesn't satisfy reliably; those route to the deferred paid-unblocker tier (`03e`), not here.
- **Policy / ToS.** Automated captcha solving may violate a target site's terms; gate behind the explicit `CAPTCHA_SOLVING_ENABLED` flag and treat as an opt-in, owner-acknowledged capability. Public data only (no logged-in bypass).

## Work items

1. **`app/utils/captcha/`**: `CaptchaConfig` + env resolution + `captcha_enabled()` static.
2. **`page_action` factory**: detection (v2/v3/hcaptcha/image sitekey), harvest via `captchatools` with bound proxy/UA, inject+submit, outcome closure cell.
3. **Crawler wiring**: construct StealthyFetcher with the factory when `captcha_enabled()`; enforce per-URL attempt cap; surface the crawl's chosen proxy endpoint into the factory.
4. **Billing**: `WebCrawlCreditService.captcha_solves_to_micros` + the two knobs; debit per-attempt on the indexer path (owner) and fold into the turn on the chat path; `record_token_usage(usage_type="web_crawl_captcha")`.
5. **Config + docs**: all env knobs in `Config` + `.env.example` (commented, hosted=TRUE / self-hosted=FALSE), plus the `captchatools` dependency.
6. **Tests**: solving disabled → zero attempts, zero solver cost (self-hosted); v2 detected → harvest+inject+submit path invoked with the **crawl's** proxy endpoint (not a re-rotated one); `ErrNoBalance` → stops solving + no retry loop; attempt cap honored; billing enabled → per-attempt debit even when the crawl ultimately fails; chat path folds captcha micros into a premium turn and record-only on anonymous; `web_crawl_captcha` `TokenUsage` rows written.

## Out of scope

- Anything owned by `03a`/`03b`/`03c`/`03e`.
- Cloudflare Turnstile (already handled by Scrapling in `03a`).
- Logged-in / account-gated captcha flows (no authenticated scraping this MVP → umbrella Phase 8 + `03b` static-proxy hand-off).
- Enterprise/behavioral anti-bot (DataDome/Kasada/reCAPTCHA-Enterprise) → deferred paid-unblocker tier (`03e`).
