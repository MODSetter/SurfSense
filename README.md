<!--
  Rationale: plans/community-local/seo/06-repo-readme.md. Anything added replaces
  something (AGENTS.md). Ship the agent copy only with the first release whose
  installer carries the agent; v2.1.0 does not.
  The format table is checked against origin/dev c5ff7938a; re-check each cell before a release.
  The Quick start is checked against dev_mod 4330d8978. Record its five images in
  surfsense_web/public/docs/quick-start/ before merge, GIFs under about 5 MB each; the note above each image says what to show.
  The demo video under the header is a GitHub upload, not a file in the repo. To replace it, drag an
  MP4 under 10 MB into any comment box in this repo, copy the user-attachments link and swap the URL.
  Time-boxed: delete the sunset callout on 18 October 2026, here and in every README.<locale>.md.
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense, the air-gapped open-source NotebookLM alternative" src="surfsense_web/public/homepage/banner.png" /></a>

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
    <a href="https://www.surfsense.com/pricing">Pricing</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    English | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

SurfSense is a free, open-source desktop app for documents you can't upload. Add your files, ask questions and get answers that cite their sources, then have the agent write a report, deck, workbook or PDF, or revise your own file as a copy. The index stays on your disk, you pick the model, local or remote, and there is no account.

| Platform | Download |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 | [AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) · [deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

> [!NOTE]
> **Used the hosted web app?** Export your workspaces before 18 October 2026 and import them here. See [the sunset page](https://www.surfsense.com/sunset).

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
| **Podcast** (audio) | — | ✓ with a transcript, voiced on your machine by default | — | — |
| **Mind maps, flashcards, quizzes** | — | ✓ in the app | — | — |

<sub>¹ With Office support (LibreOffice), turned on in Settings; it is never in the installer. ² Needs an image model, local or remote; none is chosen by default. ³ OCR reads Latin, Chinese and Japanese script.</sub>

Edits, conversions and PDF tools always make a new file; your original is never changed. PDF, Word and Excel do the most today, and support for the other formats keeps improving.

## Quick start

1. **Install and open SurfSense.** Get the file for your system from the download table above, then click **Start setting up**. On Linux, run `chmod +x SurfSense.AppImage` first; on Ubuntu 22.04 or later, use the deb (`sudo apt install ./SurfSense.deb`).

   <!-- Record before merge: the first screen after install, "Air-gapped, open source NotebookLM alternative" with the "Start setting up" button. -->
   <img src="surfsense_web/public/docs/quick-start/quick-start-01-welcome.png" alt="The SurfSense welcome screen with the Start setting up button" width="720" />

2. **Choose a chat model.** Click **Download** on the **Recommended** model, or **Connect** to an OpenAI-compatible API and click **Use** on one of its models. Click **Allow** if asked. Once the model is in use, click **Continue** and **Skip** the optional models.

   <!-- Record before merge: the "Choose a text generation model" step after the download, with the Recommended row showing "In use" and the footer reading "Using <model> on this computer" beside an enabled Continue. -->
   <img src="surfsense_web/public/docs/quick-start/quick-start-02-chat-model.png" alt="The Choose a text generation model step, with the recommended local model downloaded and in use" width="720" />

3. **Add your documents.** Drop files on the **Sources** list, or click **+** next to it and choose **Upload files…**. A file is ready when its spinner turns into a checkbox.

   <!-- Record before merge: dropping a PDF, a .docx and an .xlsx on the Sources list, the "3 sources added" toast, then each row's spinner turning into a ticked checkbox. Cut or speed up the parsing wait. -->
   <img src="surfsense_web/public/docs/quick-start/quick-start-03-add-sources.gif" alt="Three files dropped on the Sources list, each showing a spinner until it is ready" width="720" />

4. **Ask a question.** Type it in the box that reads **Turn your sources into answers** and press Enter. Click a number in the answer to see the passage it came from.

   <!-- Record before merge: a question about the step 3 files, the answer streaming in with number chips, then a click on one chip opening the Citation panel with the "Cited chunk" outlined. -->
   <img src="surfsense_web/public/docs/quick-start/quick-start-04-ask.gif" alt="A question answered from the sources, then a citation opened to show the passage it came from" width="720" />

5. **Make a file.** Close the citation, click **Word** in **Studio**, then click **Generate**. When the file is ready, click it under **Artifacts** to preview and download it.

   <!-- Record before merge: the Word tile in Studio, its dialog with "3 sources" and Generate, the spinner in Artifacts, the "<name> is ready" toast, then the Word preview with its Download button. Cut or speed up the generation wait. -->
   <img src="surfsense_web/public/docs/quick-start/quick-start-05-studio.gif" alt="Studio making a Word document from the sources, then showing its preview" width="720" />

## How it compares

| | NotebookLM (now Gemini Notebook) | SurfSense |
|---|---|---|
| Runs offline / air-gapped | No | **Yes** |
| Your documents leave your machine | Yes | **No**, unless you pick a remote model |
| Open source | No | **Apache-2.0** |
| Models | Gemini only | Any OpenAI-compatible API, or a local one |

Jan, LM Studio and Ollama pair well with it: point SurfSense at their OpenAI-compatible server.

## Community

- [Discord](https://discord.gg/ejRNvftDp9) for help, [Issues](https://github.com/MODSetter/SurfSense/issues) for bugs, [Discussions](https://github.com/MODSetter/SurfSense/discussions) for ideas.
- **Contributing:** PRs go against `dev`; see [CONTRIBUTING.md](CONTRIBUTING.md) and [`surfsense_local/`](./surfsense_local) for the dev loop. How it works is in [`docs/`](docs/README.md).
- **Self-hosting:** the Docker stack (`surfsense_backend`, `surfsense_web`) stays open source and community-supported.

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense contributors" /></a>

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

Apache-2.0, except `surfsense_backend/app/proprietary/` (BSL 1.1). See [LICENSE](LICENSE).
