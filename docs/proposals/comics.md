---
status: proposed
code:
  - surfsense_local/backend/modules/agent/prompts/agent.md
  - surfsense_local/backend/modules/agent/skills/surfsense-comics/
  - surfsense_local/backend/modules/agent/skills/surfsense-html/SKILL.md
  - surfsense_local/backend/modules/agent/tool_endpoint/make_image.py
  - surfsense_local/backend/modules/agent/tool_endpoint/render_document.py
  - surfsense_local/backend/modules/artifacts/drawn_images/
  - surfsense_local/backend/modules/artifacts/script_documents/
  - surfsense_local/backend/modules/llm/providers/
  - surfsense_local/backend/worker/studio/
---

# Comics the agent draws

> Asked for a comic, the agent plans its pages, confirms the count once, draws one picture per page with the user's image model, keeping its characters the same from page to page, and binds the pages into one PDF. A local model's slow pages no longer leave the comic for the user's next message: the PDF renders itself once its last page is drawn.

## Today

Asked for a comic, the agent wrote a web page and drew the panels as SVG. When it did call `surfsense_make_image`, it drew one picture and stopped. Nothing in the agent's text makes a comic a picture job, and two lines push it away:

- The prompt sends only "a picture or infographic" to `surfsense_make_image` ([`agent.md`](../../surfsense_local/backend/modules/agent/prompts/agent.md)). A comic is neither, and the web page skill's description, "an explainer … a figure that shows how something works", drawn "as inline SVG" ([`SKILL.md`](../../surfsense_local/backend/modules/agent/skills/surfsense-html/SKILL.md)), is the nearest match.
- The tool's description says "confirm before making more than one" and "words that must be exact belong in the document around the picture" ([`make_image.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/make_image.py)). A comic is many pictures, mostly dialogue, so both read as "do not draw this".

Three limits stay even with the wording fixed:

- **Characters drift.** Every picture is drawn from its prompt alone. The same character sheet in six prompts gives six different faces.
- **Every picture is the model's default shape**, usually square. Neither the remote request ([`image.py`](../../surfsense_local/backend/modules/llm/providers/openai_compatible/image.py)) nor the local one sends a size, and a comic page is portrait.
- **A local page is past the call's limit.** A drawing on a processor takes several minutes and an edit 657 to 962 seconds ([studio](../architecture/studio.md#editing-a-picture)). The call answers `Queued` after 150 seconds, and a render naming a picture still being drawn is refused, so the PDF waits for the user's next message ([agent, Known gaps](../architecture/agent.md#known-gaps)). Six pages is six of those.

## What changes

| | Today | With this |
|---|---|---|
| "Make a comic about …" | a web page with SVG panels, or one picture | a plan, one confirmation, one picture per page, one PDF |
| Characters across pages | redrawn from words each time | page 1, or a character sheet, given to every later page as a reference picture |
| A page's shape | the model's default, usually square | `portrait` for a page, `landscape` for a strip, `square` |
| Speech bubbles | discouraged | drawn by the model; any page whose lettering comes back garbled gets its exact lines typeset under it in the PDF |
| A page still drawing when the PDF is rendered | refused; made on the user's next message | the PDF waits as a pending version and renders when its last page is ready |
| Changing page 3 | possible, but nothing says how to put it back | edit page 3, then render the PDF's next version with the new picture's name |

The tool stays `surfsense_make_image` ([ADR 0087](../adr/0087-the-agent-makes-pictures-with-its-own-surfsense-tool.md)). opencode's `experimental_image_generate` is not used, now or as a fallback.

## Design

### 1. Routing to a comics skill

- One line in the prompt, under *Producing files*: "For a comic, manga, comic strip, storyboard or picture book, load the `surfsense-comics` skill." It sits beside the picture line, which stays for a single picture.
- `surfsense-comics` is a new skill folder beside the others ([`skills/`](../../surfsense_local/backend/modules/agent/skills/)): `SKILL.md`, the steps below, and `pdf.md`, the ReportLab script that binds the pages, to copy and fill.
- The web page skill's description gains "not a comic or a storyboard: those are drawn pictures". A page that *contains* a finished comic's pictures stays possible when the user asks for a web page by name.
- Both engines load skills the same way, so opencode threads and Claude plan threads get it alike.

### 2. What the skill tells the agent to do

1. **Plan.** From the user's request and any sources: a title, the page count, and for each page its panels, what each shows and its lines. A **character sheet**: each character's face, hair, build, clothes and colours, in a few fixed words. A **style line**: medium, palette, line weight, panel borders. Four pages when the user names no number; at most twelve, since each is billed or takes minutes.
2. **Confirm once.** One message with the page count, the plan in short, and the cost: billed once per page by the user's provider, or about a few minutes a page on this computer, a longer time with references. On yes, the agent draws every page without asking again. A one-page comic or strip needs no confirmation, as a single picture needs none today.
3. **Draw page 1 alone**, `shape: portrait`. Its prompt is the style line, the character sheet and page 1's panels, laid out as "a comic page of N panels: panel 1, top left: …". Look at it. When it is wrong, edit it before going on, since every later page copies its characters.
4. **Draw the rest with page 1 as their reference.** Each is its own call with `references: ["image-<page 1>"]`, the same style line and character sheet, and its panels. They go in one step, so a remote model draws them side by side. A user who gave a character picture of their own, or asked for a character sheet first, has that as the reference instead.
5. **Lettering.** Each bubble holds one short line, at most about eight words, two or three bubbles a panel, written in the prompt in quotes. When a page comes back with a line misspelt, the agent does not redraw it: the PDF typesets that page's exact lines in a strip under it. When the picture was drawn on this computer, or the agent cannot see pictures, every page is drawn without words and every page gets its strip, since lettering cannot be relied on or checked.
6. **Bind the PDF** with `surfsense_render_document`, `format: pdf`, every page's name in `images`: one picture per page, full bleed, in order, a title page only when the user asks for one. A page still being drawn is named all the same ([section 5](#5-a-render-that-waits-for-its-pictures)).
7. **Answer** with the PDF and one line naming each page, so the user can ask for "page 3 again".
8. **A later change.** To change a page, edit it with its `artifact_id`, then read the PDF's script with `surfsense_read_document` and render its next version with the new name in place of the old. To add a page, draw it with page 1 as reference and render again.

### 3. `surfsense_make_image` changes

Two new arguments and a rewritten description. Everything else, the waiting, the three-failure limit, the naming and the placing, stays as it is.

| Argument | Type | Meaning |
|---|---|---|
| `references` | up to 4 picture names | Pictures this chat made, each ready, for the new picture to keep: the same characters, the same style. Only for a new picture, not with `artifact_id`. |
| `shape` | `square`, `portrait` or `landscape` | The picture's proportions. Left out, the model's default, as today. |

- **A picture with references is drawn by the edit model**, the one that already reads a picture with its instruction ([image edit](../architecture/studio.md#editing-a-picture)). It is a new artifact, v1 of its own document, with the recipe `{"kind": "image_drawn", "prompt", "references": [<artifact ids>]}`, so Studio lists it, versions it and lets it be edited like any other picture. With no edit model chosen, the call is refused before anything is billed: "No image editing model is chosen, so a page cannot copy another: draw it from the character sheet alone, or tell the user they can choose one in Settings › Image edit." The skill then draws every page from words alone and says so to the user.
- **References are checked as placing is**: a name of this chat, ready (a picture still being drawn is refused, with a sentence to draw page 1 first), a still picture, and at most four, to bound what one call uploads; the spike may lower it. A refused reference is not a failed run.
- **The description**, rewritten:
  - "Only when the user asks for one" stays. "Confirm before making more than one" becomes "When a request needs more than one picture, confirm how many once, before the first: each is billed, or takes minutes on their computer."
  - "Words that must be exact belong in the document around the picture" becomes "Lettering may come out misspelt: keep any words in a picture short, and put text that must be exact in the document around it."
  - "Draw no data chart" stays.
- **The result** adds where it was drawn, "Drawn on this computer" or "Drawn by <connection name>", so the skill can choose wordless pages for a local model.

### 4. Many references and a shape, per provider

The image protocols ([`protocols.py`](../../surfsense_local/backend/modules/llm/providers/protocols.py)) widen:

```python
class ImageGenerator(Protocol):
    async def generate(self, model: str, prompt: str, shape: Shape | None = None) -> GeneratedImage: ...

class ImageEditor(Protocol):
    async def edit(self, model: str, prompt: str, images: Sequence[GeneratedImage], shape: Shape | None = None) -> GeneratedImage: ...
```

An edit of one picture passes one image and no shape, so the edit job keeps its output size.

- **Remote drawing** sends `size`: `1024x1024`, `1024x1536` or `1536x1024`. A `400` sends it once more without `size`, as a refused `response_format` already is ([`image.py`](../../surfsense_local/backend/modules/llm/providers/openai_compatible/image.py)), remembered per endpoint, and the result says the model kept its own shape.
- **Remote with references** posts every picture as an `image[]` part of the multipart `/images/edits` ([`image_edit.py`](../../surfsense_local/backend/modules/llm/providers/openai_compatible/image_edit.py)), with `size` as above. An endpoint that answers `400` to several pictures gets the first alone, once, remembered per endpoint, and the result says only one reference reached the model. The spike below decides whether that fallback is kept or the call is refused instead.
- **Local drawing with a shape** moves to sd-server's native `POST /sdcpp/v1/img_gen`, which the edit client already uses ([`editor.py`](../../surfsense_local/backend/modules/llm/providers/sdcpp/editor.py)), with `width` and `height` set to the shape at the launch default's pixel count, each a multiple of 64. A drawing with no shape keeps its route.
- **Local with references** puts every picture in `ref_images`, the field the edit client already sends one picture in, and sets `width` and `height` from the shape, or from the first reference when none is given.

### 5. A render that waits for its pictures

Amends ADR 0087's "A document needing a picture still being drawn waits for the user's next message".

- `surfsense_render_document` with a picture name still being drawn is no longer refused. It creates the pending version as today, with the metadata `waits_for: [<artifact ids>]`, and does not queue its job. The call answers at once: "Queued artifact <id>, version <n>: it renders once image-12 and image-14 are drawn. Do not render it again." The agent tells the user the PDF will appear in Studio.
- **A picture's job ending queues what waits on it.** At the end of every Studio job, in the same place it notifies the app ([`job.py`](../../surfsense_local/backend/worker/studio/job.py)), the worker finds the pending renders in that picture's thread whose `waits_for` names it. Each one whose pictures have all ended is queued then, through `queue_job` as every version is.
- **A picture that failed or was cancelled** fails the waiting render with a sentence naming it: "image-14 failed, so this PDF was not made. Draw that page again, or render without it." The render's failure counts under renders' three-failure limit when the next render is asked for, as a queued render's late failure does today ([`failed_renders.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/failed_renders.py)).
- **Only drawn pictures wait.** A source's figure or a chat's chart is either there or not, so a missing one is refused as today. A web page saved with `surfsense_save_page` still refuses a picture being drawn, since the page is checked and screenshotted as it is saved.
- **A restart** settles waiting renders at worker start, beside the interrupted documents ([`interrupted_documents.py`](../../surfsense_local/backend/worker/interrupted_documents.py)): a render whose pictures have all ended is queued, one still waiting stays pending, and one waiting on a picture that was itself interrupted fails with the same sentence.
- **Cancel** in Studio works as on any pending version: it is cancelled and never queued.
- **The agent cannot check its previews** when it renders this way, since the render finishes after its turn. The skill's PDF script is a fixed layout, one full-bleed picture per page, so there is little to go wrong. The open thread already reads its messages again when an artifact becomes ready, so the step links the PDF then ([agent](../architecture/agent.md#pictures-the-agent-makes)).

### 6. In Studio

- Each page is its own picture, titled "<comic title> · page <n>", so the same-title refusal ([`same_title_documents.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/same_title_documents.py)) never meets two pages of one comic, and the user can open, edit or download any page. The PDF is its own artifact. Nothing in Studio's lists, viewer or buttons changes.

## Decisions

- **One picture per page, not per panel.** A page is one call, so six pages bill six pictures, not twenty-four, and a local comic takes minutes a page rather than an hour a page. A page also composes its panels as a comic artist would. The cost is that one bad panel redraws its page; an edit fixes most of those without a redraw.
- **Consistency by reference picture, not by words.** A character sheet in words is kept in every prompt too, but words alone redraw a face from scratch each time. Passing page 1 to the edit model is the one way both remote and local models already take to hold a face. A remote API's own "character" or "seed" features are not used: few providers have them and none agree.
- **The edit model draws a page with references.** It is the slot that reads pictures; `/images/generations` takes none. A user with only a drawing model still gets a comic, from words alone, and is told why the faces may differ.
- **The fallback for lettering costs nothing.** A garbled bubble is covered by a typeset strip rather than a redraw, so a bad letter never bills a second picture. Local pages are wordless because lettering the local model draws itself is not measured ([studio, Known gaps](../architecture/studio.md#known-gaps)); a measurement can lift that.
- **The PDF waits on the server, not in the agent.** A tool that polls, or a turn that waits, holds a tool call past its limit or a chat open for an hour; ADR 0087 rules out both. A pending version that the last picture's job queues needs no new process, no polling and no model awake.
- **No Studio comic format.** A Studio button would need a chat model to write the plan from sources, a second path beside the agent's, and Studio's drafts cannot place these pictures. It can be added later on top of the same tool and recipe.
- **Not a web page.** A comic is read as pages and printed or shared as a file; the PDF is what the user keeps. SVG panels drawn by a chat model are not a comic.
- **opencode's image tool is never used.** It finishes after the turn ends and is listed only on opencode 2.2 ([ADR 0087](../adr/0087-the-agent-makes-pictures-with-its-own-surfsense-tool.md)).

## Not decided here

- Grouping a comic's pages under its PDF in Studio, so twelve pages are not twelve rows.
- A comic button in Studio.
- Panels placed and lettered by SurfSense from wordless panel pictures, with real speech bubbles drawn by the PDF script where the model left room. It needs the agent to know where each bubble may go.
- A limit on pictures per turn enforced by the server rather than by the skill's twelve.

## Spikes before code

Each runs in the scratchpad against the real endpoint or binary, and its result is posted on the implementation PR.

- **Remote, several references.** gpt-image-1 on OpenAI's `/images/edits` with two and four `image[]` parts and `size=1024x1536`; the same on one OpenAI-compatible gateway in the catalog that serves an image model from another vendor. Decides the one-reference fallback.
- **Remote shape.** Which providers in the catalog take `size` on `/images/generations`, and how each refuses it.
- **Local references.** The pinned sd-server with the catalog's edit model, `ref_images` of one and of two pictures and a portrait `width` and `height`: whether a face holds over four pages, and the seconds a page on a processor, to put in the confirmation.
- **Local shape.** The native route's drawing at a portrait size against the OpenAI-compatible route's square one, for time and quality.

## Checks

- **Routing:** an agent test, with the stand-in model, that "make a comic" loads `surfsense-comics`, draws page 1, then the rest with `references`, then renders one PDF naming them all, as [`test_agent_makes_image.py`](../../surfsense_local/backend/tests/integration/agent/test_agent_makes_image.py) does for one picture.
- **Tool:** [`test_make_image.py`](../../surfsense_local/backend/tests/integration/agent/test_make_image.py) gains `references` and `shape` against the stand-in painter: references reach the edit model in order, a reference from another chat, a picture still drawing, a fifth reference and references with `artifact_id` are refused unbilled, no edit model refuses references, and the result names where it was drawn.
- **Providers:** unit tests on the multipart parts and the `400` fallbacks for the remote clients, and on the `img_gen` body for the local ones.
- **Waiting render:** a render naming a picture still drawing returns `Queued`; it renders once the picture is ready; a failed or cancelled picture fails it with the sentence; one of two pictures ending leaves it waiting; a worker restart queues, keeps or fails it as section 5 says.
- **Manual:** a four-page comic on a remote model and on a local one, each read as a PDF, with page 3 changed afterwards.

## When it ships

- [agent](../architecture/agent.md): the comics skill, the tool's new arguments and the waiting render, and the two Known gaps on slow pictures and lettering deleted.
- [studio](../architecture/studio.md): the `image_drawn` recipe's references, the shape, and the providers' new requests.
- An ADR for the render that waits on its pictures, amending ADR 0087.
- The user docs: [`guides/images.mdx`](../../www/content/docs/v2/guides/images.mdx) and [`agent.mdx`](../../www/content/docs/v2/agent.mdx) gain making a comic.
