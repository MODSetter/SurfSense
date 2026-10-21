---
status: in-progress
code:
  - surfsense_local/backend/modules/agent/tool_endpoint/
  - surfsense_local/backend/modules/agent/skills/surfsense-html/
  - surfsense_local/backend/modules/agent/previews/
  - surfsense_local/backend/modules/artifacts/
  - surfsense_local/backend/worker/studio/made_file/
  - surfsense_local/backend/worker/studio/web/html/
  - surfsense_local/electron/src/main/docx-snapshot/
  - surfsense_local/frontend/src/features/studio/viewers/html-viewer.tsx
  - surfsense_local/frontend/src/features/agent/
---

# Web pages the model writes

> A web page becomes HTML the model writes itself, with its own CSS, script and inline SVG, on the two paths Word and PDF already have. In an agent thread the agent writes it, taught by a new skill, `surfsense-html`, and saves it as a versioned Studio artifact with a new tool, `surfsense_save_page`. Studio's Web page button splits as its Word button does: a model at the agent's bar writes the page in one call, and any other keeps today's template. The only limits are size and that a page cannot reach the network. Basic (Q&A) chats make no artifacts and do not change.

Today both paths end in Studio's [html pipeline](../architecture/studio.md): the model returns a title and plain-text sections, and every value is escaped into a template with no style and no script, so the most capable models in the app produce an unstyled page. Word and PDF already let a strong model write the file: Studio's buttons through [`writes_script()`](../architecture/studio.md#word-and-pdf), the agent through [script documents](../architecture/agent.md#documents-the-agent-makes). Web pages follow the same split. The decision it rests on is [ADR 0066](../adr/0066-web-pages-are-html-the-model-writes-without-network.md).

## Where a page comes from

| | Word and PDF today | Web page with this |
|---|---|---|
| Basic (Q&A) chat | none | none |
| Studio, model below the bar | Markdown, rendered by a builder | JSON sections, escaped into the template (unchanged) |
| Studio, model at the bar | the model writes a script | the model writes the page |
| Agent thread | `surfsense_render_document`: a script, versions, previews | `surfsense_save_page`: the page, versions, screenshots |

Word needs a script because python-docx builds the file. A page is already the file, so nothing the model wrote runs on the machine; it runs only in the viewer's frame.

## What changes

| | Today | With this |
|---|---|---|
| Agent asks for a web page | `create_artifact(html)`, Studio's escaped template | writes `outputs/<name>.html`, then `surfsense_save_page` |
| Who writes the markup | SurfSense's template | the agent: any HTML, CSS, script, inline SVG |
| Versions | none; each call is a new page | v1, v2… on one page, as script documents |
| What the agent sees after | "Studio started" | `Rendered artifact <id>, version <n>`, the page's text, and up to four screenshots |
| Viewer frame | `sandbox="allow-scripts allow-popups"` | `allow-scripts` only, a no-network CSP, frame navigation blocked |
| Studio's Web page button | escaped template for every model | the page written by a model at the bar; the template below it |
| `create_artifact(html)` from the agent | starts a Studio job | refused, pointing at the skill and the tool, as Word is |

## The path

1. **Prompt.** [`prompts/agent.md`](../../surfsense_local/backend/modules/agent/prompts/agent.md) gains one line beside the documents line: for a web page, load `surfsense-html`, write the file under `outputs/`, save it with `surfsense_save_page`; to change it, edit the file and save with its `artifact_id`.
2. **Skill.** `skills/surfsense-html/SKILL.md`, SurfSense's own text: the contract (one complete HTML document, everything inline, images as `data:` URIs, no network, at most 5 MB), grounding as the documents skill words it, editing, checking the screenshots, and the stop rule. It points at the [design guide](#the-design-guide) beside it for how a page looks and moves. opencode allows it by name in [`opencode_config.py`](../../surfsense_local/backend/modules/agent/opencode_config.py); Claude Code's `surfsense` plugin picks up any folder under `skills/` and rewrites tool names for it.
3. **Write.** The agent writes the page with its own tools: opencode's, or Claude Code's `Write` and `Edit`, which its gate already holds to `outputs/`. A later change is an `Edit` of that file, not the whole page sent again as an argument.
4. **Save.** `surfsense_save_page(path, title, artifact_id?)`, below.
5. **Index.** The Studio job reads the stored page and indexes its text, as a made file's job does.
6. **Screenshots.** Electron draws the page in a hidden window and the result carries up to four images.
7. **View.** Studio's HTML viewer shows it in the hardened frame.

## The tool

`surfsense_save_page`, `waits=True`, wrapped by `stop_after_three_failures` with the renders' shared limit ([`failed_renders.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/failed_renders.py)).

- **`path`** is relative to the thread's folder and must resolve, links followed, inside `outputs/`, as Claude Code's gate holds writes ([`gate.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/gate.py)). It ends in `.html` or `.htm`.
- **Refused before anything is stored:** a path outside `outputs/` or missing; over 5 MB; not UTF-8; no markup; no embedding model chosen (indexing needs one, as every Studio path does). Each refusal is a tool error naming the fix. A refusal is not a failed run.
- **Notes, not refusals:** each external URL in `src`, `href`, `@import` or `url()` is listed as "blocked by the viewer", as the hosted verifier did. Links (`<a href>`) are left out of the notes.
- **Same title.** A call without `artifact_id` whose title matches a page this thread saved is refused naming that page's id, through [`same_title_documents.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/same_title_documents.py), whose format check widens to `html`.
- **Version.** v1 of a new page, or the next version of `artifact_id`'s root. Only a page this tool saved continues: a Studio-made page, or another format, is refused with "make a new page".
- **Store.** The bytes are written at once, as [`made_file.py`](../../surfsense_local/backend/modules/artifacts/made_file.py)'s `keep_made_file` does, with the kit inlined where asked and the CSP `<meta>` (below) inserted right after the doctype, before anything the page wrote, so no script of the page runs without it. The artifact's metadata holds `made_by: {"tool": "save_page", "path": …}` and the `version`; the HTML is the file, not a copy in metadata.
- **Index.** Studio's job takes the made-file branch. [`made_file/pipeline.py`](../../surfsense_local/backend/worker/studio/made_file/pipeline.py) gains `html` beside `pdf`, `docx`, `pptx` and `xlsx`: its text comes from a new extractor on the standard library's `html.parser` that keeps headings, paragraphs, list items, table cells and `alt` text, drops `<script>`, `<style>` and `<template>`, and writes Markdown headings so the body chunks as other artifacts do.
- **Wait and answer** as `render_document` does: up to 150 seconds inside the call's deadline, then the `Rendered artifact <id>, version <n>: <title>` line, the first 1,500 characters of the text, the notes, and the screenshots; or `Queued artifact…` if the index is still behind.

## Screenshots

[Previews](../architecture/agent.md#previews) for Word and decks already use an Electron queue: the API posts a request, Electron polls it, prints a page in a hidden, confined window and posts the PDF back. HTML is a new format on that queue with its own branch in Electron, because the snapshot page's own CSP (`script-src 'self'`) would stop the agent's script, and the artifact file route serves HTML as an attachment.

- The snapshot router serves the request's page inline, `text/html`, with the same CSP as a response header, on the request-id route that Word's source files already use.
- Electron loads it directly in the confined `docx-snapshot` partition, whose request filter already allows only the file being drawn. The window is 1,280 px wide, emulates `prefers-reduced-motion: reduce` through the debugger's `Emulation.setEmulatedMedia`, waits for `load` plus one second, then `capturePage` at the page's height, up to four viewport heights.
- The PNG comes back on a new route beside `/pdf`, checked for the PNG signature. Python cuts it into at most four tiles of 1,280 by 1,000 and they go into the result as JPEGs through [`inline_images.py`](../../surfsense_local/backend/modules/agent/previews/inline_images.py), only when the model reads images, as now.
- No Electron (Docker, tests without one), a timeout, or a failure: no images, and the reason, as a Word version without Electron gets.

`capturePage` over `printToPDF` because a page is judged on screen: print media drops backgrounds and breaks a long page at arbitrary points.

## Viewing

The page runs, and it is built from the user's sources, which can carry instructions aimed at the model. A page that could reach the network could send what it read anywhere. The frame already has an opaque origin (no `allow-same-origin`), so it cannot touch the app. Three holes remain:

- **Requests.** The sandbox does not stop `fetch`, `<img src>`, fonts or CSS `url()`. The stored page carries `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; form-action 'none'; base-uri 'none'">`. The viewer inserts the same `<meta>` before setting `srcDoc` too, so an older or edited file is held as well. The downloaded copy carries it, so a browser holds it there.
- **Popups.** `allow-popups` lets `window.open("https://…?d=…")` reach Electron, and no CSP directive covers it. Electron already sends every new window from the app's own window through its link allowlist and refuses the rest (`denyAppWindows`), so the viewer drops `allow-popups` as a second line. Links in a page do not open from the viewer in this version.
- **Navigating the frame itself.** A sandboxed frame may still set its own `location`, and the app's guard ([`index.ts`](../../surfsense_local/electron/src/main/index.ts), `denyAppWindows`) listens only to `will-navigate`, the main frame's. A `will-frame-navigate` handler refuses any subframe navigation to an origin other than the app's.

Google Fonts, which the hosted viewer allowed, are not allowed: a stylesheet URL is itself a request that can carry data. A page uses system font stacks, or a font as a `data:` URI.

## The design guide

One file, `skills/surfsense-html/design.md`, is how every model-written page looks, and both paths read it: the agent opens it from its skill, and Studio's prompt for a model at the bar includes it whole. One file, so the two paths cannot drift apart. It covers a type scale, a readable measure, light only, with a palette the model chooses and text and marks in contrast with what they sit on (every other Studio document is light, and a frame's `prefers-color-scheme` follows macOS, not SurfSense's theme), responsive layout down to phone width, one `h1` and ordered headings, native controls with labels, visible focus, charts as inline SVG from figures the sources state, system font stacks, and motion (below). The API ships the skills folder already ([packaging](../architecture/packaging.md)); the worker's bundle gains this one file.

## Motion

The guide's motion rules: motion is time-based (`requestAnimationFrame` timestamps, `dt` clamped), values ease toward a target rather than snap, a loop stops when settled or off screen (`IntersectionObserver`), and under `prefers-reduced-motion: reduce` the page shows its final state and still answers input. Animate what carries meaning, a chart drawing in or a figure counting up, never every card. The agent's screenshots are taken with reduced motion on, so a page that only works animated shows the agent so.

## Figures

A page may carry an explanatory figure: an isometric drawing of a real object whose working is the idea, a pin-tumbler lock for a cache key rather than boxes and arrows. It is optional; the skill says when one helps (a mechanism or a process) and when it does not (a report, a summary, a dashboard).

- **SurfSense's own kit,** `skills/surfsense-html/kit/fig.js`, with no dependency: a true isometric camera fitted to the mechanism; rounded boxes, cylinders and prisms shaded by the way each side faces, with silhouettes, glints and soft shadows; coil springs; small parts that paint with what they sit on (screws, hole grids, ticks, knurls, panels, slots, an engraved label); light colours the page sets from its own palette; SVG in painter's order; and the motion helpers: easing, a spring, and a loop that stops when settled or off screen and honours reduced motion. A first, smaller kit drew a turnstile as a few boxes on a mostly empty plate; detail and composition are what make a figure read as a made object.
- **SurfSense inlines it, not the agent.** The page writes `<script data-kit="fig"></script>` before its own script, and `surfsense_save_page` replaces that element with the kit's code. The model never copies the kit, and the stored page stays self-contained, so the no-network CSP holds it.
- **The skill splits** so a plain page loads little: `SKILL.md` and `design.md` always, `figures.md` (how to find the object, list 40 to 80 parts, put detail on every face, let the mechanism fill the frame, order the parts back to front, frame the figure with a live readout, and check the screenshot) and `kit.md` (the kit's functions) only when the agent draws a figure.
- **No WebGL.** Pages draw with SVG and CSS only: WebGL, a 3D canvas or a shader makes a page heavy and laggy for what an SVG figure already shows. The design guide says so.

## Editing a page

The page's working file is the agent's own, under `outputs/`, and the save records its path in the artifact's metadata. A change edits that file and saves it with the `artifact_id`. The stored page is not handed back to edit: it holds the inlined kit and the CSP, which the agent did not write.

## The thread

[`steps.py`](../../surfsense_local/backend/modules/agent/agent_threads/steps.py) adds the tool to `VERSION_STEPS`, so its step links the page as a render's does. The frontend's [`step-label.tsx`](../../surfsense_local/frontend/src/features/agent/step-label.tsx) gains its case ("Saved web page", "Saving web page…"), translated with the `translate` skill.

## Studio's Web page button

[`html/pipeline.py`](../../surfsense_local/backend/worker/studio/web/html/pipeline.py) chooses its path with `writes_script()` from [`strength.py`](../../surfsense_local/backend/worker/studio/office/document/strength.py), the same check Word and PDF use, read from the [measured levels](../architecture/model-capabilities.md): `agent` and `agent_limited` write the page; `studio_only` keeps the template; a model not measured writes the page when it is remote and keeps the template when it is served from this computer.

- **A model at the bar** gets a new tier prompt: the contract of the skill without its tools, the design guide, Studio's grounding rules, and the user's focus. It returns one complete HTML document and nothing else.
- **Checked as a save is,** without screenshots: UTF-8, markup, a closing `</html>` (a reply cut off at the output limit has none), and at most 300 KB, about the most one reply carries. A failed check goes back to the model with its reason, up to three attempts, as an Office script's does. After the third the job fails with that reason. It never falls back to the template, which would hide the failure.
- **Stored** with the CSP `<meta>`, its text extracted as a saved page's is, and the page kept as the spec, `{"kind": "html", "text"}`, so the draft is v1 under the same `version` keys as Word's.
- **Refine** sends the page and the instruction to the model and checks the reply the same way. Refine's window check applies: a page too long for the selected model's window is refused with its reason, as a Word spec is. **Regenerate** drafts again from the recorded source scope.
- **Below the bar,** the JSON pipeline and its three prompts are unchanged.

Whether the template is kept is measured, not assumed. The levels were set on document tasks, not pages. Once the HTML prompt exists, the [model ladder](../proposals/file-agent/08-model-ladder-results.md)'s models write the same set of pages, and each page is counted as passing when it passes the checks above and its screenshot shows the content laid out. If the `studio_only` models pass, the template and its prompts are deleted and every model writes the page. If `agent` models fail, the bar gains an HTML case before Studio's path ships.

## Build order

1. **Shared:** the viewer's hardening, the CSP insertion, the text extractor and the design guide. The hardening holds every html artifact, Studio's template pages included.
2. **Agent path:** `surfsense_save_page`, the skill with the kit, screenshots and versions.
3. **Studio's path at the bar:** the tier prompt, the checks and attempts, Refine and Regenerate; then the ladder measurement.

## Not in this

- Basic (Q&A) chats, which make no artifacts.
- Libraries from a CDN. Bundling a few with the app, served from its own origin, is later work if pages need them.
- Opening a page's links from the viewer. A later change can pass a clicked link to the app through `postMessage` for the app's own link rules.
- A limit for small models. A model allowed into Agentic may write a poor page, as it may a poor script; the screenshots and the failure limit bound it.

## Tests

- `tests/integration/agent/test_page_tools.py`, beside `test_document_tools.py`: a page saved and listed with its version, the next version through `artifact_id`, each refusal, same title, a Studio page refused as a base, the CSP inserted, the notes, the kit inlined where the page asks for it, and the text indexed without script.
- `test_previews.py` with a stand-in Electron: the page served inline with its CSP header, a PNG delivered and tiled, no Electron giving the reason.
- Studio, with a stub model: a model at the bar gets the HTML prompt and one below it the JSON prompt; a cut-off page, an oversized one and one without markup sent back with their reasons; the third failure failing the job; the stored page carrying the CSP and its spec; Refine refused past the window.
- `test_tool_endpoint.py`, `test_tool_registration.py`, `test_tool_names.py`, `test_skills_plugin.py`, `test_render_steps.py` for the listing, the names and the step.
- Electron: the html branch's `capturePage` and reduced motion, and `will-frame-navigate` refusing an outside origin.
- Frontend: the viewer's sandbox and inserted CSP.

## Docs once built

[`agent.md`](../architecture/agent.md) gains the tool, the skill and the HTML previews; [`studio.md`](../architecture/studio.md) gains the html format's two paths beside Word and PDF's; [`model-capabilities.md`](../architecture/model-capabilities.md) names the Web page button among what the levels decide; this proposal is deleted.
