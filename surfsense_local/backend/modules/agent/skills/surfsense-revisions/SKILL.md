---
name: surfsense-revisions
description: Edit the user's own Word (.docx), Excel (.xlsx, .xlsm) or PowerPoint (.pptx) source file with surfsense_revise_document, as a revised copy with tracked changes and comments. Load it whenever the user asks to change, correct, redline, comment on or fill in a file they gave you, rather than to make a new document.
---

# Revising the user's own files

`surfsense_revise_document` edits a copy of a source file the user selected. Their file is never changed: the first call makes version 1 of a new revised copy in Studio, and each later call on that copy makes its next version. The user reviews it there and downloads it "With changes" or "Clean".

## Revise, or make a new document?

- **Revise** when the user wants *their* file back changed: "fix the dates in this contract", "redline clause 7", "comment on the risks", "update the Q3 numbers in my workbook", "change the title on slide 1". Their layout, styles, headers, charts and everything you do not touch stay exactly as they were.
- **Make a new document** with `surfsense_render_document` (load surfsense-documents) when the user wants something that does not exist yet: a summary, a report from several sources, a fresh deck. Also when the change is so large that almost nothing of the original survives.
- When unsure, ask the user which they want.

## Before you edit

1. Read the file's text first (`read` on its file in `sources/`, or `surfsense_read_document`), so every quote you send is copied from what is really there.
   For a workbook, read its cells with `surfsense_read_document` with its `document_id` (or the revised copy's `artifact_id`): it lists each sheet's name and used range, then every cell's address and value or formula. The text in `sources/` has no sheet names, cell addresses or formulas, so never guess them from it.
   To read a revised copy again, call `surfsense_read_document` with its `artifact_id`: a Word copy comes back with every author's tracked changes marked inline and its comments listed with the text each is on, a deck as each slide's text.
2. Give `document_id` (the number at the end of the source's file name) for the first edit. The result names the revised copy's `artifact_id`; every later edit of the same file uses `artifact_id` instead, so the changes build on one copy.
3. Send all the edits for one request in one call, in reading order. All of them apply or none do.

## Anchoring quotes

Word and PowerPoint operations find their place by `quote`: text copied exactly from the document.

- Copy it character for character, including punctuation and capitals. Runs of spaces and tabs count as one space.
- Quote enough words to be unique: one match only. "30 days" may appear five times; "payment is due within 30 days" appears once.
- Keep a quote inside one paragraph. To act on several paragraphs, quote the first and give `through` with a quote from the last (delete_paragraphs).
- Quote the text as it reads now, with earlier tracked changes applied: deleted text is gone, inserted text is there.
- Quote only the words that change in `replace_text`: replacing "30 days" inside a long quote marks the whole quote as deleted and re-inserted.

## Word: always tracked changes

Every Word edit is a tracked change (shown underlined when inserted, struck through when deleted) that the user accepts or rejects in Studio or in Word. There is no way to edit without tracking, so never tell the user a change is final.

- `replace_text`: `quote` and the new `text`; an empty `text` deletes the quote.
- `insert_paragraphs`: new paragraphs after the paragraph holding `quote`; a newline in `text` starts another paragraph; `style` names a paragraph style (else the anchor's).
- `delete_paragraphs`: the paragraph holding `quote`, through the one holding `through`.
- `add_comment`: a comment on `quote`. Any edit can carry a `comment` explaining it.
- `internal: true` keeps a comment for the user only: it stays in their copy in SurfSense and is left out of both downloads. Use it for advice to the user ("push back on this"), never for notes meant for the other side.

### What a comment may say

A comment justifies a change only from the document itself or the user's request: quote the clause it fixes, the clause it matches, or what the user asked for. So never cite laws, regulations, market practice, "standard terms" or facts that are not in the sources or the request, even ones you believe are true; the other side reads these comments as the user's own claims. If a reason needs outside support, leave it out of the comment and tell the user in your answer that they may want to check it.

Headers, footers and footnotes cannot be edited yet: say so if the user asks.

## Excel

- Take sheet names, addresses and formulas from the cells `surfsense_read_document` gave you.
- `set_cell`: `sheet` (its name), `cell` (like `B7`) and either `value` (text, number, true/false, or null to clear) or `formula` (like `=SUM(B2:B6)`).
- `set_range`: `sheet`, `range` (like `A2:C4`) and `values`, rows of values of exactly that shape.
- Charts, shapes, formatting and other sheets are kept. Formulas are not recalculated in SurfSense: when the result says so, tell the user the totals update when the file is opened in Excel.

## PowerPoint

- `replace_text`: `slide` (1-based), `quote`, `text`, and `where: "notes"` for the speaker notes. The text keeps the quoted words' formatting.
- `delete_slide` and `duplicate_slide` by `slide`. Slide numbers always mean the deck as it was before this call, so number every operation against the deck you read.

## Reading the result

- Each operation has a line: `#0 replace_text: applied.` or, when nothing was saved, which one was refused, its code and why (`QUOTE_NOT_FOUND`, `QUOTE_AMBIGUOUS` with a count, `SHEET_NOT_FOUND` with the sheet names, and so on). Fix that operation and send all of them again; the others were skipped only because of it.
- `Note` lines are things the user must hear, such as formulas not recalculated. Tell them.
- The counts say how many tracked changes and comments the version holds in all, including earlier versions'.
- Look at every page preview before you answer. Insertions are underlined and deletions struck through. If an edit landed in the wrong place, revise again with `artifact_id`.
- Tell the user what you changed, that it is a revised copy in Studio, and that their file is unchanged.
