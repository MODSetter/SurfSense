# Phase 3c — Crawl credit billing ($1 / 1000 successful requests)

> Part of **Phase 3 — WebURL Crawler & Crawl Billing**. See `00-umbrella-plan.md`.
> Depends on `03a-crawler-core.md` (the `CrawlOutcomeStatus.SUCCESS` signal + `crawls_succeeded` counter). Sibling: `03b-proxy-expansion.md`. `03d` is deferred.

## Objective

Charge **$1 per 1000 successful crawl requests** = **1000 micro-USD per successful crawl**, drawn from the existing unified credit wallet, **off by default for self-hosted/OSS** installs. Two surfaces crawl, so both are metered:

- **Connector / pipeline crawls** (the `webcrawler_indexer` path) → billed to the **workspace owner** via a dedicated `WebCrawlCreditService` (check + charge).
- **Ad-hoc chat scrapes** (`scrape_webpage` tools) → the crawl cost is **folded into the chat turn's existing bill** (added to the turn accumulator), so it settles with the turn's normal premium finalize (`start_turn()` + `credit_finalize`). No second wallet hit. (Implies a second gate: only charged when the turn itself is a premium/billed turn — see §3.)

> **Migration impact: none.** This phase adds config flags + code only. `TokenUsage.usage_type` is already a free-form `String(50)`, so the new `web_crawl` value needs **no Alembic migration or schema change**. (Per the standing guidance, the migration-sensitive work lives in Phases 1 and 5+; 03c is purely additive.)

## The key realization (don't use `billable_call`)

My first instinct was to add a flat reserve/finalize path around `TokenQuotaService` because `billable_call` settles at the LLM token accumulator (`acc.total_cost_micros`, `billable_calls.py:367`) — which is 0 for a non-LLM crawl, so `billable_call` would finalize at nothing.

But there's already a **purpose-built precedent for per-unit, non-LLM wallet billing**: `app/services/etl_credit_service.py` (`EtlCreditService`). It deliberately **skips** the reserve/finalize dance and does a simple **gate → pre-check → post-charge**:

- `billing_enabled()` → `config.ETL_CREDIT_BILLING_ENABLED` (`etl_credit_service.py:44–46`); **every method is a no-op when disabled** — that's what keeps self-hosted "effectively free" (`:9–11`, `:59–60`, `:84–85`, `:115–116`).
- `pages_to_micros(pages, multiplier)` → `pages * multiplier * config.MICROS_PER_PAGE` (`:48–51`).
- `check_credits(user_id, estimated_pages)` → raises `InsufficientCreditsError` if `required > available` where `available = balance - reserved` (`:76–102`).
- `charge_credits(user_id, pages)` → `user.credit_micros_balance -= cost; commit; maybe_trigger_auto_reload(...)` (`:104–138`).

It's wired into the **sibling connector indexers** exactly the way we need: `google_drive_indexer.py` (`558,562,605`), `dropbox_indexer.py` (`426,504,593`), `local_folder_indexer.py` (`639,698,864`) — instantiate `EtlCreditService(session)`, `check_credits(...)` before processing, `charge_credits(...)` after.

**So 03c mirrors `EtlCreditService` with a crawl-specific unit and flag — no `billable_call`, no reserve/finalize.**

## Current state (cited)

- **Crawled URLs are billed nothing today.** `webcrawler_indexer.py` does not import `EtlCreditService` or touch the wallet (verified — it's absent from the file). The crawler extracts content directly via Trafilatura and bypasses the ETL page pipeline, so there's **no existing ETL charge** to double up with.
- **Wallet model** (`token_quota_service.py`): the balance lives on `User.credit_micros_balance` / `User.credit_micros_reserved`; spendable = `balance - reserved`. Direct debit is exactly what `EtlCreditService.charge_credits` does.
- **Audit trail**: `record_token_usage(session, *, usage_type, search_space_id, user_id, cost_micros=…, call_details=…, message_id=None, …)` (`token_tracking_service.py:517–568`) inserts a `TokenUsage` row (best-effort; caller commits). `TokenUsage.usage_type` is a `String(50)` indexed column explicitly intended for non-chat usage with `message_id` NULL (`db.py:1068–1116`, comment at `:1072–1084`: "indexing, image generation, podcasts — which keep message_id NULL").
- **Per-feature config knobs** are the convention: `MICROS_PER_PAGE` (`config/__init__.py:655`, default `1000`), `ETL_CREDIT_BILLING_ENABLED` (`:652–653`, default FALSE), `QUOTA_DEFAULT_IMAGE_RESERVE_MICROS` (`:729`), etc. `maybe_trigger_auto_reload` (`auto_reload_service`) is the shared low-balance top-up nudge.

> **Implementation note.** Same convention as `03a`/`03b`: citations use **today's** names (`search_space_id`/`SearchSpace`) so they stay greppable against current code; post Phases 1–2 the live code says `workspace_id`/`Workspace` — map accordingly (e.g. the `record_token_usage(search_space_id=…)` kwarg becomes `workspace_id=…`). Locate code by **symbol/grep**, not the absolute line numbers cited here, since Phase 2's rename and `03a`'s `crawl_url`/`scrape_webpage` refactor shift them.

## Target design

### 1. `WebCrawlCreditService` (mirror of `EtlCreditService`)

New `app/services/web_crawl_credit_service.py` — a dedicated service (independent flag + price; lowest risk, matches the per-feature-knob convention). The two `@staticmethod` helpers are the **shared primitives both surfaces reuse**:

- `billing_enabled()` → `config.WEB_CRAWL_CREDIT_BILLING_ENABLED` (new flag, default FALSE). *(static — also called by the chat tool)*
- `successes_to_micros(n)` → `n * config.WEB_CRAWL_MICROS_PER_SUCCESS` (new knob, default `1000` = $1/1000). *(static — also called by the chat tool)*
- `check_credits(owner_user_id, estimated_urls)` → no-op when disabled; else raise `InsufficientCreditsError` (reuse the one from `etl_credit_service`) if `successes_to_micros(estimated_urls) > available`.
- `charge_credits(owner_user_id, successes)` → no-op when disabled; else debit `credit_micros_balance -= successes_to_micros(successes)`, commit, `maybe_trigger_auto_reload`.

A separate `CreditMeterService` generalization is deliberately deferred until a third per-unit biller appears — exposing the price/flag as statics already lets the chat surface share the math without coupling the two flows.

### 2. Wiring in `webcrawler_indexer.py`

1. **Resolve the owner.** Bill the **workspace owner** (the product concept), not the triggering `user_id`: `owner_user_id = (select SearchSpace.user_id where id == search_space_id)`. (Mirrors how `billable_calls._resolve_agent_billing_for_search_space` (func `:441`) reads `search_space.user_id` at `billable_calls.py:499` — but we only need the owner id, so a direct `select` is enough; no need to call that LLM-model-resolving helper.)
2. **Pre-flight gate** (after URL parse, before the crawl loop — i.e. the indexer's second pass that actually fetches URLs; "phase 2 of the 2-phase indexer", not roadmap Phase 2): `await svc.check_credits(owner_user_id, len(urls))`. On `InsufficientCreditsError`, `log_task_failure` with a clear "out of crawl credit" message and return — don't crawl. Because **successes ≤ len(urls)**, this upper-bound check means the wallet can never go negative from crawls (unlike ETL, where actual pages can exceed the estimate).
3. **Audit (add, don't commit)**: `record_token_usage(session, usage_type="web_crawl", search_space_id=search_space_id, user_id=owner_user_id, cost_micros=successes_to_micros(crawls_succeeded), call_details={"urls": len(urls), "successes": crawls_succeeded, "connector_id": connector_id}, message_id=None)` — `record_token_usage` only `session.add`s the row (`token_tracking_service.py:552`), it does not commit.
4. **Charge actuals**: `await svc.charge_credits(owner_user_id, crawls_succeeded)`. `charge_credits` debits the balance and **commits** (mirroring `EtlCreditService.charge_credits`), which flushes the step-3 audit row **and** the balance debit in one transaction.

Ordering matters: audit must be added **before** the charge, because the charge's commit is what persists both. Both run on the indexer's existing `session` (same as the ETL services), after the final per-URL document commit (`webcrawler_indexer.py:432`). If `crawls_succeeded == 0`, skip both (no-op).

### 3. Chat scrape crawls (folded into the chat turn's bill)

The chat `scrape_webpage` tools (`main_agent/tools/scrape_webpage.py:183`, plus the `research` sibling) crawl via `WebCrawlerConnector.crawl_url` (`main_agent/tools/scrape_webpage.py:232–233`) — the **same** call `03a` refactors. The chat hook therefore keys off `03a`'s `CrawlOutcomeStatus.SUCCESS` return (a hard dependency on 03a's new `crawl_url` signature).

**How the chat turn actually bills** (this is *not* `billable_call`): the chat orchestrators create the turn accumulator with `start_turn()` (`new_chat/orchestrator.py:185`, `resume_chat/orchestrator.py:147`, `anonymous_chat_routes.py:360`); a premium turn reserves up front and, at the end, `finalize_credit` debits `accumulator.total_cost_micros` via `credit_finalize` (`shared/premium_quota.py:83–104`). So adding to the accumulator before finalize is debited with the turn:

```python
from app.services.token_tracking_service import get_current_accumulator
from app.services.web_crawl_credit_service import WebCrawlCreditService

# after a SUCCESS crawl in the scrape tool
acc = get_current_accumulator()              # token_tracking_service.py:212–213 (turn ContextVar)
if acc is not None and WebCrawlCreditService.billing_enabled():
    acc.add(                                 # :112–135 — appends a TokenCallRecord
        model="web_crawl",
        prompt_tokens=0, completion_tokens=0, total_tokens=0,
        cost_micros=WebCrawlCreditService.successes_to_micros(1),
        call_kind="web_crawl",
    )
```

`accumulator.total_cost_micros` sums every call's `cost_micros` (`:174–186`), so the crawl micros ride along into the premium finalize — "included in the already-billed chat." `call_kind="web_crawl"` keeps it distinguishable in `per_message_summary` (`:137–159`).

**Why the ContextVar is reliably visible (not hand-waving):** the LiteLLM `TokenTrackingCallback` already populates *this same* `_turn_accumulator` from deep inside the graph's LLM calls — that's how chat billing works today. If the ContextVar set by `start_turn()` reaches the LLM callback, it reaches a `scrape_webpage` tool in the same graph. The tools are `async` and `await crawl_url` in-loop, so the context is intact (the only thing that would break propagation is offloading to a raw OS thread without `copy_context`, which this path doesn't do).

Two gates, both required, for a chat scrape to actually cost money:
- **`WEB_CRAWL_CREDIT_BILLING_ENABLED`** (self-hosted: off → adds nothing).
- **The turn is premium.** `needs_credit_quota` = `agent_config.is_premium` (`premium_quota.py:43–44`). Free / BYOK / **anonymous** (`anonymous_chat_routes.py:360`, no wallet) turns never reserve/finalize → the `web_crawl` cost is recorded in the accumulator breakdown but **not debited**. This is intentional: if the chat turn isn't billed, neither is its scrape.

Other notes:
- **No per-scrape pre-block.** The turn's up-front reservation is an LLM-only estimate (`reserve_credit`/`estimate_call_reserve_micros`, `premium_quota.py:65`); crawl micros added afterward aren't reserved, but `credit_finalize` debits actuals regardless and may push the balance slightly negative — same allow-exceed posture as ETL. Pre-blocking applies only to the indexer batch path (§2).
- **Accounting caveat.** Chat-scrape crawl spend lands on the turn's `usage_type="chat"` `TokenUsage` row (inside `cost_micros` / the `web_crawl` line of `model_breakdown`), **not** a `usage_type="web_crawl"` row. "Total crawl spend" analytics must sum the indexer's `web_crawl` rows **plus** the `web_crawl` call-kind inside chat rows.

### 4. What counts (from `03a`)

One unit per `CrawlOutcomeStatus.SUCCESS` — a URL that yielded usable extracted content — **regardless of internal fallback tiers** and **regardless of downstream KB dedupe** (unchanged/duplicate still crawled successfully). `EMPTY`/`FAILED` are free.

## Config / env changes

- `config/__init__.py` (next to `ETL_CREDIT_BILLING_ENABLED`/`MICROS_PER_PAGE`, `:649–655`):
  - `WEB_CRAWL_CREDIT_BILLING_ENABLED = os.getenv(..., "FALSE").upper() == "TRUE"`
  - `WEB_CRAWL_MICROS_PER_SUCCESS = int(os.getenv("WEB_CRAWL_MICROS_PER_SUCCESS", "1000"))`
- `.env.example`: document both (commented), noting hosted = TRUE, self-hosted = FALSE.

## Work items

1. **`WebCrawlCreditService`** mirroring `EtlCreditService` (gate + `check_credits` + `charge_credits` + static `successes_to_micros`/`billing_enabled`).
2. **Config knobs** + `.env.example` docs.
3. **Indexer wiring**: owner resolution, pre-flight `check_credits`, then at end-of-run (after `:432`) `record_token_usage(usage_type="web_crawl")` (add) **followed by** `charge_credits(crawls_succeeded)` (commits both); skip when `crawls_succeeded == 0`.
4. **Chat scrape wiring**: in both `scrape_webpage` tools, on SUCCESS fold `successes_to_micros(1)` into the turn accumulator (§3).
5. **Tests**: billing-disabled → both surfaces no-op (self-hosted); indexer enabled + sufficient → debits `successes * 1000` + one `web_crawl` `TokenUsage`; indexer enabled + insufficient → task fails pre-crawl, no debit; owner (not trigger user) billed; `EMPTY`/`FAILED` free; chat scrape on a **premium** turn → `acc.total_cost_micros` rises by `1000` per success and is debited at finalize; chat scrape on a **free/anonymous** turn → recorded in the accumulator but **not** debited.

## Risks / trade-offs

- **Celery retry re-billing.** A task retry re-crawls only the URLs not already `ready`/`pending`/`processing` (the 2-phase indexer skips those, `webcrawler_indexer.py:196–219,341–347`), so a retry charges only re-crawled successes. Acceptable for MVP; Phase 5's `PipelineRun` can persist `charged_micros` for stronger idempotency.
- **Same URL across connectors.** Each connector that crawls it performs a real request → each successful crawl bills, even though the 2nd is KB-deduped. This is intended per the `03a` billing-policy note.
- **Session coupling.** `charge_credits` commits the indexer session; placing it after the final doc commit avoids entangling a debit with mid-run document state.
- **Gating asymmetry (intended).** The **indexer** path bills whenever `WEB_CRAWL_CREDIT_BILLING_ENABLED` is on and the owner has credit — no "premium tier" requirement (matches ETL, which gates only on its own flag). The **chat** path additionally requires the turn to be premium, because it piggybacks the turn's reserve/finalize machinery. Same price, two different gate sets — call this out in the credit-status UI copy (frontend phase).
- **No cross-surface double charge.** A chat scrape calls `crawl_url` directly and never enters `webcrawler_indexer`, so a given crawl is billed by exactly one surface.
- **Proxy/captcha cost.** Absorbed into the flat $1/1000 (margin), **not** metered separately (see `03b`, and `03d` for captcha which has its own per-solve upstream cost — revisit there).

## Resolved decisions (this pass)

- **Bill ad-hoc chat scrapes? → YES.** Chat scrape crawls are metered too, but folded into the chat turn's existing bill via the turn accumulator (§3) rather than a separate wallet debit.
- **Dedicated `WebCrawlCreditService` vs generalized meter? → dedicated**, with `billing_enabled`/`successes_to_micros` exposed as statics so the chat surface shares the price/flag. Generalize later only if a third per-unit biller appears.
- **Pre-flight strictness → pre-block** the indexer batch run on insufficient credit (`len(urls)` is a safe upper bound). Chat scrapes are governed by the turn's own reservation, not a per-scrape block.

## Out of scope (hand-offs)

- Per-**pipeline** run accounting / `charged_micros` persistence for idempotency → Phases 5–7.
- Captcha-solver upstream cost pass-through → `03d` (deferred).
- Surfacing crawl spend in the credit-status UI → frontend umbrella.
