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
Connect any LLM to your internal knowledge sources and chat with it in real time alongside your team. OSS alternative to NotebookLM, Perplexity, and Glean.

SurfSense is a highly customizable AI research agent, connected to external sources such as Search Engines (SearxNG, Tavily, LinkUp), Google Drive, OneDrive, Dropbox, Slack, Microsoft Teams, Linear, Jira, ClickUp, Confluence, BookStack, Gmail, Notion, YouTube, GitHub, Discord, Airtable, Google Calendar, Luma, Circleback, Elasticsearch, Obsidian and more to come.



# Demo

https://github.com/user-attachments/assets/cc0c84d3-1f2f-4f7a-b519-2ecce22310b1

## Video Agent Sample



https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a



## Podcast Agent Sample

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## How to Use SurfSense

### Cloud

1. Go to [surfsense.com](https://www.surfsense.com) and login.

<p align="center"><img src="https://github.com/user-attachments/assets/b4df25fe-db5a-43c2-9462-b75cf7f1b707" alt="Login" /></p>

2. Connect your connectors and sync. Enable periodic syncing to keep connectors synced.

<p align="center"><img src="https://github.com/user-attachments/assets/0740f351-23fa-4909-9880-70aa1dcc1df7" alt="Connectors" /></p>

3. Till connectors data index, upload Documents.

<p align="center"><img src="https://github.com/user-attachments/assets/daf3dbae-ef86-4e86-82ea-fcbcad988761" alt="Upload Documents" /></p>

4. Once everything is indexed, Ask Away (Use Cases):

   - Video Generation

   <p align="center"><img src="https://github.com/user-attachments/assets/af85c0f3-6cfd-4757-9706-07fd5e32c857" alt="Search and Citation" /></p>
   
   - Basic search and citation

   <p align="center"><img src="https://github.com/user-attachments/assets/81e797a1-e01a-4003-8e60-0a0b3a9789df" alt="Search and Citation" /></p>

   - Document Mention QNA

   <p align="center"><img src="https://github.com/user-attachments/assets/65c3bf06-1d46-4dd5-b169-4d934c9b6798" alt="Document Mention QNA" /></p>
   <p align="center"><img src="https://github.com/user-attachments/assets/be958295-0a8c-4707-998c-9fe1f1c007be" alt="Document Mention QNA" /></p>

   - Report Generations and Exports (PDF, DOCX, HTML, LaTeX, EPUB, ODT, Plain Text)

   <p align="center"><img src="https://github.com/user-attachments/assets/9836b7d6-57c9-4951-b61c-68202c9b6ace" alt="Report Generation" /></p>

   - Podcast Generations

   <p align="center"><img src="https://github.com/user-attachments/assets/58c9b057-8848-4e81-aaba-d2c617985d8c" alt="Podcast Generation" /></p>

   - Image Generations

   <p align="center"><img src="https://github.com/user-attachments/assets/25f94cb3-18f8-4854-afd9-27b7bfd079cb" alt="Image Generation" /></p>

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

### How to Realtime Collaborate (Beta)

1. Go to Manage Members page and create an invite.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Invite Members" /></p>

2. Teammate joins and that SearchSpace becomes shared.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Invite Join Flow" /></p>

3. Make chat shared.

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="Make Chat Shared" /></p>

4. Your team can now chat in realtime.

   <p align="center"><img src="https://github.com/user-attachments/assets/83803ac2-fbce-4d93-aae3-85eb85a3053a" alt="Realtime Chat" /></p>

5. Add comment to tag teammates.

   <p align="center"><img src="https://github.com/user-attachments/assets/3b04477d-8f42-4baa-be95-867c1eaeba87" alt="Realtime Comments" /></p>

## Key Features

| Feature | Description |
|---------|-------------|
| OSS Alternative | Drop in replacement for NotebookLM, Perplexity, and Glean with real time team collaboration |
| 50+ File Formats | Upload documents, images, videos via LlamaCloud, Unstructured, or Docling (local) |
| Hybrid Search | Semantic + Full Text Search with Hierarchical Indices and Reciprocal Rank Fusion |
| Cited Answers | Chat with your knowledge base and get Perplexity style cited responses |
| Deep Agent Architecture | Powered by [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) planning, subagents, and file system access |
| Universal LLM Support | 100+ LLMs, 6000+ embedding models, all major rerankers via OpenAI spec & LiteLLM |
| Privacy First | Full local LLM support (vLLM, Ollama) your data stays yours |
| Team Collaboration | RBAC with Owner / Admin / Editor / Viewer roles, real time chat & comment threads |
| Video Generation | Generate videos with narration and visuals |
| Presentation Generation | Create editable, slide based presentations |
| Podcast Generation | 3 min podcast in under 20 seconds; multiple TTS providers (OpenAI, Azure, Kokoro) |
| Browser Extension | Cross browser extension to save any webpage, including auth protected pages |
| 27+ Connectors | Search Engines, Google Drive, OneDrive, Dropbox, Slack, Teams, Jira, Notion, GitHub, Discord & [more](#external-sources) |
| Self Hostable | Open source, Docker one liner or full Docker Compose for production |

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
