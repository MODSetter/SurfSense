# Comics

> A comic, a storyboard or a picture book loads one skill, `surfsense-pictures`. The agent plans the pages, confirms the count once, draws page 1, draws the rest with page 1 as their reference, and binds every page into one PDF. The PDF is the comic.

## Routing

- **The prompt.** The picture line in [`agent.md`](../../../surfsense_local/backend/modules/agent/prompts/agent.md) becomes: "For a picture, an infographic, a comic, a storyboard, a picture book or any set of pictures, load the `surfsense-pictures` skill, then use `surfsense_make_image`."
- **The web page skill** ([`SKILL.md`](../../../surfsense_local/backend/modules/agent/skills/surfsense-html/SKILL.md)) adds to its description: "Not for a comic, a storyboard or a picture: those are drawn pictures." A page that holds a finished comic's pictures stays possible when the user asks for a web page by name.
- **Both engines** load skills the same way, so opencode threads and Claude plan threads get it alike.

## The skill

`surfsense-pictures` is the craft beside the tool's contract, as `surfsense-documents` is beside `surfsense_render_document`. It sits with the other skills ([`skills/`](../../../surfsense_local/backend/modules/agent/skills/)):

| File | Holds |
|---|---|
| `SKILL.md` | One picture or a set; writing a prompt; lettering; the series steps below; what to say when a model cannot take pictures |
| `comics.md` | Pages and panels, bubbles and captions, the comic's PDF |
| `pdf.md` | The binding script, to copy and fill |

A storyboard or a picture book later is one more file beside `comics.md`, with no new skill and no prompt change.

## The steps

1. **Plan.** A title, the page count, and for each page its panels, what each shows and its lines. A **character sheet**: each character's face, hair, build, clothes and colours, in a few fixed words. A **style line**: medium, palette, line weight, panel borders. Four pages when the user names no number; at most twelve, since each is billed or takes minutes.
2. **Confirm once.** One message: the page count, the plan in short, and what it costs: billed once a page by their provider, or minutes a page on this computer. When the image model cannot take pictures in, one more plain line: "Each page is drawn from the description, so the characters may differ a little between pages." On yes, every page is drawn without asking again. A one-page comic or strip needs no confirmation, as a single picture needs none.
3. **Page 1 alone,** `shape: portrait`. Its prompt is the style line, the character sheet and page 1's panels, laid out as "A comic page of N panels: panel 1, top left: …". Look at it; when it is wrong, edit it before going on, since every later page copies its characters.
4. **The rest, with page 1 as their reference.** Each is its own call, with `references: ["image-<page 1>"]`, the same style line and character sheet, and its panels, all in one step so a remote model draws them side by side. A character picture the user gave, or a character sheet they asked for first, is the reference instead.
5. **Look at every page.** Redraw or edit one only when it is plainly wrong, and say so; a misspelt word is not a reason ([below](#lettering)).
6. **Bind the PDF** ([below](#the-pdf)).
7. **Answer** with the PDF and one line per page, so the user can ask for "page 3 again".
8. **A later change.** Edit the page with its `artifact_id`, read the PDF's script with `surfsense_read_document`, and render its next version with the new name in place of the old. To add a page, draw it with page 1 as reference and render again.

Each page is its own picture, titled "<comic title> · page <n>", so the one-title-per-chat refusal never meets two pages of one comic.

## Lettering

- **Bubbles are drawn by the model.** Each holds one short line, at most about eight words, two or three to a panel, written in the prompt in quotes. The best three models in [the spike](README.md#the-spike) spelled every line right.
- **A misspelt page is not redrawn.** The PDF typesets that page's exact lines in a strip under it, so a bad letter never bills a second picture.
- **On this computer, or when the agent cannot see pictures,** every page is drawn without words and every page gets its strip. Lettering a local model draws itself is not measured ([studio, Known gaps](../../architecture/studio.md#known-gaps)), and a page the agent cannot see it cannot check.

## The PDF

Made with `surfsense_render_document`, `format: pdf`, every page's name in `images`, from the script in `pdf.md`:

- One picture per page, full bleed, in order, at comic-book width (6.625 in) and the page's own height. A title page only when the user asks for one.
- **Pages placed as JPEG at quality 90**, not PNG: four PNG pages made 10 to 28 MB in the spike. Pillow converts each before ReportLab places it; a page is drawn once, so the loss is once.
- A page with a lettering strip is a little taller, the strip below the picture, the lines in the PDF's own font.
- A page still being drawn is named all the same ([the render that waits](04-waiting-render.md)).

## Which models to recommend

From [the spike](README.md#the-spike): `gpt-image-2.6`, Gemini's image models and Seedream letter well and hold characters, and the user docs name them for comics. FLUX.2 klein, remote or local, draws fast and holds characters but garbles lettering, so its pages get strips. The app recommends nothing in the moment: the user's chosen model is used as it is.

## Checks

- An agent test, with the stand-in model, as [`test_agent_makes_image.py`](../../../surfsense_local/backend/tests/integration/agent/test_agent_makes_image.py) does for one picture: "make a comic" loads `surfsense-pictures`, draws page 1, then the rest with `references`, then renders one PDF naming every page.
- `pdf.md`'s script, run as the render runs it, on four stand-in pages: four PDF pages, JPEG images, under 5 MB, and a strip page when asked.
- Manual: a four-page comic on a remote model that takes pictures, on one that does not, and on a local model, each read as a PDF, with page 3 changed after.
