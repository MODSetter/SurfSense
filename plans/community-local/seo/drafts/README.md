<!--
  DRAFT for SurfSense 2.0.0. Not the live README.
  Rationale, keyword targets, the competitor-structure analysis and the
  sign-off checklist: ../06-repo-readme.md

  Two assets are required before this ships and both are marked REPLACE-ME:
  a hero wordmark, and a Studio demo GIF. All three of the biggest repos in
  this category put a visual above the feature list; we currently have none
  for the desktop app.
-->

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Forks](https://img.shields.io/github/forks/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/network/members)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

<div align="center">
  <a href="https://www.surfsense.com/"><img width="1584" height="396" alt="SurfSense, the air-gapped open-source NotebookLM alternative" src="REPLACE-ME-hero" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>The air-gapped, open-source NotebookLM alternative.</b>
    <br />
    Turn your own documents into study guides, flashcards, quizzes, slides, mind maps and podcasts, entirely on your own machine.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Download</b></a> ·
    <a href="https://www.surfsense.com/docs">Docs</a> ·
    <a href="#what-surfsense-makes">What it makes</a> ·
    <a href="https://www.surfsense.com/pricing">Pricing</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <p>
    English | <a href="README.es.md">Español</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

> [!NOTE]
> **The hosted version of SurfSense is being retired.** SurfSense is now a desktop app you install and own. If you used the hosted web app, open it once to export your workspaces, then import the bundle into the desktop app. Your documents, folders, titles and chat threads all come across. You have 30 days from launch to export. Details on [the sunset page](https://www.surfsense.com/sunset).

![SurfSense Studio turning a folder of PDFs into a flashcard deck](REPLACE-ME-studio-demo.gif)

SurfSense is a free, open-source desktop app that reads your own documents and writes things from them: summaries, study guides, flashcards, quizzes, slide decks, mind maps, spreadsheets and podcasts. It runs on your own machine. The index sits on your disk, you pick the model, and the app uploads nothing. There is no account to create.

**[Download for Windows, macOS or Linux](https://www.surfsense.com/downloads)**, then either bring your own model key or let the app pull a local model for you.

## What SurfSense makes

Select some documents, pick a format, and the app writes it. Every artifact is grounded in the sources you chose, and the app builds all of them locally.

| Format | What you get | Needs |
|---|---|---|
| **Summary** | A structured brief of the selected sources | generation model |
| **Flashcards** | An interactive deck: one card at a time, reveal the answer | generation model |
| **Quiz** | Multiple-choice questions with answers, to test recall | generation model |
| **Mind map** | A zoomable, collapsible map rendered with Markmap | generation model |
| **Slides** | An editable `.pptx`, not a picture of a deck | generation model |
| **Document** | An editable `.docx` report | generation model |
| **Spreadsheet** | An `.xlsx` of tables and figures pulled from the sources | generation model |
| **Web page** | A self-contained HTML page | generation model |
| **PDF** | A typeset PDF | generation model |
| **Podcast** | A two-host audio conversation, voiced offline by the bundled Kokoro-82M | generation model + bundled voice |
| **Image** | An illustration for the material | image model + generation model |
| **Infographic** | A single-panel visual summary | image model + generation model |

A study guide is three of those formats over one source set: a summary to read, a flashcard deck to drill, and a quiz to check yourself. Point the app at a semester of lecture PDFs and you get all three without your coursework leaving your laptop.

Video overviews are not built yet.

## NotebookLM's outputs. None of NotebookLM's cloud.

Most local AI tools are chat windows. Jan, AnythingLLM, Open WebUI and LM Studio are good ones: you point them at a local model, you ask questions, and the conversation scrolls away. None of them hands you anything to keep, so there is no deck for Monday's meeting and no card set to revise from.

The tools that *do* produce those things — the study and presentation SaaS — take the opposite trade. You upload your material to their servers, you pay monthly, and your PDFs live in someone else's account.

SurfSense is the third option. It produces those deliverables and builds them on your own machine.

|  | Local chat apps | Study / slides SaaS | SurfSense |
|---|---|---|---|
| Runs on your machine | Yes | No | **Yes** |
| Produces artifacts to keep | No | Yes | **Yes** |
| Works with no network | Yes | No | **Yes** |
| Needs an account | No | Yes | **No** |
| Open source | Mostly | No | **Apache-2.0** |

## Quick start

There is no Docker to install, no terminal, no GPU and no compose file to edit.

1. **Download the installer** for [Windows, macOS or Linux](https://www.surfsense.com/downloads) and open it. It is signed, so your OS will not fight you.
2. **Pick a model.** Either let the app pull a local one for you, or paste a base URL and key for any OpenAI-compatible API. Nothing else needs configuring.
3. **Drop in documents.** The app parses PDFs, Office files and images on your own machine.
4. **Ask questions,** and every answer cites the source it came from.
5. **Open Studio,** choose a format, and collect the file.

The download is the slow part, because the installer carries the document parser, the retrieval model and the podcast voice so that the app works with the network off. After that there is nothing to set up.

## Models: bundled, or bring your own

SurfSense does not sell you inference and does not resell anyone else's. Three of the four model roles work offline with no key at all.

| Role | Bundled and offline | Bring your own |
|---|---|---|
| Chat and artifact generation | A private Ollama with Qwen3 in six sizes, the smallest 0.5 GB on disk | Any OpenAI-compatible API |
| Retrieval embedding | Yes, fixed and local | — |
| Podcast voice | Kokoro-82M | — |
| Image and infographic | — | Any OpenAI-compatible image API |

The model picker checks whether your machine can actually run a model before it offers it. Generation, embedding and image roles are chosen separately, so a small local model can answer chat while a bigger one writes artifacts. Keys live in your OS keychain.

## Everything runs on your machine

- **The index is local.** The app parses, chunks and embeds your documents on your own computer, into a SQLite database under `~/.surfsense`. There is no vendor copy and no vendor log.
- **It works with the network off.** The installer bundles the parser (Docling), the retrieval embedding model and the podcast voice. We test that by running ingest on a machine with networking disabled.
- **Outbound connections are off by default.** An egress panel lists every destination the app can reach, and you switch on the ones you want. Pulling a model is one of them.
- **No telemetry and no crash reporting.** Nothing in the app reports back anywhere, so there is no opt-out to find and no anonymous-usage policy to read. Support runs on logs you choose to send.

This matters most if your documents are client files, patient records, unpublished research or your own notes. No second copy exists on anyone's server, so there is no privacy policy to read and nothing to subpoena.

## SurfSense vs Google NotebookLM

NotebookLM is a good product, and it is how most people find this repo.

| | Google NotebookLM | SurfSense | Why it matters |
|---|---|---|---|
| **Runs offline / air-gapped** | No | **Yes** | Works on a plane, and inside networks with no route out |
| **Your documents leave your machine** | Yes | **No** | No second copy to leak or subpoena |
| **Account required** | Google account | **None** | Nothing to sign up for, nothing to cancel |
| **Open source** | No | **Yes, Apache-2.0** | You can audit it, and keep running it if we disappear |
| **Price** | Free tier; Pro $19.99/mo; Ultra $249.99/mo | **App is free** | You pay for model usage, if anything |
| **Models** | Gemini only | Any OpenAI-compatible API, or a local model | Choose on cost, or on privacy |
| **Sources per notebook** | 50 (free) to 600 (Ultra) | As many as your disk holds | No tier to hit |
| **Source size limit** | 500,000 words / 200 MB | Your disk | Whole books, long transcripts |
| **Summaries, flashcards, quizzes, mind maps** | Yes | Yes | Same jobs, different machine |
| **Slides** | Better looking, not editable | Editable `.pptx` | Fix a typo without starting over |
| **Podcasts / audio overviews** | Yes, and better: more voices and languages | Yes, generated offline | NotebookLM wins on quality, we win on privacy and cost |
| **Video overviews** | Yes (Ultra) | Not yet | NotebookLM wins |
| **Self-hostable** | No | Yes | Run the server stack if you want one |

If you want the best-looking audio and video overviews, and you are content with your sources sitting on Google's servers, use NotebookLM. If you want the same kind of outputs without the upload, use this.

## Questions people actually ask

**Can I run NotebookLM locally?** No. NotebookLM is a hosted Google product with no offline mode and no self-host option. SurfSense is an open-source desktop app built to do the same job on your own machine.

**Is there an open-source alternative to NotebookLM?** This is one. The app is Apache-2.0 and the installers are free.

**Is there a free version of NotebookLM?** Google offers a free tier with source and notebook caps. The SurfSense app is free outright and has no caps, because you supply the model.

**Is there an AI I can use without internet?** Yes. With a local model installed, SurfSense runs with networking off: ingest, search, chat and every Studio format.

**Can I self-host an AI?** Two ways here. The desktop app is local by default and needs no server. If you would rather run the server stack, see below.

**Do I need a GPU?** No. Retrieval is CPU-only. A GPU helps if you run a large local model, and it makes no difference if you bring an API key.

**Does it work with Ollama?** Yes, including a private bundled copy, so you do not have to install or manage one yourself.

## Self-host the server stack

The Docker stack in this repo (`surfsense_backend`, `surfsense_web` and the compose files) remains open source and installable. It is **community-supported: no SLA, and no hosted service behind it.** The desktop app is the supported path for new users.

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

## Pricing

The app is free and so are updates. The paid tiers:

| | |
|---|---|
| **Self-build and the app** | Free, forever, Apache-2.0 |
| **Trial** | 14 days |
| **Individual** | $120/year |
| **Team** | $80/seat/year, 5-25 seats |
| **Enterprise** | $80/seat/year, $3,000 minimum, invoiced |

A license unlocks plugins and priority support, and gates nothing else. It never disables the app: when a license expires you keep the app and every future update, and you lose plugins and priority support. There is no account either way, since checkout takes an email address and sends back a license file.

The first plugin is a hosted scraper API for live data from the open web (Reddit, YouTube, Google Search, Maps, Amazon and more, as one typed API and an [MCP server](./surfsense_mcp)).

## Roadmap

In 2.0.0: all twelve Studio formats, interactive viewers for the flashcard, quiz and mind-map artifacts, and import from the hosted app.

Next, a week after launch: the first plugin. Then video overviews and an interactive viewer for the web-page artifact.

Further out: sandboxed artifact generation, SSO and SAML, an on-premise license and plugin mirror for zero-egress networks, and a local egress audit log.

Track it on the [roadmap discussion](https://github.com/MODSetter/SurfSense/discussions/565) and the [project board](https://github.com/users/MODSetter/projects/3).

## Documentation

- [Documentation](https://www.surfsense.com/docs) for install, choosing a model, the Studio formats and self-hosting
- [Importing from the hosted app](https://www.surfsense.com/sunset)
- [Developing the desktop app](./surfsense_local)

## Community and contributing

- [Discord](https://discord.gg/ejRNvftDp9) for help, ideas and workflow sharing
- [GitHub Discussions](https://github.com/MODSetter/SurfSense/discussions) to shape features and direction
- [Issues](https://github.com/MODSetter/SurfSense/issues) for reproducible bugs
- **Star the repo** if you want to follow where this goes

Issues and pull requests are both welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md). The desktop app lives in [`surfsense_local/`](./surfsense_local); its README covers the development loop. The hosted web app, browser extension and Obsidian plugin are retired and archived.

Thanks to all our Surfers:

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" />
</a>

## Star history

<a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
 </picture>
</a>

## License

Apache-2.0. See [LICENSE](LICENSE).
