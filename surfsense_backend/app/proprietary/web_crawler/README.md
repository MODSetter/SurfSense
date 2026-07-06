# Web Crawler Engine

Proprietary crawling engine (licensed separately from the Apache-2.0 project
root — see `app/proprietary/LICENSE`). Single framework (Scrapling) for
fetching, Trafilatura for HTML → markdown extraction. Callers import only from
`__init__.py`: `WebCrawlerConnector` / `crawl_url` for one page, `crawl_site`
for depth-bounded multi-page crawls, both returning the same outcome contract.

## Module map

| Module | Role |
|---|---|
| `connector.py` | Single-URL crawl: tiered fetch ladder, extraction, escalation heuristics |
| `site_crawler.py` | Multi-page crawl: Scrapling `CrawlerEngine` frontier over the connector |
| `url_policy.py` | Link record extraction and categorization (nav/social/contact/document) |
| `captcha.py` | Captcha detection, token harvesting, and injection page-actions |
| `stealth.py` | Stealth/anti-bot configuration for the StealthyFetcher tier |
| `testbench/` | Live-site regression bench (own README) |

Contact extraction (`extract_contacts`) lives in `app/utils/crawl/contacts.py`
because non-proprietary callers use it too.

## The fetch ladder

Every crawl walks the same escalation ladder until one tier produces usable
content; callers see only the resulting `CrawlOutcome`, never the tier:

1. **AsyncFetcher** — static HTTP, TLS-impersonated, cheap. Handles most pages.
2. **DynamicFetcher** — full browser (thread), for JS-rendered content.
3. **StealthyFetcher** — patchright Chromium with anti-bot + Cloudflare
   solving and captcha handling, the expensive last resort.

Success alone does not stop the ladder — two content-quality heuristics can
force escalation or re-extraction:

### Thin-page (JS-shell) escalation

A static fetch can "succeed" on an SPA that server-renders only a hero
paragraph and hydrates everything else client-side (a16z.com/team ships 4.2 MB
of HTML that extracts to 597 chars). A result is tagged `thin_static` and
escalated to the browser tier when **both** hold:

- raw HTML ≥ 1 MB (`_JS_SHELL_MIN_HTML_BYTES`), and
- extracted content < 2.5 KB (`_JS_SHELL_MAX_CONTENT_CHARS`).

Calibrated on live pages: true shells shipped ≥ 3.4 MB with < 0.05 % text;
every healthy page was under ~650 KB. Semi-shells (~150 KB, e.g.
ycombinator.com/people) intentionally stay on static — their server-rendered
link records still carry the roster. Upgrade path: hydration-marker sniffing
instead of size thresholds.

### Lossy-extraction repair (currency-guarded)

Trafilatura sometimes drops structured content (pricing cards, tables). We
can't detect every loss, but currency amounts are a cheap, high-precision
tripwire: if the raw HTML's visible text contains a currency amount
(`_CURRENCY_AMOUNT_RE`) and the extracted markdown doesn't, re-extract with
`favor_recall=True`; if the amount is still missing, fall back to a sanitized
`markdownify` of the whole `<body>`.

## Link records and contacts

`url_policy.extract_link_records` returns categorized links with anchor-text
provenance — these records, not the markdown, are the primary source for
roster/directory answers (names survive in link records even when extraction
drops them). `extract_contacts` harvests emails, phones, and social profiles
country-agnostically (global social-host list, `unquote()` applied to
percent-encoded `mailto:`/`tel:` hrefs — both here and in `url_policy`).

## Multi-page crawls

`crawl_site` uses Scrapling's spider engine for the traversal only (frontier,
dedupe, same-site scope, `includeUrlPatterns`/`excludeUrlPatterns` regex
filtering); every fetch still goes through `crawl_url`, so the ladder, proxy
rotation, and captcha handling are reused unchanged. Each `CrawlPage` carries
provenance (depth, referrer).

## Agent tooling layer (outside this package)

- The `web_crawler` subagent exposes the `web.crawl` capability (single URL at
  `maxCrawlDepth=0`, or site mode at higher depth); the main chat agent reaches
  it by delegating via `task(web_crawler, …)`.
- Tool outputs over the 40k-char cap (`RUN_OUTPUT_CHAR_CAP` in
  `app/capabilities/core/runs.py`) are stored as JSONL runs; agents page them
  with `read_run` (line paging + `char_offset` for giant single items), grep
  them with `search_run` (returns excerpts around matches), and export them
  deterministically with `export_run` (JSONL → CSV → workspace document, with
  filtering and dedupe). Prompts live in
  `app/agents/chat/multi_agent_chat/subagents/`.

## Session learnings (agent E2E hardening, Jul 2026)

Natural-language tasks run end-to-end through the multi-agent chat surfaced
these; each fix has a matching unit test:

1. **Search discovers — the crawler reads.** The agent initially summarized
   from SERP snippets instead of crawling the pages it found. Routing guidance
   (`main_agent/system_prompt/prompts/routing.md`) now tells it to crawl every
   URL whose full content would improve the answer, executing bounded fan-out
   without asking permission.
2. **Success alone is not enough** — content-quality tripwires (thin-page,
   currency-loss) must gate the ladder, because a "successful" fetch can carry
   an empty shell or a lossy extraction. Tests:
   `tests/unit/proprietary/web_crawler/test_connector.py`.
3. **Full datasets become files, not chat.** LLMs are bad data pipes:
   transcribing a 486-row roster through the model loses rows and burns
   tokens. `export_run` converts the stored run to CSV in code and saves it to
   the workspace KB. Tests: `tests/unit/capabilities/test_run_truncation.py`.
4. **Truncation needs an escape hatch the model will actually use.** Large
   items defeated line-based paging until `read_run` grew `char_offset` and
   `search_run` grew match excerpts; subagent prompts explicitly list the
   readers and forbid re-running tools to "see more".
5. **Shared budgets starve precise queries.** In the Reddit scraper, one noisy
   search consumed the whole `maxItems` cap before precise phrasings returned;
   the fix fair-shares the budget across concurrent searches and de-dupes
   across them (`tests/unit/platforms/reddit/test_search_budget.py`). The same
   failure shape applies to any multi-query fan-out with a shared collector cap.
6. **Subagents must not hand back work they can do.** The universal output
   contract (`subagents/shared/snippets/output_contract_base.md`) now requires:
   if `next_step` is a call to one of the subagent's own tools (paging a run,
   re-running with better parameters), execute it instead of returning
   `partial`.
7. **Sizing caps to the ask.** When a task requests N items, tool caps
   (`max_items`, findings limits in output contracts) must be set above N or
   the task is unwinnable by construction; prompts now say so.
