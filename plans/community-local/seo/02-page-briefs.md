# On-page briefs for the rewritten public pages

Build sheets for the pages Workstream B rewrites. Every keyword and metric here
is justified in [`01-keyword-research.md`](01-keyword-research.md); the SERP
shapes the briefs are written against are in
[`05-serp-landscape.md`](05-serp-landscape.md), and the competitor pages they
copy are in [`04-competitors.md`](04-competitors.md).

Two rules shape all of these briefs:

- **Spell it "air-gapped".** The one-word form gets 10 searches a month; the
  hyphenated form gets 1,900 at KD 9 with a $21.78 CPC. The tagline stays in
  the H1 because it explains the product in one line, and written with the
  hyphen it is also a target. The words with more demand still go in the title
  tag, H2s and body: *private*, *self-hosted*, *local*, *offline*,
  *on-premise*.
- **Open with the answer.** Every vendor page the AI Overviews cite starts with
  a definition or a verdict, and the People Also Ask questions reproduced in
  `05` are the H2s. Marketing voice is not liftable; plain declarative
  sentences are.

Volumes below are `recent` (median of the last three months) where the research
has it, otherwise the 12-month figure; see the reading notes in `01`.

Page status and ownership live in
[`../portal/02-pages.md`](../portal/02-pages.md); this file does not track
progress, only what each page should contain.

Conventions used below: title tags ≤60 characters, meta descriptions ≤155, one
H1 per page. Character counts are given so nobody has to recount.

## Every page: hreflang and the shared vocabulary

[`03-international.md`](03-international.md) measures 26 markets. The English
pages serve all of them until a localised set exists; do not create `en-GB` or
`en-IN` copies, they would be duplicates. Every page declares its alternates
and `sitemap.xml` repeats them:

| page language | hreflang | served markets |
|---|---|---|
| English (root) | `en`, `x-default` | US, UK, CA, AU, IN, IE, SG, NZ, ZA, AE, PH, ID and every market without a localised page |
| Japanese `/ja/` | `ja` | Japan (Tier 2, first localisation) |
| German `/de/` | `de`, `de-AT`, `de-CH` | Germany, Austria, Switzerland (Tier 2) |
| French `/fr/` | `fr`, `fr-CA` | France, Canada (Tier 3) |
| Spanish `/es/` | `es`, `es-MX`, `es-419` | Spain, Mexico, Latin America (Tier 3) |
| Portuguese `/pt-br/` | `pt-BR`, `pt` | Brazil (Tier 3) |

None of the localised sets is a launch item; the `hreflang` block is. So is
one writing rule for the English downloads and pricing pages, which carry the
two brand intents with demand in every market: the first screen uses the words
that have volume everywhere (*app*, *download*, *free*) and keeps the US
vocabulary (*private*, *self-hosted*, *on-prem*, *HIPAA*, *air-gapped*) for
the sections below it. Outside the US those words are jargon: `private ai` is
5,400 a month in the US, 720 in India, 390 in the UK and Canada, 260 in
Germany, and 170 or fewer, or no row at all, in the other 21 markets.

The same rule, the other way round, on the study pages: US English says
*studying* and UK English says *revision* (`flashcards for revision` 1,900 at
KD 1 in the UK, a phrasing the 700-term US discovery pull never surfaced).
One H2 with the UK word on the English page covers the market; do not make
an `en-GB` copy for it.

---

## `/` landing — B6

The founder's landing brief (an open item in `../portal/02-pages.md`) owns the
message. This is the SEO skeleton it has to fit inside.

**Do not measure this page on head-term rankings.** Reddit and GitHub hold the
top three for nearly every term we want; a vendor landing page does not displace
them with copy. This page exists to convert the traffic that arrives from the
repo, the launch coverage, the blog and brand search.

| role | keyword | recent | kd | note |
|---|---|---|---|---|
| primary | self hosted ai | 2900 | 10 | |
| primary | private ai chatbot | 5400 | 12 | product-choosing form of `private ai` |
| primary | air-gapped ai | 1900 | 9 | $21.78 CPC; the tagline word, hyphenated |
| secondary | offline ai | 1600 | 7 | |
| secondary | self hosted llm | 2400 | 5 | plus `self-hosted llm` 1300, KD 2 |
| secondary | best private ai | 5400 | 15 | |
| secondary | on premise ai | 2400 | 13 | `on prem llm` 720 at KD 1 is unclaimed |
| secondary | open source notebooklm | 90 | 17 | the AI Overview term |
| tertiary | local notebooklm | 90 | 19 | |
| tertiary | best local ai | 720 | 5 | |
| tertiary | private ai assistant | 210 | 10 | |

- **Title:** `Air-Gapped, Open Source NotebookLM Alternative | SurfSense` (58)
- **Meta:** `A private, self-hosted NotebookLM alternative that runs air-gapped on your own machine. Your documents, your model keys, no cloud, no account.` (142)
- **H1:** the tagline, hyphenated. "Air-gapped open source NotebookLM" is now
  both the human sentence and a keyword.
- **H2s**, in this order, each carrying one demand phrase:
  1. *Runs entirely on your machine* — the offline/local/air-gapped claim,
     concretely: the index is on disk, nothing is sent anywhere
  2. *Self-hosted, no account required* — `self hosted ai`, `self hosted llm`
  3. *Bring your own model* — the BYO-key argument; XDA's own complaint about
     NotebookLM being "Gemini-only", so use their framing
  4. *Install and go — no Docker, no terminal, no GPU* — the wedge against the
     incumbent (its coverage cites Docker and env-var setup as the cost of
     entry) and the two related searches on `self hosted ai`, "without GPU"
     and "docker", that have no good result today
  5. *Turn sources into podcasts, offline* — links to the feature page
  6. *Open source, audit it yourself* — links to the repo
  7. *Private by construction* — one paragraph on why "nothing leaves the
     machine" matters after *US v. Heppner*; links to the compliance page
- **FAQ block** (also the `FAQPage` schema), taken from the PAA boxes in `05`:
  *Can I self-host an AI?* · *Is there an AI I can use without internet?* ·
  *Can I run NotebookLM locally?* · *Is there an open-source alternative to
  NotebookLM?* · *Is there a free version of NotebookLM?* Each answered in one
  plain paragraph that could be quoted verbatim.
- **Above the fold:** a download button that resolves a **pinned tag**, never
  `/releases/latest`. This is currently broken — `hero-section.tsx` pulls
  `desktop-download-utils`, which resolves `/releases/latest` and therefore
  serves legacy v0.0.40. Fixing it is a prerequisite, not a nice-to-have.
- **Must not survive:** `AuthRedirect` (redirects to a dashboard that will not
  exist) and the `Get Started → /login` CTA. Component-by-component notes are in
  `../portal/02-pages.md`.
- **Must survive:** position 1 for `surfsense` (590/mo, +127%). Keep the brand
  name in the title tag and the H1 and do not change the URL.
- **Schema:** `SoftwareApplication` with `offers.price: 0`, `applicationCategory`,
  and `operatingSystem` listing Windows, macOS and Linux, plus `FAQPage` for
  the block above. The app is free, so price 0 is honest.
- **Internal links out:** `/downloads`, `/pricing`, `/mcp-server`, the podcast
  feature page, the compliance page, the repo.

## `/downloads` — B5

May be a landing section rather than a route; either way this content needs a
crawlable URL, because "how do I install it" is transactional intent we can
actually win.

| role | keyword | recent | kd | note |
|---|---|---|---|---|
| primary | notebooklm download | 720 | 50 | transactional, +175%; 2,400/mo in India, +400% |
| primary | notebooklm desktop app | 260 | 36 | there is no such thing; we are the answer |
| secondary | notebooklm for windows | 210 | 42 | +420% |
| secondary | download notebooklm | 210 | 38 | +133% |
| secondary | offline ai | 1600 | 7 | related searches: "app for Windows", "download" |
| secondary | notebooklm mac app | 140 | 67 | plus `notebooklm mac` 170 |
| tertiary | offline ai download | 30 | 21 | |
| tertiary | local ai for mac | 40 | 30 | $28.45 CPC |
| tertiary | local ai linux | 30 | 15 | |
| tertiary | offline ai assistant | 90 | 4 | |

Jan's `/download` ranks 7th for 1,770 monthly volume on its own; a downloads
page is a ranking page in this niche, not a utility.

- **Title:** `Download SurfSense — Offline AI App for Windows, Mac, Linux` (59)
- **Meta:** `Free signed installers for Windows, macOS and Linux. The NotebookLM-style desktop app that runs offline on your own machine. No account needed.` (143)
- **H1:** `Download SurfSense`
- **H2 per platform** so each can rank for its own qualifier: *Windows 10 and
  11*, *macOS (Apple silicon)*, *Linux (deb, AppImage)*. "Windows 11" appears in
  the query set (`notebooklm download for windows 11`, $12.31 CPC).
- **One H2 answering the platform question directly:** *Is there a NotebookLM
  desktop app?* No; SurfSense is an open-source desktop app that does the
  same job offline. That paragraph is what the `notebooklm desktop app` and
  `notebooklm for windows` SERPs lack.
- **Required factual notes**, all from the pivot plan's distribution section:
  the deb build does not auto-update; there is no Intel Mac build; four build
  targets, not five. Hardware: any laptop, no GPU, because inference is
  bring-your-own-key; the `offline ai` AI Overview quotes RAM minimums, so
  state ours.
- **Never link `/releases/latest`.** It is pinned to legacy v0.0.40 so that
  0.0.39 clients do not auto-update onto 2.x. Link the specific tag.
- **International** (`03-international.md`; hreflang table above): this page
  carries one of the two brand intents with demand in all 26 markets (the
  other is the free question, on `/pricing`): `notebooklm app` in
  every pull, `notebooklm download` 2,400/mo in India (+400%), 1,000 in
  Brazil, 590 in Germany, `NotebookLM 下載` 1,900 in Taiwan. Install-oriented
  copy converts there; licence-oriented copy does not. Keep the licence pitch
  on `/pricing`. The page renders from the release manifest, so localising it
  later is one string file per language; Taiwan's `下載` is the first string
  worth adding.
- **Schema:** `SoftwareApplication` with `softwareVersion`, `operatingSystem`
  and `downloadUrl` per platform.

## `/pricing` — B5

Currently still selling pay-as-you-go hosted credits. Beyond the rewrite, there
is an unusually soft keyword opportunity here: the NotebookLM pricing-and-limits
cluster is 36 keywords and ~9,100 recent searches a month, with the core terms
at **KD 2-3**. The tier names are collapsing (`notebooklm pro` -87%,
`notebooklm plus` -83%) while the limit questions grow (+200 to +425%): people
are hitting the source cap and asking whether paying removes it.

| role | keyword | recent | kd | trend |
|---|---|---|---|---|
| intercept | is notebooklm free | 2900 | 36 | +19 |
| intercept | notebooklm pricing | 1000 | 2 | |
| intercept | notebooklm price | 1000 | 2 | |
| intercept | notebooklm cost | 480 | 3 | -34 |
| intercept | how many sources can you add to notebooklm | 320 | 3 | +333 |
| intercept | how much is notebooklm | 260 | 10 | +24 |
| intercept | notebooklm limits / source limit | 530 | 15-16 | |
| intercept | does notebooklm have a limit | 210 | 19 | +425 |
| intercept | notebooklm plans | 210 | 13 | +200 |
| intercept | notebooklm enterprise | 210 | 10 | |
| intercept | notebooklm for students / student discount / free for students | 700 | 13-21 | +133 to +350 |
| own | private ai assistant | 210 | 10 | |

This only works as an **honest comparison**, and the page must answer the
question it ranks for before it pivots to us — state NotebookLM's actual tiers,
prices and limits, then contrast. A page that ranks for "is notebooklm free"
and answers only "buy SurfSense" will not hold the position and deserves not to.
If that is more than the pricing page should carry, move the comparison to a
blog post and link it; do not fake it.

- **Title:** `SurfSense Pricing — Free App, Paid Plugins` (42)
- **Meta:** `The app and its updates are free forever. Licences add scraper plugins and priority support. Compare with NotebookLM's tiers and source limits.` (143)
- **H1:** `Pricing`
- **Required content** from the pivot plan: buy buttons going straight to Stripe
  Checkout, the early-bird end date, copy stating the first plugin arrives the
  week after launch, and the trial email form.
- **Lead with free.** The app and updates cost nothing; licences buy plugins and
  priority support. Burying that reads as a bait-and-switch to an audience that
  arrived via the word "open source".
- **The free question is global** (`03-international.md`; hreflang table
  above): `is notebooklm free` is 2,400/mo in India and 480 in Canada;
  `notebooklm gratis` 2,900 in Mexico and 880 in Spain, `gratuit` 1,900 in
  France, `料金` 8,100 and `無料` 1,900 in Japan, `kostenlos` 320 in Germany.
  The first screen answers it in plain words before any tier table; the tier
  names and the licence pitch are US vocabulary and go below.
- **Comparison H2s, phrased as the queries:** *Is NotebookLM free?* · *How much
  is NotebookLM?* · *How many sources can you add to NotebookLM?* · *Does
  NotebookLM have a limit?* · *Is NotebookLM free for students?* · *What does
  NotebookLM Enterprise cost?* Each opens with the factual answer about
  Google's product (with a date, since these change), then the SurfSense
  line: no source limit and no daily cap, because the index lives on your disk.
- **Schema:** `Product` with `offers` per tier, plus `FAQPage` for the
  comparison H2s.

## `/free` — B5, rewritten in place

The one page on the site with rankings worth defending, and the decision to
keep it is closed (`01`, "Our baseline"; [`../portal/02-pages.md`](../portal/02-pages.md)).
It keeps its URL. Read the position-band analysis in `01` before touching the
copy, because the target set is not what the page's current `keywords` array
says it is.

**Target the no-signup cluster and nothing else.** It is 62.4% of the page's
estimated value and 28 of its 31 top-10 positions, and it is the one promise
the desktop app keeps better than the hosted page did:

| role | keyword | volume | current pos | etv | note |
|---|---|---|---|---|---|
| primary | chat free no sign up | 6,600 | 6 | $223 | most valuable row on the site bar the unwinnable head |
| primary | ai chat no signup | 9,900 | 10 | $112 | plus `ai chatbot no sign up` 9,900 at 26 |
| primary | free ai no sign-up | 1,300 | **3** | $126 | hyphenated and unhyphenated are separate rows, both ours |
| primary | free ai no sign up | 1,300 | 5 | $86 | |
| secondary | ai without login | 320 | **3** | $31 | `ai no login` 880 at 8, `no login ai` 480 at 9 |
| secondary | ai no sign up | 1,000 | 6 | $47 | `no sign up ai` 480 at 4, `ai no sign in` 480 at 4 |
| secondary | free ai no login | 720 | 6 | $34 | |
| secondary | free ai chats no sign up | 3,600 | 13 | — | winnable from 13 |
| tertiary | ai chat no registration | 170 | 7 | $6 | `chat for free no registration` 6,600 at 74 |
| tertiary | ai chat no restrictions no sign up | 480 | 6 | $16 | the no-restrictions set is 20 kw, $65 |

- **Title:** `Free AI Chat, No Sign-Up — Runs on Your Own Machine` (51)
- **Meta:** `Free AI chat with no sign-up, no login and no account, ever. Download the app, pull a model once, and chat offline with no token limits or quotas.` (146)
- **H1:** `Free AI chat with no sign-up`
- **First paragraph carries the whole conversion.** Four facts in order: no
  account exists, so there is nothing to sign up for; it is free, not
  free-tier; there is no token cap or quota because nothing is metered; it runs
  on the visitor's machine. Then the one honest caveat, because it protects the
  offline claim — one download to fetch a model (Qwen3 0.6B is 0.5 GB), after
  which it needs no network.
- **H2s, phrased as the queries themselves**, which is how the page already
  earns its top-10 rows: *AI chat with no sign up* · *Use AI without login* ·
  *No registration, no email, no account* · *Is there an AI chat with no
  limits?* · *Free ChatGPT alternative with no sign-up* — that last one is the
  only brand framing this page can make, and "alternative" is the honest one.
  Keep it to a single H2. The whole brand cluster is 27 keywords and $101, and
  the three "like ChatGPT" rows we actually hold (`free ai like chat gpt` 210
  at 21, `ai tools like chatgpt free online` 170 at 32, `ai like chat gpt free`
  110 at 31) are worth **$1.49 between them**. The page's current `keywords`
  array claims `sites like chatgpt` and `chatgpt alternative free`; we rank for
  neither. Do not build pages for this cluster.
- **The model table stays, and its rows must be real.** Render it from
  [`curated-models.json`](../../../surfsense_local/backend/modules/llm/recommendations/curated-models.json)
  (Qwen3 0.6B/1.7B/4B/8B/14B/32B, Qwen2.5 Coder 7B/32B, with the sizes in
  [`providers/ollama/catalog.py`](../../../surfsense_local/backend/modules/llm/providers/ollama/catalog.py)),
  vendored into the web app at build time with a check that fails the build
  when the two drift. The roster is Qwen-family for v1 and grows when
  llama.cpp lands; a generated table cannot advertise a model the app cannot
  run. Columns that serve the intent: model, download size, what laptop runs
  it, and — the reason the visitor is here — that it needs no account.
- **Where the rows link.** Not to per-model pages. Each row goes to the
  matching provider page under "Model-provider pages" below (Ollama first,
  which is also a 135,000-volume brand term), and every row's CTA is
  `/downloads`. The existing `/free/[model_slug]` routes **301 to `/free`**:
  their demand basis was hosted brand-name chat, and eight Qwen pages would be
  thin pages against near-zero volume.
- **Delete, do not rewrite, the hosted-era claims.** The hub's nine `FAQ_ITEMS`
  promise 500,000 free tokens, `$5` of premium credit on registration, and
  answer *Is Claude AI available without login?* with "Yes" — in body copy and
  in `FAQPage` markup. The model routes add a `WebApplication` with
  `offers: price 0` for a hosted chat service. None of it is true after the
  pivot, and false `FAQPage` markup is its own manual action. Re-author the FAQ
  against the real product; keep `FAQPage`, it is fine when the answers are
  true. Both `/register` links go too — the *Want More Features?* CTA and
  *Sign Up Free* in the footer nav — because there is no register route after
  the cutover.
- **Schema:** `FAQPage` for the H2s plus `SoftwareApplication` with
  `offers: { price: 0 }` — accurate now in a way it was not before, because the
  app itself is free.
- **Ads are a separate call.** The page carries two `AdUnit` slots
  (`freeHubInContent`, `freeHubBeforeFaq`) and an ads-removal banner. Both
  compete with the download CTA on a page whose job is now conversion rather
  than impressions. Recommend removing them; it is Dev B's call with the
  founder, and it is not blocked by anything here.
- **Measure it on the cluster, not the total.** The 435,390 combined volume
  mostly sits at position 21+. The success metric is the no-signup cluster's
  positions and installer clicks, and `01` says to expect the generic heads
  and brand terms to go.

## `/mcp-server` — rewritten for licence mode at T+7

**The single best keyword-to-capability match in the research.** `notebooklm mcp`
is 720 searches a month at **KD 1**, a **$16.97 CPC**, and **+556% year on year** —
and we ship an MCP server. `notebooklm api` adds another 1,000 at KD 22, and one
of the top-10 organic results for "open source notebooklm" is a video titled
"Finally… A NotebookLM Alternative With an API" with 43,600 views.

| role | keyword | recent | kd | cpc | trend |
|---|---|---|---|---|---|
| primary | notebooklm mcp | 720 | **1** | 16.97 | +556 |
| primary | notebooklm api | 590 | 22 | 10.36 | -61 |
| secondary | notebooklm mcp server | 140 | **3** | 16.80 | +367 |
| secondary | local mcp server | 320 | 30 | **45.04** | |
| tertiary | does notebooklm have an api | 70 | 15 | | |
| tertiary | notebooklm mcp cli | 90 | 9 | 9.27 | |
| tertiary | ai second brain | 390 | 16 | 9.11 | +700 |

Every result on this SERP today (`05-serp-landscape.md`) is a community project
that drives a headless Chrome against Google's product and asks for a Google
login. That is the page's opening sentence, in effect: **a native MCP server
over your own library, no browser automation, no Google account.**

- **Title:** `NotebookLM MCP Server, Native and Local — SurfSense` (51)
- **Meta:** `Query your own documents from Claude, Cursor or any MCP client. No browser automation, no Google account. The local MCP server NotebookLM does not have.` (152)
- **H1:** `MCP server`
- Name the clients explicitly — Claude Desktop, Claude Code, Cursor, and any MCP
  client — these are the qualifiers people add, and the PAA questions are
  *How to add NotebookLM MCP to Claude?*, *Can I connect Claude to NotebookLM?*
  and *Can I use Claude Code with an MCP server?* Answer each as an H2.
- Include a copy-pasteable config block per client. GitHub ranks #1 for
  `notebooklm mcp` and npm 7th; this query wants working configuration, not
  marketing. The `notebooklm mcp cli` queries want an `npx` one-liner.
- **Registries:** publish to npm (and PyPI if the server is Python), and list on
  mcpservers.org, mcpmarket.com, composio.dev and skillsllm.com. Five of the
  top 17 results are directory listings; being absent from them is the gap.
- Carry both product names, "NotebookLM" and "Gemini Notebook"; the SERP and
  the Overview have started using the latter.
- Do not delay this page to T+7 for SEO reasons if the licence-mode rewrite is
  the only blocker; a KD 1 term growing at +556% is worth an interim page.

## New feature and docs pages — copy the two patterns that rank

`open-notebook.ai/features/podcast` ranks for **31 keywords at best position 2**
from a single feature page; OpenWebUI's `/features/open-terminal/` is #1 for
its feature's name; AnythingLLM's, Jan's and OpenWebUI's footprints are
otherwise integration docs. One page per feature, named for the job it does,
and one page per integration, named for the integration, are the two patterns
that demonstrably work in this niche (`04-competitors.md`). The edtech set
that owns the Studio-output SERPs proves the first pattern harder: RemNote
holds a median position of 2 across eleven artifact terms from
`/feature/<job>-maker` pages alone (`01`, "Who owns these SERPs").

Slugs are the portal's call; the rule this research needs is that the path
and the H1 name the *job* (`/features/study-guide-maker`,
`/features/flashcard-generator`), not the builder (`/studio/flashcards`).

### Podcast

Post-peak demand (`ai podcast generator` halved from its December 2024 high),
but the incumbent's positions on it are soft, 38-61 on most terms, and we have
a genuine differentiator: offline generation with a bundled Kokoro-82M, no
cloud TTS.

| role | keyword | recent | kd | incumbent's position |
|---|---|---|---|---|
| primary | ai podcast generator | 2400 | 13 | — |
| secondary | notebooklm podcast | 480 | 25 | 38 |
| secondary | turn notes into podcast | 260 | — | 54 |
| secondary | notebooklm podcast generator | 260 | 20 | 5 |
| secondary | notes to podcast | 140 | 16 | 42 |
| secondary | notebooklm audio overview | 140 | **5** | — |
| tertiary | ai podcast from notes | 110 | 14 | 61 |
| tertiary | google (ai) podcast generator | 380 | 23-27 | 13-18 |

- **Title:** `Offline AI Podcast Generator — SurfSense Studio` (47)
- **H1:** `Turn your sources into a podcast`
- State plainly that generation runs locally with no cloud TTS and no
  per-minute cost. That sentence is the whole differentiator, and it is the
  one the incumbent's page does not make.
- An H2 for *NotebookLM Audio Overview, offline*: the KD 5 term, and the
  feature name people know.
- Note the current gap honestly in any copy claiming formats: the podcast
  builder emits **WAV, not MP3**, with no ffmpeg bundled (see the pivot plan's
  C5 status). Do not promise MP3 until it ships.

### The other Studio outputs — a hub and three feature pages

The app ships eleven more formats (`01`, section 3). Demand says: one hub
page for the study-guide job, three feature pages (flashcards, quiz, slides)
and H2s or docs pages for the rest. Two rules apply to all of them:

- **Timing.** Study demand peaks in September-October and March-April and
  bottoms in June-August; October 2025 was the record month for every study
  head. The hub, flashcards and quiz pages need to be indexed by
  **mid-August**, or failing that the first week of January. Publishing them
  in June and judging them in July would read as failure.
- **The argument.** Every incumbent here (RemNote, Knowt, NoteGPT,
  StudyFetch, Quizlet, Revisely, Mindgrasp, Gamma) is a subscription that
  uploads the student's material. "Free, on your laptop, your PDFs never
  leave it" is the landing page's argument re-used, and none of them can make
  it. Say it in the first paragraph of every one of these pages.

#### Study guide (hub)

There is no "study guide" builder; the page sells the summary, flashcards and
quiz builders run on one source set, which is exactly what the #1 result
promises ("AI Study Guide Maker From Notes and PDFs", RemNote).

| role | keyword | recent | 12-month (peak) | kd | cpc |
|---|---|---|---|---|---|
| primary | study guide maker | 1900 | 8100 (14800) | **6** | 4.10 |
| primary | study guide generator | 1600 | 2400 | **7** | 8.76 |
| secondary | ai study guide maker | 720 | 2900 | 10 | 6.74 |
| secondary | ai study tools | 1900 | 6600 (12100) | 27 | 6.10 |
| secondary | best ai for studying | 880 | 1300 | 18 | 6.85 |
| secondary | notebooklm for studying | 320 | 590 | 31 | **14.29** |
| tertiary | how to use notebooklm to study | 170 | 210 | 6 | 4.08 |
| tertiary | ai study guide | 260 | 590 | 16 | 5.48 |
| tertiary | ai study assistant | 170 | 170 | 35 | 5.07 |

- **Title:** `Study Guide Maker from Your Notes and PDFs — Free, Offline` (58)
- **H1:** `Turn your notes and PDFs into a study guide, flashcards and a quiz`
- First paragraph: what comes out (a summary, a flashcard deck, a practice
  quiz), from what (PDFs, slides, YouTube lectures, web pages), where (on
  your laptop), for how much (free). Those four facts are the AI Overview's
  citation material; the Overview on this SERP quotes Quizlet, StudyFetch,
  Scribe and Penseum saying exactly those things about themselves.
- H2s from the PAA, in order: *Can AI create study guides from PDFs?* ·
  *How can I create my own study guide?* (the manual answer, honestly, then
  the shortcut) · *Can ChatGPT create a study guide?* (yes, one PDF at a
  time and it keeps it; here, forty sources and nothing leaves) · *Which
  study guide creator is the best?* (a plain comparison table: local, free,
  open source, formats, source limit — the incumbents lose on the first
  three columns).
- An H2 *NotebookLM for studying, offline*: the fastest-growing branded term
  in the set (+680%, $14.29 CPC) and its how-to sibling (KD 6).
- Link the three format pages from the H1 block and from each H2; this is
  the parent in the breadcrumb schema.
- Teachers are on this SERP (r/Teachers at position 10). One paragraph
  addressed to them, not a section.

#### Flashcards

| role | keyword | recent | 12-month (peak) | kd | cpc |
|---|---|---|---|---|---|
| primary | ai flashcard generator | 480 | 1000 | 31 | 3.84 |
| primary | ai flashcard maker | 1000 | 3600 | 33 | 2.91 |
| secondary | flashcard generator | 9900 | 33100 (60500) | 42 | 2.12 |
| secondary | pdf to flashcards | 110 | 320 | 34~ | 2.40 |
| secondary | turn notes into flashcards | 90 | 320 | 30 | 3.85 |
| secondary | anki ai | 320 | 390 | 32 | **7.62** |
| secondary | pdf to anki | 70 | 170 | **9** | 2.43 |
| tertiary | notebooklm flashcards | 70 | 140 | 29 | 8.19 |
| tertiary | make flashcards from notes | 70 | 260 | 24 | 2.83 |

- **Title:** `AI Flashcard Generator from PDFs and Notes — Offline, Free` (58)
- **H1:** `Make flashcards from your PDFs, notes and lectures`
- Revisely, Quizlet and Knowt own the head; do not chase `flashcard
  generator` on copy. The page wins on the "from PDF / from notes" forms and
  on the Anki family, where nothing local ranks.
- **Export.** The builder emits front/back cards as JSON and shows them in
  the app. If it gains a TSV or `.apkg` export, this page gets an *Export to
  Anki* H2 and the `pdf to anki` / `anki ai` terms for free. That is a
  product suggestion for the Studio contractors, not a decision made here.
- UK English says *revision*: `flashcards for revision` is 1,900 a month at
  **KD 1**, `revision ai` 320 at KD 11. One H2 titled *Flashcards for
  revision* costs nothing and no `en-GB` copy is needed
  (`03-international.md`, "Studio outputs abroad").

#### Quiz

| role | keyword | recent | 12-month (peak) | kd | cpc |
|---|---|---|---|---|---|
| primary | ai quiz generator | 1000 | 3600 (6600) | 32 | 5.40 |
| primary | ai quiz maker | 1300 | 2900 | 30 | 5.31 |
| secondary | pdf to quiz | 90 | 390 | 17 | 4.20 |
| secondary | quiz generator from pdf | 50 | 140 | 14 | 3.42 |
| secondary | free ai quiz generator | 170 | 390 | 18 | 4.59 |
| secondary | practice test generator | 140 | 480 | 26 | 5.34 |
| secondary | ai question generator | 320 | 880 | 25 | 4.37 |
| tertiary | ai practice test generator | 90 | 320 | 25 | 8.23 |
| tertiary | notebooklm quiz | 30 | 50 | 34 | 5.64 |

- **Title:** `AI Quiz Generator from Your PDFs and Notes — Offline, Free` (58)
- **H1:** `Generate a practice quiz from your own material`
- "From your own material" is the differentiator against Quizlet and Jotform,
  whose quiz makers start from a blank form. Multiple choice and short answer
  with the source passage under each answer; say that the source stays on
  the machine.
- Teachers and trainers are half this audience (`ai test generator`,
  `practice test generator`, r/Teachers). One H2 *For teachers: a test from
  the chapter you assigned*.
- Skip `ai test generator` (KD 84) and `quiz ai` (3,600 but ambiguous; a
  navigational share we cannot size).

#### Slides

The US head terms are KD 43-84 and owned by Canva, Adobe, Slidesgo and Gamma;
the US page exists for the NotebookLM-branded set and as the parent of the
Japanese and German pages, where the demand is (`スライド 作成 ai` 14,800 at
KD 15; `präsentation erstellen ki` 5,400 at KD 11).

| role | keyword | recent | kd | cpc |
|---|---|---|---|---|
| primary | ai slides generator / ai slide generator | 2400 each | 43-44 | 7.84 |
| secondary | notebooklm slides | 90 | 17 | 5.19 |
| secondary | notebooklm slide deck | 90 | 15~ | 7.69 |
| secondary | notebooklm ppt | 70 | 12 | 4.67 |
| secondary | notebooklm presentation | 50 | 22 | 6.55 |
| tertiary | best ai presentation maker | 720 | 36 | **15.76** |
| tertiary | pdf to presentation | 70 | 19 | 3.00 |

- **Title:** `Slides from Your Documents — Offline AI Slide Generator` (55)
- **H1:** `Turn your sources into a slide deck`
- Say **PPTX** (an editable PowerPoint file, opens in Keynote and Google
  Slides), because "editable" is the recurring complaint in the NotebookLM
  branded queries (`how to edit notebooklm slides`, 90).
- Do not use "presentation maker" in the H1; that is Canva's phrase and
  Canva's SERP.

#### Infographic, summary, report, spreadsheet, web page, mind map, video

- **Infographic**: an H2 on the podcast or study-guide page titled
  *NotebookLM infographic, offline* (`notebooklm infographic` 210, KD 10~,
  +800%; 880 in Japan). A page of its own when the branded term holds a
  second season; the generic heads are KD 45 and Venngage's.
- **Summary**: no page. An H2 on the sources page for the YouTube forms
  (`youtube video summarizer` 4,400 recent, KD 30; `summarize youtube video`
  1,900, KD 26) and the first line of the study-guide bundle.
- **Report (DOCX)**: a docs page, and the blog post *Literature review with
  AI, from your own papers* (`literature review ai` 720, KD 17, $8.46).
- **Spreadsheet (XLSX)**: a docs page titled *Extract tables from your PDFs
  into a spreadsheet* (`pdf table extractor` 480, KD 17; `ai spreadsheet
  generator` 480, KD 14, $18.01; `ai excel generator` 170, KD 8).
- **Web page (HTML) and PDF**: one line each in the formats list on the hub;
  `ai html generator` is 90, and "AI PDF generator" describes every format.
- **Mind map**: a blog post, *NotebookLM mind map, offline and exportable*
  (`notebooklm mind map` 320, KD 7~; Reddit and Xmind hold 2 and 3 with
  posts). The generic heads are KD 65-78.
- **Video**: nothing on any page until the builder ships; then a feature
  page for `notebooklm video overview` (KD 5, decaying from a 1,300 peak) and
  `pdf to video ai`. Listed under "After the MVP" in the pivot plan.

### Model-provider pages

One docs page per provider, titled with the provider's name, is how AnythingLLM
ranks 6th for `anthropic llm` and `bedrock llm`, how Jan ranks 8th for
`openrouter` (149,000/mo) and how OpenWebUI ranks 2nd for its Ollama page. The
page is a setup guide: where to get the key, where to paste it, which models
work, one screenshot.

Pages, in order: Ollama (135,000 brand volume; `ollama rag` 260 at KD 4,
`ollama frontend` 90, `ollama desktop app` 140 at +333%), LM Studio
(`lm studio alternative` 390 at KD 5 is also ours), OpenAI, Anthropic, Google
Gemini, OpenRouter. Then one page per MCP client: Claude Desktop, Claude Code,
Cursor.

### Sources and search

Weak demand, but the category noun lives here and the incumbent holds it
loosely: `ai notebook` (1,300 recent, KD 22, held at 16), `notebook ai` (8,100,
KD 45, held at 5), `notebook search` (480, KD 13, held at 18),
`document intelligence` (590, KD 23, $14.80). Title the ingestion page for the
formats it accepts and the search page for the job: *Search across all your
documents, offline*. Avoid the 2023 "chat with your PDF" framing; that cluster
collapsed (`01`).

### Compliance page

New in this pass, and the cluster with the highest CPCs in the research:
`hipaa compliant ai` (4,400, KD 34, **$46.33**), `secure ai` (3,600, KD 19,
$27.04), `hipaa compliant chatgpt` (390, $63.56), `ai for legal documents`
(140, KD 10, **$82.76**), and in other markets `gdpr compliant ai` ($23.45) and
`dsgvo konforme ki` (260, +256%).

- **Title:** `AI for Confidential Documents — Nothing Leaves Your Machine` (59)
- **The rule:** say only what is architecturally true. "HIPAA compliant" and
  "GDPR compliant" are claims about the deployer's controls, not properties the
  software has on its own. The page states: the index and every prompt stay on
  the user's disk; there is no vendor log to subpoena; the deployer keeps
  custody. It lets the reader draw the compliance conclusion. One H2 on
  *US v. Heppner* explaining why consumer AI chat logs are discoverable, with
  a link to the opinion; that is what the summer 2026 searchers are reading.
- **Legal review before publishing.** Record who signed off in the PR.
- Sections per audience: legal, healthcare, finance, research with human
  subjects. Each is one paragraph and one concrete workflow.

**Write all of these pages to be quotable.** The AI Overview sits at position 1
on three of our four priority terms and cites three kinds of source: the repo,
docs pages with declarative feature statements, and third-party reviews. Plain
factual sentences — "SurfSense runs entirely on your machine", "supported
formats are X, Y, Z" — are liftable. Marketing voice is not.

## The GitHub repo is a page too

Probably the highest-return item in this research, and it costs nothing.
**The drafts are written:** description, topics and a paste-ready README in
[`06-repo-readme.md`](06-repo-readme.md). What follows is the brief they answer.
GitHub ranks **#1** for `open source notebooklm`, `local notebooklm`,
`notebooklm mcp` and `notebooklm api`, and appears in the top ten for 11 of our
18 tracked keywords at an average position of 5.7. The repo outranks anything
the marketing site will achieve on these terms.

- **Repo description** is the meta description for those SERPs. It should contain
  "open source", "NotebookLM alternative", "local" and "private" in a readable
  sentence. Compare the incumbent's, which the SERP shows verbatim as: "An open
  source, privacy-focused alternative to Google's Notebook LM".
- **README first paragraph** is what gets quoted into AI Overviews. Lead with one
  declarative sentence of what it is and that it runs locally — not a badge wall.
- **Topics:** `notebooklm`, `notebooklm-alternative`, `notebooklm-mcp`, `rag`,
  `local-llm`, `self-hosted`, `self-hosted-ai`, `air-gapped`, `offline`,
  `local-first`, `privacy`, `private-ai`, `mcp`, `mcp-server`, `electron`,
  `ollama`. `github.com/topics/self-hosted-ai` ranks 10th for `self hosted ai`
  on its own, so being listed on the topic page is a ranking.
- Keep the release notes readable; `sourceforge.net` mirrors of the incumbent
  rank on page 2, which shows how much of this SERP is machine-generated from
  repo metadata.
- **Registries are pages too:** npm (and PyPI) for the MCP server;
  mcpservers.org, mcpmarket.com, composio.dev, skillsllm.com for directory
  listings; `openalternative.co` already lists us under NotebookLM
  alternatives and ranks on page 2. Claim and complete each listing.

## Blog — the questions are already written for us

Four formats, each proven by a competitor page in `04-competitors.md`, in the
order to write them.

**1. Answer-shaped posts.** Jan's *"You can't run ChatGPT offline, do this
instead"* ranks 3rd for `offline ai` and is cited by its AI Overview. Ours:

- *You can't run NotebookLM offline. Do this instead.* — `notebooklm offline`
  (40, KD 5) and the four `offline ai` PAA questions as H2s.
- *Self-hosted AI without a GPU (and without Docker)* — the two related searches
  on `self hosted ai` with no good result; structured like the hosting-company
  guides the Overview cites, with the hardware section they keep quoting, except
  the answer is "any laptop, bring a key".
- *Is NotebookLM private?* — one post for `notebooklm privacy`, `is notebooklm
  private`, `is notebooklm secure`, `is notebooklm safe`, `notebooklm data
  privacy`, `does notebooklm use my data` (all KD 5-12), answered from Google's
  own terms, then the local alternative.
- The `open source notebooklm` PAA set, one post each: *Is there an
  open-source alternative to Google NotebookLM?* · *Is there a free version of
  NotebookLM?* · *Can I run NotebookLM locally?* · *Which AI is fully
  open-source?*

**2. The alternatives listicle.** Jan's `/post/chatgpt-alternatives` ranks for 37
keywords from one post. Ours is *NotebookLM alternatives* (590 + `notebooklm
alternatives` 590, `alternative to notebooklm` 170, `apps like notebooklm` 50,
`notebooklm competitors` 140), honest, including open-notebook and the hosted
options, with a comparison table an Overview can lift. Follow with
`lm studio alternative` (390, **KD 5**, $14.71) and `anythingllm alternative`
(70, $13.21).

**3. Comparisons**, phrased both ways in the title because both are searched:
*NotebookLM vs Gemini* (800 combined, KD 10-13), *NotebookLM vs Obsidian* (310,
+143%), *NotebookLM vs ChatGPT* (320), *NotebookLM vs Notion* (280),
*NotebookLM vs Claude* (140, **+325%**), *Open Notebook vs NotebookLM* (40,
+200%), and a straight *SurfSense vs NotebookLM*. Carry "Gemini Notebook" as
a second name.

**4. `Run <model> locally` per release.** Jan publishes one per major
open-weights model (`deepseek-r1-locally`, `run-gpt-oss-locally`) and ranks
top 10 within weeks. Ours is framed as "use <model> with your documents in
SurfSense", one per release, linking the provider page.

Also worth a post each: `obsidian ai` (4,400, KD 16, **$24.47 CPC**, +662%,
Obsidian's audience is already local-first and own-your-files),
`ai second brain` (390, KD 16, +700%) and `second brain app` (260, **KD 3**),
`best local llm` (1,600, KD 8, $20.65) as an honest roundup that names ours as
a notebook rather than a runtime.

**5. The Studio how-tos**, timed for August and December so they are indexed
before the September and January study peaks (`01`, section 3):

- *How to use NotebookLM to study — and the offline way* — `how to use
  notebooklm to study` (210, **KD 6**, +180%), `notebooklm for studying`
  (590, +680%), `how to use notebooklm for studying` (70, KD 5). Reddit is #1
  on the second term; answer the thread's question in the first paragraph.
- *NotebookLM mind map, offline and exportable* — `notebooklm mind map` (320,
  KD 7~), `mind map notebooklm` (70, KD 11); Reddit and Xmind hold 2 and 3
  with posts, so a post is the right shape.
- *Literature review with AI, from your own papers* — `literature review ai`
  (720, KD 17, $8.46, Reddit #1), `research paper summarizer` (170, $9.56),
  the report builder's use case.
- *Best AI for studying* — `best ai for studying` (1,300, KD 18, +49%;
  4,400 and +184% in India), `best ai study tools` (880, KD 20). An honest
  roundup that includes Knowt, RemNote and NotebookLM and says where a local,
  free tool fits.

Earned coverage matters as much as owned content here. XDA, KDnuggets,
MakeUseOf, The New Stack and Android Authority all publish in this exact niche
and all currently cite the incumbent; several of them are AI Overview sources.
Reddit (r/selfhosted, r/LocalLLM, r/notebooklm) is cited in every Overview we
pulled; a launch post that the community receives well is a ranking asset.

## Localised pages, later

Not launch items. `03-international.md` ranks them; the order is Japan, then
Germany, then three translated pages each for France, Spain with Mexico, and
Brazil. Glossaries, per-market notes and the URL plan are there; this is the
build order.

- **Japan** (`/ja/`): `ローカルLLM` is 22,200 a month at **KD 0** and ran at
  33,100-40,500 over the last three months, with no competitor ranking for it;
  `NotebookLM 料金` 8,100 (KD 3), `無料` 1,900, `使い方` 27,100 for a
  quickstart, `生成AI 情報漏洩` 480 for the security section. The home page
  is written as a `ローカルLLM` page, not as a translation of the English one.
  The Studio pass adds two pages Japan wants more than the US does: **slides**
  (`スライド 作成 ai` 14,800 at **KD 15**, `パワポ 作成 ai` 3,600,
  `notebooklm スライド` 1,000 against 170 in the US) and **summary**
  (`要約 ai` 5,400 at **KD 1**, `youtube 要約 ai` 2,900, `論文 要約 ai` 1,000,
  `pdf 要約 ai` 590, all KD 1-11), plus a study page around `勉強 ai` (4,400,
  KD 3~) and `notebooklm 勉強` / `使い方 勉強` (710). No flashcard or quiz
  generator demand exists in Japanese; do not translate those two pages.
- **Germany** (`/de/`, serving Austria and Switzerland through hreflang):
  `open source KI` (1,300, **KD 5**), `lokale KI` (720, +400%),
  `KI Datenschutz` (480), `DSGVO-konforme KI` (260, +255%, $11.79),
  `KI für Anwälte` (320, $12.25), and `notebooklm alternative` at 320, the
  largest alternative demand in any non-English market. "DSGVO-konform" and data
  residency do the work "air-gapped" does in English, with the same rule as
  the compliance page: state what is true, let the reader conclude. Studio:
  a slides page (`Präsentation erstellen KI` 5,400 at **KD 11**, `KI
  PowerPoint erstellen` 1,600 at KD 5) and a study page in German vocabulary:
  the study guide is a **Lernzettel** (`Lernzettel erstellen KI` 1,000),
  flashcards are **Karteikarten** (three forms, 1,190 together), summaries
  are `KI Zusammenfassung` (720, KD 11), and the audience words are `KI zum
  Lernen` (880, +86%) and `KI für Studenten` (260, KD 7, +91%). Quiz demand
  in German is about 240 a month across five phrasings; an H2, not a page.
- **France, Spain + Mexico, Brazil**: home, downloads and the free/pricing FAQ
  only, because 60-85% of their addressable demand is brand-download, the
  free question and in-my-language searches (`gratuit` 1,900, `gratis` 3,780
  across ES + MX, `download` + `baixar` 1,320 in Brazil).

## Pages that should be `noindex`

No search value, and some carry real risk:

| page | why |
|---|---|
| `/license/success` | reached only by Stripe redirect; serves a licence file |
| `/license` | resend and trial forms; indexing invites abuse |
| `/sunset` | wind-down content, login-gated, obsolete after T+30 |

## Open, and deliberately not answered here

`/free` is no longer on this list — it is kept and rewritten in place, briefed
above, with the reasoning in `01-keyword-research.md`, "Our baseline".

**Seven public routes still have no disposition**, recorded in
[`../portal/02-pages.md`](../portal/02-pages.md): `/external-mcp-connectors`,
`/announcements`, `/changelog`, `/contact`, `/privacy`, `/terms` and the
`[slug]` catch-all. None of them ranks for anything in our top 200, so there is
no SEO argument either way and this document does not make one. `/privacy` and
`/terms` are the two that need a decision on content rather than indexing,
since they are hosted-service legal text the EULA work does not cover.
