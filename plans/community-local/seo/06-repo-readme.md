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
roughly 155, so the terms have to be at the **front**. Recommended:

> Open source, air-gapped NotebookLM alternative. Turn your documents into study
> guides, flashcards, quizzes, slides and podcasts — locally, private by default.
> Free desktop app, bring your own model, no account, no cloud.

220 characters, and the first 149 — everything a searcher sees — carry
*open source*, *NotebookLM alternative*, *air-gapped*, *local*, *private* and
five artifact nouns. Compare the incumbent's, which the SERP shows verbatim at
67 characters: "An open source, privacy-focused alternative to Google's Notebook
LM". We say that and what comes out of it.

Alternate, if "free" matters more in the visible window than "private":

> Open source, air-gapped NotebookLM alternative. Local AI that turns your
> documents into study guides, flashcards, quizzes, slides and podcasts. Free
> desktop app for Windows, macOS and Linux — private, offline, no account.

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

**But not against NotebookLM.** NotebookLM already ships flashcards, quizzes,
mind maps and audio overviews. The differentiator is against the *local* tools —
Jan, AnythingLLM, Open WebUI, LM Studio — which are chat interfaces. Getting this
backwards would put a false claim in the comparison table, so the draft splits it:
the three-column table is versus the two competing categories, and the NotebookLM
table is about cloud, cost, models and openness, where we actually win.

The positioning line the draft lands on is **"NotebookLM's outputs. None of
NotebookLM's cloud."**

**The first paragraph is one declarative sentence plus the local claim**, not a
badge wall, because it is AI Overview feedstock. Badges sit above the H1 where
they always were; the prose below it is written to be quotable.

**H2s carry demand phrases** in the order `01` prices them: air-gapped and
open-source in the H1, then the artifact nouns, then *Everything runs on your
machine* (offline / local / air-gapped), *no Docker, no terminal, no GPU* (the
wedge against the incumbent, and two related searches on `self hosted ai` with no
good result today), *Bring your own model* (the Gemini-only complaint), and a
question block taken from the PAA boxes in [`05-serp-landscape.md`](05-serp-landscape.md).

**The questions are verbatim PAA.** *Can I run NotebookLM locally?* · *Is there
an open-source alternative to NotebookLM?* · *Is there a free version of
NotebookLM?* · *Is there an AI I can use without the internet?* · *Can I
self-host an AI?* Each answered in one paragraph that could be lifted whole,
which is how Jan's `/post/offline-chatgpt-alternative` earns its AI Overview
citation.

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
| Image and infographic need an image model | `formats.py` — `requires_roles=("image_generation", "generation")` |
| Qwen3 in six sizes from 0.5 GB | [`curated-models.json`](../../../surfsense_local/backend/modules/llm/recommendations/curated-models.json) and `providers/ollama/catalog.py` (`qwen3:0.6b` at 0.5 GB) |
| Four build targets, no Intel Mac, deb does not auto-update | Pivot plan, "Distribution" |
| App free, updates free, license gates plugins and priority support only | Pivot plan, "Licensing" |
| Self-host stack is community-supported, no SLA, no hosted service | Pivot plan, "Hosted code is not archived" — it requires the README to say exactly this |

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
      assets to reuse. Best single shot: a folder of lecture PDFs going in and
      a flashcard deck coming out, since that is the differentiator in one
      frame. Keep it under about 5 MB; the existing set runs from 0.6 MB to
      50 MB and the large ones do not load on a slow connection.
- [ ] **Replace the hero image.** The current one reads "the open-source
  NotebookLM alternative for open web research", which is the hosted
  positioning. The draft has a `REPLACE-ME-hero` src so it fails visibly.
- [ ] **Verify the competitor claim on the day.** The draft says the local chat
      apps do not produce artifacts. True as of the 14 Sep research pass; it is
      a claim about other people's products, so re-check Jan and AnythingLLM
      before publishing and soften to categories if either has shipped one.
- [ ] **Confirm the pricing table** against the founder's final Stripe prices.
      The draft omits the $60 early-bird because it expires at T+30 and a README
      is not a page anyone re-edits on a deadline; add it as a one-line note at
      launch if the founder wants it.
- [ ] **Fill the real links.** `/downloads`, `/docs`, `/pricing` and `/sunset`
      do not all exist yet (B5, B6); `/downloads` in particular must link a
      pinned tag, never `/releases/latest`, which stays on legacy v0.0.40.
- [ ] **Translate the four localised READMEs** (`es`, `pt-BR`, `hi`, `zh-CN`)
      or delete the language switcher until they are done. `03-international.md`
      does not fund these markets, so a stale translation is worse than none;
      Japanese and German are the two localisations the research does fund, and
      neither has a README today.
- [ ] **Set the description and topics** in repo settings. They are not in any
      file, so they are not in any PR, which is how they stay wrong.

## Not decided here

Whether the README's artifact section should link to the feature pages in `02`
(study-guide hub, flashcards, quiz, slides) or stay self-contained. Those pages
do not exist yet, and the study pages are seasonal — the briefs want them indexed
by mid-August or the first week of January. Link them when they ship.
