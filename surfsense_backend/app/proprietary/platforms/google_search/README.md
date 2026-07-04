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

1. Reuse the last known-good sticky IP if it still passes a cheap re-precheck;
   otherwise race prechecks on several fresh sticky IPs at once (DataImpulse
   maps ports → sessions) and take the first that passes,
2. render on that IP using a **shared long-lived browser** (launched once per
   process, per layout; each fetch only opens a fresh context carrying its
   vetted proxy) — during which the render clicks the AI Overview's "Show
   more" clamp and the initially-served People-Also-Ask questions open (all
   clicks fired first, then one shared wait) so their content lands in the DOM;
3. retry on fresh IPs until one returns the results container.

A warm fetch (browser up, IP cached) runs ~8 s; the first fetch of a process
also pays the ~5 s Chromium launch and a vetting round. Requires the browser
tier (patchright Chromium via Scrapling's `AsyncStealthySession`) and a
residential proxy — set `PROXY_PROVIDER=custom` + `CUSTOM_PROXY_URL` (see
`.env`). Long-running callers can `await fetch.close_sessions()` on shutdown;
scripts that exit anyway can skip it.

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
| `fetch.py`         | Proxy-vetted two-phase fetch: cheap precheck GET + headless render on a shared sticky IP, retrying across IPs.             |
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
