# Competitors: authority, footprints and the patterns that rank

Who holds the search results we want, how much authority they have, which of
their pages do the work, and which of their positions are soft enough to take.
Companion to [`01-keyword-research.md`](01-keyword-research.md) (demand) and
[`05-serp-landscape.md`](05-serp-landscape.md) (what the results pages want).

**Source:** DataForSEO, 14 Sep 2026, Google US. Backlink summaries via
`backlinks/summary/live`; footprints via `dataforseo_labs/google/ranked_keywords/live`;
gaps via `dataforseo_labs/google/domain_intersection/live` with
`intersections: false` (keywords they rank for that `surfsense.com` does not).
Files and render commands are at the end.

## Authority: we are not the underdog we look like

`referring domains` counts distinct sites linking in. `dofollow domains`
subtracts the nofollow ones and is the closest single number to what Google
weighs. Raw `backlinks` is listed only to show why it misleads.

| domain | backlinks | ref domains | dofollow domains | crawled pages | first seen |
|---|---|---|---|---|---|
| openwebui.com | 44,102 | 3,736 | **2,827** | 2,845 | 2019 |
| jan.ai | 23,007 | 2,598 | **1,899** | 365 | 2023-11 |
| anythingllm.com | 16,869 | 2,251 | **1,600** | 457 | 2023-08 |
| msty.app | 12,362 | 607 | 442 | 118 | 2024-03 |
| khoj.dev | 7,940 | 687 | 398 | 1,671 | 2023-07 |
| open-notebook.ai | 5,711 | 528 | 161 | **5** | 2024-11 |
| **surfsense.com** | 29,517 | 250 | **136** | **4** | 2023-10 |

Three readings:

- **Our 29,517 backlinks are one site.** 16,775 come from `.net` domains and
  19,080 of 22,662 referring pages are nofollow — a sitewide footer or a scraper
  mirror. The real number is 136 dofollow domains. Anyone quoting the raw
  backlink count for surfsense.com is quoting noise.
- **The SEO incumbent has barely more authority than us.** open-notebook.ai wins
  the AI Overview on `open source notebooklm` and ranks 31 keywords from one
  feature page with 161 dofollow domains and **five crawled pages**. It wins on
  relevance, a repo and third-party coverage — not on links. That is the
  encouraging finding in this file: the gap to the incumbent is content, not
  authority.
- **The tools with real authority earned it with docs.** OpenWebUI, Jan and
  AnythingLLM have 365–2,845 crawled pages and an order of magnitude more
  linking domains. Khoj is the counter-example: 1,671 pages and 398 domains, yet
  it ranks for 15 keywords, 12 of them its own brand. Pages that are not named
  for what people search do not rank, however many there are.

DataForSEO's crawler sees **four pages** on surfsense.com. Whatever else the
rebuild does, it has to leave a site with more than four indexable URLs.

## Footprints: which pages carry each competitor

### open-notebook.ai — the SEO incumbent

Covered in `01-keyword-research.md` (113 keywords on `/`, 31 on
`/features/podcast` at best position 2). The gap pull adds the detail that
matters: **their podcast positions are soft.**

| keyword | volume | kd | their pos | their page |
|---|---|---|---|---|
| notebook ai | 8,100 | 45 | 5 | / |
| ai notebook | 2,400 | 22 | 16 | / |
| turn notes into podcast | 880 | — | **54** | /features/podcast |
| notebooklm podcast | 720 | 25 | 38 | /features/podcast |
| notebooklm podcast generator | 480 | 20 | 5 | /features/podcast |
| notes to podcast | 480 | 16 | **42** | /features/podcast |
| ai podcast from notes | 480 | 14 | **61** | /features/podcast |
| notebook search | 480 | 13 | 18 | /features/search |
| google podcast generator | 390 | 27 | 13 | /features/podcast |
| notes into podcast | 320 | — | **59** | /features/podcast |

Positions 38–61 at KD 14–25 (or unscored) are not held; they are the best
result Google could find. A podcast feature page that states the offline, no-cloud-TTS claim
plainly takes these. The rest of their 93-keyword gap is NotebookLM
misspellings on the homepage (`lm notebook` 22,200, `note book lm` 6,600,
`no book lm`, `noteboom`) — accidental, low intent, not worth copying.

### anythingllm.com — the docs-that-rank model

206 keywords they rank for that we do not. Grouped by what the ranking page is:

| pattern | example | volume | kd | their pos | their page |
|---|---|---|---|---|---|
| provider integration docs | perplexity.ai | 368,000 | 43 | 52 | /setup/llm-configuration/cloud/perplexity-ai |
| | anthropic llm | 590 | 41 | 6 | …/cloud/anthropic |
| | bedrock llm | 320 | 24 | 6 | …/cloud/aws-bedrock |
| | gemini llm | 1,000 | 66 | 18 | …/cloud/google-gemini |
| feature docs | transcription models | 880 | 30 | 27 | /features/transcription-models |
| | agent flows | 320 | 4 | 5 | /agent-flows/overview |
| | llm mcp | 390 | 29 | 11 | /mcp-compatibility/overview |
| category terms on `/` | **private llm** | 1,600 | 21 | **10** | / |
| | **local ai models** | 1,600 | 18 | **18** | / |
| | free llm | 1,300 | 30 | 7 | / |
| | **on prem llm** | 720 | **1** | **46** | / |
| | open source llm model | 720 | 25 | 15 | / |

Two lessons. A docs page per third-party provider captures that provider's
brand demand — `perplexity.ai` at 368,000 is mostly navigational and not
winnable, but `anthropic llm` at position 6 is real. And the category leader
holds `private llm` at 10, `local ai models` at 18 and `on prem llm` at 46 —
weak positions on exactly our vocabulary. `on prem llm` at KD 1 is unclaimed
by anyone.

### jan.ai — the blog patterns

| url | keywords | volume | best pos | what it is |
|---|---|---|---|---|
| / | 66 | 366,910 | 1 | brand (`jan ai` 4,400) plus category terms |
| /docs/desktop/remote-models/openrouter | 8 | 149,010 | 8 | ranks for `openrouter` — provider docs again |
| /post/deepseek-r1-locally | 3 | 10,480 | 9 | "run <hot model> locally" |
| /post/chatgpt-alternatives | **37** | 9,670 | 6 | "X alternatives" listicle |
| /post/run-ai-models-locally | 12 | 9,120 | 5 | evergreen how-to |
| /post/offline-chatgpt-alternative | 3 | 2,200 | **3** | answer-shaped post; **cited in the `offline ai` AI Overview** |
| /post/run-gpt-oss-locally | 5 | 890 | 14 | "run <hot model> locally" |
| /download | 3 | 1,770 | 7 | the downloads page ranks on its own |

Jan's blog is four repeatable formats: a `<competitor> alternatives` listicle
(37 keywords from one post), a `run <model> locally` post per major model
release, an evergreen `run AI models locally` guide, and the answer-shaped
`you can't run X offline, do this instead` post that the AI Overview quotes.
All four transfer directly; the last one is already specified in
`05-serp-landscape.md`.

### openwebui.com — programmatic and integration pages

| url | keywords | volume | best pos | what it is |
|---|---|---|---|---|
| /getting-started/quick-start/connect-an-agent/openclaw/ | 10 | 339,370 | 3 | integration doc for a hot agent — captures its brand demand |
| / | 36 | 86,930 | 1 | brand (`open webui` 14,800) |
| /leaderboard | 24 | 63,700 | 21 | programmatic: `llm leaderboard`, `ai leaderboard`, `best ai models` |
| /features/…/web-search/providers/exa/ | 3 | 20,920 | 3 | integration doc |
| /features/…/image-generation-and-editing/automatic1111/ | 3 | 8,920 | 4 | integration doc |
| /models/anthropic/claude-opus-4.5 | 2 | 7,320 | 20 | programmatic model page |
| /getting-started/…/connect-a-provider/starting-with-ollama/ | 6 | 3,740 | **2** | integration doc |
| /features/open-terminal/ | 5 | 3,240 | **1** | feature page at #1 for the feature's name |

Same two patterns at larger scale: one page per integration, named for the
integration; and feature pages at #1 for the feature's own name. The
leaderboard and per-model pages are programmatic SEO we should not copy — they
need a data source we do not have and they attract traffic with no purchase
intent.

### khoj.dev — the anti-pattern

15 ranking keywords, 12 on the homepage, all brand, from 1,671 crawled pages.
`/advanced/use-openai-proxy/` ranks 24th for two keywords; nothing else
registers. Khoj has more authority than open-notebook and a fraction of the
visibility. Titles that describe the product's internals instead of the user's
query do not rank, and page count does not compensate.

### msty.app

Included for the authority table only. Brand demand is large (110,000/mo,
down 80% and now around 49,500) and its positions are its own name; no
footprint pull was needed.

### The edtech set — who owns the Studio-output SERPs

None of the local-AI competitors above has a flashcards, quiz, study-guide or
slides page. Those results pages (`01`, section 3) belong to a different set
of companies, sized by brand searches and by their positions across the 28
artifact heads in `data/artifacts-serp-competitors.json`:

| domain | brand searches/mo (recent) | artifact keywords (of 28) | median position | top-3 | what ranks |
|---|---|---|---|---|---|
| knowt.com | 135,000 (33,100) | 6 | 6 | 1 | #3 on `flashcard generator`, #4 on `ai pdf summarizer` |
| gamma.app | 110,000 (60,500) | 0 | — | — | slides brand; absent from the 28 SERPs |
| notegpt.io | 49,500 (27,100) | **19** | 13 | 2 | #1 on `ai quiz generator`; `/ai-study-guide-maker`, one URL per artifact |
| studyfetch.com | 33,100 (12,100) | 12 | 8 | 2 | `/study-guide-maker`; #1 on `ai study tools` |
| napkin.ai | 22,200 (12,100, −63%) | 0 | — | — | infographics brand; absent from the 28 |
| quizlet.com | (`quizlet ai` 2,400) | 10 | 3 | **5** | `/features/study-guides`; #1 on `ai quiz maker` |
| remnote.com | — | 11 | **2** | **6** | `/feature/study-guide-maker`; #1 on `pdf to flashcards`, `pdf to quiz`, `best ai for studying` |
| revisely.com | 4,400 (1,900) | 7 | 3 | 4 | #1 on `flashcard generator` and both AI flashcard forms |
| anki-decks.com | — | 5 | 4 | 2 | #2 on both AI flashcard forms |
| mindgrasp.ai | 4,400 (1,600) | 15 | 19 | 2 | `/ai-study-guide-maker`; wide, shallow |
| youlearn.ai, turbolearn.ai | 6,600 (1,900), 14,800 (1,900) | 0 | — | — | brand only, both falling |

Three things to take from them.

- **The winning shape is one URL per job, titled for the job.** RemNote's six
  top-3 positions come from `/feature/<job>-maker` pages, Quizlet's five from
  `/features/<job>`, NoteGPT's nineteen appearances from one URL per artifact
  (`/ai-study-guide-maker`). Nobody wins these from a homepage or a "Studio"
  page that lists twelve formats.
- **They all upload, and they all charge.** Every one is a subscription with
  the student's material on the vendor's servers. The argument the landing
  page makes (`02`) has no competitor on these SERPs.
- **They are small.** The `study guide maker` SERP is KD 6 because Flint,
  Penseum, Scribe, Notesight, StudyPDF, HomeworkAid and Linnk are on page
  one. The authority we have (`04`, top of file) is enough here in a way it
  is not on `ai presentation maker` (Canva, Adobe) or `ai summarizer`
  (QuillBot), which is why the briefs take flashcards, quiz and the hub and
  leave the generic slide and summary heads.

## Patterns to copy, with our version

| pattern | who proves it | our page |
|---|---|---|
| One feature page per feature, titled for the job | open-notebook `/features/podcast` (31 kws), openwebui `/features/open-terminal` (#1), remnote `/feature/study-guide-maker` (median position 2 across 11 artifact terms) | podcast, study-guide hub, flashcards, quiz, slides, sources, search, bring-your-own-model |
| One docs page per provider or integration, titled with its name | anythingllm `/setup/llm-configuration/cloud/*`, jan `/remote-models/openrouter`, openwebui `/connect-a-provider/*` | one page each for Ollama, OpenAI, Anthropic, Gemini, OpenRouter, LM Studio as model providers; one per MCP client |
| `<competitor> alternatives` listicle | jan `/post/chatgpt-alternatives` (37 kws) | `notebooklm alternatives` (590), honest, including open-notebook |
| Answer-shaped "you can't X, do this instead" | jan `/post/offline-chatgpt-alternative` (pos 3 + AIO citation) | "You can't run NotebookLM offline" |
| `run <model> locally` per release | jan (`deepseek-r1`, `gpt-oss`) | one post per major open-weights release, framed as "use <model> with your documents in SurfSense" |
| A downloads page that ranks on its own | jan `/download` (7th for 1,770) | `/downloads`, already briefed |

## Where they are weak — the openings

- **Onboarding cost.** open-notebook needs Docker and env vars; AnythingLLM,
  Jan and OpenWebUI assume a model runtime. "Signed installer, bring a key,
  no terminal" is the line none of them can write.
- **Document-first framing.** All of them are chat UIs for models. Only
  open-notebook is a notebook, and its ranking pages are podcast and misspelled
  brand. `ai notebook` (2,400, KD 22, transactional) and `notebook ai` (8,100,
  KD 45) are category terms they hold at 16 and 5 respectively.
- **MCP without browser automation.** Every `notebooklm mcp` result drives a
  headless Chrome against Google's product. A native server is a different
  category of thing; see `05-serp-landscape.md`.
- **Offline audio.** open-notebook's podcast page does not claim offline
  generation; SurfSense ships Kokoro-82M locally. That is the one sentence the
  podcast feature page needs.
- **Soft positions on our vocabulary.** `on prem llm` (KD 1, held at 46),
  `private llm` (held at 10), `notes to podcast` (held at 42), `ai podcast from
  notes` (held at 61). These are the first-quarter targets.
- **No local, free tool on the study SERPs.** Every incumbent above uploads
  the student's PDFs and charges monthly; the `study guide maker` SERP is
  KD 6 and the AI Overview on it cites four vendors' own feature pages. The
  hub, flashcards and quiz briefs in `02` are the second-quarter targets,
  timed for the September peak.

## What not to copy

- Misspelling traffic (`noteboom`, `no book lm`, `notebook l`). It is accidental
  and converts at nothing.
- Programmatic pages that need a data feed (leaderboards, per-model pages).
- Chasing competitor brand terms (`ollama` 135,000, `msty` 110,000). They are
  navigational and the searcher already chose.

## Files and re-rendering

```bash
cd plans/community-local/seo/data
python parse.py --mode authority domain-authority.json
python parse.py --mode gap --min-volume 200 gap-open-notebook.json
python parse.py --mode gap --min-volume 300 gap-anythingllm.json
python parse.py --mode urls ranked-jan.json
python parse.py --mode urls ranked-openwebui.json
python parse.py --mode urls ranked-khoj.json
python parse.py --mode competitors artifacts-serp-competitors.json   # the edtech set
```

The edtech table is `python parse.py --mode competitors
artifacts-serp-competitors.json` (`serp_competitors/live`, 28 artifact
keywords, top 40 of 854 domains kept, one best position per keyword under
`keywords_positions`); the per-keyword #1s in the last column are read from
that field by eye.

`domain-authority.json` merges seven single-target `backlinks/summary/live`
calls (the live endpoint takes one target per request) and keeps only the
fields the authority renderer reads. The gap files are
`domain_intersection/live` with `target1: <competitor>`, `target2: surfsense.com`,
`intersections: false`, ordered by volume; open-notebook returned 93 keywords
in total, AnythingLLM 206.
