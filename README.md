<a href="https://www.surfsense.com/"><img width="1584" height="396" alt="readme_banner" src="https://github.com/user-attachments/assets/9361ef58-1753-4b6e-b275-5020d8847261" /></a>



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

# SurfSense

NotebookLM is one of the best and most useful AI platforms out there, but once you start using it regularly you also feel its limitations leaving something to be desired more.

1. There are limits on the amount of sources you can add in a notebook.
2. There are limits on the number of notebooks you can have.
3. You cannot have sources that exceed 500,000 words and are more than 200MB.
4. You are vendor locked in to Google services (LLMs, usage models, etc.) with no option to configure them.
5. Limited external data sources and service integrations.
6. NotebookLM Agent is specifically optimised for just studying and researching, but you can do so much more with the source data.
7. Lack of multiplayer support.

...and more.

**SurfSense is specifically made to solve these problems.** SurfSense empowers you to:

- **Control Your Data Flow** - Keep your data private and secure.
- **No Data Limits** - Add an unlimited amount of sources and notebooks.
- **No Vendor Lock-in** - Configure any LLM, image, TTS, and STT models to use.
- **25+ External Data Sources** - Add your sources from Google Drive, OneDrive, Dropbox, Notion, and many other external services.
- **Real-Time Multiplayer Support** - Work easily with your team members in a shared notebook.
- **AI File Sorting** - Automatically organize your documents into a smart folder hierarchy using AI-powered categorization by source, date, and topic.
- **Desktop App** - Get AI assistance in any application with Quick Assist, General Assist, Screenshot Assist, and local folder sync.

...and more to come.



## Video Agent Sample

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a



## Podcast Agent Sample

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## How to Use SurfSense

### Cloud

1. Go to [surfsense.com](https://www.surfsense.com) and login.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/LoginFlowGif.gif" alt="Login" /></p>

2. Connect your connectors and sync. Enable periodic syncing to keep connectors synced.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ConnectorFlowGif.gif" alt="Connectors" /></p>

3. Till connectors data index, upload Documents.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/DocUploadGif.gif" alt="Upload Documents" /></p>

4. Once everything is indexed, Ask Away (Use Cases):

   - Desktop App — General Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/general_assist.gif" alt="General Assist" /></p>

   - Desktop App — Quick Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

   - Desktop App — Screenshot Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/screenshot_assist.gif" alt="Screenshot Assist" /></p>

   - Desktop App — Watch Local Folder

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/folder_watch.gif" alt="Watch Local Folder" /></p>

   - Video Generation

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/video_gen_gif.gif" alt="Video Generation" /></p>

   - Basic search and citation

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BSNCGif.gif" alt="Search and Citation" /></p>

   - Document Mention QNA

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="Document Mention QNA" /></p>
   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="Document Mention QNA" /></p>

   - Report Generations and Exports (PDF, DOCX, HTML, LaTeX, EPUB, ODT, Plain Text)

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="Report Generation" /></p>

   - Podcast Generations

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/PodcastGenGif.gif" alt="Podcast Generation" /></p>

   - Image Generations

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ImageGenGif.gif" alt="Image Generation" /></p>

   - And more coming soon.


### Self Hosted

Run SurfSense on your own infrastructure for full data control and privacy.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) must be installed and running.

#### For Linux/MacOS users:

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

#### For Windows users:

```bash
irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
```

The install script sets up [Watchtower](https://github.com/nicholas-fedor/watchtower) automatically for daily auto-updates. To skip it, add the `--no-watchtower` flag.

For Docker Compose, manual installation, and other deployment options, see the [docs](https://www.surfsense.com/docs/).

### Desktop App

SurfSense also ships a desktop app that brings AI assistance to every application on your computer. Download it from the [latest release](https://github.com/MODSetter/SurfSense/releases/latest).

The desktop app includes these powerful features:

- **General Assist** — Launch SurfSense instantly from any application with a global shortcut.
- **Quick Assist** — Select text anywhere, then ask AI to explain, rewrite, or act on it.
- **Screenshot Assist** — Select a region on your screen and attach it to chat so answers stay grounded in your knowledge base.
- **Watch Local Folder** — Watch a local folder and automatically sync file changes to your knowledge base. **Pro tip:** Point it at your Obsidian vault to keep your notes searchable in SurfSense.

All features operate against your chosen search space, so your answers are always grounded in your own data.

### How to Realtime Collaborate (Beta)

1. Go to Manage Members page and create an invite.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Invite Members" /></p>

2. Teammate joins and that SearchSpace becomes shared.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Invite Join Flow" /></p>

3. Make chat shared.

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="Make Chat Shared" /></p>

4. Your team can now chat in realtime.

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="Realtime Chat" /></p>

5. Add comment to tag teammates.

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="Realtime Comments" /></p>

## SurfSense vs Google NotebookLM

| Feature | Google NotebookLM | SurfSense |
|---------|-------------------|-----------|
| **Sources per Notebook** | 50 (Free) to 600 (Ultra, $249.99/mo) | Unlimited |
| **Number of Notebooks** | 100 (Free) to 500 (paid tiers) | Unlimited |
| **Source Size Limit** | 500,000 words / 200MB per source | No limit |
| **Pricing** | Free tier available; Pro $19.99/mo, Ultra $249.99/mo | Free and open source, self-host on your own infra |
| **LLM Support** | Google Gemini only | 100+ LLMs via OpenAI spec & LiteLLM |
| **Embedding Models** | Google only | 6,000+ embedding models, all major rerankers |
| **Local / Private LLMs** | Not available | Full support (vLLM, Ollama) - your data stays yours |
| **Self Hostable** | No | Yes - Docker one-liner or full Docker Compose |
| **Open Source** | No | Yes |
| **External Connectors** | Google Drive, YouTube, websites | 27+ connectors - Search Engines, Google Drive, OneDrive, Dropbox, Slack, Teams, Jira, Notion, GitHub, Discord & [more](#external-sources) |
| **File Format Support** | PDFs, Docs, Slides, Sheets, CSV, Word, EPUB, images, web URLs, YouTube | 50+ formats - documents, images, videos via LlamaCloud, Unstructured, or Docling (local) |
| **Search** | Semantic search | Hybrid Search - Semantic + Full Text with Hierarchical Indices & Reciprocal Rank Fusion |
| **Cited Answers** | Yes | Yes - Perplexity-style cited responses |
| **Agentic Architecture** | No | Yes - powered by [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) with planning, subagents, and file system access |
| **Real-Time Multiplayer** | Shared notebooks with Viewer/Editor roles (no real-time chat) | RBAC with Owner / Admin / Editor / Viewer roles, real-time chat & comment threads |
| **Video Generation** | Cinematic Video Overviews via Veo 3 (Ultra only) | Available (NotebookLM is better here, actively improving) |
| **Presentation Generation** | Better looking slides but not editable | Create editable, slide-based presentations |
| **Podcast Generation** | Audio Overviews with customizable hosts and languages | Available with multiple TTS providers (NotebookLM is better here, actively improving) |
| **AI File Sorting** | No | LLM-powered auto-categorization into source, date, category, and subcategory folders |
| **Desktop App** | No | Native app with General Assist, Quick Assist, Screenshot Assist, and local folder sync |
| **Browser Extension** | No | Cross-browser extension to save any webpage, including auth-protected pages |

<details>
<summary><b>Full list of External Sources</b></summary>
<a id="external-sources"></a>

Search Engines (Tavily, LinkUp) · SearxNG · Google Drive · OneDrive · Dropbox · Slack · Microsoft Teams · Linear · Jira · ClickUp · Confluence · BookStack · Notion · Gmail · YouTube Videos · GitHub · Discord · Airtable · Google Calendar · Luma · Circleback · Elasticsearch · Obsidian, and more to come.

</details>


## FEATURE REQUESTS AND FUTURE


**SurfSense is actively being developed.** While it's not yet production-ready, you can help us speed up the process.

Join the [SurfSense Discord](https://discord.gg/ejRNvftDp9) and help shape the future of SurfSense!

## Roadmap

Stay up to date with our development progress and upcoming features!  
Check out our public roadmap and contribute your ideas or feedback:

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
