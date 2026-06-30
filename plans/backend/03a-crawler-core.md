# Phase 3a — WebURL Crawler core (Scrapling-only) + success semantics

> Part of **Phase 3 — WebURL Crawler & Crawl Billing**. See `00-umbrella-plan.md`.
> Sibling subplans: `03b-proxy-expansion.md`, `03c-crawl-billing.md`, `03e-stealth-hardening.md`, `03d-captcha-solving.md`, `03f-undetectability-testing.md` (manual scorecard).

> **Implementation note (applies to all Phase-3 plans).** Phases 1–2 are **SHIPPED** (2026-06-27) — `SearchSpace`→`Workspace` and `search_space_id`→`workspace_id` are renamed everywhere, so the **live code already says `workspace_*`**. Where citations below use the **old** `search_space_*`/`SearchSpace` names (written pre-rename), substitute the `workspace_*` equivalent and **grep the new name** (grepping the old name now returns nothing). Apply every edit by **symbol/grep** (e.g. `firecrawl_api_key`, `crawl_url`, `FIRECRAWL_API_KEY`), **not** by the absolute line numbers cited here — the rename (and `03a`'s own Firecrawl removal) shifted them.

> **Status: ✅ IMPLEMENTED (local on `ci_mvp`, uncommitted).** All 5 work items done: Firecrawl removed repo-wide, `crawl_url` is the 3-tier Scrapling ladder returning `CrawlOutcome` (`impersonate="chrome"` on the static tier + `solve_cloudflare=True` on the stealthy tier), `crawls_succeeded` added to the indexer (positional return unchanged — surfaced in task metadata), both `scrape_webpage` tools updated, unit tests added/passing. Crawler relocated to `app/proprietary/web_crawler/connector.py` under the non-Apache-2 boundary (see umbrella decisions log + `app/proprietary/README.md`).

## Objective

Make the Universal WebURL Crawler a **single-framework (Scrapling) component** with deterministic per-URL outcome semantics and a clean, explicit **"successful crawl" signal** that Phase 3c bills on.

Two hard requirements from the decisions log:

1. **Remove Firecrawl entirely.** No other scraping framework now or planned. Scrapling's `StealthyFetcher` can bypass Cloudflare Turnstile when invoked with `solve_cloudflare=True` (see tier design below); captcha-tools (`03d`) covers reCAPTCHA/hCaptcha, and `03e` adds the broader stealth-hardening that makes the crawler "undetectable" as far as free tooling reaches.
2. **One billable unit = one URL that yields usable extracted content**, regardless of how many internal fallback tiers ran. `03a` must expose that signal; `03c` meters it.

This subplan does NOT touch proxy rotation (→ `03b`), credit metering (→ `03c`), or captcha (→ `03d`).

## Current state (cited)

### The crawler

> **Post-implementation note (location moved).** 03a is implemented. The crawler now lives at `app/proprietary/web_crawler/connector.py` (public API re-exported from `app/proprietary/web_crawler/__init__.py`), under the non-Apache-2 license boundary `app/proprietary/` (see `app/proprietary/README.md` + `LICENSE`). Importers use `from app.proprietary.web_crawler import WebCrawlerConnector, CrawlOutcomeStatus`. The file:line references below describe the *original* `app/connectors/webcrawler_connector.py` surface that 03a refactored away (kept for historical context).

`app/connectors/webcrawler_connector.py` — `WebCrawlerConnector.crawl_url()` is a 4-tier fallback ladder:

1. **Firecrawl** (premium, if `firecrawl_api_key` set) — `_crawl_with_firecrawl()` (lines 89–100, 223–272), imports `from firecrawl import AsyncFirecrawlApp` (line 22).
2. Scrapling `AsyncFetcher` (static HTTP, curl_cffi) — `_crawl_with_async_fetcher()` (lines 274–310).
3. Scrapling `DynamicFetcher` (browser, run in a thread) — `_crawl_with_dynamic()` (lines 312–339).
4. Scrapling `StealthyFetcher` (patchright-Chromium anti-bot, run in a thread) — `_crawl_with_stealthy()` (lines 341–369).

> **Engine note (do not say "Camoufox").** As of the pinned `scrapling[fetchers]>=0.4.9` (`pyproject.toml:91`), `StealthyFetcher` is **"completely stealthy built on top of Chromium"** (`references/Scrapling/scrapling/fetchers/stealth_chrome.py:8`) driven by **patchright** (`references/Scrapling/scrapling/engines/_browsers/_stealth.py:8–9`), **not** Camoufox — Scrapling removed Camoufox (zero matches in the 0.4.9 tree; `uv.lock` carries `patchright`, no `camoufox`). The default Playwright `channel` is `"chromium"` (patchright), or `"chrome"` when `real_chrome=True` (`_browsers/_base.py:469`). Stealth = the compiled-in flag set `DEFAULT_ARGS + STEALTH_ARGS` (`engines/constants.py:24–99`, incl. `--disable-blink-features=AutomationControlled` `:94`) + a persistent context by default (`_stealth.py:90–93`) — this is **runtime/config-level** stealth, which sets the realistic ceiling (see `03e`).
>
> **Scrub the in-code "Camoufox" mentions too.** The connector still carries stale Camoufox wording in its own docstrings — the module header tier list (`webcrawler_connector.py:10–12`) and `_crawl_with_stealthy`'s docstring (`:343` "StealthyFetcher (Camoufox)"). Fix these in the 03a refactor so the code matches reality (patchright-Chromium).

Extraction is Trafilatura HTML→markdown in `_build_result()` (lines 371–469). Every Scrapling tier passes `proxy=get_proxy_url()` (lines 287, 329, 359). `crawl_url()` returns a tuple `(result_dict | None, error | None)`; `result_dict` has `content` / `metadata` / `crawler_type`.

### The two call sites

- **Type-1 indexer (billable path):** `app/tasks/connector_indexers/webcrawler_indexer.py` reads `FIRECRAWL_API_KEY` from connector config (line 115), builds `WebCrawlerConnector(firecrawl_api_key=api_key)` (line 139), and calls `crawler.crawl_url(url)` per URL (line 297). It already tracks `documents_indexed` / `documents_updated` / `documents_skipped` / `documents_failed` / `duplicate_content_count` (lines 167–171), but **none of these is a clean "crawl succeeded" count** — duplicates and unchanged docs are bucketed as skipped even though a successful fetch happened.
- **Chat scrape tool (ad-hoc):** `main_agent/tools/scrape_webpage.py` (line 232) and `subagents/builtins/research/tools/scrape_webpage.py` (line 226) build `WebCrawlerConnector(firecrawl_api_key=...)` and call `crawl_url(url, formats=["markdown"])`. The `formats` arg is Firecrawl-only (declared at `crawl_url` signature line 59; docstring line 72: "only for Firecrawl").

### Firecrawl threading (the cross-cutting surface)

Firecrawl's API key is plumbed end-to-end and must be removed everywhere:

| Layer | File:line | What to remove |
|-------|-----------|----------------|
| Crawler | `app/connectors/webcrawler_connector.py` | `firecrawl` import (22), `firecrawl_api_key`/`use_firecrawl` ctor (36–46), `set_api_key()` (48–56), tier-1 block (89–100), `_crawl_with_firecrawl()` (223–272), `formats` param + Firecrawl mentions in docstrings |
| Dependency | `pyproject.toml:45` | `"firecrawl-py>=4.9.0"` (+ regenerate `uv.lock`). Scrapling stays (`pyproject.toml:91` → `"scrapling[fetchers]>=0.4.9"`) |
| Connector config | `app/utils/validators.py` | `FIRECRAWL_API_KEY` from `WEBCRAWLER_CONNECTOR.optional`/`validators` (573–580); delete `validate_firecrawl_api_key_format()` (472–478) |
| Indexer | `app/tasks/connector_indexers/webcrawler_indexer.py` | `api_key = connector.config.get("FIRECRAWL_API_KEY")` (115), `use_firecrawl` log field (135), pass-through to ctor (139) |
| Chat setup | `app/tasks/chat/streaming/flows/shared/pre_stream_setup.py` | `setup_connector_and_firecrawl()` returns `firecrawl_api_key` (1–30) — collapse to connector-service-only |
| Chat orchestrators | `new_chat/orchestrator.py` (86, 378, 412, 665), `resume_chat/orchestrator.py` (65, 317, 347, 483) | `firecrawl_api_key` threading |
| Automations | `automations/actions/builtin/agent_task/dependencies.py` (19, 34, 85, 103), `.../invoke.py` (174) | `firecrawl_api_key` dep field |
| Main agent | `main_agent/runtime/factory.py` (71, 142), `main_agent/tools/registry.py` (36) | `firecrawl_api_key` param/wiring |
| Scrape tools | `main_agent/tools/scrape_webpage.py` (170, 232), `research/tools/scrape_webpage.py` (164, 226), `research/tools/index.py` (28) | `firecrawl_api_key` factory arg + ctor arg |
| Tests | `tests/unit/automations/actions/builtin/agent_task/test_dependencies.py` (44, 81) | `firecrawl_api_key == "fc-key"` assertion + fake |

> **Not a global env var.** `FIRECRAWL_API_KEY` is **not** in `.env.example` and there is no `Config.FIRECRAWL_API_KEY`. It lives only inside each WebCrawler connector's `config` JSON — the validator reads it from that dict (`validators.py:474`). So removal is code-only; **no env/docs change**. Existing `WEBCRAWLER_CONNECTOR` rows may still carry a now-dead `FIRECRAWL_API_KEY` key in `config` — harmless (it's simply ignored), optionally scrubbed by a tiny data migration if we want clean rows.
>
> **Signature change, not just deletions.** Removing `firecrawl_api_key` mutates the `RuntimeDeps`-style dataclass (`agent_task/dependencies.py:34`) and the agent runtime factory/tool factories — a coordinated signature change across the chat + automations call graph, so land it atomically.

### Runtime/deps already in place

- `Dockerfile:112–115` runs `RUN scrapling install`; the `scrapling[fetchers]` extra pulls playwright/patchright. **No new install step needed** once Firecrawl is gone. *(Accuracy fix: the Dockerfile comment says "patchright Chromium + Camoufox", but `scrapling install` in 0.4.9 only fetches Chromium — `references/Scrapling/scrapling/cli.py:122,131` runs `playwright install chromium` + `install-deps chromium`, no Camoufox. Drop the stale "+ Camoufox" wording from the comment when touching this file. `03e` may add `install-deps` extras for fonts/Xvfb.)*
- Proxy is read via `app/utils/proxy/get_proxy_url()` (`__init__.py:13`), backed by the `PROXY_PROVIDER` registry (`config/__init__.py:983`). `03a` leaves this single-URL model untouched (rotation is `03b`).

## Target design

### Tier ladder (Scrapling-only)

`crawl_url()` becomes a 3-tier ladder, preserving the existing thread-offload + `NotImplementedError` handling for the browser tiers (Windows `SelectorEventLoop` cannot spawn subprocesses — lines 134–141, 161–168):

1. `AsyncFetcher.get(...)` — fast static HTTP. **TLS gap to close:** the current call passes `stealthy_headers=True` but **not** `impersonate` (`webcrawler_connector.py:284–289`), so its TLS ClientHello is curl_cffi's *default* JA3 — trivially bot-flagged and incoherent with the browser tiers' UA. Add an `impersonate="chrome"` profile here (Scrapling's static engine accepts it — `references/Scrapling/scrapling/engines/static.py:36–47`). Tracked as a lever in `03e §2b` and validated by `03f §S3`.
2. `DynamicFetcher.fetch(...)` — full browser (via `asyncio.to_thread`).
3. `StealthyFetcher.fetch(...)` — patchright-Chromium anti-bot, last resort. Enable Cloudflare solving here by passing **`solve_cloudflare=True`** — a documented `StealthyFetcher.fetch` kwarg ("Solves all types of the Cloudflare's Turnstile/Interstitial challenges before returning the response", `references/Scrapling/scrapling/fetchers/stealth_chrome.py:38`; it's a `StealthSession` TypedDict key passed via `**kwargs`). The current stealthy call (connector lines 354–360) passes `headless`/`network_idle`/`block_ads`/`proxy` but **not** `solve_cloudflare`, so this is a real behavior add. (Note: `solve_cloudflare` runs the full browser challenge loop, so it's correctly scoped to the last-resort tier only.)

Trafilatura extraction (`_build_result`) and `format_to_structured_document()` are unchanged.

### Explicit outcome model

Replace the implicit `(dict|None, str|None)` contract with an explicit outcome so callers (indexer, chat tool, and `03c` metering) agree on what "success" means. Proposed:

```python
class CrawlOutcomeStatus(str, Enum):
    SUCCESS = "success"   # a tier returned usable extracted content
    EMPTY   = "empty"     # fetched, but no usable content after ALL tiers
    FAILED  = "failed"    # invalid URL or every tier errored
```

`crawl_url()` returns a small dataclass `CrawlOutcome(status, result, error, tier)` — **commit to the dataclass** (not a tuple): `03c` keys billing off `status == SUCCESS`, and Phase 6's fetch-only path (`06-pipelines-exec.md`) consumes `outcome.status` / `outcome.result` / `outcome.error` as attributes, so a tuple form would break that consumer. The **billable success predicate is single-sourced**: `status == CrawlOutcomeStatus.SUCCESS`. Picking a dataclass (over a tuple) also leaves room for later subplans to **append fields without breaking callers** — `03d` adds `captcha_attempts` / `captcha_solved` for per-attempt billing, and `03e`'s block classifier can attach a `block_type`. (This is distinct from the indexer's positional return, which must stay 2-tuple — see the wrapper note below.)

| Outcome | When | Billable (`03c`)? | Document status (indexer) |
|---------|------|-------------------|---------------------------|
| `SUCCESS` | a tier extracted usable content (`_build_result` returned a dict) | **Yes — 1 unit** | `ready` (or unchanged/duplicate, see note) |
| `EMPTY` | every tier was reached but none produced usable extracted content (the static tier also treats HTTP ≥ 400 as a miss and falls through — connector lines 292–301; the browser tiers attempt extraction regardless of status) | No | `failed("No content extracted")` |
| `FAILED` | invalid URL, or all tiers raised | No | `failed(<error>)` |

**Billing-policy note for `03c`:** success is the *crawl* succeeding (we fetched + extracted), independent of downstream KB dedupe. The indexer currently marks unchanged content as `skipped` (`webcrawler_indexer.py:341–347`) and cross-connector duplicates as `failed` (`:350–369`) — those still represent a **successful crawl** and should bill. `03c` must count `CrawlOutcomeStatus.SUCCESS`, not `documents_indexed`. Flagging here; final call lives in `03c`.

### Extensibility seam (the tier ladder is a strategy chain)

The 3-tier ladder is the first instance of a deliberate **`FetchStrategy` seam**: an *ordered list of strategies*, each `(url, ctx) -> CrawlOutcome`, tried in order until one returns `SUCCESS`. `crawl_url()` owns the chain; **every caller depends only on `CrawlOutcome`, never on which strategy produced it** (the indexer, the chat tool, and `03c` metering already do — keep that invariant sacred). This is what lets the moat grow without rework:

- `03d` (captcha) attaches by escalating to the StealthyFetcher strategy with a `page_action` token-injector — a *parameterization* of the last tier, not a new caller contract.
- `03e` (stealth-hardening) tunes/adds strategies (humanize, headed/Xvfb, persistent profiles, fingerprint flags) **behind the same return type**.
- A future **paid-unblocker tier** (deferred — see `03e`) is just one more strategy appended last, flippable by config; no caller changes.
- Future **platform actors** (Phase 8) reuse the same fetch strategies under their own structured extractors.

MVP scope here is only the 3 Scrapling tiers + the `CrawlOutcome` contract; the seam is a design constraint (keep tiers pluggable + callers outcome-only), **not** a call for a heavyweight Strategy framework now.

### Success counter for the indexer

Add an explicit `crawls_succeeded` counter in `index_crawled_urls()` incremented whenever `crawl_url` returns `SUCCESS` (right after line 297's call, before the dedupe/unchanged branches), and surface it in the task-success metadata (lines 455–466). `03c` meters against this **in-function** counter (it charges inside the indexer — the count does not need to escape via the return).

> **Do NOT widen the positional return tuple.** The shared `_run_indexing_with_notifications` wrapper unpacks every indexer's return **by length** (`search_source_connectors_routes.py:1499–1507`: `if len(result) == 3: a,b,c = result else: a,b = result`) — a 3-tuple would mislabel `crawls_succeeded` as `documents_skipped`, a 4-tuple would raise `ValueError`. Keep the existing `(total_processed, error)` shape. **Phase 6** (`06-pipelines-exec.md`) later exposes `crawls_succeeded`/`documents_indexed`/`crawls_attempted` to the pipeline run engine via an optional `stats` **out-param** (plus `folder_id`/`urls`/`bill`), not via the return — so `03a` only needs the counter + metadata here.

### Chat scrape tool

Drop the Firecrawl-only `formats=["markdown"]` arg (markdown is already the Trafilatura default). The tool keeps returning its asset dict; map the new outcome onto the existing `error` / `content` shape (lines 235–269) with no behavioral change for the agent.

## Work items

1. **Rip out Firecrawl** across the surface table above (crawler, dep, validators, indexer, chat plumbing, automations, tests) — code-only, no env/docs change.
2. **Refactor `crawl_url`** to the 3-tier Scrapling ladder + explicit `CrawlOutcome`; enable `solve_cloudflare` on the stealthy tier.
3. **Add `crawls_succeeded`** counting in `webcrawler_indexer.py` + expose in **task metadata only** (03c bills off the in-function counter). **Do not change the positional return tuple** (the shared wrapper unpacks by length; Phase 6 adds a `stats` out-param).
4. **Update both `scrape_webpage` tools** to drop `firecrawl_api_key` + `formats`.
5. **Tests:** unit tests for `crawl_url` outcomes (mock Scrapling fetchers → SUCCESS/EMPTY/FAILED); update `test_dependencies.py`; assert the indexer's `crawls_succeeded` count.

## Risks / trade-offs

- **Loss of a managed fallback.** Firecrawl was a hosted last resort for hostile anti-bot sites. Mitigation: the in-house stack — `StealthyFetcher` + Cloudflare solving (this plan), `03b` proxy rotation, `03e` stealth-hardening (humanize/headed/profiles/fonts + block-classifier), `03d` captcha solving — plus a **deferred paid-unblocker tier** behind the seam for the hostile residual. Realistic ceiling: this defeats Cloudflare + the long tail of moderate anti-bot, but runtime-level (patchright) stealth does **not** reliably beat top-tier fingerprinting (DataDome/Kasada/reCAPTCHA-Enterprise) — that's the deferred paid tier's job (`03e`). Acceptable per the decisions log (single-framework intent + in-house moat).
- **Browser tiers on dev/Windows.** `DynamicFetcher`/`StealthyFetcher` need subprocess support; the existing `to_thread` + `NotImplementedError` guards (lines 134–141, 161–168) are preserved so static-only crawling still works in `uvicorn --reload`.
- **`uv.lock` churn.** Removing `firecrawl-py` requires a lockfile regen + image rebuild; no new runtime deps are added.

## Out of scope (hand-offs)

- Proxy provider expansion + rotation → `03b`.
- Crawl credit metering on `CrawlOutcomeStatus.SUCCESS` → `03c`.
- reCAPTCHA/hCaptcha solving via captcha-tools → `03d` (**now active**, sequenced after `03e`). Cloudflare Turnstile stays in-framework (Scrapling).
- Stealth-hardening (humanize, headed/Xvfb, persistent profiles, fonts, geoip locale/tz, block-classifier + per-domain strategy memory) and the deferred paid-unblocker tier → `03e`.
- Whether ad-hoc **chat** scrapes are billed (vs only pipeline crawls) → decided in `03c`.
