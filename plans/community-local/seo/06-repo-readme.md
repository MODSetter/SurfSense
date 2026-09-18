# The repo: description, topics and README

The paste-ready README draft is [`drafts/README.md`](drafts/README.md). This file
is why it says what it says, the shorter strings that go around it, and what has
to be checked before it ships.

Why this is an SEO document at all: GitHub ranks **#1** for `open source
notebooklm`, `local notebooklm`, `notebooklm mcp` and `notebooklm api`, and is in
the top ten for 11 of our 18 tracked keywords at an average position of 5.7
([`02-page-briefs.md`](02-page-briefs.md), "The GitHub repo is a page too").
The repo outranks anything the marketing site will achieve on those terms, so
the description is a meta description and the README's first paragraph is what
gets quoted into AI Overviews.

## Project description

GitHub's About field allows 350 characters, but Google truncates the snippet at
roughly 155, so the terms have to be at the **front**. Recommended, revised
17 Sep 2026:

> Open source, air-gapped NotebookLM alternative. Turn documents you can't
> upload into briefings, decks, reports and study guides — locally, private by
> default. Free desktop app, bring your own model, no account, no cloud.

224 characters, and the first 150 — everything a searcher sees — carry *open
source*, *NotebookLM alternative*, *air-gapped*, *local*, *private* and the
deliverable nouns. Compare the incumbent's, which the SERP shows verbatim at 67
characters: "An open source, privacy-focused alternative to Google's Notebook
LM". We say that and what comes out of it.

**Why this changed.** The previous version opened "Turn your documents into
study guides, flashcards, quizzes, slides and podcasts", which put three study
nouns in the visible window. Production chat says professional work outruns
study by about 1.8 to 1 among users who state a task
([`07-what-users-do.md`](07-what-users-do.md)), so the visible window now leads
with the work artefact and "you can't upload" — the confidentiality hook that
the highest-CPC terms in the research are built on. Study is still named; it is
no longer the first thing a searcher reads.

Alternate, if "free" matters more in the visible window than "private":

> Open source, air-gapped NotebookLM alternative. Local AI that turns your
> documents into briefings, decks, reports and study guides. Free desktop app
> for Windows, macOS and Linux — private, offline, no account.

Use the same string in the `surfsense_local/` README's opening line, the npm and
PyPI descriptions for the MCP server, and every directory listing
(mcpservers.org, mcpmarket.com, composio.dev, openalternative.co). They are all
pages that rank.

## Topics

Sixteen, research-backed, from the brief in `02`. `github.com/topics/self-hosted-ai`
ranks 10th for `self hosted ai` on its own, so being listed there is a ranking:

```
notebooklm  notebooklm-alternative  notebooklm-mcp  rag  local-llm
self-hosted  self-hosted-ai  air-gapped  offline  local-first
privacy  private-ai  mcp  mcp-server  electron  ollama
```

GitHub allows 20, so there is room for four artifact topics. Nothing in the
research measures topic-page rankings for them, so treat these as a cheap guess
rather than a finding: `flashcards`, `study-tools`, `text-to-speech`,
`document-ai`.

## What the big repos in this category actually do

Pulled 15 Sep from the GitHub API and their live READMEs, so the structure below
is copied from what works rather than guessed at:

| repo | stars | forks | their one-line description |
|---|---|---|---|
| open-webui/open-webui | 152,179 | 22,274 | "User-friendly AI Interface (Supports Ollama, OpenAI API, ...)" |
| Mintplex-Labs/anything-llm | 66,069 | 7,335 | "Stop renting your intelligence. Own it with AnythingLLM." |
| lfnovo/open-notebook | 38,927 | 4,501 | "An Open Source implementation of Notebook LM with more flexibility and features" |
| khoj-ai/khoj | 37,350 | 2,482 | long keyword-stuffed sentence; the SEO anti-pattern in `04` |
| **MODSetter/SurfSense** | **16,154** | **1,538** | current description is the hosted-agent positioning |

Re-pulled **17 Sep 2026** and widened to the tools a professional buyer would
also be looking at, since the audience changed (`07`). Counts moved by under 1%
in two days, so the table above stands; what the wider set adds is structure:

| repo | stars | their one-line description |
|---|---|---|
| nomic-ai/gpt4all | 77,400 | "Run Local LLMs on Any Device. Open-source and available for commercial use." |
| zylon-ai/private-gpt | 57,516 | "Complete API layer for private AI applications on local models" |
| menloresearch/jan | 44,514 | "an open source alternative to ChatGPT that runs 100% offline on your computer" |
| danny-avila/LibreChat | 44,235 | keyword-stuffed; the same anti-pattern as khoj |
| onyx-dot-app/onyx | 32,147 | "Open Source AI Platform - AI Chat with advanced features that works with every LLM" |

PrivateGPT is the one to read closely. It has **repositioned onto the
professional buyer** — "production AI applications", "enterprises across the
globe" — and its README is built around that reader rather than around a feature
list.

### Length: the biggest projects have the shortest READMEs

Measured across all eight on 17 Sep, because the draft had grown and nobody had
checked it against anything:

| repo | stars | words | H2s |
|---|---|---|---|
| open-webui | 152k | 2,141 | 8 |
| gpt4all | 77k | **610** | 6 |
| anything-llm | 66k | 2,061 | 8 |
| private-gpt | 57k | 1,530 | 8 |
| jan | 44k | **755** | 10 |
| open-notebook | 39k | 2,253 | 12 |
| khoj | 37k | **481** | 7 |
| onyx | 32k | **731** | 6 |
| **median** | | **1,142** | **8** |

**Star count does not predict length, and if anything it runs the other way.**
The two shortest files in the set belong to projects with 77k and 37k stars;
the longest belongs to the one with 39k. gpt4all says what it is in 610 words.

The draft was **2,730 words across 14 H2s** when this was measured, longer than
every repo in the category including the 152k-star one. It is now about 1,760
across 11, which sits between private-gpt and open-webui. Three cuts got it
there, and they are the ones to repeat if it grows again:

- **Merge the duplicated privacy argument.** "Built for documents you can't
  upload" and "Everything runs on your machine" were making the same case in two
  places. One section.
- **Delete the redundant comparison table.** The three-column
  chat-apps/study-SaaS/SurfSense grid restated what the two prose subsections
  above it already said, and the subsections rank where a table cell cannot.
  The NotebookLM table went from 13 rows to 8, keeping the concessions.
- **Collapse the tail.** Roadmap, Documentation, Community, Pricing and
  Self-host were five H2s of links and short prose; they are one section now.
  Nobody completes a purchase or runs a Docker install from a README, so both
  are a sentence and a link.
- **Cut the FAQ.** Six questions, about 230 words. This one has a real cost and
  is argued separately below.
- **Cut the provider matrix.** Pattern 6 above says every big repo has one, but
  that turns out to be a *long*-README pattern rather than a universal one:
  khoj (481 words), onyx (731) and jan (755) have no model or provider section
  at all, while open-notebook (2,253) has two. At 1,400 words we are in the
  first group. Its four facts moved into Quick start step 2 and the offline
  bullet, which cost 15 words and saved 90. Restore the table if the model
  roster ever gets complicated enough that a reader cannot hold it in their
  head.

The format table survived at full length on purpose. Twelve rows is a lot, but
it is the differentiator and the competitor pattern supports it: open-notebook
runs a 22-row provider matrix and AnythingLLM lists 35+ providers. A reader
scanning for "can it make slides" is answered in one glance.

**Rule for future edits: anything added replaces something.** The draft is
already above the median for a project a fifth the size of the leader.

What all three of the leaders do, in order, above the first feature list:

1. **Badges on line one.** Open WebUI leads with social-style star, fork and
   watcher counts; open-notebook uses `for-the-badge` shields. Social proof
   before prose.
2. **A centred block: logo, name, one bold sentence, then a row of links.**
   open-notebook's row is *Get Started · User Guide · Features · Deploy*;
   AnythingLLM's is *Discord | License | Docs | Hosted Instance*. The reader
   gets a destination before they get a paragraph.
3. **A visual before any feature list.** All three. AnythingLLM puts a product
   GIF directly under its pitch, Open WebUI a `demo.png`, open-notebook a
   screenshot under a keyword-bearing H2. This is the single biggest gap in our
   draft, and the reason it now carries a `REPLACE-ME-studio-demo.gif`.
4. **An explicit download line for the desktop build.** AnythingLLM:
   "👉 AnythingLLM for desktop (Mac, Windows, & Linux)! Download Now".
5. **A copy-paste quick start with numbered steps.** open-notebook calls its
   section "Quick Start (2 Minutes)", inlines the whole compose file, and tells
   you "wait 15-20 seconds, then open localhost:8502". Concrete, and it sets
   an expectation about elapsed time.
6. **A provider support matrix.** open-notebook has a 22-row table with ✅/❌
   per role; AnythingLLM lists 35+ LLM providers, 13 embedders, 4 TTS and 9
   vector stores. Both are answering one question: *does it work with my
   stack?*
7. **Star history and an explicit "star the repo" ask.** All three carry the
   chart; two ask outright.

Two further patterns from the 17 Sep pull, both now in the draft:

8. **A "How X compares" section with a named subheading per competitor
   category.** PrivateGPT's reads `### vs Ollama, LM Studio, LocalAI, vLLM,
   llama.cpp` and `### vs Onyx, Open WebUI`. Each says which question that
   category answers, draws a two-line ASCII diagram of the distinction, and ends
   *"Use them together"*. It is the best thing in any of these READMEs: a
   heading can rank for `surfsense vs anythingllm` where a table cell cannot,
   and conceding that the other tool is good makes the distinction land instead
   of reading as a pitch. Our draft previously had this content as one
   three-column table with no headings; it is now three subheadings, and the
   table survives as the summary of the first two.
9. **A section addressed to the commercial buyer.** Onyx has `## Onyx for
   Enterprise` — collaboration, SSO, RBAC, analytics, query history,
   whitelabeling.

**Do not copy the substance of that last one.** Onyx is selling a team
deployment and we have none of it: no shared workspaces, no SSO, no RBAC, no
admin console. Copying the shape while lacking the features would put a false
claim in the highest-intent section of the page. The draft takes the *slot* and
fills it with the thing that is true: `## Everything stays on your machine`,
which names the material rather than job titles, and an explicit "there is no
team mode" so the absence is stated rather than implied. An earlier version
listed four professions with a bullet each; see the audience note below for why
that was cut.

Two of their moves are worth stealing precisely:

- **open-notebook's comparison table has a third column, "Advantage",** which
  tells the reader why each row matters instead of leaving them to work it out.
  Our NotebookLM table now has a "Why it matters" column for the same reason.
- **AnythingLLM spends a long collapsed section justifying its telemetry**
  (what it collects, why, how to opt out, which other domains it still calls).
  We have none, which is one line for us and five paragraphs of defence for
  them. The draft now says so where it lists the privacy properties.

What not to copy: Open WebUI's feature list runs to about 25 emoji bullets,
which works when you are the 152k-star default but buries a differentiator;
khoj's README is long and its search footprint is 15 keywords, 12 of them its
own brand (`04`); and the deploy-button walls only make sense for a server
product.

**On emoji.** All three use them heavily, in headings and on every feature
bullet. Our own README never has, in any version, so the house style wins and
the draft stays emoji-free. If we ever A/B this, emoji on the major section
headings is the cheap version of the experiment.

## What the README does differently, and why

**Artifacts lead.** This was the founder's read and the competitor data supports
it: none of the local-AI tools has a flashcards, quiz, study-guide or slides page
([`04-competitors.md`](04-competitors.md), "The edtech set"). Those SERPs belong
to RemNote, Quizlet, NoteGPT, StudyFetch and Mindgrasp, and **every one of them
uploads the user's material and charges monthly.** So the artifact capability is
the one claim that separates us from both sides at once, and the draft states it
as a three-column table rather than prose.

**The audience was rebalanced on 17 Sep, and the rebalance then had to be
corrected.** Both moves are recorded because the first one over-shot.

The draft used to open on "study guides, flashcards, quizzes, slides, mind maps
and podcasts" and illustrate with a semester of lecture PDFs, which addresses
the smaller audience: study is 21-31% of users who state a task, professional
work is about 1.8 times that, and the deliverable job is the largest single
thing anyone does with the product
([`07-what-users-do.md`](07-what-users-do.md)). So the hero line, the opening
paragraph and the demo GIF now lead with the work artefact.

The first attempt gave four professions a section with a bullet each, which
inverts the weighting the data supports. **Legal is 8.3% of users who state a
task and finance 7.1%, against study at 21-31%.** The professional total only
beats study by adding seven fragmented domains together and no single one is
close, so a section that out-weights study four-to-one is not what a 1.8-to-1
ratio licenses.

It was also argued on the wrong grounds. Those bullets were partly justified as
capturing `ai for lawyers` and `ai for accountants`, but **GitHub is absent from
those SERPs entirely** (`01`, "Who owns these SERPs": the artifact and
profession results are product pages, not repositories). This repo ranks for
`open source notebooklm`, `local notebooklm`, `notebooklm mcp` and
`notebooklm api`, and for 11 of 18 privacy keywords at average position 5.7.
**It will never rank for a profession term, so profession copy in this file
cannot be an SEO decision.** It can only be a conversion decision, and has to
earn its space on that basis.

What replaced it is one section, `## Everything stays on your machine`, which
merges the old privacy list with the material argument and puts lecture notes in
the same sentence as case papers and client working papers. That is proportionate
to the audience split, and it argues the privacy cluster, which *is* the repo's
real ranking cluster. The sentence carrying it: **the material worth doing this
to is usually the material you would not paste into a chat box** — something
neither the local chat apps nor the study SaaS can say.

**But not against NotebookLM.** NotebookLM already ships flashcards, quizzes,
mind maps and audio overviews. The differentiator is against the *local* tools —
Jan, AnythingLLM, Open WebUI, LM Studio — which are chat interfaces. Getting this
backwards would put a false claim in the comparison table, so the draft splits it:
the three-column table is versus the two competing categories, and the NotebookLM
table is about cloud, cost, models and openness, where we actually win.

The positioning line was an H2, **"NotebookLM's outputs. None of NotebookLM's
cloud."** It is a good sentence and a bad heading — it ranks for nothing, and
the 17 Sep pull showed PrivateGPT getting far more out of that slot with
`## How PrivateGPT compares` and a named subheading per rival. The draft now
does the same, so the line survives as prose inside the section rather than as
its title. Keep it for the landing page, where a heading does not have to earn
a query.

**The first paragraph is one declarative sentence plus the local claim**, not a
badge wall, because it is AI Overview feedstock. Badges sit above the H1 where
they always were; the prose below it is written to be quotable.

**H2s carry demand phrases** in the order `01` prices them, and the phrases that
count are the ones the *repo* can rank for: air-gapped and open-source in the
H1, then the artifact nouns (*What SurfSense makes*), then *Everything stays on
your machine* (offline / local / air-gapped, which is where GitHub actually
ranks, and not the profession terms, where it does not appear at all), *How
SurfSense compares* with a bolded lead-in per rival category, and *no Docker, no
terminal, no GPU* inside Quick start (the wedge against the incumbent, and two
related searches on `self hosted ai` with no good result today).

The bring-your-own-model argument, which answers XDA's "Gemini-only, no way to
override the choice" complaint, no longer has a heading of its own. It survives
as a row in the NotebookLM table and a clause in Quick start step 2. That is
thinner than it was; if `bring your own model` or `lm studio alternative`
(390, KD 5) ever justify it, the provider table comes back as the place to make
the case properly.

The comparison subheadings were `###` in the 17 Sep draft and are bold lead-ins
now. That loses a little heading weight and saves four lines; if `surfsense vs
anythingllm` ever shows real volume, promote them back.

### The FAQ was cut, and that has a cost worth naming

**Removed 17 Sep on length grounds.** It was six questions, five of them
verbatim PAA from [`05-serp-landscape.md`](05-serp-landscape.md): *Can I run
NotebookLM locally?* · *Is there an open-source alternative to NotebookLM?* ·
*Is there a free version of NotebookLM?* · *Is there an AI I can use without the
internet?* · *Can I self-host an AI?*

That block was the one part of the README written to be lifted whole into an AI
Overview, which is how Jan's `/post/offline-chatgpt-alternative` earns its
citation on `offline ai`. Cutting it takes about 230 words off a file that
needed to lose 1,200, so the trade was reasonable, but **the play is not
cancelled, only moved.** Those five questions are already briefed as page and
blog content in [`02-page-briefs.md`](02-page-briefs.md) and the landing FAQ
block carries the same five into `FAQPage` schema, where they do more than they
would here. If the README ever regains room, this is the first thing to restore.

The sixth question, *Can I use this on confidential client work?*, had no PAA
box behind it; it came from the production chat logs. Its substance survives in
`## Everything stays on your machine`, which still states what is
architecturally true and still refuses to say whether that satisfies anyone's
regulator. That refusal is the compliance-page rule from `02` and it must stay
wherever the claim lives.

### Two things that must survive any future cut

- **"Community-supported, no SLA, no hosted service."** The pivot plan requires
  the README to say this, twice over ([`00d`](../00d-pivot-plan.md), "Hosted code
  is not archived" and the T+120 runbook line). When the `## Self-host the
  server stack` section was removed for length, the sentence was kept inside
  `## Docs, roadmap and community`. Losing the section is fine; losing the
  sentence is a cross-workstream breach.
- **Chat.** The draft briefly said "there is no box here to paste it into",
  which reads as though the app has no chat. It has: `modules/chat/` streams a
  cited answer per turn, and the Quick start has always said so four lines
  later. Any privacy copy that implies the absence of chat is wrong and makes
  the product sound weaker than it is. The line now says you can ask questions
  across the material and that none of it is uploaded to make that work.

**It concedes where NotebookLM is better.** Audio and video overviews, plainly.
The current README already does this and it reads as credible rather than weak;
the alternative is a table a reader can falsify in one click.

## Accuracy constraints the draft holds to

Checked against the code, not the plan, because the plan's status table is a day
old in places:

| Claim | Source |
|---|---|
| Twelve formats, video absent | [`formats.py`](../../../surfsense_local/backend/modules/artifacts/formats.py) — 12 entries; pivot plan, "Artifacts": **Video is out** |
| Flashcards, quiz and mind map are interactive | `frontend/src/features/studio/viewers/` — `flashcards-viewer.tsx` (one card, reveal), `quiz-viewer.tsx`, `mindmap-viewer.tsx` (real Markmap). **These landed 15 Sep**, after the pivot plan's status note said the panel "renders mind map, flashcards, quiz and HTML as plain markdown". That note is stale; the README claim is safe and the plan needs updating. |
| Podcast says "audio", never MP3 | The builder takes its extension from the voice provider's media type (`worker/studio/media/audio/podcast/pipeline.py`, `_EXTENSIONS`), and the bundled Kokoro returns `audio/wav` (`modules/llm/providers/kokoro/provider.py`). So the artifact is a WAV today; no ffmpeg is in the repo and pivot plan C5 says the MP3 leg is unbuilt |
| Image and infographic need an image model, **which can be local** | `formats.py` — `requires_roles=("image_generation", "generation")`. The role is required, but it does **not** imply a remote key: `electron-builder.yml` ships stable-diffusion.cpp's `sd-server` in `extraResources`, `providers/sdcpp/` offers SD 1.5, SDXL Base and SDXL Turbo, and `resolution.py` routes an `sdcpp` selection to a loopback image provider. A draft table said the bundled column was empty for this role and that all-offline covered only three of four; both were wrong and under-sold air-gapped image generation |
| Qwen3 in six sizes from 0.5 GB | [`curated-models.json`](../../../surfsense_local/backend/modules/llm/recommendations/curated-models.json) and `providers/ollama/catalog.py` (`qwen3:0.6b` at 0.5 GB) |
| Four build targets, no Intel Mac, deb does not auto-update | Pivot plan, "Distribution" |
| App free, updates free, license gates plugins and priority support only | Pivot plan, "Licensing" |
| Self-host stack is community-supported, no SLA, no hosted service | Pivot plan, "Hosted code is not archived" — it requires the README to say exactly this |
| No team features to claim; a team licence carries a seat count that no software reads | `modules/license/verify.py` parses `maxUsers` and `service.py` surfaces it, so the seat number is real — but nothing in the app enforces or even uses it (pivot plan: "`maxUsers` is a number in the key; enforcement is the audit clause"). The draft says the seat count is commercial, not functional |
| API keys are "stored encrypted, with the secret held in your OS keychain" — not "in your keychain" | `shared/secrets.py` — the key itself is Fernet-encrypted into `provider_connections.api_key_ciphertext` in SQLite; what the keychain holds is the per-install *secret* Electron passes as `SURFSENSE_LOCAL_SECRET`. Earlier drafts said keys "live in your OS keychain", which a security-minded reader could check and find false |
| Egress destinations default to off | `modules/egress/models.py` — `enabled: Mapped[bool] = mapped_column(default=False)`. The draft says "off by default" and **must not** be strengthened to "nothing reaches the network until you allow it": two call sites still bypass `egress.require()` (pivot plan A10), so the stronger sentence is false today |

**Deliberately not claimed:** sandboxed artifact generation (generation is
unsandboxed on the user's machine; sandboxing is an enterprise roadmap item),
MP3 podcasts, video overviews, HIPAA or GDPR compliance (architectural facts
only — see the compliance page rule in `02`), and any real-time collaboration,
RBAC or connector feature from the hosted product, all of which are sunset.

## Before it ships

- [ ] **Record a Studio demo GIF.** This is the highest-value missing asset,
      because all three leaders put a visual above their feature list and we
      have none for the desktop app. `surfsense_local/` contains one image, an
      Electron icon. The hosted GIFs in `surfsense_web/public/homepage/` show
      the old web UI, so `PodcastGenGif.gif` and `ReportGenGif_compressed.gif`
      are the right *subjects* to re-record in the desktop app rather than
      assets to reuse. **Subject settled 17 Sep: a podcast.** A folder of
      documents goes in, a two-host audio conversation comes out, voiced on the
      same machine. Not the flashcard deck the first draft specified — the GIF
      is the first thing above the feature list and it tells the reader who the
      app is for before any copy does, and study is 21-31% of users who state a
      task against roughly 1.8x that for professional work.

      Podcast is the right pick for three reasons beyond that. It is the one
      format where the offline claim is *visible* rather than asserted, because
      the voice is synthesised locally and the viewer can see it happen with no
      network. It is the hardest format to fake, so it reads as a real product
      rather than a mockup. And `PodcastGenGif.gif` already exists at 3.15 MB,
      inside the budget, which makes the framing and pacing a solved problem
      even though the asset itself still has to be re-shot — it shows the
      hosted web UI, which will not exist.

      Keep it under about 5 MB; the existing set runs from 0.6 MB to 50 MB and
      the large ones do not load on a slow connection. Say "audio" in any
      caption, never MP3: the builder emits WAV (see the accuracy table).
- [ ] **Replace the hero image.** The current one reads "the open-source
  NotebookLM alternative for open web research", which is the hosted
  positioning. The draft has a `REPLACE-ME-hero` src so it fails visibly.
- [ ] **Verify the competitor claim on the day.** The draft says the local chat
      apps do not produce artifacts. True as of the 17 Sep re-pull; it is a
      claim about other people's products, so re-check Jan and AnythingLLM
      before publishing and soften to categories if either has shipped one. The
      named-subheading format makes this cheaper to keep honest than a table
      did, because each claim now sits next to the products it is about.
- [ ] **Re-read the "no team mode" paragraph before launch.** It states an
      absence — no shared workspaces, SSO, RBAC or admin console — and that is
      correct for 2.0.0. It is also the paragraph most likely to go stale first,
      since every item in it is on the enterprise roadmap.
- [ ] **Confirm the pricing table** against the founder's final Stripe prices.
      The draft omits the $60 early-bird because it expires at T+30 and a README
      is not a page anyone re-edits on a deadline; add it as a one-line note at
      launch if the founder wants it.
- [ ] **Fill the real links.** `/downloads`, `/docs`, `/pricing` and `/sunset`
      do not all exist yet (B5, B6); `/downloads` in particular must link a
      pinned tag, never `/releases/latest`, which stays on legacy v0.0.40.
- [ ] **Rewrite the four localised READMEs before restoring the language
      switcher.** The switcher is commented out in the draft, not deleted, with
      the reason inline. `README.es.md`, `README.pt-BR.md`, `README.hi.md` and
      `README.zh-CN.md` all still open on the hosted positioning ("la
      alternativa de código abierto a NotebookLM para la investigación de la
      web abierta ... para agentes de IA") and were last edited 16 Aug 2026,
      before the pivot. Linking them from a 2.0.0 README sends a reader to a
      page about an app that no longer exists, and `07` says most of our users
      are the readers who would click. `03-international.md` does not fund these
      four markets, so either rewrite them cheaply from the English draft or
      leave the row commented; Japanese and German are the two localisations
      the research does fund, and neither has a README today.
- [ ] **Fill `REPLACE-ME-DATE` in the sunset callout** with the actual export
      deadline (T+30) on publish day, and **delete the callout at T+30** along
      with the "Importing from the hosted app" link. A README is not a page
      anyone revisits on a deadline, so "30 days from launch" without a date
      would have gone stale in place.
- [ ] **Set the description and topics** in repo settings. They are not in any
      file, so they are not in any PR, which is how they stay wrong.

## Not decided here

Whether the README's artifact section should link to the feature pages in `02`
(study-guide hub, flashcards, quiz, slides) or stay self-contained. Those pages
do not exist yet, and the study pages are seasonal — the briefs want them indexed
by mid-August or the first week of January. Link them when they ship.
