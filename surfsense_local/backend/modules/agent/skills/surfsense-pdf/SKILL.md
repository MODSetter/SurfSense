---
name: surfsense-pdf
description: Work on PDFs the user has, or PDFs in Studio, without changing them - merge, take out, split, turn or reorder pages, add a watermark, page numbers, a header or a footer, and list or fill a form's fields. Load it whenever the user asks for one of these on a PDF.
---

# Working on PDFs

Three tools work on PDFs the user selected and on PDF artifacts in Studio. None of them runs a script and none of them changes the PDF it reads: each result is a new PDF artifact in Studio, and the user's own file stays exactly as it was. Say so when the user worries about their original.

| The user wants | Tool | Call |
|---|---|---|
| Several PDFs as one | `surfsense_pdf_pages` | `operation: "merge"`, the PDFs in order |
| Only some pages | `surfsense_pdf_pages` | `operation: "extract"`, `pages` |
| One file per chapter, per section, per page | `surfsense_pdf_pages` | `operation: "split"`, a range per part in `pages` |
| A page turned the right way up | `surfsense_pdf_pages` | `operation: "rotate"`, `angle`, `pages` |
| The pages in another order | `surfsense_pdf_pages` | `operation: "reorder"`, every page once in `pages` |
| "DRAFT" or "CONFIDENTIAL" across each page | `surfsense_pdf_stamp` | `kind: "watermark"`, `text` |
| Page numbers | `surfsense_pdf_stamp` | `kind: "page_numbers"`, optional `text` with `{page}` and `{total}` |
| A line of text at the top or bottom of each page | `surfsense_pdf_stamp` | `kind: "header"` or `"footer"`, `text`, optional `position` |
| What a form asks for | `surfsense_pdf_form` | `action: "list"` |
| A form filled in | `surfsense_pdf_form` | `action: "list"`, then `action: "fill"` with `fields` |

A new document written from scratch, even a PDF, is `surfsense_render_document` with the surfsense-documents skill, not these tools.

## Naming the PDFs

- A source by `document_id` (or `document_ids` for pages): the number in brackets at the end of its file name in `sources/`.
- A PDF in Studio by `artifact_id` (or `artifact_ids`): every result names its new artifact's id. Pass it to the next tool to go on, for example extract pages, then number them.
- A merge takes `document_ids` in their order, then `artifact_ids` in theirs. For another mix, merge in two steps.

## Page ranges

`pages` is text: page numbers from 1 and ranges, separated by commas.

- `"1-3,7"`: pages 1, 2, 3 and 7.
- `"5-"`: page 5 to the last page.
- `"9-7"`: pages 9, 8 and 7, backwards.
- Extract keeps the pages in the order written, so `"3,1,2"` reorders as it extracts.
- Split makes one PDF per comma-separated item: `"1-4,5-9,10-"` makes three. Left out, each page becomes its own PDF; at most 20 parts.
- Reorder must name every page exactly once.
- Rotate and stamp work on every page when `pages` is left out. For a stamp, `"2-"` skips a cover.

When you do not know how many pages a PDF has, look at its text in `sources/`, or run the tool: a page past the end is refused with the count.

## Stamps

- Write the text in the language of the PDF, not in English by default: `"Seite {page} von {total}"` for a German document.
- `{page}` is each page's own number in the file, so numbers on pages `"2-"` start at 2.
- `position` places a header, footer or page number: `top-left`, `top-center`, `top-right`, `bottom-left`, `bottom-center`, `bottom-right`. A watermark always runs corner to corner.
- Text in a script beyond Latin needs a font on this computer that has it; the tool says when there is none.

## Forms

1. List the fields first. The names to fill are exactly the names the list gives, with any dots in them.
2. Fill text fields with text, checkboxes with `true` or `false`, and radio groups, dropdowns and lists with one of the options the list shows.
3. Fill only what the user gave you or what the sources say. Ask about a field you would have to guess, such as a date of birth or a signature.
4. `flatten: true` prints the values into the pages so nobody can change them. Use it only when the user asks for a final, locked copy.

A signature field cannot be filled here. A form made in Adobe's XFA format cannot be read or filled: tell the user to fill it in Adobe Acrobat or Reader.

## Checking the result

When you can see images, the result brings the new pages. Look at them: a turned page should read upright, a stamp should not cover the text, a filled field should show its value. Then tell the user the new PDF's title, and that it is in Studio.

A PDF protected by a password cannot be opened; ask the user for a copy without the password.
