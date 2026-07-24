# Google Search Results Scraper

A platform-native Google SERP scraper intended as a **drop-in clone of the
Apify "Google Search Results Scraper" actor** — same input surface, same
output item shape (one item per SERP page). Built on the same layout and
progressive-implementation approach as the sibling `../youtube` and
`../google_maps` scrapers.

**Current status: organic + paid SERP scraping works end-to-end.** The full
Apify input surface is accepted and validated, the output models mirror the
actor's example JSON, query composition is implemented, and `_serp_page_flow`
fetches and parses live SERPs: **organic results (with `siteLinks`), text ads
(`paidResults`), product/shopping ads (`paidProducts`), related queries,
suggested results, People Also Ask questions *and answers* (with source
url/title), the inline AI Overview (content + cited sources), and
`resultsTotal`**. `mobileResults` renders with a phone UA and parses Google's
mobile lightweight layout; `includeUnfilteredResults` (`filter=0`) is verified
live; **Google AI Mode** (`aiModeSearch.enableAiMode`) emits a conversational
answer + cited sources as its own item; `includeIcons` puts the base64 favicon
on organic/paid results; `saveHtml` attaches the raw page. The only remaining
piece is the HTTP route.

### How fetching works (and why it's slow)

Google's web `/search` is hostile: most residential IPs get a 429 "unusual
traffic" wall, and the IPs that pass serve a JavaScript shell whose organic
results only materialize after the page's JS runs. So `fetch.py` needs both a
**non-blocked IP** and a **real browser render**, on the same IP:

1. Take a **warm sticky IP from the pool** (`_pool`): reuse an already-solved IP
   under its soft per-IP concurrency cap — concurrent fetches fan out across the
   pool's IPs (least-loaded first) instead of funneling onto one hot IP (which
   Google re-walls). If the pool is below target, grow it: first try to **adopt**
   an IP another process already solved (see the shared store below), else race
   prechecks on several fresh sticky IPs at once (DataImpulse maps ports →
   sessions) and solve on the first that passes. If the pool is full and every
   IP is busy, wait briefly for a slot rather than burn a fresh solve,
2. render on that IP using a **shared long-lived browser** (launched once per
   process, per layout; each fetch only opens a fresh context carrying its
   vetted proxy). Renders drop image/font/media/stylesheet requests
   (`disable_resources`; the parsed DOM is text/attributes only) — except AI
   Mode, whose answer streams in. During the render it clicks the AI Overview's
   "Show more" clamp and the initially-served People-Also-Ask questions open
   (all clicks fired first, then one shared wait) so their content lands in the
   DOM;
3. on success (re)admit the IP to the pool; a walled render evicts it (and drops
   its exemption fleet-wide). Retry until a render returns the results container
   or the per-fetch deadline / IP budget runs out.

**The reCAPTCHA wall.** A curl-vetted IP is only *half* the battle: the initial
`/search` GET returns a 200 JS shell, but the shell's JS reloads `/search` with
a `sei` token, which Google 302s into a reCAPTCHA-**Enterprise** `/sorry` page.
This trips *every* real browser (the block is on the browser access pattern, not
the IP — curl "passes" only because it never runs the reload, and so never gets
results either). When a solver is configured (`CAPTCHA_SOLVING_ENABLED=TRUE` +
`CAPTCHA_SOLVER_API_KEY`, see `app/utils/captcha/`), `captcha.py` runs inside the
render's `page_action`: on landing at `/sorry` it harvests an Enterprise token
(with the page's dynamic `data-s`) from the solver **egressing through the same
sticky proxy**, injects it, and submits. Google then issues a
`GOOGLE_ABUSE_EXEMPTION` cookie, which the fetch seam caches per proxy
(`_exemption_jar`) and replays via `page_setup` so **one solve unlocks the
sticky IP for all subsequent queries** on it. That solve is also **published to
Redis** (`pool_store.py`), so any *other* worker process can adopt the same
warm IP instead of re-solving — cost then tracks the shared pool size, not the
worker count (best-effort: no Redis ⇒ each process just keeps its own pool).
Without a solver configured the stealth tier is unchanged (and
brand/navigational queries will 429-wall).

Timings (measured): a fetch that must solve runs **~40–110 s and is entirely
dominated by the solver** — the reCAPTCHA-Enterprise harvest alone measured
**27–39 s on capsolver** (the configured default; AI-native, tighter spread) and
37–100 s on 2captcha (pure vendor worker latency, not our overhead). NB the
sub-10 s figures both vendors advertise are for the plain reCAPTCHA *demo*
sitekey; Google's Enterprise `/sorry` wall is genuinely harder and slower for
everyone. Every *subsequent* fetch on that sticky IP reuses the cached exemption
and runs **~12–16 s** (two proxy navigations for Google's `sei` reload + ~3–4 s
of block expansion; the vet precheck is skipped, `render_ms` is the whole
render). The first fetch of a process also pays the ~5 s Chromium launch. So the
one lever that actually moves the needle is **solving less often** (the pool +
Redis-shared exemptions already amortize it) — or a faster solver.

**Scale.** Per-process throughput ceiling = `GOOGLE_SEARCH_MAX_CONCURRENT_PAGES`
÷ warm-render-secs ≈ **4 / 14 s ≈ 17 SERP/min** at the default. Because renders
drop images/fonts/media, one Chromium holds well more than 4 text contexts, so
raise `GOOGLE_SEARCH_MAX_CONCURRENT_PAGES` to trade RAM/CPU for throughput
before adding processes (e.g. 16 → ~69/min/process ⇒ ~7 processes cover 500/min;
the sim in `scripts/scale_google_search.py` reproduces these numbers offline).
`GOOGLE_SEARCH_WARM_POOL_TARGET` sizes the shared warm-IP pool: steady-state
paid solves ≈ pool size (not request count), and it must be large enough that
fleet-wide per-IP load (local `GOOGLE_SEARCH_IP_MAX_CONCURRENCY` × processes)
stays gentle enough that Google doesn't re-wall a pool IP. Requires the
browser tier (patchright Chromium via
Scrapling's `AsyncStealthySession`) and a residential proxy — set
`PROXY_PROVIDER` + `PROXY_URL` (see `.env`; **do not** pin a `__cr.<country>`
suffix — DataImpulse's per-country sub-pools are 429-walled even for the curl
precheck, which starves vetting; `gl=` in the URL sets result locale instead).
Long-running callers can `await fetch.close_sessions()` on shutdown; scripts
that exit anyway can skip it.

## Scope

Included (this actor's own features):

- Organic results, paid results (ads), product ads
- Related queries, People Also Ask, suggested results
- AI Overview extraction (`aiOverview.scrapeFullAiOverview`)
- Google AI Mode (`aiModeSearch.enableAiMode`) — google.com's dedicated AI
  search interface, distinct from inline AI Overviews
- Full localization: country (`gl`), search language (`lr`), interface
  language (`hl`), exact location (`uule`)
- Advanced search filters composed into query operators (site, related,
  intitle/intext/inurl, filetype, before/after/qdr date ranges, exact match)
- Inline HTML capture (`saveHtml`), icons (`includeIcons`). The actor's
  key-value-store snapshot (`saveHtmlToKeyValueStore` → `htmlSnapshotUrl`) is
  Apify storage plumbing and is skipped (accepted but ignored).

Excluded on purpose (Apify implements these by piping into *other* actors /
third-party data brokers): `perplexitySearch`, `chatGptSearch`,
`copilotSearch`, `geminiSearch`, `linkProspecting`, and business leads
enrichment (`maximumLeadsEnrichmentRecords`, `leadsEnrichmentDepartments`,
`verifyLeadsEnrichmentEmails`). A verbatim Apify payload containing them still
validates (`extra="allow"`) but they are ignored.

## Quick start

```python
from app.proprietary.platforms.google_search import (
    GoogleSearchScrapeInput, scrape_serps,
)

# One output item per SERP page; queries mixes terms and Google Search URLs.
items = await scrape_serps(
    GoogleSearchScrapeInput(
        queries="best SEO tools\nhttps://www.google.com/search?q=apify",
        maxPagesPerQuery=2,
        countryCode="us",
        site="example.com",
        aiModeSearch={"enableAiMode": True},
    )
)
```

`iter_serps()` is the streaming twin. (No HTTP route yet — module only, per
the progressive rollout.)

## Module map

| File               | Responsibility                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `__init__.py`      | Public exports (entry points + schemas).                                                                                  |
| `schemas.py`       | Pydantic input/output models mirroring the Apify camelCase spec. `extra="allow"` on outputs keeps the contract open.      |
| `scraper.py`       | Orchestrator. `iter_serps` dispatches each `queries` line to `_term_flow` / `_url_flow` (+ `_ai_mode_flow` per term).      |
| `query_builder.py` | Pure: classify `queries` lines, fold advanced filters into search operators, resolve relative dates, build the URL.        |
| `fetch.py`         | Proxy-vetted two-phase fetch: cheap precheck GET + headless render on a **warm sticky-IP pool** (spread across IPs, per-IP soft cap, grow-to-target), retrying across IPs. Caches per-IP reCAPTCHA exemptions. |
| `pool_store.py`    | Best-effort Redis cache of solved-IP exemptions so a solve on one worker warms that IP for the whole fleet (adopt/publish/evict); silent no-op without Redis. |
| `captcha.py`       | Async reCAPTCHA-Enterprise solve for the `/sorry` wall (via the `app.utils.captcha` solver seam — capsolver/2captcha, `enterprise`+`data-s`), run inside the render's `page_action`.  |
| `parsers.py`       | Rendered SERP HTML → organic / text ads / product ads / related / People-Also-Ask / `resultsTotal` (degrades per-field). |

## Input semantics (matching Apify)

- `queries` (required) is a **newline-separated string**; each line is either
  a plain search term (advanced Google operators allowed) or a full Google
  Search URL (scraped as-is; its own URL parameters win).
- `maxPagesPerQuery` unset means 1 page (~10 results per page).
- `forceExactMatch` wraps the whole term in quotes.
- `site:` takes precedence over `related:` — when both are set,
  `relatedToSite` is ignored.
- `wordsInTitle`/`wordsInText`/`wordsInUrl` emit one `intitle:`/`intext:`/
  `inurl:` per word (never the `allin*:` forms — they conflict with other
  operators).
- `fileTypes` are OR-joined (`filetype:pdf OR filetype:doc`).
- `beforeDate`/`afterDate` accept absolute (`2024-05-03`, UTC) or relative
  (`3 months`) dates → `before:`/`after:` operators. `quickDateRange`
  (`d10`/`w2`/`m6`/`y1`) → `tbs=qdr:`. Avoid combining the two.
- `includeUnfilteredResults` → `filter=0`.
- Localization: `countryCode` → `gl=`, `searchLanguage` → `lr=lang_*`,
  `languageCode` → `hl=`, `locationUule` → `uule=`. Google retired country
  ccTLDs (google.es et al. redirect to google.com since 2025), so the country
  is carried by `gl` and the domain is always `google.com`.
- `saveHtmlToKeyValueStore` defaults **true** (matching the actor);
  `saveHtml` defaults false.

## Output shape (`SerpItem`, one per SERP page)

- `searchQuery` — provenance: `term`, `url`, `device` (DESKTOP/MOBILE),
  `page`, `type`, `domain`, `countryCode`, `languageCode`, `locationUule`
- `resultsTotal`
- `organicResults[]` — `title`, `url`, `displayedUrl`, `description`,
  `emphasizedKeywords`, `siteLinks`, `productInfo`, `icon`, `type`,
  `position`
- `paidResults[]`, `paidProducts[]`
- `relatedQueries[]`, `peopleAlsoAsk[]`
- `suggestedResults[]` — the related queries re-emitted in result shape
  (`title`, google-search `url`, `type: "organic"`, 1-based `position`),
  matching how the actor synthesizes them
- `aiOverview` — `{content, sources[{title, url, description, imageUrl}]}`
  when an AI Overview appears (always fully expanded)
- `aiModeResult` — `{engine, provider, text, sources[], query, kvsHtmlUrl,
  url}` when the AI Mode add-on is enabled
- `html` / `htmlSnapshotUrl` — HTML capture add-ons

All list fields default to `[]`, unsourced scalars to `None` — parity is
additive, consumers never break on missing keys.

## Testing

Offline unit tests (no network — query building, schema, and SERP parsing
against a synthetic fixture):

```bash
cd surfsense_backend
.venv/Scripts/python.exe -m pytest tests/unit/platforms/google_search/
```

Live end-to-end (needs the proxy + browser tier configured):

```bash
.venv/Scripts/python.exe scripts/e2e_google_search.py
```

## Implementation TODO (progressive, like YouTube/Maps)

- **Done:** `_serp_page_flow` organic / text-ad (`paidResults`) / product-ad
  (`paidProducts`) / related / PAA / `resultsTotal` parsing over a proxy-vetted
  browser render.
- **Done:** `focusOnPaidAds` — re-renders on fresh IPs (up to 3 tries) until
  ads surface, since Google serves ads non-deterministically; falls back to the
  richest ad-less render.
- **Done:** People-Also-Ask answers — the render clicks the first ~4 questions
  open (`fetch._expand_paa`); the parser handles both answer shapes
  (featured-snippet `.hgKElc` with a source link, and AI-generated `.n6owBd`
  paragraphs with inline source chips stripped). Expansion appends extra
  collapsed questions, which emit question-only.
- **Done:** `siteLinks` on organic results (the expanded sitelinks table of
  brand queries' top result) and `suggestedResults` (related queries re-shaped
  with `type`/`position`, per the actor's output).
- **Done:** inline AI Overview (`#m-x-content`) — generated prose (paragraphs
  + bullets, inline source chips stripped) plus cited sources (title, url,
  snippet, thumbnail). The render always clicks "Show more", so the full
  overview is scraped whether or not `scrapeFullAiOverview` is set (a superset
  of the actor's gated behavior).
- **Done:** `mobileResults` — renders with a Chrome-on-Android UA + phone
  viewport. Google serves its *lightweight mobile layout* (a different DOM:
  `Gx5Zad` blocks, `/url?q=` redirect anchors, PAA answers and the full AI
  Overview pre-loaded — no clicks needed); `parse_serp` auto-detects the
  layout and dispatches to the `_mobile_*` extractors. Mobile pages carry no
  `resultsTotal`, marked ads, or sitelinks, so those emit `None`/`[]`.
- **Done:** `includeUnfilteredResults` (`filter=0`) verified live end-to-end.
- **Done:** `_ai_mode_flow` — renders `google.com/search?udm=50`; the
  conversational answer streams into `[data-subtree='aimc']`, which is built
  from the same DOM blocks as the AI Overview, so the prose/source extractors
  are shared. Emits one extra item per term with `aiModeResult`
  (`engine/provider/text/sources/query/url`).
- **Done:** `includeIcons` — the rendered desktop SERP inlines every favicon
  as a `data:image/...;base64,` URI (`img.XNo5Ab`), which is exactly the
  actor's output shape, so it's a straight attribute read on organic + paid
  results. The mobile lightweight layout carries no favicons.
- **Skipped on purpose:** key-value-store HTML snapshots
  (`saveHtmlToKeyValueStore` → `htmlSnapshotUrl`) — that's Apify storage
  plumbing (persist the raw page for debugging/auditing), not extraction; we
  have no KVS equivalent and `saveHtml` already returns the raw HTML inline
  when callers want it.
- HTTP route + registration once the flows are live.
