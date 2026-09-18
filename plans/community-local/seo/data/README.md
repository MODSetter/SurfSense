# Raw DataForSEO pulls

Backing data for [`../01-keyword-research.md`](../01-keyword-research.md) and
its companions. All pulled **14 Sep 2026**, Google **US desktop**
(`location_code: 2840`, `language_code: en`) unless a row says otherwise.
Render any of them with [`parse.py`](parse.py); `python parse.py --self-check`
runs the parser's own tests.

Most files are DataForSEO's AI-optimised subset, so `items` sits at the top
level rather than under `tasks[].result[]`; a few are full API responses, and
the `intl/` files are full responses trimmed by `parse.py --compact-from`
(the `artifacts-intl-*` files were trimmed by hand into the same shape, with a
`note` in place of the `missing` list). `parse.py` reads all three shapes,
gzipped or not, with or without a UTF-8 BOM (PowerShell 5 adds one when
redirecting stdout).

## Files

| file | endpoint | what it answers |
|---|---|---|
| `keyword-overview-curated.json.gz` | `dataforseo_labs/google/keyword_overview/live` | exact metrics for the first 70 hand-picked targets |
| `keyword-overview-variants.json` | same | spelling variants: `air gap ai` / `air-gapped ai` / `airgap ai`, `on prem` / `on-premise`, `private llm`, `local rag` |
| `keyword-overview-notebooklm-family.json` | same | the NotebookLM query family: pricing, tiers, limits, platforms, comparisons, trust |
| `keyword-overview-brand-questions.json` | same | `surfsense*`, `best …` and question forms, NotebookLM vs X |
| `keyword-overview-verticals.json` | same | compliance (HIPAA, legal), Ollama ecosystem, homelab, PKM |
| `keyword-overview-gap-terms.json` | same | terms surfaced by the competitor gap pulls, re-checked for full metrics |
| `keyword-overview-artifacts.json.gz` | same | the Studio outputs (`01`, section 3): 208 terms for study guide, flashcards, quiz, summary, slides, mind map, infographic, report, spreadsheet, web page, video and the edtech brands; 196 came back |
| `keyword-overview-deliverable.json` | same | **pulled 17 Sep 2026** for [`../07-what-users-do.md`](../07-what-users-do.md): 102 "document into a deliverable" and "ai for `<profession>`" terms, 68 returned |
| `keyword-overview-workintercept.json` | same | **17 Sep 2026**: the NotebookLM-at-work intercept (dead: 10-30 a month), the `chat with X` family (dying), and the business-qualified privacy terms (`private ai for business`, `secure ai for business`, `ai workspace`) that replaced them |
| `keyword-ideas-deliverable.json.gz` | `dataforseo_labs/google/keyword_ideas/live` | **17 Sep 2026**: discovery from 8 professional seeds, 700 results. The head is generic-AI noise as usual — the useful rows are the tail, filtered to keywords naming a profession, a deliverable or a confidentiality concern and sorted by `volume × cpc` |
| `intl-pro-es-es.json` | `keyword_overview/live` | **17 Sep 2026**: the professional list in Spanish for Spain. See [International pulls](#international-pulls) for why Mexico and Brazil are not archived |
| `keyword-ideas-broad.json.gz` | `dataforseo_labs/google/keyword_ideas/live` | category discovery from 8 seeds, 700 results, volume > 30 |
| `keyword-ideas-questions.json` | same, filtered | question and "best" phrasings (mostly generic-AI noise; the parser's `EXCLUDE` list came from reading this) |
| `keyword-ideas-artifacts.json.gz` | same | discovery seeded with the Studio format names, 700 results by volume; the top is generic-AI heads (`ai`, `character ai`), the artifact tail is what the clusters pick up |
| `keyword-suggestions-notebooklm.json.gz` | `dataforseo_labs/google/keyword_suggestions/live` | long-tail containing "notebooklm" |
| `historical-head-terms.json` | `dataforseo_labs/google/historical_search_volume/live` | monthly volume back to 2018 for 14 head terms |
| `historical-artifact-terms.json` | same | back to 2018 for 10 Studio heads (`study guide maker`, `flashcard generator`, `ai quiz generator`, `ai summarizer`, `ai presentation maker`, …); the source of the school-year seasonality figures |
| `ranked-surfsense.json.gz` | `dataforseo_labs/google/ranked_keywords/live` | our baseline: 425 ranking keywords, top 200 saved |
| `ranked-open-notebook.json.gz` | same | the SEO incumbent |
| `ranked-anythingllm.json.gz` | same | the docs-pages-rank pattern |
| `ranked-jan.json` | same | the blog-format pattern, 150 rows |
| `ranked-openwebui.json` | same | the integration-docs pattern, 150 rows |
| `ranked-khoj.json` | same | the anti-pattern: 1,671 pages, 15 keywords |
| `gap-open-notebook.json` | `dataforseo_labs/google/domain_intersection/live` | keywords open-notebook.ai ranks for and surfsense.com does not (93) |
| `gap-anythingllm.json` | same | same for anythingllm.com (206) |
| `domain-authority.json` | `backlinks/summary/live` | referring domains and crawled pages for surfsense.com and six competitors, merged from seven single-target calls |
| `serp-self-hosted-ai.json` | `serp/google/organic/live/advanced` | full SERP with AI Overview, depth 20 |
| `serp-offline-ai.json` | same | trimmed to the fields the renderer reads |
| `serp-notebooklm-mcp.json` | same | trimmed |
| `serp-private-ai.json` | same | trimmed |
| `serp-study-guide-maker.json` | same | trimmed; the study SERP with its AI Overview citations and PAA |
| `artifacts-serp-competitors.json` | `dataforseo_labs/google/serp_competitors/live` | who ranks across 28 Studio heads: top 40 of 854 domains, best position per keyword under `keywords_positions`; the edtech table in `04` |
| `artifacts-intl-<market>.json` | `keyword_overview/live`, trimmed | the Studio list abroad: `gb-en` (48 rows, with the `revision` forms), `in-en` (48, with `mcq`/exam forms), `de-de` (46, German forms under `language_code: de`), `jp-ja` (28 of 56; every flashcard and quiz form fell below threshold, listed in the file's `note`) |
| `master-keywords.csv` | derived | **600** scored, clustered keywords (565 before 17 Sep 2026); regenerate with the command below |
| `intl/lists.json` | config | the keyword lists behind the international pass (`en-core` 43, `en-extended` 70, one translated list per language) and a `markets` map of `location_code`, `language_code` and which lists each market gets |
| `intl/<market>.json` | `keyword_overview/live`, compacted | 27 pulls for 26 markets (Canada in English and in French), same lists, same day; see [International pulls](#international-pulls) |
| `intl/markets.csv` | derived | market × keyword long table: `recent`, `volume`, `cpc`, `kd`, `concept`, `variant_of`; regenerate with the command below |

## Methodology notes

**`recent` and `spike`.** Google Ads' `search_volume` is a 12-month average,
and the privacy cluster stepped up 5-25x in July-August 2026, so the average
overstates the year and understates today. `parse.py` reports `recent` as the
median of the last three months (capped at the reported figure) and flags
`spike` when the peak month exceeds 4x the 12-month median. A row with `spike`
whose `recent` still equals `volume` has held its new level for three months.

**Seasonality.** The study clusters (study, flashcards, quiz, and less so
summary and slides) follow the academic year: peaks in September-October and
March-April, a floor in June-August. A 14 September pull's last three months
*are* that floor, so `recent` understates term-time demand for those clusters
by 2-5x; the privacy clusters have no season. Size study terms from `python
parse.py --mode history historical-artifact-terms.json` (yearly averages and
peak month), not from `recent`.

**Position bands beat combined volume.** `--mode urls` sums a landing page's
volume, which flatters it: on `/free`, 81% of the 435,390 sits at position 21+
and returns 37% of the value, while the 31 top-10 keywords are 6.8% of the
volume and nearly half the value. `--mode baseline` splits one page both ways —
by position band, then by what the query asks for (`BASELINE_CLUSTERS`) — and
that second table is what settled the `/free` decision in `01`. The clusters
overlap by design (a brand term is usually also a no-signup term), so only
"everything else" is a true complement, of the no-signup cluster alone.

**KD proxy.** DataForSEO leaves `keyword_difficulty` blank on most sub-100
terms. Where blank, `parse.py` substitutes `20 × log10(referring_domains + 1)`
from the average backlink profile of the current top 10 (`avg_backlinks_info`),
which is the raw signal KD is built from: 10 domains → ~21, 100 → ~40,
1,000 → ~60. Proxy values carry a `~` suffix. Where neither exists the row gets
`30?`.

**Score.** `log10(recent + 1) × (100 − KD)/100 × intent weight × trend factor
× 10`. Intent weights: transactional 1.3, commercial 1.2, informational 1.0,
navigational 0.6. Trend factor is `1 + clamp(yoy, −50, +200)/400`, so +200%
caps at 1.5x and −50% floors at 0.875x. The score sorts; it is not a forecast.

**Clusters.** First-match regexes in `parse.py` (`CLUSTERS`), with an
`EXCLUDE` list for generic-AI noise that shares a word (laptops, coding
agents, image generators, podcasts *about* AI). Order matters: `mcp`,
`podcast` and the Studio clusters (`competitor` for the edtech brands, then
the eleven format clusters `study`, `flashcards`, `quiz`, `mindmap`,
`summary`, `slides`, `infographic`, `report`, `spreadsheet`, `video`,
`webpage`) are claimed before
the NotebookLM clusters, so `notebooklm mcp` lands in `mcp` and `notebooklm
flashcards` in `flashcards`; `notebooklm-switch` (alternatives, comparisons,
trust) is claimed before `notebooklm-brand` (everything else). The Studio
regexes want a tool word (`generator`, `maker`, `from pdf`, `to quiz`) so that
`flashcards` the noun or `text to video ai` stay in `other`. Expect one
misassignment in twenty and fix it in the CSV, not the regex, unless it is
systematic.

**The `professional` cluster, added 17 Sep 2026.** `CLUSTERS` had no regex for
`ai for lawyers`, `legal ai`, `ai workspace` or `ai knowledge base`, so
`--drop-other` discarded all 29 of them and the master list could not represent
the strategy in [`../07-what-users-do.md`](../07-what-users-do.md). One cluster
was added, placed after `compliance` (so HIPAA and GDPR still route to the
compliance page) and after the artifact clusters (so `ai report generator` stays
with `report`). Regenerating took the CSV from 565 rows to 600 with **nothing
lost and nothing moved between clusters**. Before accepting any future cluster
change, keep a copy of the CSV and diff it on `keyword` (added, lost) and on
`cluster` (moved): first-match-wins means a new regex can silently steal rows
from an existing cluster, and the risk is never what it adds.

**Two rows drifted in that regeneration.** `private ai` and `sovereign ai` both
re-read at 27,100 (from 8,100) because they appear in the 17 Sep discovery pull
as well as the 14 Sep overview pull, and `keyword_ideas` and `keyword_overview`
do not always report the same string identically. The prose in `01` quotes the
14 Sep overview figures; the CSV carries the newer reading for these two only.
Re-pull both through `keyword_overview/live` before either decides anything.

**Hyphens.** DataForSEO sometimes holds one record for two spellings (`air gap
ai` and `air-gapped ai` report identical metrics) and sometimes two (`self
hosted llm` 2,400 vs `self-hosted llm` 1,300). Pull both forms; do not sum the
identical ones. In `markets` mode `parse.py` finds the merged records by
their identical monthly series (`close_variants`: six shared months, three
distinct non-zero values) and fills `variant_of` on the duplicate, so the
per-market sums count each once; `ローカルllm` / `ローカル llm` and
`alternative` / `alternatives` are the common cases.

## Reproducing

Each call is a `POST` with a single task object. Overview, one array of up to
700 keywords:

```json
[{ "location_code": 2840, "language_code": "en", "include_serp_info": true,
   "keywords": ["notebooklm alternative", "open source notebooklm", "..."] }]
```

Discovery:

```json
[{ "location_code": 2840, "language_code": "en", "include_serp_info": true,
   "limit": 700,
   "keywords": ["notebooklm", "local llm", "offline ai", "self hosted ai",
                "chat with pdf", "ai knowledge base", "private ai", "rag"],
   "filters": [["keyword_info.search_volume", ">", 30]],
   "order_by": ["keyword_info.search_volume,desc"] }]
```

Historical volume:

```json
[{ "location_code": 2840, "language_code": "en",
   "keywords": ["private ai", "self hosted ai", "on premise ai", "..."] }]
```

Rankings and gaps:

```json
[{ "target": "open-notebook.ai", "location_code": 2840, "language_code": "en",
   "limit": 150, "order_by": ["keyword_data.keyword_info.search_volume,desc"] }]

[{ "target1": "open-notebook.ai", "target2": "surfsense.com",
   "location_code": 2840, "language_code": "en", "intersections": false,
   "order_by": ["keyword_data.keyword_info.search_volume,desc"] }]
```

Authority, one target per call (the live endpoint rejects batches), merged by
hand:

```json
[{ "target": "surfsense.com", "include_subdomains": true,
   "backlinks_status_type": "live" }]
```

SERP, one keyword per call:

```json
[{ "keyword": "self hosted ai", "location_code": 2840, "language_code": "en",
   "device": "desktop", "depth": 20, "load_async_ai_overview": true }]
```

Save as `serp-<keyword-with-dashes>.json`; the renderer takes the heading from
the filename, and `--mode serp "serp-*.json"` picks up every file with that
prefix, so nothing else may start with `serp-`.

SERP competitors, one call for the whole keyword set:

```json
[{ "location_code": 2840, "language_code": "en",
   "keywords": ["study guide maker", "flashcard generator", "ai quiz generator", "..."],
   "limit": 40, "order_by": ["rating,desc"] }]
```

Keep `keywords_positions` (one best position per keyword per domain); that is
what the competitors renderer counts.

## Rendering

```bash
python parse.py --self-check
python parse.py keyword-overview-variants.json                      # metrics table
python parse.py --mode ranked ranked-open-notebook.json             # keyword, volume, kd, position, url
python parse.py --mode urls ranked-jan.json                         # grouped by landing page
python parse.py --mode baseline ranked-surfsense.json.gz            # /free by position band and intent
python parse.py --mode baseline --url-prefix /docs ranked-jan.json  # any page; the prefix is matched, not equalled
python parse.py --mode gap --min-volume 200 gap-open-notebook.json  # they rank, we don't
python parse.py --mode history historical-head-terms.json           # yearly averages + peak month
python parse.py --mode history historical-artifact-terms.json       # the study season, back to 2018
python parse.py --mode authority domain-authority.json
python parse.py --mode serp "serp-*.json"                           # the five archived SERPs
python parse.py --mode competitors artifacts-serp-competitors.json  # who ranks across the 28 Studio heads
python parse.py keyword-overview-artifacts.json.gz                  # the 196 Studio-output terms
python parse.py artifacts-intl-de-de.json                           # one market's Studio list (any of the four)
python parse.py --mode score --drop-other --min-volume 40 --csv master-keywords.csv \
    "keyword-overview-*.json" "keyword-ideas-*.json" "keyword-suggestions-*.json"
python parse.py --compact-from raw-jp.json --market jp-ja --pulled 2026-09-14   # trim a pull into intl/jp-ja.json
python parse.py --mode markets --csv intl/markets.csv                            # every market: summary, concept pivot, long table
python parse.py --mode markets "intl/jp-ja.json" "intl/de-de.json"               # a subset; globs are expanded by the script
```

## International pulls

The 27 pulls behind [`../03-international.md`](../03-international.md) are
archived under [`intl/`](intl/), one compacted `keyword_overview/live`
response per market, pulled **14 Sep 2026** like everything else here. The
markets, with their `location_code` and `language_code`, are the `markets`
map in [`intl/lists.json`](intl/lists.json):

| language | markets (file stem) | lists |
|---|---|---|
| English | `us-en` `gb-en` `ca-en` `au-en` `in-en` `ie-en` `sg-en` `nz-en` `za-en` `ae-en` `ph-en` `id-en` | `en-core` + `en-extended` |
| German | `de-de` `at-de` `ch-de` | `de` + both English lists |
| French | `fr-fr` `ca-fr` | `fr` + both English lists |
| Spanish | `es-es` `mx-es` | `es` + both English lists |
| Portuguese, Japanese, Italian, Dutch, Korean, Polish, Swedish, Traditional Chinese | `br-pt` `jp-ja` `it-it` `nl-nl` `kr-ko` `pl-pl` `se-sv` `tw-zh` | own list + both English lists |

Every market gets the two English lists, so the English-term columns are
comparable across all 27 pulls; non-English markets add the translated list
for their language. Non-English markets are pulled under the local
`language_code`, English terms included: DataForSEO rejects `en` for
`location_code: 2276` with `40501 Invalid Field: 'language_code'` (it holds
no English-language records for Germany), and the other non-English markets
were pulled the same way for comparability. So `local llm` in `de-de` is the
figure for German-language targeting in Germany, which is what a `/de/` page
would meet. Canada is pulled twice (`ca-en`, `ca-fr`); the totals in `03`
drop `ca-fr` so Canada is counted once.

Each archive keeps, per keyword, `search_volume`, `cpc`,
`keyword_difficulty`, `search_volume_trend.yearly`, intent, the top-10
backlink profile (`avg_backlinks_info`, for the KD proxy) and the last 12
months of `monthly_searches` (the API goes back to 2019; a 1.4 MB response
compacts to 11-53 KB), plus a `missing` list of the requested keywords that
came back with no row. Under roughly ten searches a month DataForSEO returns
nothing, and "below threshold" in `03` means exactly that. The compactor
reads the request echoed under `tasks[].data` in a full response and refuses
to file a pull under a market whose `location_code` or `language_code` does
not match; AI-mode responses carry no echo and pass.

Re-pulling is one call per market, the market's lists concatenated:

```json
[{ "location_code": 2392, "language_code": "ja", "include_serp_info": true,
   "keywords": ["<lists.ja>", "<lists.en-core>", "<lists.en-extended>"] }]
```

then the two `parse.py` lines above. Diff `intl/markets.csv` against the
committed one; `03` names the terms to watch.

The Studio-output list was run separately in four of these markets
(`artifacts-intl-{gb-en,in-en,de-de,jp-ja}.json`, "Studio outputs abroad" in
`03`) with the local vocabulary added per market: UK `revision`, Indian
`mcq`/exam forms, German `Karteikarten`/`Lernzettel`, Japanese `スライド`/`要約`.
They sit outside `intl/` because they are not on the shared lists and would
skew the market totals; render them with the default metrics mode.

## Not saved here

- **The professional list in Mexico (`2484`, `es`) and Brazil (`2076`, `pt`)**,
  pulled 17 Sep 2026 alongside `intl-pro-es-es.json`. One
  `keyword_overview/live` per market with the same list; the figures are in
  [`../07-what-users-do.md`](../07-what-users-do.md). They are omitted for the
  reason the `artifacts-intl-*` files sit outside `intl/`: they are not on the
  shared lists and would skew the market totals in `--mode markets`.
- **Historical volume for the 15 professional and business-privacy terms**
  (`historical_search_volume/live`, 17 Sep 2026). This is what separates
  `private ai for business` and `ai for compliance`, which have held three
  months, from `secure ai for business` and `ai for professional services`,
  which are two months old. Re-pull before betting on any of the four; the call
  is one array of keywords, shape as above.

- **SERP competitors** across the 18 privacy and NotebookLM target keywords —
  the call shape above with those keywords. Produced the Reddit/GitHub
  dominance table in `01`. (The Studio-head run *is* archived, as
  `artifacts-serp-competitors.json`.)
- **The live SERP for `open source notebooklm`** — same call shape as the
  archived five. Produced the AI Overview citation list and PAA questions in
  `01`. The four priority SERPs and `study guide maker` *are* archived; this
  one predates the decision to keep them.

Both go stale within days and are cheap to re-pull.
