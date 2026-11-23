# ADR 0095: The agent scripts documents with a helper and a short skill, and a script that does not parse never runs

- **Status:** Accepted
- **Date:** 2026-11-22
- **Source:** maintainer decision, 22 Nov 2026 (no permalink): the small-documents experiment's four changes ship on for everyone, with its two known risks fixed first

## Context

The documents skill was 19,066 characters, about 5,900 tokens, of rules and six examples, read whole before every document. A small local model runs the agent in a 32K window that opencode compacts at 24,576 tokens, after a first request of about 9,500, so the skill took a fifth of what was left. It then wrote python-docx or ReportLab by hand: 150-line scripts that failed on a missing bracket, or never rendered.

The weak-hardware tests of 22 Nov 2026 put four changes behind one switch in a worktree (`plans/community-local/local-models-weak-hardware.md`, experiment C): a helper that lays a document out from a few calls, a short skill built on it, a syntax check before a script runs, and a rule for asks that name no format. On the two document cases they were tuned on, run twice each, Nemotron 3.5 Bolt E4B went from 1 of 4 to 4 of 4 and Spark-X2.5-4B from 1 to 3; Spark-X2.6-4B `Q8_0` passed 4 of 4 either way. On the 11 scored cases of the live suite that tuning never saw, Spark-X2.6-4B `Q8_0` passed 8 with the switch on and 7 with it off, one run each: a wash. Claude Haiku 5.5, Qwen3.8 27B and Gemma 4 31B through OpenRouter passed 4 of 4 both ways.

Two risks came with it. The helper's automatic total added every listed row, so a model that listed a monthly fee among one-off costs got a wrong total. And the short skill dropped the full skill's rules for workbooks, templates, native charts and matching a look.

## Decision

- **A helper beside every script.** `worker/document_script/surfsense_docs.py` is copied into each document script's run folder, which the child puts first on `sys.path`, so a script can `from surfsense_docs import Doc`. `Doc(title)`, then headings, paragraphs, lists, tables, images, charts and speaker notes in reading order, then `save()`, writes a PDF, a Word document or a deck from the same script, as `OUTPUT_PATH`'s extension says: A4 or US Letter pages, real heading and list styles, tables whose header row repeats, 16:9 slides from the deck's own layouts with list paragraphs PowerPoint draws the bullets of. A workbook is still xlsxwriter or openpyxl.
- **A short skill, nothing dropped.** `SKILL.md` holds the helper, its example, the rules every script keeps, looking at the pages, changing a document, converting it to PDF and failed runs. The full rules move beside it, for the agent to read when a task needs them: `workbooks.md` before any workbook, `by-hand.md` before a script that writes the libraries itself, for a template, a native PowerPoint chart, the look of a source or a layout of its own, with the five hand-written examples. The skill stays one skill, so nothing in the permissions changes; `by-hand.md` and `workbooks.md` are read as the pictures skill's `comics.md` is.
- **Totals are typed.** A table's total is the row the script gives; rows outside it go in `after`, below it. `total="Total"` sums every number column of the rows, and the skill offers it only for a table whose number columns are all amounts. The example types its total.
- **A script that does not parse never runs.** `surfsense_render_document` parses the script before it makes a version. A Markdown fence around it is removed and closing brackets left out are added, with a note at the end of the result naming each; any other syntax error is a tool error with its line, the lines around it, a caret and a hint, no version is made, and it counts as one of the turn's three failed runs, as the run that failed on it would have.
- **An ask that names no format is made.** The prompt says not to ask which format: a PDF for something to send as it is, a Word document for a draft to edit, a deck only when slides are asked for, and a line saying which.
- **On for everyone.** No switch: big models lost nothing in the tests, and the full rules are one read away.

## Consequences

- A document costs the agent about 2,300 tokens of skill instead of 5,900, and a brief is about twenty lines of script instead of 150.
- The tests are a smoke test: invented sources, one run per suite case, a switch tuned on two of its cases, and a final skill longer than the one measured (about 7,300 characters against 3,600, for the rules the short one dropped). The verification runs on the shipped text are in the pull request.
- The helper is an API kept in the stored scripts: a later version of a document renders its script with the helper of the app that renders it. A change to the helper must keep every call and argument a stored script can make, and lay the document out as before or better.
- A document built with the helper has the helper's look. A brand, a template or the look of a source is a script written by hand, with `by-hand.md`.
- A model that writes a workbook without reading `workbooks.md` has only the short skill's line on workbooks, as the tested version did.
