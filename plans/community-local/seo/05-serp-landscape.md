# SERP landscape for the four priority head terms

What the Google results page looks like for `self hosted ai`, `offline ai`,
`notebooklm mcp` and `private ai`, read as a spec for what a page has to be to
appear there, plus `study guide maker`, the head of the Studio-output pass,
which is a different kind of results page. Companion to
[`01-keyword-research.md`](01-keyword-research.md) (which picks the terms) and
[`04-competitors.md`](04-competitors.md) (who is winning them).

**Source:** `serp/google/organic/live/advanced`, US desktop, depth 20, AI
Overview loaded, pulled 14 Sep 2026. The five responses are archived as
`data/serp-*.json` and re-render with `python data/parse.py --mode serp "serp-*.json"`.
SERPs move daily and AI Overviews move faster; re-pull before acting on a
specific position. The *shape* of each page is what this document records, and
that is stable for months.

## The pattern across all four

| term | AI Overview | organic #1 | UGC in top 10 | vendor pages in top 10 | GitHub in top 10 | ads |
|---|---|---|---|---|---|---|
| self hosted ai | position 1 | Reddit r/selfhosted | Reddit ×2, YouTube, Medium, forum | DreamHost, Budibase, Northflank (blogs) | `/topics/self-hosted-ai` at 10 | none |
| offline ai | position 1 | Reddit r/LocalLLM | Reddit ×2, YouTube | Layla (app), Play Store | `Wakoma/OfflineAI` catalog at 6 | none |
| notebooklm mcp | position 5, below four organic results | GitHub `PleasePrompto/notebooklm-mcp` | Reddit, Medium | mcpservers.org, npm, mcpmarket.com | #1 and #14 | none |
| private ai | position 1 | venice.ai | Reddit, YouTube | Venice, Privatemode, Confer, Cloudera | none | zanusai.com ×2 |

Five things hold on every one of them:

1. **The AI Overview is the first result on three of four.** "Ranking #1" means
   position 2 on the page. Being *cited* by the Overview is worth more than the
   blue link, and the citation lists below show what gets cited.
2. **Reddit and YouTube are cited on all four.** They are not competitors we
   displace; they are surfaces we need to be present on. A well-received post
   in r/selfhosted, r/LocalLLM or r/notebooklm is a ranking asset.
3. **Vendor pages appear only when they are shaped like answers.** Jan's blog
   post, Northflank's guide, DreamHost's list, Cloudera's FAQ. Nobody's
   marketing homepage is cited except on `private ai`, where the products *are*
   the answer (Venice, Lumo, Privatemode).
4. **GitHub is in the top 10 on three of four**, as a topic page, a catalog
   repo and a project repo. Registry and directory pages (npm, mcpservers.org,
   Play Store, Chrome Web Store) rank alongside it.
5. **People Also Ask boxes are finished H2 lists**, and Related Searches are the
   modifiers people add. Both are reproduced per term below and should go
   straight into the page briefs.

## `self hosted ai` — 2,900/mo, KD 10

**AI Overview at position 1**, citing nine sources: Reddit r/selfhosted,
YouTube, forum.level1techs.com, deployhq.com, dreamhost.com, northflank.com,
qualixsolutions.com, ibl.ai and a University of South Florida library guide.

| pos | domain | title |
|---|---|---|
| 2 | reddit.com | Self-Hosting AI Models: Lessons Learned? Share Your Pain |
| 4 | youtube.com | The Best Self-Hosted AI Tools You Can Actually Run in Your Home Lab |
| 5 | dreamhost.com | Self-Hosted AI: 10 Best Local AI Models to Run |
| 6 | budibase.com | 10 Self-Hosted AI Tools |
| 8 | medium.com | I Spent 3 Days Researching Self-Hosted AI. Here's Why… |
| 9 | guides.lib.usf.edu | AI Tools and Resources: Self Hosting AIs for Research |
| 10 | github.com | `/topics/self-hosted-ai` |
| 11 | northflank.com | Self-hosting AI models: Complete guide to privacy, control, and cost |
| 15 | xda-developers.com | I turned my home server into an AI appliance |
| 16 | tailscale.com | Self-host a local AI stack and access it from anywhere |

**People also ask:** Can I self host an AI? · What is the best self-hosted AI? ·
Is self-hosting legal? (plus one unrelated question.)

**Related searches:** self hosted ai free · reddit · llama · hardware · best
self-hosted AI model · **without GPU** · **docker** · for coding.

**Reading.** Every result frames "self-hosted AI" as *running a model on a home
lab*: hardware, GPUs, Docker, Ollama. Nobody frames it as a document workspace.
The related searches expose two anxieties — "without GPU" and "docker" — and
both are things SurfSense removes: bring-your-own-key means no GPU, and signed
installers mean no Docker. A guide titled for those two modifiers is the entry
point; the head term is Reddit's.

Two cheap actions fall out of this SERP: add the `self-hosted-ai` topic to the
repo (the topic page itself ranks 10th), and note that four of the cited
sources are hosting-company blogs writing "complete guide" posts. That format is
citable; a marketing page is not.

## `offline ai` — 1,600/mo, KD 7

**AI Overview at position 1**, citing eight sources: Reddit r/LocalLLM, YouTube
×2, Medium, swmansion.com, **jan.ai/post/offline-chatgpt-alternative**,
gamma.app, layla-network.ai and overchat.ai. Its text says: download a local
inference app and an open-source model; names LM Studio, Ollama, Jan and mobile
apps; and gives hardware minimums (8 GB RAM for small models, 16 GB ideal).

| pos | domain | title |
|---|---|---|
| 2 | reddit.com | Anyone here actually using AI fully offline? r/LocalLLM |
| 4 | swmansion.com | Top 6 Local AI Models to Run Offline (2026) |
| 5 | play.google.com | Local AI - Offline AI chatbot |
| 6 | github.com | `Wakoma/OfflineAI` — a catalog of offline AI tools |
| 7 | layla-network.ai | Layla: Private Offline AI Assistant for Android & iOS |
| 9 | reddit.com | Looking to Build My Own Offline AI — Where Do I Start? |
| 10 | youtube.com | I Found an AI That Works Offline (And It's 100% Free) |
| 18 | makeuseof.com | I now use this offline AI assistant instead of cloud chatbots |
| 21 | localai.io | LocalAI · Make AI run on every machine |
| 22 | overchat.ai | Best Offline AI Apps in 2026 |

**People also ask:** Is there any AI that is offline? · Can AI be run offline? ·
Which AI tool can I use offline? · Is there an AI I can use without internet?

**Related searches:** offline ai chatbot · free · Ollama · apk · **app for
Windows** · by Google · **download** · chatbot free.

**Reading.** The one vendor inside the Overview is Jan, with a post titled
*"You can't run ChatGPT offline, do this instead"*. That title is the template:
it names the thing people want, says it is impossible, and offers the answer.
Ours writes itself — *"You can't run NotebookLM offline. Do this instead."* —
and `notebooklm offline` (40/mo) plus the four PAA questions are its H2s.

This SERP skews consumer and mobile (Play Store, apk, Layla, Chrome extension).
"Offline AI for your documents" on desktop is the unoccupied angle. "Offline AI
app for Windows" and "Offline AI download" are related searches with no good
result, and they are `/downloads` H2s.

## `notebooklm mcp` — 720/mo, KD 1

The only one of the four where **organic results beat the AI Overview**, which
sits at position 5 behind four organic results.

| pos | domain | title |
|---|---|---|
| 1 | github.com | `PleasePrompto/notebooklm-mcp` — "drives a real Chrome via Patchright" |
| 2 | mcpservers.org | NotebookLM MCP Server |
| 3 | xda-developers.com | NotebookLM now connects to Claude through MCP (Feb 2026) |
| 4 | reddit.com | Made NotebookLM MCP Way Easier to Install, r/notebooklm |
| 5 | *AI Overview* | cites Reddit, YouTube, GitHub `moodRobotics`, mcpservers.org, notebooklm-guide.com |
| 6 | medium.com | Automate Google NotebookLM from your AI agent |
| 7 | npmjs.com | `@m4ykeldev/notebooklm-mcp` |
| 10 | juliangoldie.com | NotebookLM MCP Setup |
| 11 | mcpmarket.com | NotebookLM for Claude |
| 14 | github.com | `jacob-bd/gemini-notebook-mcp-cli` |
| 15–17 | skillsllm.com, composio.dev, mcpservers.org | directory listings |

**People also ask:** How to add NotebookLM MCP to Claude? · Can I connect Claude
to NotebookLM? · Can I use Claude Code with an MCP Server? · How is NotebookLM
different from ChatGPT?

**Related searches:** notebooklm mcp-cli · github · claude · antigravity ·
reddit · "Install the NotebookLM MCP tool" · npx notebooklm-mcp latest.

**Reading.** Every result is a community project that connects *Google's*
NotebookLM to Claude by automating a browser: "drives a real Chrome",
`nlm login` with a Google account, Patchright. The Overview's setup steps
include authenticating with Google. That is the whole SERP's weakness and
SurfSense's opening in one sentence: **a NotebookLM-style MCP server that is
native, needs no browser automation and no Google account.**

Three surfaces we are absent from and every competitor is on: the repo (two
GitHub results), the package registry (npm at 7; PyPI would do the same), and
the MCP directories (mcpservers.org twice, mcpmarket.com, composio.dev,
skillsllm.com). Listing costs an afternoon. The page brief in
[`02-page-briefs.md`](02-page-briefs.md) has the copy-pasteable config
requirement; this SERP is why.

One more signal: the Overview and two results call the product "Gemini
Notebook (formerly NotebookLM)". `gemini notebooklm` is 590/mo and up 1,614%;
`gemini notebook vs notebooklm` has just appeared. If Google is renaming it,
our comparison copy should carry both names.

## `private ai` — 8,100/mo (5,400 recent), KD 14

**AI Overview at position 1**, citing lumo.proton.me, privatemode.ai,
cloudera.com ×2, venice.ai, a vellum.ai listicle and ai21.com ×2. It defines
private AI as systems "where your data, prompts, and interactions never leave
your own device or organization's private infrastructure", then lists four
mechanisms: local processing, zero data retention, end-to-end encryption, and
regulatory compliance (HIPAA, GDPR).

| pos | domain | title |
|---|---|---|
| 2 | venice.ai | Venice — Private AI for Unlimited Creative Freedom |
| 4 | cloudera.com | What Is Private AI? (FAQ) |
| 5 | privatemode.ai | Private AI chatbot, always encrypted |
| 6 | reddit.com | Are there any viable private AI options? r/privacy |
| 7 | confer.to | Confer — Private AI. Speak freely. |
| 8 | youtube.com | STOP using ChatGPT (use private AI alternatives) — 55k views |
| 9 | digitalrealty.com | What is Private AI? |
| 11 | play.google.com | Private AI — run models on your phone |
| 12, 24 | **paid: zanusai.com** | "Private on-premise AI… No Internet Required. Buy once, own forever." |
| 15 | vellum.ai | 10 Best Private Personal AI Assistants in 2026 |
| 16–23 | vmware.com, blog.google, hpe.com, teradata.com, coresite.com | enterprise glossaries |

**People also ask:** What AI can I use privately? · Can I have my own private
AI? · How much is private AI? (plus one unrelated question.)

**Related searches:** private ai chatbot · free · app · for android · Venice AI
· **github** · software · login.

**Reading.** Two markets share this page and neither is ours. Consumer "private
chatbot" products (Venice, Lumo, Confer, Privatemode) are *encrypted cloud*, not
local; enterprise "private AI" (Cloudera, VMware, HPE, Teradata) is
infrastructure. The Overview's own definition — data never leaves your device —
describes SurfSense more exactly than it describes most of what it cites, and
the only local-first mention is inside a listicle.

Do not chase the head term; chase its children. `private ai chatbot` (5,400,
KD 12) and `best private ai` (5,400, KD 15) are the two top-scored keywords in
the master list, with `private llm` (2,900, KD 21) further down, and "for your
documents" is the qualifier nobody on this page uses.

The advertiser is worth noting. Zanus is paying for `private ai` with the pitch
"on-premise, no internet required, buy once, own forever" — a perpetual licence
for offline AI. Someone has already validated the offer shape the pivot plan
chose. Whether to test paid search on these terms is not this document's call;
the CPCs (`private ai` $4, `self hosted ai` $14, `air-gapped ai` $22) are in
the master list if anyone wants to model it.

## What a page must be to appear here

Derived from the citation lists above, in priority order.

| requirement | evidence |
|---|---|
| A direct answer in the first paragraph, under a title shaped like the question | Jan, Northflank, DreamHost and Cloudera are the only vendors cited; all four open with a definition or a verdict |
| Present on GitHub with a query-shaped repo name, description and topics | GitHub in top 10 on three of four SERPs; `/topics/self-hosted-ai` ranks on its own |
| Listed in the registries the query implies | npm, mcpservers.org, mcpmarket.com, composio.dev for MCP; Play Store and Chrome Web Store for offline |
| The PAA questions answered as H2s, one paragraph each | PAA sits at position 3 on three of four SERPs, above most organic results |
| A Reddit thread that mentions us, ideally ours | Reddit cited in every Overview and #1 or #2 organic on three of four |
| Third-party inclusion in "N best…" listicles | Vellum, Overchat, SwMansion, DreamHost, Budibase all cited or ranking; we are in none |

Two content pieces this SERP set asks for directly, beyond the page briefs:

- **"You can't run NotebookLM offline. Do this instead."** — the Jan template
  applied to our incumbent. Targets `notebooklm offline`, the `offline ai` PAA
  set, and the Overview's appetite for answer-shaped vendor posts.
- **"Self-hosted AI without a GPU (and without Docker)"** — the two related
  searches on `self hosted ai` that name our differentiators. Structured as the
  hosting-company guides are, with the hardware section the Overview keeps
  quoting (RAM minimums), except our answer is "any laptop, bring a key".

## Re-pulling

```bash
cd plans/community-local/seo/data
python parse.py --mode serp "serp-*.json"            # render the archived five
```

To refresh one, `POST serp/google/organic/live/advanced` with
`{"keyword": "...", "location_code": 2840, "language_code": "en",
"device": "desktop", "depth": 20, "load_async_ai_overview": true}` — one
keyword per call, the live endpoint rejects batches — and save the response as
`serp-<keyword-with-dashes>.json`. The renderer derives the heading from the
filename. Three of the archived files are trimmed to the fields the renderer
reads because their responses arrived inline; `serp-self-hosted-ai.json` is the
full response.
