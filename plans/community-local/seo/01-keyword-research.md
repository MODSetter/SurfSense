# Keyword research for the pivot positioning

Reference data for whoever rewrites the public pages under Workstream B (B5, B6)
and the open route decisions in [`../portal/02-pages.md`](../portal/02-pages.md).

This is the demand document. The rest of the set:

| file | what it holds |
|---|---|
| [`02-page-briefs.md`](02-page-briefs.md) | per-page title, meta, H1/H2, schema and internal links |
| [`03-international.md`](03-international.md) | 26 markets in 15 languages: market sizes, localisation tiers, per-language glossaries, hreflang plan |
| [`04-competitors.md`](04-competitors.md) | domain authority, competitor footprints, keyword gaps, patterns to copy; the edtech set that owns the Studio SERPs |
| [`05-serp-landscape.md`](05-serp-landscape.md) | what the results page looks like for the four priority terms and the study-guide head, AI Overview citations, PAA |
| [`06-repo-readme.md`](06-repo-readme.md) | the repo as a ranking page: description, topics, and a paste-ready README draft in [`drafts/`](drafts/README.md) |
| [`data/master-keywords.csv`](data/master-keywords.csv) | 565 keywords scored and clustered, the single list to work from |

**Source:** DataForSEO, pulled 14 Sep 2026, Google **United States** desktop
(`location_code: 2840`, `language_code: en`). Raw responses and the script that
renders every table are in [`data/`](data/); every number below is reproducible
with `python data/parse.py <file>`.

## How to read the numbers

- **Volumes are US-only.** A free open-source desktop app has a global audience,
  so these undercount; treat them as relative weights, not traffic forecasts.
  `03-international.md` runs the same list through 25 more markets: the US is
  68% of the value index and its pages serve every English market through
  hreflang; Japan is the second-largest market and the first localisation;
  India is the largest download market; Germany is the second localisation.
  Nothing there changes a US brief.
- **`volume` is Google Ads' 12-month average and it is inflated this year.**
  Most of the privacy cluster stepped up 5-25x in July-August 2026 (next
  section). `recent` is the median of the last three months, which is what to
  plan on. Where a table shows both, the gap between them is the size of the
  uncertainty. A `spike` flag means one month was more than 4x the 12-month
  median; if `recent` still equals `volume`, the step has held for three
  months and is not a blip.
- **`KD`** is DataForSEO's 0-100 difficulty. Their database has no score for most
  sub-100-volume terms, and blank is not the same as "easy". In the master list
  a `~` suffix (e.g. `13~`) means the score is a proxy from the referring
  domains of the current top 10, described in `data/README.md`.
- **`trend`** is year-on-year percent change. It reaches five digits on terms
  coming off a near-zero base; read direction, not magnitude.
- **Study terms are seasonal, and `recent` is their trough.** Everything in
  the study, flashcards, quiz and (less so) summary and slides clusters follows
  the academic year: peaks in September-October and March-April, a floor in
  June-August. The three months behind `recent` are that floor, so for those
  clusters `recent` understates term-time demand by 2-5x (the ratios are in
  section 3). The privacy clusters have no season; their `recent` is real.
- **Spellings are separate records, sometimes.** `self hosted llm` (2,400,
  KD 5) and `self-hosted llm` (1,300, KD 2) are two records; `air gap ai` and
  `air-gapped ai` report identical numbers and are one. Check both forms of any
  hyphenated term before quoting a volume, and do not add the two air-gap rows.
- **`AIO`** means an AI Overview was on the SERP. It was on nearly every term we
  care about; `05-serp-landscape.md` covers what that means.

## The headline: the demand vocabulary, corrected

The first pass concluded that "airgapped" had no search demand. That was a
spelling artefact. The one-word form has none; the hyphenated and two-word forms
are a real, growing, expensive keyword:

| keyword | volume | recent | kd | intent | cpc | trend | features |
|---|---|---|---|---|---|---|---|
| air gap ai / air-gapped ai (one record) | 1900 | 1900 | 9 | info | **21.78** | +20011 | AIO PAA video |
| airgap ai | 590 | 590 | 9 | info | 7.36 | +4809 | PAA video |
| air-gapped llm | 20 | — | — | info | 0 | — | — |
| airgapped ai | 10 | — | 9 | info | 15.79 | +100 | — |
| ai without internet | 30 | — | — | info | 3.64 | -50 | AIO PAA |
| notebooklm offline | 40 | — | 5 | nav | 0 | -50 | AIO PAA video |

About 2,500 searches a month at KD 9 with a $21.78 CPC. The trend figure is a step from near zero in mid-2026, and `recent`
matching `volume` means the new level has held. So the tagline word is a target
after all, **written "air-gapped"**, never "airgapped". The recommendation that
follows is unchanged: the words that carry the most demand are still *private*,
*local*, *self-hosted*, *offline* and *on-premise*, and the page structure in
`02-page-briefs.md` puts the tagline in the H1 and that vocabulary in the title
tag, H2s and body. "Air-gapped" now earns a place in both.

The "NotebookLM alternative" family is still small and shrinking. It peaked at
27,100 searches in October 2024, the month Audio Overviews went viral, and has
settled at around 600:

| keyword | volume | recent | kd | intent | cpc | trend |
|---|---|---|---|---|---|---|
| notebooklm alternative(s) | 590 | 480 | 4~ | info | 13.16 | **-46** |
| alternative to notebooklm | 170 | — | — | info | 7.94 | +27 |
| notebooklm open source alternative | 70 | — | 4 | comm | 0 | -20 |
| apps like notebooklm | 50 | 40 | 9~ | info | 6.79 | — |
| notebooklm local alternative | 30 | — | 2 | nav | 0 | +100 |
| notebooklm free alternative | 10 | — | — | comm | 3.71 | — |

The people who want off NotebookLM search for what they want instead, and the
next section is what that looks like.

## Summer 2026: the privacy cluster stepped up, and why

Annual average monthly volume, from `historical_search_volume`. 2026 is
January to August.

| keyword | 2023 | 2024 | 2025 | 2026 | peak month |
|---|---|---|---|---|---|
| private ai | 780 | 1,358 | 1,575 | **10,985** | 60,500 (Jul 2026) |
| sovereign ai | 30 | 960 | 3,598 | **11,085** | 60,500 (Jul 2026) |
| local llm | 740 | 2,191 | 3,191 | **16,171** | 74,000 (Jul 2026) |
| self hosted ai | 204 | 366 | 565 | **3,750** | 14,800 (Aug 2026) |
| on premise ai | 43 | 83 | 142 | **3,735** | 18,100 (Aug 2026) |
| private chatgpt | 318 | 235 | 292 | **3,226** | 18,100 (Aug 2026) |
| self-hosted llm | 259 | 387 | 525 | 1,934 | 6,600 (Jul 2026) |
| offline ai | 158 | 417 | 758 | 1,842 | 2,900 (Jul 2026) |
| obsidian ai | 510 | 742 | 1,375 | 7,185 | 9,900 (Jul 2026) |
| notebooklm mcp | 0 | 0 | 82 | 1,091 | 1,900 (Mar 2026) |
| notebooklm alternative | 7 | 3,939 | 650 | 613 | 27,100 (Oct 2024) |
| ai podcast generator | 246 | 3,265 | 7,950 | 3,928 | 12,100 (Dec 2024) |
| run llm locally | 369 | 683 | 881 | 782 | 1,300 (Jan 2025) |
| notebooklm | 8,991 | 88,400 | 409,666 | 978,625 | 1,220,000 (Apr 2026) |

Three readings:

1. **The privacy cluster was growing 2-3x a year before 2026, then stepped up
   5-25x in July-August 2026, all in the same two months.** That is one cause,
   not six. The most likely one: *United States v. Heppner* (S.D.N.Y., 17 Feb
   2026), in which Judge Rakoff held that documents a defendant drafted with a
   consumer AI chatbot were not privileged, partly because the vendor's terms
   allowed retention, training and disclosure. Legal-industry coverage of the
   ruling ran through the summer alongside the order compelling OpenAI to
   produce 20 million ChatGPT logs in the copyright litigation, and much of it
   framed on-premise AI as the remedy. Whatever share of the step each event
   owns, the search behaviour is what matters here: buyers now type
   *private*, *on-premise* and *air-gapped* into Google, and the question they
   are answering is "can this be subpoenaed". That is the hook for a compliance
   page, and it is a factual statement a page can make without a legal claim:
   data that never leaves the machine has no third-party custodian.
2. **The step has held.** `recent` equals `volume` on `self hosted ai`,
   `on premise ai`, `air-gapped ai` and `private ai chatbot`, meaning the last
   three months are all at the new level. Plan on `recent`, not on the peak.
3. **Two clusters are past their peak.** `notebooklm alternative` was a moment
   in late 2024; `ai podcast generator` peaked December 2024 and has halved.
   Both still justify a page, neither justifies a bet.

## Where the demand is

Clusters in descending order of volume we could plausibly reach. Other
products' brand terms (`ollama` 135,000, `lm studio` 60,500, `msty` 49,500 and
falling, `open webui` 14,800, `anythingllm` 8,100, `jan ai` 4,400) are
navigational and only size the category.

### 1. Private, self-hosted, local, offline, air-gapped

Low difficulty, commercial intent, and CPCs from $4 to $27 confirming buyers
exist. Sorted by `recent`.

| keyword | volume | recent | kd | intent | cpc | trend | features |
|---|---|---|---|---|---|---|---|
| local llm | 9900 | 8100 | 24 | nav | 11.41 | +1956 | AIO PAA |
| private ai chatbot | 5400 | 5400 | **12** | comm | 4.31 | +4525 | PAA |
| best private ai | 5400 | 5400 | 15 | comm | 4.37 | (new) | AIO PAA |
| private ai | 8100 | 5400 | 14 | info | 4.08 | +3681 | AIO PAA forums |
| sovereign ai | 8100 | 3600 | 15 | info | 18.36 | +1275 | AIO PAA |
| secure ai | 3600 | 3600 | 19 | comm | **27.04** | +1985 | PAA |
| self hosted ai | 2900 | 2900 | **10** | comm | 13.88 | +2408 | AIO forums video PAA |
| private llm | 2900 | 2900 | 21 | info | 5.92 | +2414 | AIO PAA |
| on premise ai | 2400 | 2400 | 13~ | comm | 15.03 | +10547 | AIO PAA |
| self hosted llm | 2400 | 2400 | **5** | info | 12.77 | +1956 | forums AIO PAA |
| air-gapped ai | 1900 | 1900 | **9** | info | 21.78 | +20011 | AIO PAA video |
| private chatgpt | 1900 | — | 13 | nav | 2.83 | +6862 | AIO PAA |
| offline ai | 1600 | 1600 | **7** | info | 6.57 | +303 | AIO PAA forums video |
| local ai models | 1600 | 1600 | 18 | comm | 11.73 | +303 | AIO PAA video |
| best local llm | 1600 | 1600 | 8 | info | 20.65 | +90 | AIO PAA video |
| self-hosted llm | 1300 | 1300 | **2** | info | 4.27 | +817 | forums |
| on-premise ai | 1000 | 1000 | 18~ | comm | 16.42 | +4614 | PAA video |
| local ai server | 880 | 880 | 14 | comm | 13.30 | +9329 | AIO PAA video forums |
| on prem llm / on-premise llm | 720 | 720 | **1** | nav | 0 | +4809 | AIO PAA |
| best local ai | 720 | 720 | **5** | comm | 14.62 | +488 | AIO forums PAA video |
| airgap ai | 590 | 590 | 9 | info | 7.36 | +4809 | PAA video |
| private ai assistant | 590 | 210 | 10 | comm | 7.40 | +320 | AIO video PAA forums |
| offline ai chatbot | 390 | — | 19 | info | 4.44 | -18 | AIO PAA video |
| private ai app | 320 | 320 | 21 | comm | 9.43 | +875 | AIO PAA |
| offline llm | 260 | — | — | nav | 0 | -34 | AIO video PAA |
| best ai for privacy | 170 | — | 8 | comm | 1.29 | +55 | AIO forums PAA |
| local rag | 170 | — | 4 | info | 0 | — | AIO PAA video |
| most private ai | 140 | — | **1** | info | 0 | +89 | AIO forums PAA |

The five best head terms by opportunity score are `private ai chatbot`,
`best private ai`, `self hosted ai`, `on premise ai` and `best local ai`; the
softest real-volume terms are `on prem llm` (KD 1, held by AnythingLLM at
position 46), `self-hosted llm` (KD 2) and `self hosted llm` (KD 5). The
`best …` and `… chatbot` forms are worth noting: the head noun `private ai` is
split between encrypted-cloud consumer products and enterprise infrastructure
(see `05`), while `best private ai` and `private ai chatbot` are people
choosing a product.

`local ai` (4,400) is KD 62 against KD 7 for `offline ai`; the cheap synonyms
win. `run llm locally` has been flat at ~800 for two years while `local llm`
grew 20x; the noun is what people search, the how-to framing is saturated.

Supporting terms for the repo and blog rather than the landing page:

| keyword | volume | recent | kd | intent | cpc | trend |
|---|---|---|---|---|---|---|
| open source ai platform(s) | 14800 | 14800 | 36-45 | comm | **35.32** | +15757 |
| open source ai | 6600 | 6600 | 33 | info | 8.92 | +23 |
| open source ai assistant | 4400 | 3600 | 50 | info | 7.11 | +1157 |
| free llm | 1300 | — | 30 | info | 7.31 | +30 |
| open source llm model | 720 | — | 25 | info | 3.39 | +49 |
| how to run llm locally | 320 | — | 7 | info | 0 | -34 |
| how to run ai locally | 260 | — | 13 | info | 10.14 | +24 |
| self-hosted ai models | 140 | 140 | 23~ | comm | 12.62 | +133 |
| best self-hosted llm | 90 | — | 4 | comm | 6.84 | — |
| best self hosted ai | 70 | — | 9 | comm | 0 | +29 |
| self-hosted ai chatbot | 50 | — | **1** | comm | 7.75 | -57 |
| self hosted knowledge base | 50 | — | 25 | nav | 25.48 | +40 |

### 2. NotebookLM's unmet needs, the interception cluster

`notebooklm` itself is 823,000 a month (673,000 recent) at KD 64 and belongs to
Google. The modifiers people attach to it are requests for things it does not
do, and the full query family was pulled this time. Grouped by what the
searcher wants; the cluster tag is the one used in the master list.

**Pricing and limits** (`notebooklm-pricing`, 36 keywords, 9,140 recent):

| keyword | volume | recent | kd | intent | cpc | trend |
|---|---|---|---|---|---|---|
| is notebooklm free | 2900 | — | 36 | info | 6.73 | +19 |
| notebooklm pricing | 1300 | 1000 | **2** | comm | 5.29 | — |
| notebooklm price | 1300 | 1000 | **2** | comm | 5.29 | — |
| notebooklm pro | 880 | — | 40 | comm | 5.40 | -87 |
| notebooklm plus | 590 | — | 34 | trans | 3.13 | -83 |
| notebooklm for students | 590 | 390 | 21 | trans | 6.59 | +255 |
| notebooklm cost | 480 | — | **3** | info | 3.82 | -34 |
| how much is notebooklm | 320 | 260 | 10 | comm | 7.65 | +24 |
| how many sources can you add to notebooklm | 320 | 320 | **3** | info | 0 | +333 |
| notebooklm limits | 320 | — | 15 | info | 0 | -66 |
| notebooklm enterprise | 320 | 210 | 10 | nav | 7.15 | -73 |
| notebooklm student discount | 260 | 170 | 13 | comm | 6.37 | +133 |
| notebooklm plans | 210 | 210 | 13 | comm | 6.16 | +200 |
| notebooklm source limit | 210 | — | 16 | info | 0 | -35 |
| does notebooklm have a limit | 210 | 210 | 19 | info | 0 | +425 |
| notebooklm free for students | 210 | 140 | 16 | comm | 5.35 | +350 |
| notebooklm enterprise api | 210 | 70 | 16~ | info | 31.11 | +600 |

The `pro`/`plus` tier names are collapsing (-83 to -87%) while the limit
questions grow (+200 to +425%). People are hitting the source cap and the
per-day caps and asking whether paying removes them. A pricing page that
states NotebookLM's tiers and limits factually, then says SurfSense has no
source limit because the index is on your disk, answers the query it would
rank for. The honesty condition from the page brief still applies.

**Platform** (`notebooklm-install`, 18 keywords, 5,100 recent):

| keyword | volume | recent | kd | intent | cpc | trend |
|---|---|---|---|---|---|---|
| notebooklm app | 2900 | 2400 | 62 | trans | 3.30 | — |
| notebooklm download | 720 | 720 | 50 | trans | 3.85 | +175 |
| notebooklm desktop app | 320 | 260 | 36 | nav | 5.66 | -35 |
| notebooklm mac | 260 | 170 | 67 | trans | 15.64 | +143 |
| download notebooklm | 210 | 210 | 38 | trans | 3.31 | +133 |
| notebooklm for windows | 210 | 210 | 42 | trans | 10.03 | +420 |
| notebooklm mac app | 140 | 140 | 67 | nav | 11.69 | +57 |
| notebooklm desktop | 140 | 140 | 67 | nav | 3.42 | — |
| notebooklm windows / download windows | 90 | 90 | 37-41 | nav | 0 | +25 to +67 |
| notebooklm download for windows 11 | 70 | 70 | 41 | trans | 12.31 | — |

There is no NotebookLM desktop app; these are people asking for one. This is
the `/downloads` page's cluster, and `03-international.md` shows it is one of
the two brand intents with demand in all 26 markets, the other being the free
question (`notebooklm app` in every pull; `notebooklm download` 2,400/mo in
India, +400%).

**Trust** (inside `notebooklm-switch`):

| keyword | volume | recent | kd | intent | trend |
|---|---|---|---|---|---|
| notebooklm privacy | 140 | 50 | **6** | nav | -90 |
| is notebooklm private | 140 | 70 | **5** | info | -71 |
| notebooklm data privacy | 50 | 30 | 12 | nav | -91 |
| is notebooklm secure | 50 | 20 | **5** | info | -82 |
| is notebooklm safe | 30 | — | — | info | — |
| does notebooklm use my data | 10 | — | — | nav | — |

Small and falling, at KD 5-12. One post answers all six.

**Comparisons** (inside `notebooklm-switch`):

| keyword | volume | recent | kd | trend |
|---|---|---|---|---|
| notebooklm vs gemini / gemini vs notebooklm | 800 | 560 | 10-13 | -18 to -33 |
| notebooklm vs chatgpt | 320 | 170 | 6~ | -65 |
| notebooklm vs obsidian / obsidian vs notebooklm | 310 | 280 | 13~ | +143 |
| notion vs notebooklm / notebooklm vs notion | 280 | 180 | 8-9~ | -36 to -71 |
| notebooklm vs claude | 140 | 140 | 6~ | **+325** |
| notebooklm competitors | 140 | 70 | 8~ | -59 |
| notebooklm vs perplexity | 70 | 50 | 5~ | -57 |
| notebooklm vs onenote | 70 | 50 | 5~ | -55 |
| gemini notebook vs notebooklm | 70 | 70 | 24 | new |
| open notebook vs notebooklm | 40 | 30 | 13 | +200 |

Google appears to be renaming the product: `gemini notebooklm` is 590 and up
1,614%, and `gemini notebook vs notebooklm` has just appeared. Comparison copy
should carry both names.

**API and MCP** (`mcp`, 11 keywords, 52,200 recent, most of it the generic
`mcp server`):

| keyword | volume | recent | kd | intent | cpc | trend |
|---|---|---|---|---|---|---|
| mcp server | 60500 | 49500 | 34 | nav | 31.38 | -18 |
| notebooklm api | 1000 | 590 | 22 | info | 10.36 | -61 |
| notebooklm mcp | 720 | 720 | **1** | nav | **16.97** | **+556** |
| local mcp server | 590 | 320 | 30 | nav | **45.04** | — |
| llm mcp / mcp llm | 870 | 470 | 29-42 | info | 4-9 | -71 to -79 |
| notebooklm mcp server | 210 | 140 | **3** | nav | 16.80 | +367 |
| mcp host | 260 | 210 | 23 | nav | 21.07 | -64 |
| does notebooklm have an api | 110 | 70 | 15 | info | 0 | -71 |
| notebooklm mcp cli / notebooklm-mcp-cli | 90 | 90 | 9 | nav | 9.27 | — |

`notebooklm mcp` is still the single best keyword-to-capability match in the
research: KD 1, $16.97 CPC, +556%, and it went from zero to 1,091 average
monthly searches in 2026. Every current result automates a browser against
Google's product (`05-serp-landscape.md`); a native server is a different
category of answer. `notebooklm api` is shrinking (-61%) while
`notebooklm enterprise api` is +600%, so the API demand is moving to the
enterprise tier; "an API you can run locally" is the framing either way.

**Audio** is cluster 3 below. **Study and how-to** (`notebooklm-brand`, 198
keywords, 62,090 recent: `how to use notebooklm` 2,900, `what is notebooklm`
5,400, `notebooklm for studying` 590, `how to use notebooklm to study` 210) is
Google's own how-to demand. Not ours, except as the audience for a "do this
in SurfSense instead" post once a feature is at parity.

### 3. Studio outputs: podcast, then the other ten formats

The app ships twelve Studio formats
([`formats.py`](../../../surfsense_local/backend/modules/artifacts/formats.py)):
summary, document, slides, spreadsheet, web page, PDF, mind map, flashcards,
quiz, podcast, image and infographic; video is still being built. The first
pass sized podcast only. This section sizes all of them: 208 US terms through
Keyword Overview (196 returned), a 700-term discovery pull seeded with the
format names, SERP competitors across 28 heads, ten heads back to 2018, the
live `study guide maker` SERP, and the same list in the UK, India, Germany and
Japan (`03-international.md`, "Studio outputs abroad"). Archives are the
`*-artifact*` and `artifacts-*` files in `data/`.

#### Podcast

Post-peak, still worth one page. The head term halved from its December 2024
high and the whole cluster is 10,130 reported against 4,610 recent.

| keyword | volume | recent | kd | intent | cpc | trend | incumbent's position |
|---|---|---|---|---|---|---|---|
| ai podcast generator | 5400 | 2400 | 13 | comm | 6.42 | -65 | — |
| turn notes into podcast | 880 | 260 | 33~ | info | 8.43 | -46 | 54 |
| notebooklm podcast | 720 | 480 | 25 | nav | 4.77 | -45 | 38 |
| notebooklm podcast generator | 480 | 260 | 20 | nav | 5.74 | -56 | 5 |
| notes to podcast | 480 | 140 | 16 | info | 8.66 | -59 | 42 |
| ai podcast from notes | 480 | 110 | 14 | info | 9.60 | -73 | 61 |
| google (ai) podcast generator | 780 | 380 | 23-27 | info | 4.5 | -56 to -64 | 13-18 |
| notes into podcast | 320 | 70 | 37~ | info | 5.55 | -59 | 59 |
| notebooklm audio overview(s) | 140 | 140 | **5** | nav | 3.36 | +50 | — |

The incumbent, open-notebook.ai, holds the only dedicated podcast page in the
niche and most of its positions on these terms are 38-61 (`04-competitors.md`).
A feature page that says "generates the audio on your machine, no cloud TTS,
no per-minute cost" (Kokoro-82M is bundled) takes the soft ones. Do not promise
MP3; the builder emits WAV and no ffmpeg is bundled (pivot plan, C5).

#### The other ten, sized

Cluster totals from the master list. `recent` is the June-August median, which
for the study clusters is the trough (see the last column, term-time months
divided by summer months for the head term).

| format (builder) | keywords | 12-month | recent | median KD | term ÷ summer |
|---|---|---|---|---|---|
| slides (pptx) | 26 | 77,180 | 44,050 | 44 | 2.1x |
| study guide (the hub: summary + flashcards + quiz from one source set) | 24 | 79,920 | 25,190 | 26 | **5.2x** |
| flashcards | 22 | 64,320 | 30,930 | 31 | 3.4x |
| summary | 23 | 65,490 | 24,070 | 27 | 2.2x |
| quiz | 22 | 17,230 | 6,160 | 25 | **4.8x** |
| podcast | 14 | 10,130 | 4,610 | 22 | 1.4x |
| infographic | 9 | 3,450 | 2,430 | 45 | 1.1x |
| report (docx) | 7 | 3,110 | 2,100 | 30 | — |
| mind map | 10 | 3,200 | 1,990 | **70** | 2.0x |
| video (in progress) | 10 | 1,720 | 650 | 14 | — |
| spreadsheet (xlsx) | 5 | 1,270 | 820 | 14 | — |
| web page (html) | 1 | 90 | 50 | 3 | — |
| PDF, image | — | no demand of their own, see below | | | |

138,000 recent searches across the eleven clusters, but read the big rows
before adding them up: `pdf to ppt` (12,100 recent) is a file converter, not
slide generation; `study ai` (8,100) is mostly an app name; `flashcard
generator` and `flashcards for studying` (24,700 together) are Quizlet-shaped
demand for making cards by hand as much as for AI; the generic slide heads
(~31,000) are KD 43-84 and the generic summary heads (~20,000) are being
absorbed by the AI Overview. Strip all of that and the addressable figure is
35,000-60,000 recent depending on how much slide and summary demand you
count, 2-5x that in term time, mostly at KD 6-35.

Four things hold across all of it:

1. **The season is the plan.** `study guide maker` averaged 9,766 a month in
   the 2025-26 school year and 1,866 over summer 2026; `flashcard generator`
   39,777 against 11,533; `ai quiz generator` 4,133 against 863; `ai study
   tools` 8,555 against 2,033. October 2025 was the peak month for all four
   (14,800, 60,500, 6,600 and 12,100). Pages that are not indexed by
   mid-August miss the year's biggest window; the second window opens in the
   first week of January.
2. **"Study" is growing; generic "AI X generator" is not.** `study guide maker`
   averaged 523 a month in 2023, 1,894 in 2024, 7,050 in 2025; `ai study tools`
   218, 1,215, 5,483; `ai quiz generator` 465, 1,533, 3,566. The generic heads
   peaked and turned: `ai presentation maker` peaked at 40,500 in October 2024
   and is down 45% year on year; `ai summarizer` peaked at 49,500 in September
   2025 and is down 45%; `ai infographic generator` held at ~2,000 through
   2024-25 and is lower this year. The AI Overview now answers "summarise this" and "make me
   slides" directly; it does not answer "make me a study guide from these
   forty PDFs".
3. **NotebookLM's own artifact launches spike and decay.** `notebooklm mind
   map` went 20 → 1,900 in March 2025 and sits at 260; `notebooklm video
   overview` launched at 590 in May 2025, hit 1,300 in July-August and sits
   at 90. Launch news, not durable demand. The durable NotebookLM-branded terms here are the *study*
   ones: `notebooklm for studying` (590, +680%, CPC $14.29), `how to use
   notebooklm to study` (210, KD 6, +180%).
4. **These SERPs belong to edtech subscriptions, not to our niche.** The
   incumbents are RemNote, Knowt (135,000 brand searches a month), NoteGPT
   (49,500), StudyFetch (33,100), Quizlet, Revisely, Mindgrasp, Gamma
   (110,000) and Napkin (22,200). None is local, open source or offline; all
   are subscriptions; none of the local-AI competitors in `04-competitors.md`
   has a single one of these pages. The same *local, private, free* argument
   that carries the landing page is unclaimed here.

#### Study guide — the hub page

The format that does not exist as a single builder is the one with the
cleanest demand: a study guide is the summary, flashcards and quiz builders
run on the same source set. RemNote's #1 result is titled "AI Study Guide
Maker From Notes and PDFs" and its description promises exactly that bundle.

| keyword | volume | recent | kd | intent | cpc | trend | aio |
|---|---|---|---|---|---|---|---|
| study guide maker | 8100 | 1900 | **6** | comm | 4.10 | -21 | AIO |
| study guide generator | 2400 | 1600 | **7** | info | 8.76 | +233 | AIO |
| ai study guide maker | 2900 | 720 | 10 | comm | 6.74 | -45 | AIO |
| ai study guide | 590 | 260 | 16 | info | 5.48 | -19 | AIO |
| ai study guide generator | 320 | 110 | 37~ | info | 8.53 | — | AIO |
| ai study tools / ai study tool | 6600 each | 1900 each | 27 / 31 | info | 6.10 | +30 | — |
| best ai for studying | 1300 | 880 | 18 | comm | 6.85 | +49 | — |
| ai for studying | 880 | 390 | 25 | info | 5.73 | — | AIO |
| best ai study tools | 880 | 320 | 20 | comm | 5.43 | -19 | — |
| ai tools for students | 880 | 320 | 29 | comm | 4.38 | -75 | AIO |
| ai study assistant | 170 | 170 | 35 | info | 5.07 | +875 | AIO |
| notebooklm for studying | 590 | 320 | 31 | trans | **14.29** | +680 | AIO |
| how to use notebooklm to study | 210 | 170 | **6** | info | 4.08 | +180 | AIO |
| how to use notebooklm for studying | 70 | 50 | 5 | info | 0 | +150 | AIO |

Sizing-only rows: `study ai` (18,100, 8,100 recent, KD 22) is largely an app
name; `ai powered study companion` (3,600, +3782%, CPC 0, one record) is
unverified, same rule as `ai-powered research assistant`; `ai-powered study
tools` is one record reported under three spellings (8,100 each, 590 recent,
-89%) and counts once.

The live SERP (`05-serp-landscape.md`, fifth section): every organic result is
a dedicated feature page, the AI Overview sits at position 4 citing Quizlet,
StudyFetch, Scribe and Penseum, Reddit is at 10 (r/Teachers), and the PAA is
"How can I create my own study guide? · Can ChatGPT create a study guide? ·
Which study guide creator is the best? · Can AI create study guides from
PDFs?". KD 6 because the rankers are small: RemNote, Flint, StudyFetch,
Penseum, Scribe, NoteGPT, Quizgecko, Notesight, StudyPDF, Mindgrasp. A page
that opens "turn your notes and PDFs into a study guide, flashcards and a
practice quiz, on your laptop, free, nothing uploaded" is competitive on
day one; brief in `02-page-briefs.md`.

#### Flashcards

| keyword | volume | recent | kd | intent | cpc | trend | aio |
|---|---|---|---|---|---|---|---|
| flashcard generator | 33100 | 9900 | 42 | info | 2.12 | -18 | — |
| flashcards for studying | 14800 | 14800 | 47 | info | 1.73 | +311 | AIO |
| make flashcards | 6600 | 2900 | 39 | info | 2.56 | +26 | — |
| ai flashcard maker | 3600 | 1000 | 33 | trans | 2.91 | -46 | — |
| ai flashcards | 1600 | 480 | 37 | info | 3.33 | -46 | AIO |
| ai flashcard generator | 1000 | 480 | 31 | info | 3.84 | — | — |
| anki ai | 390 | 320 | 32 | info | **7.62** | — | AIO |
| pdf to flashcards | 320 | 110 | 34~ | info | 2.40 | -46 | AIO |
| turn notes into flashcards | 320 | 90 | 30 | info | 3.85 | — | AIO |
| make flashcards from notes | 260 | 70 | 24 | info | 2.83 | -47 | AIO |
| pdf to anki | 170 | 70 | **9** | info | 2.43 | -67 | AIO |
| notebooklm flashcards | 140 | 70 | 29 | nav | 8.19 | +40 | AIO |

`flashcard generator` peaked at 60,500 in October 2025 and has grown every
year since 2019 (3,484 → 28,408 monthly average). Owners: Revisely #1 on the
head and both AI forms, Quizlet #2-3, Knowt #3, anki-decks.com #2 on the AI
forms, RemNote #1 on `pdf to flashcards` with ChatPDF #2, Reddit at 4 on
both AI forms and on `pdf to flashcards`. The opening is the Anki family: `anki ai` and `pdf to anki`
are the cheapest terms in the cluster and nobody local serves them. The
builder emits front/back card JSON today; an Anki or TSV export would be a
small change with its own keywords, and is a product suggestion, not a
decision.

#### Quiz

| keyword | volume | recent | kd | intent | cpc | trend | aio |
|---|---|---|---|---|---|---|---|
| ai quiz maker | 2900 | 1300 | 30 | comm | 5.31 | -19 | — |
| ai quiz generator | 3600 | 1000 | 32 | info | 5.40 | -47 | — |
| quiz ai | 3600 | 1000 | 29 | info | 4.22 | -45 | — |
| ai quiz | 1300 | 880 | 45 | info | 4.52 | +164 | — |
| ai test generator | 1000 | 390 | **84** | info | 6.95 | -19 | — |
| ai question generator | 880 | 320 | 25 | info | 4.37 | -64 | — |
| quiz maker ai | 720 | 260 | 33 | comm | 6.00 | -18 | — |
| free ai quiz generator | 390 | 170 | 18 | info | 4.59 | -19 | AIO |
| practice test generator | 480 | 140 | 26 | info | 5.34 | — | — |
| pdf to quiz | 390 | 90 | 17 | info | 4.20 | -72 | AIO |
| ai practice test generator | 320 | 90 | 25 | info | 8.23 | — | AIO |
| quiz generator from pdf | 140 | 50 | 14 | info | 3.42 | -55 | AIO |
| notebooklm quiz feature | 140 | 140 | 29 | comm | 0 | — | AIO |

Owners: NoteGPT #1 on `ai quiz generator`, Quizlet #1 on `ai quiz maker`,
Jotform #2, Revisely #3, Smallpdf #4, Reddit 5-6; RemNote #1 on `pdf to
quiz`, Adobe #3. The "from PDF" forms are KD 14-17 and half the cluster's
CPC is above $5. Teachers are a second audience here (`ai test generator`,
`practice test generator`, r/Teachers on the study-guide SERP); the page copy
should say "quiz from your own material" rather than "test yourself".

#### Summary

| keyword | volume | recent | kd | intent | cpc | trend | aio |
|---|---|---|---|---|---|---|---|
| ai summarizer | 22200 | 6600 | 33 | comm | 3.95 | -45 | — |
| youtube video summarizer | 8100 | 4400 | 30 | info | 2.96 | -33 | — |
| summary ai | 5400 | 3600 | 32 | info | 3.39 | +23 | AIO |
| summarize ai | 9900 | 2900 | 46 | info | 5.12 | -76 | — |
| summarize youtube video | 3600 | 1900 | 26 | info | 3.05 | -47 | — |
| article summarizer | 5400 | 1300 | 34 | info | 4.03 | -64 | — |
| pdf summarizer | 4400 | 880 | **14** | info | 4.57 | -80 | — |
| ai pdf summarizer | 1300 | 320 | 23 | comm | 5.47 | -93 | AIO |
| document summarizer | 590 | 210 | 31 | info | 6.19 | -46 | AIO |
| research paper summarizer | 170 | 70 | 31 | info | 9.56 | -59 | AIO |

The whole cluster is falling, -45% to -93%, because the AI Overview and the
chat apps now do this inline. Owners: QuillBot #1 on `ai summarizer`, Adobe #1
on both PDF forms with ChatPDF, iLovePDF and Smallpdf behind it, Knowt at 4.
Not a standalone page. Two uses: the YouTube forms are the part holding best
(6,300 recent, 11,700 over the year, KD 26-30, down a third rather than three
quarters) and the app ingests YouTube, so the sources page gets an H2 for it;
and "summary" is the first line of the study-guide bundle, where it needs no
keyword of its own.

#### Slides

| keyword | volume | recent | kd | intent | cpc | trend | aio |
|---|---|---|---|---|---|---|---|
| pdf to ppt | 18100 | 12100 | 34 | info | 0.80 | -33 | — |
| ai presentation maker | 9900 | 5400 | 54 | comm | 9.24 | -45 | — |
| ai ppt generator / ai powerpoint generator | 6600 each | 3600 each | 54-55 | trans | 9.99 | -56 | — |
| ai slide generator / ai slides generator | 4400 each | 2400 each | 43-44 | trans | 7.84 | -17 | — |
| ppt ai | 4400 | 2900 | 54 | info | 7.61 | -45 | — |
| slides ai | 5400 | 1900 | 62 | trans | 6.58 | -71 | — |
| ai slide maker | 3600 | 1900 | 66 | trans | 8.05 | -32 | — |
| ai ppt maker | 2400 | 1300 | 66 | trans | 10.06 | -46 | AIO |
| ai presentation generator | 1300 | 1000 | 55 | info | 10.53 | +233 | AIO |
| best ai presentation maker | 1000 | 720 | 36 | comm | **15.76** | -41 | AIO |
| notebooklm slides / slide deck / slide | 170-210 | 90 each | 15-39 | nav | 5.19-7.69 | +150 where reported | AIO |
| notebooklm ppt / presentation / powerpoint | 70-170 | 40-70 | 12-22 | nav | 4.67-6.71 | +100 to +300 | AIO |

The most expensive artifact cluster ($8-16 CPC) and the hardest: Canva #1 and
Adobe #2 on `ai presentation maker`, Slidesgo #1 on `ai slides generator`,
Manus #3, Gamma with 110,000 brand searches. `pdf to ppt` is a converter
query owned by iLovePDF, Adobe, Canva and Smallpdf; not ours. The US entry is
the NotebookLM-branded set, small but KD 12-39 and all growing; the real
slides opportunity is Japan (`スライド 作成 ai`, 14,800 at KD 15) and Germany
(`präsentation erstellen ki`, 5,400 at KD 11), covered in
`03-international.md`.

#### Infographic

| keyword | volume | recent | kd | intent | cpc | trend | aio |
|---|---|---|---|---|---|---|---|
| ai infographic generator | 1600 | 1600 | 47 | info | 8.73 | +46 | AIO |
| infographic ai | 590 | 210 | 45 | info | 13.33 | -64 | AIO |
| ai infographic maker | 320 | 140 | 46 | comm | 8.16 | -59 | AIO |
| free ai infographic generator | 260 | 140 | 45 | info | 8.77 | -35 | AIO |
| notebooklm infographic | 210 | 110 | **10~** | nav | 11.70 | **+800** | AIO |
| infographic maker ai | 210 | 110 | 37 | comm | 9.46 | -59 | AIO |

No season (1.1x), so this is business demand. Venngage #1, Canva #2,
Piktochart #4, Napkin the new entrant. The generic heads are KD 45; the entry
is `notebooklm infographic` (KD 10~, +800%, and 880 in Japan), which is Google
having launched the format in 2025 and users looking for it. One H2 on the
study-guide or podcast page, not a page of its own until the branded term
holds.

#### Mind map, report, spreadsheet, web page, PDF, image

- **Mind map** is KD 65-78 across the board (`mind map ai` 1,000, `mind map
  generator free` 880, `ai mind map generator` 260): mindmapai.app #1 on
  both heads, then the Play Store, Xmind and Canva. Only `notebooklm mind
  map` (320, 260 recent, KD 7~) and `mind map notebooklm` (70, KD 11) are
  reachable, and Xmind ranks #3 for the first with a blog post, behind Reddit
  at 2. That is the format: a blog post, not a feature page.
- **Report (docx)**: `literature review ai` (720, KD 17, $8.46, AIO) is a
  research-blog term; `ai report generator` (480, KD 35~, **$15.73**) and `ai
  report writer` (320, $14.42) are small and expensive; `ai document
  generator` (1,300) is KD 65. India has `ai report generator` at 1,600 and
  KD 7. One docs page, and the literature-review post.
- **Spreadsheet (xlsx)**: `ai spreadsheet generator` 480 (KD 14, **$18.01**),
  `pdf table extractor` 480 (KD 17), `ai excel generator` 170 (KD 8). Tiny,
  cheap, and the highest CPCs in the artifact set. One docs page titled for
  "extract tables from your PDFs into a spreadsheet".
- **Web page (html)**: `ai html generator` 90 at KD 3. Docs page.
- **PDF**: `ai pdf generator` (390, KD 5, +23%) and `ai pdf maker` (260,
  KD 14) mean "make me a PDF with AI", which every format here already is.
  Mention it on each format's page; no page.
- **Image**: bring-your-own-key, and generic image-generation demand (`ai
  image generator`, 823,000) is excluded from this research on purpose.
  Nothing to build.

#### Video, when it ships

`notebooklm video overview(s)` (390 + 260, now 110 + 90 recent, **KD 5**,
-93% and -96% from an August 2025 peak of 1,300), `notebooklm video` 210,
`notebooklm cinematic video overview(s)` 110 + 110 (new this year), `pdf to
video ai` 170 (KD 30~). Google's branded term is decaying at KD 5, so when the
builder exists an "offline video overview" page is a cheap intercept. Until
then there is no page, and no page mentions it; the plan lists video under
"After the MVP".

### 4. Compliance, the highest CPCs in the research

New cluster this pass, and the one the Heppner coverage feeds directly.

| keyword | volume | recent | kd | intent | cpc | trend | features |
|---|---|---|---|---|---|---|---|
| hipaa compliant ai | 4400 | 4400 | 34 | nav | **46.33** | +2610 | AIO PAA |
| secure ai | 3600 | 3600 | 19 | comm | 27.04 | +1985 | PAA |
| hipaa compliant chatgpt | 390 | 260 | 27 | info | **63.56** | -33 | AIO PAA |
| ai for legal documents | 140 | 110 | 10 | comm | **82.76** | -57 | PAA forums |
| most secure ai | 70 | 70 | 11 | comm | 24.43 | +80 | AIO PAA forums |
| gdpr compliant ai (UK) | tiny | | | | 23.45 | | |
| dsgvo konforme ki (DE) | 260 | | | | 8.47 | +256 | |

$46-83 CPCs on a developer-tool budget mean these are bought by firms, not
hobbyists. The page for this cluster has to be careful: "HIPAA compliant" is a
claim about the deployer's controls, not a property software can have on its
own, so the page says what is true, that nothing leaves the machine, that there
is no vendor log to subpoena, that the deployer keeps custody, and lets the
reader draw the compliance conclusion. Legal review before publishing; that
condition is recorded in the brief.

### 5. Research and knowledge work

Blog and docs territory. `obsidian ai` is the standout: KD 16, a $24.47 CPC,
+662%, and Obsidian's audience is already local-first and own-your-files.

| keyword | volume | recent | kd | intent | cpc | trend |
|---|---|---|---|---|---|---|
| ai-powered research assistant | 27100 | 27100 | 33 | comm | 5.99 | +1258 (spike, **verify**) |
| obsidian ai | 4400 | 4400 | 16 | info | **24.47** | +662 |
| ai for researchers | 4400 | 2900 | 53 | comm | 10.57 | -19 |
| ai note taking app | 3600 | — | 19 | trans | 8.69 | -33 |
| best ai for research | 2400 | 2400 | 19 | comm | 11.32 | — |
| ai research assistant | 1900 | 1600 | 58 | info | 9.72 | -63 |
| literature review ai | 720 | — | 17 | info | 8.46 | -46 |
| ai second brain | 390 | 390 | 16 | info | 9.11 | +700 |
| lm studio alternative | 390 | — | **5** | nav | 14.71 | +50 |
| second brain app | 260 | 260 | **3** | nav | 5.27 | +24 |
| ai for academic research | 210 | 140 | 42 | comm | 11.66 | -46 |
| anythingllm alternative | 70 | — | — | info | 13.21 | +57 |

`ai-powered research assistant` at 27,100 arrived in the discovery pull with a
spike flag and no history; it is either a Google Ads grouping artefact or a
news moment. Re-pull it before anyone builds for it.

### 6. Category and brand

| keyword | volume | recent | kd | intent | note |
|---|---|---|---|---|---|
| notebook ai | 8100 | — | 45 | trans | open-notebook holds position 5 |
| ai notebook | 2400 | 1300 | 22 | trans | open-notebook holds position 16 |
| llm notebook | 4400 | — | 41 | nav | |
| surfsense | 590 | 590 | 7 | comm | +127%, $7.66 CPC, someone bids on it |
| surfsense ai | 90 | 90 | 8 | info | +4700% |
| surfsense github | 50 | — | 5 | nav | |

Brand demand exists and is growing, and the landing page holds position 1 for
it today (`ranked-surfsense.json`). Whatever the rebuild does to `/`, that
position and the `surfsense` title tag have to survive it.

## The master list

`data/master-keywords.csv`: 565 keywords with volume ≥ 40 that fall into a
cluster, scored `log10(recent) × (100-KD)/100 × intent weight × trend factor
× 10`. The score exists to sort, not to be quoted; a 30 is worth doing before a
15. Rows the regexes could not place are dropped (`--drop-other`), and the
assignment is wrong for maybe one row in twenty, so treat the `cluster` and
`page` columns as a first pass to correct in the CSV, not as decisions.

| cluster | keywords | recent volume | median kd | page |
|---|---|---|---|---|
| notebooklm-nav | 8 | 715,370 | 52 | not ours, brand navigation |
| competitor | 32 | 435,310 | 22 | compare pages, sizing only (now includes the edtech set: knowt, gamma, notegpt, studyfetch, napkin, quizlet) |
| research | 7 | 64,140 | 42 | blog (27,100 of it is the unverified term above) |
| notebooklm-brand | 175 | 59,910 | 24 | blog, NotebookLM how-to, low priority |
| mcp | 11 | 52,200 | 22 | `/mcp-server` (49,500 of it is generic `mcp server`) |
| slides | 26 | 44,050 | 44 | slides: US branded terms only, JP and DE pages (section 3) |
| open-source | 5 | 40,520 | 36 | repo and landing |
| flashcards | 22 | 30,930 | 31 | flashcards feature page |
| study | 24 | 25,190 | 26 | study-guide hub page |
| summary | 23 | 24,070 | 27 | H2 on sources page; no page of its own |
| **private** | 11 | **21,940** | **14** | landing |
| **self-hosted** | 15 | **16,170** | **10** | landing |
| **local** | 13 | **14,630** | **14** | landing |
| notebooklm-pricing | 36 | 9,140 | 15 | `/pricing` |
| compliance | 5 | 8,440 | 19 | compliance page |
| **offline** | 12 | **7,440** | **9** | landing |
| quiz | 22 | 6,160 | 25 | quiz feature page |
| category | 2 | 5,700 | 34 | landing |
| notebooklm-install | 18 | 5,100 | 46 | `/downloads` |
| pkm | 3 | 5,050 | 16 | blog |
| podcast | 14 | 4,610 | 22 | podcast feature page |
| notebooklm-switch | 31 | 3,480 | 9 | landing and comparison posts |
| infographic | 9 | 2,430 | 45 | H2, until `notebooklm infographic` holds |
| report | 7 | 2,100 | 30 | docs page and literature-review post |
| mindmap | 10 | 1,990 | 70 | blog post |
| rag | 4 | 880 | 26 | sources feature page |
| spreadsheet | 5 | 820 | 14 | docs page |
| brand | 3 | 720 | 7 | landing |
| download | 1 | 720 | 59 | `/downloads` |
| video | 10 | 650 | 14 | nothing until the builder ships |
| webpage | 1 | 50 | 3 | docs page |

The four bold rows are the landing page's addressable demand: about 60,000
recent monthly searches at median KD 9-14. Everything above them in the table
is either not ours, dominated by one generic head term, or (the artifact
clusters) sized in its summer trough; section 3 says which rows of those
clusters to count.

## Who owns these SERPs

A SERP-competitors pull across 18 target keywords, by how many of those
keywords each domain appears for:

| domain | keywords (of 18) | avg position | what it is |
|---|---|---|---|
| reddit.com | **16** | **2.9** | UGC |
| youtube.com | 16 | 9.1 | video |
| medium.com | 13 | 14.5 | UGC |
| **github.com** | **11** | **5.7** | repos |
| linkedin.com | 8 | 25.5 | UGC |
| play.google.com | 6 | 7.8 | app store |
| news.ycombinator.com | 6 | 13.3 | UGC |
| dev.to | 7 | 28.0 | UGC |
| xda-developers.com | 4 | 3.0 | tech press |
| localai.io | 3 | 17.7 | vendor |

Reddit is top three for sixteen of eighteen, #1 for `self hosted ai`,
`offline ai`, `local llm`, `local rag`, `on premise ai` and
`offline ai assistant`. GitHub is #1 for `open source notebooklm`,
`local notebooklm`, `notebooklm mcp` and `notebooklm api`. Vendor marketing
pages appear from position 15.

The artifact SERPs are a different country. The same pull across the 28
Studio heads (`data/artifacts-serp-competitors.json`, top 40 of 854 domains):

| domain | keywords (of 28) | median position | what it is |
|---|---|---|---|
| youtube.com | 27 | 11 | video |
| reddit.com | 24 | **5** | UGC |
| notegpt.io | 19 | 13 | edtech SaaS, one page per artifact |
| adobe.com | 16 | 8 | Acrobat's free tools |
| play.google.com | 15 | 9 | app store |
| canva.com | 15 | 11 | design SaaS |
| mindgrasp.ai | 15 | 19 | edtech SaaS |
| studyfetch.com | 12 | 8 | edtech SaaS |
| **remnote.com** | 11 | **2** | edtech, `/feature/<artifact>-maker` pages |
| quizlet.com | 10 | 3 | edtech |
| revisely.com | 7 | 3 | edtech, UK |

GitHub is absent: these results pages are product pages, not repositories,
so the repo does nothing for them and the feature pages have to rank on their
own. Reddit is still at median 5 and #1 on `best ai for studying`,
`notebooklm for studying` and `literature review ai`. RemNote's median
position of 2 across eleven terms comes from one page per artifact, each
titled for the job (`/feature/study-guide-maker` is "AI Study Guide Maker
From Notes and PDFs"); that is the template.

Three consequences:

1. **The GitHub repo is an SEO surface.** Description, README first paragraph
   and topics are the on-page SEO for `open source notebooklm`,
   `local notebooklm` and `notebooklm mcp`. It costs nothing and DataForSEO's
   crawler currently sees four pages on surfsense.com.
2. **A landing page will not win head terms on copy.** Budget it for
   conversion; its search traffic arrives from the repo, coverage, the blog and
   brand. Do not measure B6 on head-term rankings.
3. **AI Overviews and forums are on most target SERPs**, so being cited and
   being present matter more than blue-link optimisation. Full per-term reading
   in `05-serp-landscape.md`; the short version is that the Overview cites
   Reddit, YouTube, GitHub, registries and vendors whose pages open with a
   direct answer.

## The AI Overview on `open source notebooklm`

Present at absolute position 3 on 14 Sep 2026 and entirely about the
competitor `open-notebook` by lfnovo. Its citations: the repo, open-notebook.ai,
elephas.app's review, kdnuggets.com, xda-developers.com and two YouTube
walkthroughs. No vendor landing page, no pricing page, no ad. Getting into that
answer needs a clear repo, a docs site with declarative feature pages, and
third-party coverage, the same three things that rank organically. XDA,
KDnuggets, MakeUseOf, The New Stack and Android Authority already publish in
this niche and are Overview sources.

People Also Ask on that SERP, each a post title:

- "Is there an open-source alternative to Google NotebookLM?"
- "Is there a free version of NotebookLM?"
- "Can I run NotebookLM locally?"
- "Which AI is fully open-source?"

Related searches: *open source notebooklm github*, *…alternative*, *…reddit*,
*Open Notebook vs NotebookLM*, *…free*, *NotebookLM GitHub*, *Local NotebookLM*.

## Our baseline, and the `/free` decision

surfsense.com ranks for **425 keywords**. The top 200 by landing page:

| url | keywords | combined volume | etv | best position |
|---|---|---|---|---|
| **/free** | **193** | **435,390** | **$2,060** | 3 |
| / | 6 | 1,610 | $182 | 1 |
| /google-search | 1 | 140 | $0.29 | 63 |

Essentially the whole footprint is one page. Authority-wise the domain has 136
dofollow referring domains; the raw 29,517 backlinks are one `.net` footer
(`04-competitors.md`).

**435,390 is a vanity number.** Split `/free` by position band — both tables
below are `python data/parse.py --mode baseline ranked-surfsense.json.gz`:

| band | keywords | volume | share of volume | etv | share of etv |
|---|---|---|---|---|---|
| top 3 | 2 | 1,620 | 0.4% | $158 | 7.6% |
| top 10 | 31 | 29,450 | 6.8% | $980 | 47.5% |
| 11-20 | 55 | 51,950 | 11.9% | $322 | 15.6% |
| 21+ | 107 | 353,990 | **81.3%** | $759 | 36.9% |

Four fifths of the volume sits on page three or worse, where it earns almost
nothing per impression. The 31 top-10 keywords are 6.8% of the volume and
carry nearly half the page's estimated value.

**That value is one cluster.** Split the same 193 keywords by what they ask for:

| cluster | keywords | volume | etv | share of etv | top-10 positions |
|---|---|---|---|---|---|
| no sign up / no login / no account | 120 | 117,320 | **$1,285** | **62.4%** | **28 of 31** |
| generic heads, brand terms, the rest | 73 | 318,070 | $775 | 37.6% | 3 of 31 |

The page ranks where it makes a specific promise and drifts to page three
where it does not. `chat free no sign up` (6,600, position 6, $223) is the
single most valuable keyword on the site after the unwinnable `free ai` head;
`free ai no sign-up` holds position 3, `ai without login` position 3,
`ai chat no signup` (9,900) position 10. Meanwhile `free ai chat` (33,100)
sits at 31 and `free chatbot` (14,800) at 36 — heads no one in this category
wins.

The hosted-brand terms are the smallest slice of all: 27 keywords
(`chatgpt without login`, `claude ai without login`, `chatgpt free no login`),
**3.2% of the volume and 4.9% of the value — $101** — at positions mostly in
the teens.

### Decision: keep `/free`, re-point it at the cluster it wins

Closed; recorded in [`../portal/02-pages.md`](../portal/02-pages.md), with the
build sheet in [`02-page-briefs.md`](02-page-briefs.md). The page keeps its URL
and is rewritten. It is not unpublished, and not redirected to `/downloads`.
The data gives three reasons:

1. **The winning claim survives the pivot and gets stronger.** The 62% cluster
   asks for AI with no account, no signup, no registration. The hosted page
   answered that with 500,000 free tokens and a "Create Free Account" CTA — a
   login wall one step back. The desktop app has **no account at all**, no
   token cap and no quota, and its bundled Ollama will pull Qwen3 0.6B in
   0.5 GB, so a visitor with no API key and no email address can genuinely
   chat for free. Same query, a better answer than the page gives today.
2. **The slice that would need a claim the app cannot make is worth $101.**
   Nothing in the new product hosts GPT-4, Claude or Gemini. Writing the page
   around those brands would put the domain's whole footprint — and the 565
   keywords in this document, which all live on the same hostname — behind
   4.9% of one page's estimated value. Google's site-reputation and
   scaled-content policies act at the domain level, and the page also carries
   live AdSense units, which are a separately revocable account.
3. **Unpublishing or redirecting discards the 62%.** Both keep some domain
   signal and neither keeps the intent. A rewrite keeps the URL's history, the
   cluster, and a conversion path the visitor actually wanted.

What this costs, stated plainly: the generic heads (`free ai` at 28,
`free ai chat` at 31, `free chatbots` at 17) and most of the brand terms will
go. They are ~73% of the headline volume and ~38% of the value, they were
never convertible, and the positions were not real traffic. The 12 months
after the rewrite should be measured on the no-signup cluster, not on the
435,390.

**One build constraint follows from all of it**, and it is in the brief: every
claim on the page has to be true of the shipped app, so the model roster
renders from
[`curated-models.json`](../../../surfsense_local/backend/modules/llm/recommendations/curated-models.json)
rather than a hand-kept list. A page that cannot advertise a model the app
cannot run cannot drift back into the hosted-era copy.

## What the competitors tell us

The full teardown is [`04-competitors.md`](04-competitors.md). The findings
that change what gets built:

- **The SEO incumbent has 161 dofollow domains and five crawled pages.**
  open-notebook.ai wins on relevance, a repo and third-party coverage, not
  authority. The gap between us and them is content.
- **Docs pages rank, marketing pages do not.** AnythingLLM's, Jan's and
  OpenWebUI's footprints are integration docs (one page per model provider,
  named for it), feature pages titled for the feature, and Jan's four blog
  formats: `<X> alternatives`, `run <model> locally`, an evergreen local-AI
  guide, and the answer-shaped "you can't do X offline, do this instead" that
  the `offline ai` AI Overview cites.
- **Page count without query-shaped titles does not rank.** Khoj: 1,671 pages,
  15 ranking keywords, 12 of them its brand.
- **Soft positions on our vocabulary:** `on prem llm` held at 46,
  `private llm` at 10, `local ai models` at 18, `notes to podcast` at 42,
  `ai podcast from notes` at 61.

Two wedges the SERP text itself hands us: press coverage of open-notebook
repeatedly cites Docker and env-var setup as the price of entry, and SurfSense
2.0 ships signed native installers; XDA's complaint that NotebookLM is
"Gemini-only, no way to override the choice" is the bring-your-own-model
argument in a reviewer's words. `openalternative.co/alternatives/notebooklm`
already lists "Open-Notebook, **SurfSense**, and Deta Surf" on page 2 of
`open source notebooklm`.

## What not to target

- **`airgapped ai` as one word.** Write "air-gapped"; the one-word form is 10
  searches, the hyphenated form is 1,900.
- **`notebooklm` (823,000, KD 64) and other product brands.** Navigational.
- **`local ai` (4,400, KD 62)** over `offline ai` (KD 7) and `self hosted ai`
  (KD 10) for the same meaning.
- **The "chat with pdf" family.** `chat with pdf` is 390 and down 76%;
  `chat with your documents` is 10. This was the product's 2023 framing and
  the language moved on; `document intelligence` (590, KD 23, $14.80) is what
  replaced it in commercial search.
- **`ai research assistant` (1,900, KD 58)** against funded SaaS.
- **NotebookLM misspellings** (`lm notebook` 22,200, `noteboom`, `no book lm`).
  The incumbent ranks for them by accident; they convert at nothing.
- **Programmatic pages that need a data feed** (OpenWebUI's leaderboard and
  per-model pages). No data source, no purchase intent.
- **`ai-powered research assistant`** until the 27,100 is confirmed by a
  second pull.
- **Generic how-to for Google's product** (`how to use notebooklm`, 2,900).
  Their audience, their documentation. The exception is the study how-to
  (`how to use notebooklm to study`, KD 6, +180%; `notebooklm for studying`,
  +680%), which is the interception path for the study-guide page.
- **Generic mind-map, presentation and summariser heads.** `mind map ai`
  (KD 78), `ai presentation maker` (KD 54, $9.24), `ai summarizer` (KD 33 and
  falling 45% a year) are owned by Canva, Adobe, QuillBot and mindmapai.app.
  Take the NotebookLM-branded and "from PDF" forms instead (section 3).
- **File converters.** `pdf to ppt` (18,100 here, 201,000 in India), `pdf to
  excel ai`: iLovePDF, Adobe and Smallpdf territory, and nobody who types
  them wants generated slides.
- **Generic generators for formats we only incidentally produce, and
  homework.** `ai image generator` (823,000, KD 69), `text to video ai`
  (8,100, KD 51), `ai homework helper` (60,500, KD 54), `homework ai`
  (27,100). Excluded from the master list by the parser's rules.

## Re-running this

```bash
cd plans/community-local/seo/data
python parse.py --self-check
python parse.py keyword-overview-curated.json                    # hand-picked targets
python parse.py keyword-overview-variants.json                   # spellings: air-gap, on-prem, private
python parse.py keyword-overview-notebooklm-family.json          # the NotebookLM query family
python parse.py keyword-overview-verticals.json                  # compliance, ollama, homelab
python parse.py --mode history historical-head-terms.json        # the multi-year table
python parse.py keyword-overview-artifacts.json.gz               # the 196 Studio-output terms
python parse.py --mode history historical-artifact-terms.json    # study seasonality, back to 2018
python parse.py --mode serp serp-study-guide-maker.json          # the study-guide SERP
python parse.py --mode urls ranked-surfsense.json                # our footprint by page
python parse.py --mode baseline ranked-surfsense.json.gz         # the /free bands and clusters below
python parse.py --mode score --drop-other --min-volume 40 --csv master-keywords.csv \
    "keyword-overview-*.json" "keyword-ideas-*.json" "keyword-suggestions-*.json"
```

The DataForSEO calls behind each file are in [`data/README.md`](data/README.md).
Volumes drift, and this year they jumped; re-pull before deciding on a number
that matters. `notebooklm mcp`, the air-gap terms and anything with a `spike`
flag are moving fast enough that a six-month-old reading is worthless.
