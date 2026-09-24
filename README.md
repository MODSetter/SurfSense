<!--
  The sunset callout is time-boxed. Delete it on 18 October 2026 when the
  export window closes, along with the "Importing from the hosted app" link
  further down. Do the same in every README.<locale>.md. Those files track
  this one section for section.
  Rationale for this page: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Forks](https://img.shields.io/github/forks/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/network/members)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img width="128" height="128" alt="SurfSense, the air-gapped open-source NotebookLM alternative" src="surfsense_web/public/homepage/icon.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>The air-gapped, open-source NotebookLM alternative.</b>
    <br />
    Turn documents you can't upload into briefings, decks, reports, study guides and podcasts, entirely on your own machine.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Download</b></a> ·
    <a href="https://www.surfsense.com/docs">Docs</a> ·
    <a href="#what-surfsense-makes">What it makes</a> ·
    <a href="#how-surfsense-compares">Compare</a> ·
    <a href="https://www.surfsense.com/pricing">Pricing</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    English | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

<p align="center">
  <img src="surfsense_web/public/homepage/offline-studio.png" alt="SurfSense desktop app with Studio open and Qwen selected, turning local sources into artifacts" />
</p>

SurfSense is a free, open-source desktop app for the documents you already have. Drop them in, ask questions and get answers that cite their sources, then turn the same documents into a briefing, a slide deck, a report, a study guide or a podcast. All of it runs on your own machine: the index sits on your disk, you pick the model, and the app uploads nothing. There is no account to create.

**Get started.** Download the installer for your machine, then bring your own model key or let the app pull a local model for you.

| Platform | Download |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 (AppImage) | [SurfSense.AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) |
| **Linux** x64 (deb) | [SurfSense.deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

Every link is a permalink to the newest release. You can also pick from [surfsense.com/downloads](https://www.surfsense.com/downloads) or browse [all releases](https://github.com/MODSetter/SurfSense/releases). The AppImage auto-updates; the deb does not.

> [!NOTE]
> **Used the hosted web app?** It is being retired. Open it once to export your workspaces, then import the bundle into the desktop app; documents, folders, titles and chat threads all come across. The export window closes on 18 October 2026. Details on [the sunset page](https://www.surfsense.com/sunset).

## What SurfSense makes

Pick some documents and a format. The app writes it from the sources you chose, on your machine.

| Format | What you get | Needs |
|---|---|---|
| **Summary** | A structured brief of the selected sources | generation model |
| **Flashcards** | An interactive deck, one card at a time | generation model |
| **Quiz** | Multiple-choice questions with answers | generation model |
| **Mind map** | A zoomable, collapsible Markmap | generation model |
| **Slides** | An editable `.pptx`, not a picture of a deck | generation model |
| **Document** | An editable `.docx` report | generation model |
| **Spreadsheet** | An `.xlsx` of tables pulled from the sources | generation model |
| **Web page** | A self-contained HTML page | generation model |
| **PDF** | A typeset PDF | generation model |
| **Podcast** | A two-host audio conversation, voiced offline by Kokoro-82M | generation model + audio model |
| **Image** | An illustration for the material | image model + generation model |
| **Infographic** | A single-panel visual summary | image model + generation model |

Some jobs need more than one. A study guide is a summary, a flashcard deck and a quiz over the same source set, and a client briefing is usually the deck you present from plus the summary you send after. Video overviews are not built yet.

## Everything stays on your machine

People point this at case papers, client working papers, interview transcripts, internal specs, unpublished research and a term's worth of lecture notes. You can ask questions across all of it and every answer cites the source it came from. The app does not upload any of it.

- **The index is local.** Parsing, chunking and embedding happen on your computer, into SQLite under `~/.surfsense`. SurfSense keeps no copy of it and no log of what you asked.
- **Every role can run locally.** The document parser, the retrieval model and the podcast voice ship inside the installer. Chat and image generation ship as local servers whose weights you download once, so you can produce text, audio and pictures without an account or an API key. We test it by ingesting a PDF with networking disabled.
- **Outbound connections are off by default.** An egress panel lists every destination the app can reach and you switch on the ones you want.
- **No telemetry, no crash reporting.** Nothing phones home, so there is no opt-out to find.

SurfSense cannot tell you whether that satisfies a particular regulation. That depends on your own controls and your regulator. All the app can tell you is which machine your documents are on.

## How SurfSense compares

Three kinds of product get called "the local NotebookLM", and they answer different questions. None of them is a bad tool; they just leave you with different things.

**vs Jan, AnythingLLM, Open WebUI, LM Studio.** These run a model locally and give you somewhere to chat with it. SurfSense answers the next question: how do you get a finished document out of one? Use them together if you like, by pointing SurfSense at any OpenAI-compatible endpoint, including one of theirs.

**vs RemNote, Quizlet, NoteGPT, StudyFetch, Gamma.** These do produce artifacts, and some look better than ours. The trade is where your material goes: you upload it, you pay monthly, and your files live in someone else's account.

**vs Google NotebookLM.** It already ships flashcards, quizzes, mind maps and audio overviews, so both produce much the same things. The difference is whose machine does the work and which model you can point at it.

| | Google NotebookLM | SurfSense |
|---|---|---|
| Runs offline / air-gapped | No | **Yes** |
| Your documents leave your machine | Yes | **No** |
| Account required | Google account | **None** |
| Open source | No | **Apache-2.0** |
| Price | Free tier; Pro $19.99/mo; Ultra $249.99/mo | **App is free** |
| Models | Gemini only | Any OpenAI-compatible API, or a local one |
| Source limits | 50 to 600 sources, 500,000 words each | Whatever your disk holds |
| Audio and video overviews | Yes, and better | Audio yes, offline; video not yet |

NotebookLM wins on audio quality and it has video. If you are content with your sources sitting on Google's servers, use it. If you are not, this is the same kind of tool without the upload.

## Quick start

You do not need Docker, a terminal, a GPU or a compose file.

1. **Download the installer** from the table above. It is signed, so your OS will not fight you.
2. **Pick a model.** Let the app pull a local one (Qwen3 in six sizes, from 0.5 GB) or paste a base URL and key for any OpenAI-compatible API. The picker checks your machine can run a model before offering it, and any key you give it is stored encrypted, with the secret held in your OS keychain.
3. **Drop in documents.** The app parses PDFs, Office files and images on your machine.
4. **Ask questions.** Every answer cites the source it came from.
5. **Open Studio,** choose a format, collect the file.

The download is the slow part, because the installer carries the parser, the retrieval model, the podcast voice and the local model servers, so the app works with the network off.

## Docs and community

The app and its updates are free. A licence adds plugins and priority support and gates nothing else, so an expired licence still leaves you the app and every future update. See [pricing](https://www.surfsense.com/pricing).

The Docker stack in this repo (`surfsense_backend`, `surfsense_web`, compose files) stays open source and installable, and is **community-supported: no SLA and no hosted service behind it.** The desktop app is the supported path for new users.

- [Documentation](https://www.surfsense.com/docs) for install, models, Studio formats and self-hosting
- [Importing from the hosted app](https://www.surfsense.com/sunset)
- [MCP server](./surfsense_mcp) for the hosted scraper API
- [Discord](https://discord.gg/ejRNvftDp9) for help and ideas, [Discussions](https://github.com/MODSetter/SurfSense/discussions) for direction, [Issues](https://github.com/MODSetter/SurfSense/issues) for reproducible bugs
- **Star the repo** if you want to follow where this goes

## Contributing

Pull requests are welcome, and [CONTRIBUTING.md](CONTRIBUTING.md) walks through the whole flow. In short:

- **Find something to work on:** an issue labelled [`good first issue`](https://github.com/MODSetter/SurfSense/labels/good%20first%20issue) or [`help wanted`](https://github.com/MODSetter/SurfSense/labels/help%20wanted), or a line from the Known gaps list at the end of each doc in [`docs/architecture/`](docs/architecture/overview.md).
- **Read how it works first:** [`docs/`](docs/README.md) explains each feature and why it is built that way, and [`docs/ROADMAP.md`](docs/ROADMAP.md) shows what the maintainers are working on.
- **Open a PR against `dev`.** Bug fixes and docs need no discussion first; a new feature starts with a short design proposal. The desktop app lives in [`surfsense_local/`](./surfsense_local), and its README covers the development loop.

Thanks to all our Surfers:

<p align="center">
  <a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense contributors" />
  </a>
</p>

## Star history

<p align="center">
  <a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
    </picture>
  </a>
</p>

## License

Apache-2.0. See [LICENSE](LICENSE).
