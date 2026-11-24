---
name: surfsense-documents
description: Make or change a Word document (.docx), a PDF, a PowerPoint deck (.pptx) or an Excel workbook (.xlsx) by writing a short Python script that surfsense_render_document runs, optionally starting from a source's own Word or PowerPoint file. Load it whenever the user asks for one of these, for a document to send or print, or for a change to one you made.
---

# Documents, decks and workbooks

Make a file with `surfsense_render_document`: give it a `title`, a `format` (`pdf`, `docx`, `pptx` or `xlsx`) and a short Python `script`. SurfSense runs the script, keeps the file as a version in Studio and keeps the script beside it. Then look at every page the result shows before you go on. To change the file later you change the script and render it again, which makes the next version.

For a PDF, a Word document or a deck, write the script with the `surfsense_docs` helper: it lays out headings, text, lists, tables, images, charts and speaker notes, so the script stays short.

## The files in this skill

| File | Read it |
|---|---|
| `workbooks.md` | Before you write any Excel workbook: numbers and formats, totals as formulas, native charts, and how to check one. |
| `by-hand.md` | Before a script that writes python-docx, ReportLab or python-pptx itself: the user's own Word or PowerPoint file as a template, a PowerPoint chart they can edit, the look of a source you can only see, or a layout the helper cannot make. |

## A whole PDF with the helper

A Word document or a deck is the same script with another `format`.

```python
from surfsense_docs import Doc

doc = Doc("Spring plan: Elm Road community garden", subtitle="For the garden committee")
doc.heading("What changes this spring")
doc.paragraph("The garden opens to members on **12 April**, two weeks earlier than last year.")
doc.bullets(["Members water their own plots", "Shared tools stay in the shed"])
doc.heading("Budget")
doc.table(["Item", "Cost (USD)"],
          [["Raised beds", 1200], ["Soil and compost", 450], ["Hand tools", 300]],
          total=["Total", 1950],
          after=[["Water, each month", 40]])
doc.chart("bar", ["Raised beds", "Soil and compost", "Hand tools"], [1200, 450, 300],
          title="Where the money goes", ylabel="USD")
doc.save()
```

- `Doc(title, subtitle=None, letter=False)`, then its parts in reading order, then `save()`. Pages are A4; `letter=True` makes US Letter pages, for a reader in the US or Canada or when the user asks for Letter.
- `heading(text, level=1)`, `paragraph(text)`, `bullets(items)`, `numbered(items)`. `**bold**` and `*italic*` work inside any text.
- `table(header, rows, total=None, bold_total=False, after=None)`. Put numbers in as numbers. `total` is the total row as you write it: add up only the rows it covers. A row that is not part of the total, such as a monthly fee below one-off costs, goes in `after`, below it. `bold_total=True` sets the total row in bold. `total="Total"` instead adds a row that sums every number column of `rows`: use it only when each of those columns is an amount to add up.
- `image(name, width_cm=None, caption=None)` places a picture by the name `surfsense_list_images` or `surfsense_make_image` gave; list every name you use in the call's `images`.
- `chart(kind, labels, values, title=None, ylabel=None)` draws a `"bar"`, `"line"` or `"pie"` chart.
- `notes(text)` is what the presenter says, in the speaker notes of the slide it falls on; a PDF or a Word document leaves it out. `page_break()` starts a new page, or a new slide under the same heading.
- In a deck each `heading` starts a slide: keep each slide to a few bullets, a table or a chart.

## Rules for every script

- Every fact and number comes from the sources you read or from the user. Never invent one, and chart only numbers you found or were given.
- The script runs alone, from an empty folder, for at most 120 seconds, without the network. It cannot read the user's sources: write the content into the script.
- A workbook does not use the helper: read `workbooks.md`, write it with xlsxwriter or openpyxl, put each total in as a formula, and save at `os.environ["OUTPUT_PATH"]`.
- Draw a picture with `surfsense_make_image` only when the user asks for a picture, never for data. To look at a source image yourself, open the copy `surfsense_list_images` names, `sources/figures/<name>.png`, with `read`.
- When the numbers the user wants charted are only in a source's figure, as its caption from `surfsense_list_images` shows, open the figure with `read` and chart the values it labels. If `read` cannot show you the image, place that figure with its caption and tell the user you could not read its values; do the same when it labels none you can read exactly, rather than charting other numbers.

## After every render

1. A PDF, a Word document or a deck comes back with up to four page previews. Look at every one, not only the first. When the result says there are no previews, check the text it returned instead. If something is wrong or missing, such as a table off the page, text off a slide, an empty page or placeholder text, fix the script without dropping anything else, render again and look at the new version's pages too. Open a preview file with `read` only when you need a closer look at one page: every image stays in the conversation.
2. Tell the user in one line what you made: its title and its format.

## Changing a document you made

1. Call `surfsense_read_document` with its artifact id: it gives the newest script. A long script comes in pages: when the result says the script goes on, call it again with the offset it names.
2. Make every change the user asked for in that script, and keep every other line as it was. Read loose words the natural way: "the cover" of a document without a cover page is the top of its first page, and a section the user names that the document lacks is the closest one or a new one. A change request always ends in a render: when the document already has what the user asks for, make that part exactly as they put it (their heading, their wording) and render it anyway. Say in a line what you assumed.
3. Render with the same `title` and `format` and `artifact_id` set to that document: that is its next version. Never start a new document for a change.

## A PDF of a Word document or deck

Call `surfsense_convert_document` with its `artifact_id`, or a selected source's `document_id`, and `format` pdf: LibreOffice lays it out as Office would, and the PDF is a new document in Studio. To change that PDF, change the Word version or deck, render it, and convert the new version. The tool needs Office support: when it is refused for that, tell the user they can turn it on in Settings, and render the PDF with the helper only if they want one now.

## When a render fails

A script that does not parse is not run: the result shows its line with a caret and a hint, and a bracket left open at the end of a call is closed for you, with a note saying so. A run that fails gives the error and the last lines of the traceback; their line numbers point into your script. Fix the cause and render again with the `artifact_id` the result names. After a third failed render for the same request, stop: tell the user in a sentence what failed, and wait for their next message.
