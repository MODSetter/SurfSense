# Tutorials: step-by-step guides and videos, on the site and in the app

The maintainer asked on 9 Nov 2026 for "as many tutorial videos and screenshot
step by step guides on everything surfsense can do", on the site and inside the
local app. This plan was agreed on 10 Nov 2026 ("yes use defaults and make
videos"). Nothing here uses an em or en dash, like every string the site ships.

## What was decided

| Question | Decision |
|---|---|
| Where the guides live | `/docs/v2/guides/<slug>` in the user docs, one page per task, with a hub at `/docs/v2/guides`; `/tutorials` redirects there |
| Where the videos live | Vercel Blob, on the site's own Vercel project: a plain `<video>`, nothing loaded until the reader presses play, no third party on the page. GitHub user-attachments were ruled out: the README's video links return 404 when fetched without a GitHub session. Committing videos to `www/public` was ruled out by the brief |
| Where the screenshots live | `www/public/guides/<slug>/`, WebP at 2×, at most 250 KB each (a unit test checks) |
| Which model answers in the captures | Qwen3.8 27B through OpenRouter, from the maintainer's `OPENROUTER_API_KEY`. The walkthrough types a placeholder into the key field and the request that saves the server carries the real key, so no key is typed or shown. Stop at $5 |
| When captures run | Only while the maintainer's `pnpm dev` is closed: a capture boots a second app stack |
| Jobs guides | A Business trial licence for a test address, with the licence status intercepted so the screen shows you@example.com |
| In the app | Links out to the site: nothing bundled, since installers have size budgets, the screenshots are English only, and the app must not fetch media on its own |
| Videos | Every guide gets one: the run that takes a guide's screenshots records its video |

## How a guide is made

`www/scripts/guides/capture.mjs` boots a throwaway SurfSense (the sidecars
Electron boots, on a data folder of its own, not the Docker entry, which blocks
model downloads), serves the built renderer, and drives it in Chromium with the
Electron bridge stubbed. Each walkthrough in `scripts/guides/walkthroughs/`
writes its screenshots and records its video in the same run. The video gets a
drawn pointer and a one-line caption, loses the frames where the overlay was
hidden for a screenshot, and plays long waits on a model faster.

The demo documents are public: `scripts/guides/demo-documents/manifest.json`
records each one's source, licence, date and sha256, and nothing is committed.

## The guides, in order of value

| # | Guide | Slug | PR |
|---|---|---|---|
| 1 | Set up SurfSense | `set-up` | 1 |
| 2 | Run a model on your computer | `local-model` | 1 |
| 3 | Use a model from a server or provider | `connect-a-server` | 1 |
| 4 | Add files and folders | `add-sources` | 1 |
| 5 | Ask a question and check its citations | `ask-and-cite` | 1 |
| 6 | Choose which sources to use | `pick-sources` | 1 |
| 7 | Add web pages and YouTube videos | `add-from-the-web` | 1 |
| 8 | Keep projects apart with workspaces | `workspaces` | 1 |
| 9 | Make a Word document, deck or PDF in Studio | `studio-documents` | 2 |
| 10 | Make flashcards, a quiz and a mind map | `study-materials` | 2 |
| 11 | Turn your sources into a podcast | `podcast` | 2 |
| 12 | Refine a document and open an earlier version | `refine-and-versions` | 2 |
| 13 | Make and edit images and infographics | `images` | 2 |
| 14 | Organise sources: folders, notes, preview and open | `organise-sources` | 2 |
| 15 | Have the agent write a report or a deck | `agent-documents` | 3 |
| 16 | Edit your own Word file with tracked changes | `tracked-changes` | 3 |
| 17 | Analyse a spreadsheet and chart it | `analyse-a-spreadsheet` | 3 |
| 18 | Merge, split, stamp and fill PDFs | `pdf-tools` | 3 |
| 19 | Let the agent search and read the web | `web-research` | 3 |
| 20 | Connect a plugin and use it in a chat | `plugins` | 3 |
| 21 | Turn a recording into a source | `transcribe-a-recording` | 3 |
| 22 | Dictate a question | `voice-input` | 3 |
| 23 | Start a trial and add your licence | `business-trial` | 4 |
| 24 | Fill in a security questionnaire from your policies | `security-questionnaire` | 4 |
| 25 | Redline a contract against your playbook | `contract-redline` | 4 |
| 26 | See and control what leaves your computer | `privacy-network` | 4 |
| 27 | Update SurfSense | `updates` | 4 |
| 28 | Run SurfSense in Docker and open it from another device | `docker` | 4 |

Not captured: signing in with a ChatGPT or Claude plan, since a capture can't
sign in to those accounts. The redline guide waits for the lawyer's read if ADR
0086 covers it.

## In the app (PR 5)

- Help menu: "Guides and Videos" beside Documentation, in English like the
  menu's other items.
- Settings › About › Links: "Guides and videos" beside Documentation.
- A Guides dialog from a Help row in the sidebar footer: the guide titles by
  area, in the app's language, each opening its guide in the browser.
- "How to" links where a task starts: the empty Sources list, Studio's empty
  artifact list, the empty Plugins page, Jobs with no runs, Add from the web,
  the speech setup box, an empty model section.
- Every link through `siteVisitUrl` with its own surface name; every string in
  all 10 catalogs.
