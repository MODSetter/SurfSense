# The comic artifact

> A comic is its own Studio format, `comic`: one artifact whose file is the bound PDF. Studio makes one from sources in its dialog, and the agent binds the pages it drew into one with `surfsense_bind_comic`. Both bind with the same code, so the agent no longer copies a script to fill. Image and infographic stay one Image card in the dialog, the infographic a type of image.

## Why

A comic was a PDF the agent rendered from a script in `pdf.md` ([03](03-comics.md)), listed in Studio as a PDF beside its pages, and Studio could not make one. The agent copied a hundred-line ReportLab script for every comic, which a small model can break.

## Studio

- **Format** `comic`, needing `image_gen` and `text_gen`, with options `{kind, pages}`: one of the ten kinds in `comics.md`, and 1 to 12 pictures, each kind starting at its own length. Checked when the job is created ([`kinds.py`](../../../surfsense_local/backend/modules/artifacts/comic/kinds.py)).
- **Plan, draw, bind** ([`media/visual/comic/`](../../../surfsense_local/backend/worker/studio/media/visual/comic/)): the chat model plans a title, a style line, a character sheet and each page's panels and lines; page 1 is drawn alone and the rest with page 1 as reference; the binder makes the PDF.
- **Lettering.** Studio cannot look at a page. A remote model letters bubbles; a local model's lettering is not measured, so it draws no words and every line goes in the strip under its page.
- **No retry, no Edit.** A retry would bill every page again. One artifact holds one primary file and keeping pages would need a schema change, so a Studio comic is changed by Regenerate.
- **The dialog** gives each format's options their own slot (`format-options/`): the podcast brief, the picture type, and the comic's kind and pages with what they cost.

## The agent

- **`surfsense_bind_comic`** takes the pictures' names in reading order, each with lines for its strip, a `layout` and a `direction`, and `artifact_id` for the comic's next version. A page still being drawn makes it wait, as a document does ([04](04-waiting-render.md)).
- **`create_artifact`** does not offer `comic`: the agent draws its pages and looks at each before it binds them.
- **The skill** drops `pdf.md`; `comics.md` gives each kind's `layout` and `direction`.
- **Pages are not listed.** `make_image` takes `comic_page: true` for every page, binding marks any page drawn without it, and a page's edits keep the mark. Studio lists the comic alone; deleting it deletes the pages nothing else uses.

## Not in this

- Changing one page of a Studio comic.
