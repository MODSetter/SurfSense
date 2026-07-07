<a href="https://www.surfsense.com/"><img width="1584" height="396" alt="SurfSense, the open-source competitive intelligence platform for AI agents" src="https://github.com/user-attachments/assets/9361ef58-1753-4b6e-b275-5020d8847261" /></a>



<div align="center">
<a href="https://discord.gg/ejRNvftDp9">
<img src="https://img.shields.io/discord/1359368468260192417" alt="Discord">
</a>
<a href="https://www.reddit.com/r/SurfSense/">
<img src="https://img.shields.io/reddit/subreddit-subscribers/SurfSense?style=social" alt="Reddit">
</a>
</div>

<div align="center">

[English](README.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | [हिन्दी](README.hi.md) | [简体中文](README.zh-CN.md)

</div>
<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>

# SurfSense: Give Your AI Agents Competitive Intelligence

SurfSense is the **open-source competitive intelligence platform for AI agents**. Your agents monitor competitors, track rankings, and listen to your market with live data from **Reddit, YouTube, Google Maps, Google Search, and the open web**, through one **REST API** or **MCP server**. Scheduled and event-triggered agents turn what they find into briefs and alerts, and a built-in knowledge base keeps every finding searchable with citations.

> [!NOTE]
> **📢 A note for our NotebookLM-alternative users**
>
> For the past couple of months we built SurfSense as the best general research agent for your own knowledge, and that chapter earned us a community we are genuinely proud of. Agentic tools like Claude, OpenCode, Hermes, and OpenClaw have now proven that agents are the future, and general research is becoming something every capable agent does out of the box. What agents still lack is **live market data and the workflows around it**, so that is where we are pointing all of our energy: becoming the definitive open-source competitive intelligence agent platform.
>
> **Nothing you rely on is going away.** Your knowledge base, chat with citations, reports, podcasts, presentations, automations, and collaborative chats all keep working, and self-hosting stays free and open source. Read the full announcement on [our changelog](https://www.surfsense.com/changelog).

## Table of contents

- [Why agents need SurfSense](#why-agents-need-surfsense)
- [What can you do with SurfSense?](#what-can-you-do-with-surfsense)
- [Live data connectors](#live-data-connectors)
- [Quick start](#quick-start)
- [Everything else in the box](#everything-else-in-the-box)
- [SurfSense vs Google NotebookLM](#surfsense-vs-google-notebooklm)
- [Roadmap](#roadmap)
- [Contribute](#contribute)

## Why agents need SurfSense

Ask any capable agent "what are competitors charging this week?" or "what is Reddit saying about us since the launch?" and it has nowhere trustworthy to look. Official platform APIs are rate-limited, priced for enterprises, or missing entirely, and scraping plumbing is brittle. SurfSense closes that gap:

- **Platform-native connectors**, each a typed REST endpoint returning structured JSON. No rate-limit roulette, no HTML parsing.
- **An MCP server** that exposes every connector as a native tool (`surfsense_reddit_scrape`, `surfsense_google_search`, and more) to Claude, Cursor, or any agent framework.
- **An agent harness**, not just raw data: retries, structured output, and credit metering are built in, so agents go from a question to a brief without you building the plumbing.
- **Open source and self-hostable**, so your competitive research stays on your own infrastructure.

## What can you do with SurfSense?

Every use case below is a real task the SurfSense agent runs end-to-end today, in one prompt or on a schedule.

### Multi-connector workflows

Chain several connectors in a single agent run and get one cited brief back.

- **Launch impact, across every platform** — "Our competitor launched v2 yesterday. Measure the reaction across search, Reddit, and YouTube." The agent scrapes SERPs, Reddit threads, and YouTube comments, then merges all three signals into one launch-impact brief.
- **Local competitor teardown** — Google Maps finds the players, the web crawler reads their pricing pages, and Google Search shows who wins the query, in one run.
- **Competitor 360, on a schedule** — an automation chains four connectors every week: site changes, rank movements, Reddit sentiment, and YouTube reaction.

### Competitor monitoring

- **Pricing watch** — extract every plan, price, and limit from competitors' pricing pages into one table, then re-check daily and alert on any change.
- **Product & changelog tracking** — crawl rivals' changelog, product, and careers pages every Monday and get a brief on what they shipped.
- **Rank & ad monitoring** — track the Google rankings, paid ads, and AI Overview citations your market actually sees, and flag movements day over day.

### B2B lead generation

- **Local business leads** — turn a category and a territory ("burger places in San Jose") into a lead list with phones, websites, ratings, and decision-maker contacts pulled from their sites.
- **Team rosters & contacts** — spider any company site and pull the full team with emails, socials, and source provenance, exported to CSV.
- **Portfolio & market mapping** — map an investor's portfolio or a whole category, then enrich every company with pricing and contacts.

### Brand & market listening

- **Reddit brand monitoring** — hear what your market says about you, your competitors, and your category in the threads where buyers speak candidly.
- **YouTube audience sentiment** — pull videos, transcripts, and comments at scale, then cluster what audiences praise and complain about.
- **Switcher & intent mining** — find the people actively asking for an alternative to a competitor, ranked by how ready they are to move.

### Market research

- **Deep research on the live web** — the agent crawls dozens of live sources on a question and synthesizes a cited answer, not a stale index.
- **AI Overview & GEO tracking** — capture when Google's AI Overviews answer your market's queries, and exactly which sources they cite.
- **Cited briefs & alerts** — everything the agents gather lands in your workspace as briefs and alerts with sources you can check.

### Automate any of it, no code

Automations run full agent turns on a schedule or in response to events, then write results back to Notion, Slack, Linear, and Jira. Describe the workflow in plain English and SurfSense builds it. Try prompts like:

- "Watch our top 3 competitors' pricing pages and alert me in Slack when a plan or price changes."
- "Track every mention of our brand on Reddit and YouTube and send me a daily digest."
- "Monitor our Google ranking for our top 10 keywords and flag drops week over week."
- "Pull new Google Maps reviews for our locations and our competitors' every Monday."
- "Run a monthly competitor analysis report and save it to my workspace."

## Live data connectors

| Connector | What your agents get | Learn more |
|---|---|---|
| **Reddit** | Posts, comments, and subreddit streams without the official API's rate limits | [Reddit Scraper API](https://www.surfsense.com/reddit) |
| **YouTube** | Videos, transcripts, and comment threads for brand and product listening | [YouTube Scraper API](https://www.surfsense.com/youtube) |
| **Google Maps** | Places, ratings, and reviews for local competitor and lead research | [Google Maps Scraper API](https://www.surfsense.com/google-maps) |
| **Google Search** | Live SERPs for rank tracking and market monitoring | [Google Search API](https://www.surfsense.com/google-search) |
| **Web Crawl** | Any page on the open web as clean, structured content | [Web Crawling API](https://www.surfsense.com/web-crawl) |
| **External MCP Connectors** | Bring any MCP server to your agents, with one-click OAuth for Notion, Slack, Jira, and more | [External MCP Connectors](https://www.surfsense.com/external-mcp-connectors) |

Billing is pay as you go: connectors bill per item actually returned, crawls per page successfully fetched, and failed calls are never billed. Self-hosted installs run with billing off. See [pricing](https://www.surfsense.com/pricing).

## Quick start

### Call a connector from code

Every connector is a REST endpoint you can call from any language with your SurfSense API key:

```bash
curl -X POST "$SURFSENSE_API_URL/workspaces/$WORKSPACE_ID/scrapers/reddit/scrape" \
  -H "Authorization: Bearer $SURFSENSE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "search_queries": ["your brand"],
    "community": "webscraping",
    "sort": "top",
    "time_filter": "week"
  }'
```

Each [connector page](https://www.surfsense.com/connectors) has copy-paste examples in Python, JavaScript, Go, PHP, Ruby, Java, and C#.

### Give the tools to your agents over MCP

Add the SurfSense MCP server to Claude, Cursor, or your own agent framework:

```json
{
  "mcpServers": {
    "surfsense": {
      "url": "https://mcp.surfsense.com/mcp",
      "headers": { "Authorization": "Bearer ${SURFSENSE_API_KEY}" }
    }
  }
}
```

Your agent can now call every connector as a native tool. See the [SurfSense MCP server](https://www.surfsense.com/mcp-server) page for the full tool list, or run the server locally from [`surfsense_mcp`](./surfsense_mcp).

### Use the cloud

Go to [surfsense.com](https://www.surfsense.com), log in, and ask the agent for live market data in plain English. New accounts start with $5 of free credit and no subscription.

### Self-host for free

Run the entire platform, connectors, agents, automations, and the MCP server on your own infrastructure. Self-hosted installs ship with billing off, so scraping, crawling, and agent runs are limited only by your hardware and the model keys you bring.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) must be installed and running.

For Linux/macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

For Windows:

```bash
irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
```

The install script sets up [Watchtower](https://github.com/nicholas-fedor/watchtower) automatically for daily auto-updates. To skip it, add the `--no-watchtower` flag. For Docker Compose, manual installation, and other deployment options, see the [docs](https://www.surfsense.com/docs/).

## Everything else in the box

The research workspace that made SurfSense the leading open-source NotebookLM alternative is still here, and everything your agents gather lands in it.

**Knowledge base**

- Upload PDFs, Office docs, images, and audio, or sync **Google Drive, OneDrive, and Dropbox**. 50+ file formats supported.
- Hybrid semantic and full-text search with cited, Perplexity-style answers.
- AI file sorting auto-organizes documents by source, date, and topic.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="Chat With Your PDFs and Docs" /></p>

**Deliverable studio**

- AI report generator with export to PDF, DOCX, HTML, LaTeX, EPUB, ODT, or plain text.
- Two-host AI podcasts from any document or folder in under 20 seconds.
- Editable slide decks, narrated video overviews, and AI image generation.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="AI Report Generator" /></p>

**Team collaboration**

- Real-time collaborative AI chats with comments and mentions.
- RBAC with Owner, Admin, Editor, and Viewer roles.

<p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="Collaborative AI Chat" /></p>

**Desktop app**

Native AI assistance in every application on your computer. Download from the [latest release](https://github.com/MODSetter/SurfSense/releases/latest).

- **General Assist**: launch SurfSense from any app with a global shortcut.
- **Quick Assist**: select text anywhere, then ask AI to explain, rewrite, or act on it.
- **Screenshot Assist**: capture any region of your screen and ask AI about it.
- **Watch Local Folder**: auto-sync a local folder to your knowledge base. Point it at your Obsidian vault to keep your notes searchable.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

**No vendor lock-in**

- 100+ LLMs via the OpenAI spec and LiteLLM, including GPT-5.5, Claude Sonnet 5, and Gemini 3.1 Pro.
- 6,000+ embedding models and all major rerankers.
- Full local and private LLM support (vLLM, Ollama), so your data stays yours.

## Video Agent Sample

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a

## Podcast Agent Sample

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7

## How to collaborate in real time (Beta)

1. Go to the Manage Members page and create an invite.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Invite Members" /></p>

2. A teammate joins and that workspace becomes shared.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Invite Join Flow" /></p>

3. Make a chat shared and work in it together in real time, with comments to tag teammates.

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="Realtime Comments" /></p>

## SurfSense vs Google NotebookLM

Still comparing us as a NotebookLM alternative? Here is the honest breakdown.

| Feature | Google NotebookLM | SurfSense |
|---------|-------------------|-----------|
| **Live market data for agents** | No | Reddit, YouTube, Google Maps, Google Search, and web crawl connectors via REST API and MCP |
| **MCP server** | No | Every connector exposed as a native agent tool, plus bring-your-own MCP servers with one-click OAuth apps |
| **Sources per Notebook** | 50 (Free) to 600 (Ultra, $249.99/mo) | Unlimited |
| **Number of Notebooks** | 100 (Free) to 500 (paid tiers) | Unlimited |
| **Source Size Limit** | 500,000 words / 200MB per source | No limit |
| **Pricing** | Free tier; Pro $19.99/mo, Ultra $249.99/mo | Free and open source to self-host; cloud is pay as you go with $5 free credit |
| **LLM Support** | Google Gemini only | 100+ LLMs via OpenAI spec & LiteLLM |
| **Embedding Models** | Google only | 6,000+ embedding models, all major rerankers |
| **Local / Private LLMs** | Not available | Full support (vLLM, Ollama), your data stays yours |
| **Self Hostable** | No | Yes, Docker one-liner or full Docker Compose |
| **Open Source** | No | Yes |
| **Knowledge Base Sources** | Google Drive, YouTube, websites | File uploads, Google Drive, OneDrive, Dropbox, local folder sync, and crawled pages |
| **File Format Support** | PDFs, Docs, Slides, Sheets, CSV, Word, EPUB, images, web URLs, YouTube | 50+ formats: documents, images, videos via LlamaCloud, Unstructured, or Docling (local) |
| **Search** | Semantic search | Hybrid semantic + full-text with hierarchical indices & reciprocal rank fusion |
| **Cited Answers** | Yes | Yes, Perplexity-style cited responses |
| **Agentic Architecture** | No | Yes, powered by [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) with planning, subagents, and file system access |
| **AI Automations & Agents** | No | Scheduled workflows, event triggers, and chat-built no-code automations with write-back to Notion, Slack, Linear & Jira |
| **Real-Time Multiplayer** | Shared notebooks with Viewer/Editor roles (no real-time chat) | RBAC with Owner / Admin / Editor / Viewer roles, real-time chat & comment threads |
| **Video Generation** | Cinematic Video Overviews via Veo 3 (Ultra only) | Available (NotebookLM is better here, actively improving) |
| **Presentation Generation** | Better looking slides but not editable | Editable, slide-based presentations |
| **Podcast Generation** | Audio Overviews with customizable hosts and languages | Available with multiple TTS providers (NotebookLM is better here, actively improving) |
| **Desktop App** | No | Native app with General Assist, Quick Assist, Screenshot Assist, and local folder sync |

## Feature requests and future

**SurfSense is actively being developed.** While it's not yet production-ready, you can help us speed up the process.

Join the [SurfSense Discord](https://discord.gg/ejRNvftDp9) and help shape the future of SurfSense!

## Roadmap

Stay up to date with our development progress and upcoming features. Check out our public roadmap and contribute your ideas or feedback:

**Roadmap Discussion:** [SurfSense 2026 Roadmap](https://github.com/MODSetter/SurfSense/discussions/565)

**Kanban Board:** [SurfSense Project Board](https://github.com/users/MODSetter/projects/3)

## Contribute

All contributions welcome, from stars and bug reports to backend improvements. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

Thanks to all our Surfers:

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" />
</a>

## Star History

<a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
 </picture>
</a>

---
---
<p align="center">
    <img 
      src="https://github.com/user-attachments/assets/329c9bc2-6005-4aed-a629-700b5ae296b4" 
      alt="Catalyst Project" 
      width="200"
    />
</p>

---
---
