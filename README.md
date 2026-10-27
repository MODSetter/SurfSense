<!--
  Rationale and how to change it: plans/community-local/seo/06-repo-readme.md. Anything
  added replaces something (AGENTS.md). The agent copy holds from v2.2.0, the first
  release whose installers carry the agent.
  The format table is checked against origin/dev c5ff7938a, which v2.2.0 contains; re-check
  each cell against the release commit before a release.
  The demo videos under the header are GitHub uploads, not files in the repo, each under a bold
  caption on its own line. To replace one, drag an MP4 under 10 MB into any comment box in this
  repo, copy the user-attachments link and swap the URL.
  Every README.<locale>.md follows this file section for section and names the app's UI in
  the words of surfsense_local/frontend/translations/<locale>.json (Arabic: the English in
  parentheses); change them together.
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense, the air-gapped open-source NotebookLM alternative" src="www/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>The air-gapped, open-source NotebookLM alternative.</b>
    <br />
    The AI agent that researches, transforms and edits your documents, on your machine.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Download</b></a> ·
    <a href="#what-it-does-with-each-format">Formats</a> ·
    <a href="#quick-start">Quick start</a> ·
    <a href="#how-it-compares">Compare</a> ·
    <a href="#plugins">Plugins</a> ·
    <a href="https://www.surfsense.com/pricing">Pricing</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    English | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

**Redline a contract with tracked changes and comments**

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

**Add sources from the web, then turn them into a web page**

https://github.com/user-attachments/assets/073577b7-f055-4f59-8540-330bd764aeb0

SurfSense is a free, open-source desktop app for documents you can't upload. A privacy-focused, NotebookLM-style AI agent that researches, transforms and edits your documents, on your machine. The index stays on your disk, you pick the model, local or remote, and there is no account.

| Platform | Download |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://www.surfsense.com/downloads/windows?src=readme) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://www.surfsense.com/downloads/mac?src=readme) |
| **Linux** x64 | [AppImage](https://www.surfsense.com/downloads/linux-appimage?src=readme) · [deb](https://www.surfsense.com/downloads/linux-deb?src=readme) |

## Quick start

1. Install SurfSense and do the initial onboarding setup.
2. Drop your files or folders in your sources.
3. Ask the agent to search or extract or edit your files.

## What it does with each format

| Format | Research (cited answers) | Create | Edit (as a copy) | Transform |
|---|---|---|---|---|
| **PDF** | ✓ scanned pages too³ | ✓ | Fill and flatten forms; stamp watermarks, page numbers, headers, footers | Merge, split, extract, rotate, reorder pages |
| **Word** `.docx` | ✓ | ✓ or from your own `.docx` as a template | ✓ body text, as tracked changes and comments | To PDF¹ |
| **Excel** `.xlsx` | ✓ the agent also reads formulas | ✓ with formulas and native charts | ✓ cell values and formulas | Analyse with pandas, chart the results |
| **PowerPoint** `.pptx` | ✓ | ✓ or from your own `.pptx` as a template | Replace text on slides and notes; delete or duplicate slides | To PDF¹ |
| **CSV** | ✓ | — | — | Analyse with pandas, chart the results |
| **Images** PNG, JPEG, TIFF, BMP, WebP | ✓ text read by OCR³ | Images and infographics² | — | Place in new documents |
| **Markdown**, plain text | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ web page | — | — |
| **Recordings** WAV, MP3, FLAC, Ogg Vorbis | ✓ transcribed on your machine | — | — | — |
| **Podcast** (audio) | — | ✓ with a transcript, voiced on your machine by default | — | — |
| **Mind maps, flashcards, quizzes** | — | ✓ in the app | — | — |

<sub>¹ With Office support (LibreOffice), turned on in Settings; it is never in the installer. ² Needs an image model, local or remote; none is chosen by default. ³ OCR reads Latin, Chinese and Japanese script.</sub>

Edits, conversions and PDF tools always make a new file; your original is never changed. PDF, Word and Excel do the most today, and support for the other formats keeps improving.

## Plugins

Connect them in **Settings › Plugins**.

**By SurfSense.** They read public pages without your own accounts and need a SurfSense license: [download the app](https://www.surfsense.com/downloads) and enter your email there for a free 14-day one.

| Plugin | What it does |
|---|---|
| **Google Search** | Search Google and read its results, ads and related questions |
| **Web Crawl** | Read a web page, or crawl a whole site into clean text |
| **YouTube** | Read YouTube videos, channels and their comments |
| **TikTok** | Read TikTok videos and their comments, search users, and see what is trending |
| **Reddit** | Read public Reddit posts with their comment threads, or a whole community |
| **Instagram** | Read public Instagram profiles, posts and reels, and find profiles by search |
| **Google Maps** | Find places on Google Maps and read their reviews |
| **Amazon** | Read Amazon products and search results |
| **Walmart** | Read Walmart products, search results and reviews |
| **Indeed** | Read job listings on Indeed |

**Third-party.** MCP servers from the [plugin registry](backend/plugins/registry), such as DeepWiki and Notion, or any you add by URL. No license needed; they stay off until you allow them.

## How it compares

| | NotebookLM (now Gemini Notebook) | SurfSense |
|---|---|---|
| Runs offline / air-gapped | No | **Yes** |
| Your documents leave your machine | Yes | **No**, unless you pick a remote model |
| Can edit your files | No | **Yes** |
| Open source | No | **Apache-2.0** |
| Models | Gemini only | Any OpenAI-compatible API, or a local one |

## Community

- [Discord](https://discord.gg/ejRNvftDp9) for help, [Issues](https://github.com/MODSetter/SurfSense/issues) for bugs, [Discussions](https://github.com/MODSetter/SurfSense/discussions) for ideas.
- **Contributing:** PRs go against `dev`; see [CONTRIBUTING.md](CONTRIBUTING.md) and [`surfsense_local/`](./surfsense_local) for the dev loop. How it works is in [`docs/`](docs/README.md).

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense contributors" /></a>

## License

Apache-2.0. See [LICENSE](LICENSE).
