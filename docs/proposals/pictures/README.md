---
status: proposed
code:
  - surfsense_local/backend/modules/llm/providers/
  - surfsense_local/backend/modules/llm/connections/
  - surfsense_local/backend/modules/llm/resolution.py
  - surfsense_local/backend/modules/artifacts/drawn_images/
  - surfsense_local/backend/modules/artifacts/image_edits/
  - surfsense_local/backend/modules/artifacts/script_documents/
  - surfsense_local/backend/modules/agent/prompts/agent.md
  - surfsense_local/backend/modules/agent/skills/
  - surfsense_local/backend/modules/agent/tool_endpoint/
  - surfsense_local/backend/worker/studio/
  - surfsense_local/frontend/src/features/studio/
  - surfsense_local/frontend/src/features/models/
  - surfsense_local/frontend/src/features/settings/models/
---

# Pictures: one image model, edits for every model, and comics

> The user chooses one image model. It draws, and when it can take a picture in it also edits and keeps characters the same from page to page. A model that cannot gets its edits redrawn instead, so Edit works for every model and nothing asks for a second model. On that, the agent makes comics: it plans the pages, confirms the count once, draws one picture per page and binds them into one PDF.

## Today

Asked for a comic, the agent wrote a web page and drew the panels as SVG, or drew one picture and stopped. Under that sit four limits in how images work:

- **Nothing makes a comic a picture job.** The prompt sends only "a picture or infographic" to `surfsense_make_image` ([`agent.md`](../../../surfsense_local/backend/modules/agent/prompts/agent.md)); the web page skill's description, "an explainer … a figure that shows how something works", drawn "as inline SVG", is the nearest match; and the tool's own description says "confirm before making more than one" and sends exact words "to the document around the picture" ([`make_image.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/make_image.py)).
- **Editing needs a second model most users never choose.** Studio's Edit and the agent's edit run only on the `image_edit` slot ([ADR 0077](../../adr/0077-an-image-edit-is-the-next-version.md)). Few local models can fill it, and an empty slot answers "Needs an image editing model" with a link to Settings. The image model the user did choose is never asked, though most remote ones take a picture in.
- **Editing through OpenRouter fails.** A remote edit always posts `/images/edits` ([`image_edit.py`](../../../surfsense_local/backend/modules/llm/providers/openai_compatible/image_edit.py)), and OpenRouter has no such route: it answers 404.
- **Every picture is the model's default shape, and drawn from words alone.** No request sends a size or a reference picture, so a comic page comes out square and its characters change from page to page. A local page is also past a tool call's limit, and a document naming a picture still being drawn is refused until the user's next message ([agent, Known gaps](../../architecture/agent.md#known-gaps)).

## What changes

| | Today | With this |
|---|---|---|
| Models the user chooses for pictures | an image model, and an edit model for edits | one image model; a different edit model only if they want one |
| Edit, with a model that takes pictures in | needs the edit slot filled | a real edit by the image model |
| Edit, with a model that does not | "Needs an image editing model", and a link to Settings | the picture drawn again from its prompt and the change, said in one neutral line |
| Editing through OpenRouter | 404 | works, through `/images` with `input_references` |
| Settings › Image models | no sign of which models edit | an **Edits** label on those that do, tooltip "Can edit pictures" |
| "Make a comic about …" | a web page with SVG panels, or one picture | a plan, one confirmation, one picture per page, one PDF |
| Characters across pages | redrawn from words each time | page 1 given to every later page as a reference |
| A page's shape | the model's default | `portrait`, `landscape` or `square` |
| A document waiting on a picture still being drawn | refused until the user's next message | a pending version that renders when its pictures are drawn |

## Parts

| Part | File | Owns |
|---|---|---|
| **Image models** | [`01-image-models.md`](01-image-models.md) | what a model can do, which model handles a picture, one client per provider, edits and redraws |
| **The agent's picture tool** | [`02-make-image-tool.md`](02-make-image-tool.md) | `shape` and `references` on `surfsense_make_image`, and its description |
| **Comics** | [`03-comics.md`](03-comics.md) | the `surfsense-pictures` skill, the routing, the PDF |
| **The render that waits** | [`04-waiting-render.md`](04-waiting-render.md) | a document that renders once its pictures are drawn |
| **In the app** | [`05-in-the-app.md`](05-in-the-app.md) | Settings' label, Studio's Edit, the words users see |

## The spike

Run on 10 Nov 2026 against OpenRouter with one four-page story, "The Lighthouse Cat": page 1 drawn from words with a portrait size, pages 2 to 4 drawn with page 1 as their reference, the four bound into a PDF. Six models, 24 pictures. The script and its outputs stayed in the scratchpad.

| Model | Lettering | Characters held | Follows the script | Seconds a page |
|---|---|---|---|---|
| `openai/gpt-image-2.6-flare` | exact | yes | every line and panel | 45–75 |
| `google/gemini-nano-banana-2.1` | exact | yes | adds lines of its own | fast |
| `bytedance-seed/seedream-5-0-pro` | exact | yes | close; adds a page number on some pages | fast |
| `qwen/qwen-image-3-pro` | good | yes | repeats a caption | 130–195, one upstream 504 |
| `black-forest-labs/flux-3-image` | good | mostly | draws two cats in one panel | 65–80 |
| `black-forest-labs/flux-3-image-klein` | garbled ("WENT CUT", labels unreadable) | yes | repeats captions | 30–50 |

What it settled:

- **OpenRouter has no `/images/edits`.** It has two kinds of image model. Pure image models (GPT image, FLUX, Qwen) refuse `/chat/completions` with a 404 that names `/api/v1/images`; chat image models (Gemini, Seedream) take it. `POST /images` with `input_references`, a list of `{"type": "image_url", "image_url": {"url": <data URL>}}`, and `aspect_ratio` worked for every pure image model tried, so it is the one route for a picture in.
- **`size` works.** `1024x1536` on `/images/generations` came back portrait from all six; FLUX gave its own 880 x 1184.
- **A reference holds a character on every model tried**, with no edit model involved.
- **Lettering is good enough on the best three** to let the model draw speech bubbles; klein shows why the PDF also needs a typed fallback.
- **A page PDF of PNGs is 10 to 28 MB** for four pages. JPEG pages are needed.
- **A read timeout must not be retried**: the provider may still be drawing, and a second request bills a second picture.

Not spiked: a local model with references (no image model is installed on the machine the spike ran on), and providers other than OpenRouter. Both are spikes before their part's code ([image models](01-image-models.md#spikes-before-code)).

## Build order

On one branch, `feat/comics`, a commit per step, each test first:

1. Image models: the capability, the rule, the clients ([01](01-image-models.md)).
2. Edits for every model: the edit job on the rule, and redraws ([01](01-image-models.md#edits-and-redraws)).
3. `shape` and `references` on the tool ([02](02-make-image-tool.md)).
4. The `surfsense-pictures` skill and its routing ([03](03-comics.md)).
5. The comic PDF ([03](03-comics.md#the-pdf)).
6. The render that waits ([04](04-waiting-render.md)).
7. Settings' label and Studio's Edit ([05](05-in-the-app.md)).
8. Docs: architecture, ADRs, user docs, and this proposal deleted ([below](#when-it-ships)).

## Decisions

- **One image model, not two slots.** Whether a model can take a picture in is a fact about the model, so it is read from the model, not asked of the user. The edit slot stays as an override for the few who want another model for edits.
- **Every model can be edited.** A model that cannot take a picture in redraws from the picture's prompt and the change. It is not an edit, and the version says so, but the user never meets a dead end or a setting.
- **The agent's own tool, never opencode's.** opencode's `experimental_image_generate` finishes after the turn ends and needs opencode 2.2 ([ADR 0087](../../adr/0087-the-agent-makes-pictures-with-its-own-surfsense-tool.md)). It is not used, now or as a fallback.
- **Comics are pictures bound into a PDF.** Not a web page, not a single picture, not a new Studio format.
- **Nothing in Studio or chat points to Settings** for pictures. A model that cannot do something is described in a neutral line, never as a warning.

## Not decided here

- Grouping a comic's pages under its PDF in Studio, so twelve pages are not twelve rows.
- A comic button in Studio, which would need a chat model to write the plan from sources.
- Panels lettered by SurfSense from wordless pictures, with speech bubbles the PDF script draws.
- A server limit on pictures per turn, beyond the skill's twelve pages.

## When it ships

- [studio](../../architecture/studio.md): image models and the rule, the clients, edits and redraws, `shape` and `references` in the recipe.
- [agent](../../architecture/agent.md): the skill, the tool's arguments, the render that waits, and the Known gaps on slow pictures and lettering deleted.
- [selection](../../architecture/local-models/selection.md): the edit slot as an override.
- ADRs: one amending [ADR 0077](../../adr/0077-an-image-edit-is-the-next-version.md) (the image model edits; a model that cannot redraws), one amending [ADR 0087](../../adr/0087-the-agent-makes-pictures-with-its-own-surfsense-tool.md) (a document waits on its pictures on the server).
- The user docs: [`guides/images.mdx`](../../../www/content/docs/v2/guides/images.mdx), [`studio.mdx`](../../../www/content/docs/v2/studio.mdx), [`agent.mdx`](../../../www/content/docs/v2/agent.mdx) and the image model pages under `models/`.
