# Create and edit: running the slice from a dev build

How to run the [create-and-edit slice](07-create-and-edit-mvp.md) on `dev_mod` with Claude Sonnet, how the live tests spend real money on it, and the script for the demo video. Every build stages opencode, so only a model off the tested list needs a developer switch ([agent](../../architecture/agent.md)).

## Run it

**Before the first run:** the usual desktop setup from [`surfsense_local/`](../../../surfsense_local/)'s README (`uv sync` in `backend/`, `pnpm install` in `frontend/` and `electron/`), and an Anthropic API key of your own.

1. **Start the app**, in one shell. `pnpm dev` runs `predev`, which stages opencode with `build:opencode` unless `SURFSENSE_LOCAL_OPENCODE_ENABLED=0` is set. The API inherits Electron's environment, which is where the switch must be. Leave the switch out to see what users get: a model on the tested list (`capabilities.json`) runs the agent, and any other uses the chat unless its "Try the agent" is on.

   ```bash
   cd surfsense_local/electron
   export SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1   # optional: let any model run the agent, untested ones too
   pnpm dev
   ```

   In PowerShell, set it with `$env:SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS = "1"`. `electron/opencode/` then holds opencode 1.18.34 and ripgrep, `opencode` and `rg`. `predev` also stages the embedding model and Docling's parser pack, which ingest and the figures need.

2. **Finish onboarding** if this data folder is new, so an embedder is chosen: Studio and the render tool refuse to start without one.

3. **Connect Claude Sonnet** in Settings › Text gen › Connect a server. Choose **Anthropic** as the provider, which fills the Base URL with Anthropic's OpenAI-compatible endpoint, `https://api.anthropic.com/v1/`, and type your key into the API key field. The app keeps it encrypted under its own keychain secret; never put it in an environment variable or a file for the app. Save, allow `api.anthropic.com` when the app asks (or in Settings › Network), and choose `claude-sonnet-5-5` as the text model.

   Choosing Anthropic, not Local or custom server, makes Anthropic's catalog entry the one SurfSense reads: its 1,000,000-token window and its image input, without which opencode never shows the agent a page preview ([agent](../../architecture/agent.md#image-input)). A key for `api.anthropic.com` goes as `x-api-key` with `anthropic-version`, as Anthropic's API expects ([connections](../../architecture/connections.md)).

4. **Add the sources.** The demo uses three made for it: a short PDF report with a drawn bar chart under a "Figure 1" caption and a pricing table, a PNG logo, and kickoff notes as a Word file. The live test's generator writes them:

   ```bash
   cd surfsense_local/backend
   PYTHON_DOTENV_DISABLED=1 uv run python -c "
   import sys; from pathlib import Path; from tests.live import demo_sources as d
   out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
   (out / 'Fleet telematics assessment.pdf').write_bytes(d.assessment_report())
   (out / 'Kestrel logo.png').write_bytes(d.our_logo())
   (out / 'Kickoff notes.docx').write_bytes(d.kickoff_notes())
   " ../../references/demo-sources
   ```

   Drop the three files on the sources panel and wait until each is ready: ingest keeps the report's chart and the logo as figures ([documents](../../architecture/documents.md#figures)). Your own sources work the same way; a report with a drawn chart and a caption shows the figures best.

5. **Open a new chat thread** once Sonnet is selected. The engine is chosen when a thread opens, so a thread opened before the switch or the model is a plain chat. An agent thread shows its steps as it works.

**When something is off:**

- *The thread answers as a chat:* `electron/opencode/` is empty (`SURFSENSE_LOCAL_OPENCODE_ENABLED=0` was set when `pnpm dev` ran), the API did not get the switch, or the thread was opened before Sonnet was selected.
- *"Word pages are drawn by the SurfSense desktop app, which is not running":* Electron serves Word previews only when it found a staged opencode at boot; restart `pnpm dev` without `SURFSENSE_LOCAL_OPENCODE_ENABLED=0`.
- *The agent says it cannot see the previews:* the connection was saved as Local or custom server, so the catalog does not say the model reads images. Recreate it with Anthropic as the provider.
- *A `403` naming `api.anthropic.com`:* allow the host in Settings › Network.

## Live tests

[`surfsense_local/backend/tests/live/`](../../../surfsense_local/backend/tests/live/) runs the real path against Claude Sonnet 5.5 unless told otherwise: Anthropic's OpenAI-compatible API, SurfSense's model endpoint, the staged opencode, the tool endpoint, Studio's job and the runner. Every live test skips unless `SURFSENSE_LIVE_TESTS=1` and the chosen provider's key are both set, so CI and ordinary runs never call a paid model; the proxy, ledger, run folder, Word printer and the readers the cases check files with have unit tests that run without them.

| Case | File | Passes when | Cost of a run, 4 Oct 2026 |
|---|---|---|---|
| Smoke | `test_smoke.py` | one turn calls `surfsense_search_sources` and the answer cites a passage | about $0.03 |
| Images reach the model | `test_images_reach_the_model.py` | the agent renders a one-page PDF with a coloured shape and a word, the page reaches the model as the image the render attached, and the agent describes it correctly | about $0.09 |
| Demo flow | `test_demo_flow.py` | the three demo turns below on the generated sources make two Word versions and a PDF (a failed render keeps its number, so a document can start at v2), the edit holds a timeline table, a chart and the logo, and in each turn every page of the last version rendered reached the model | about $1.50 |
| PDF brief | `test_pdf_brief.py` | a client brief asked for as a PDF is a PDF, and the answer does not claim no format was named; "make it fit on one page and bold the totals" then gives one page with the 39,800 total in bold | about $0.34 |
| Spreadsheet report | `test_spreadsheet_report.py` | a Word report draws bars of every year's revenue from an `.xlsx`; "switch the chart to a line chart and add a short trend paragraph" then draws the same figures as a line, as a new picture, beside a new paragraph | about $0.80 |
| Memo restructure | `test_memo_restructure.py` | a Word memo has three sections; "merge sections 2 and 3, add a summary table at the top and number the headings" then puts a table above two sections, Background first, with every section heading numbered | about $0.70 |
| Figure swap | `test_figure_swap.py` | from a PDF report holding a photo and a labelled bar chart, a Word summary places the chart, not the photo; "replace it with your own chart of the same numbers" then drops it for a new picture whose script holds all six values, which the report has only as bar labels | about $0.30 |
| Board pack | `test_board_pack.py` | "make me something I can send to the board" from two notes and a `.docx` risk register makes a Word file or a PDF without asking, and the answer names the format and what it assumed; "add a short 'Decisions needed' section at the end" then ends on that heading | about $0.48 |
| Office conversion | `test_office_conversion.py` | with Office support on through the installed LibreOffice ([`installed_office.py`](../../../surfsense_local/backend/tests/installed_office.py), skipped without one), a Word summary of a catering quote is converted with `surfsense_convert_document` into a new PDF with pages, every page of which reached the agent; then a workbook of the line items is recalculated by LibreOffice and a formula saves the quote's total, which the source never states | about $0.20 |
| Contract redline | `test_contract_redline.py` | "change the payment term from 60 to 30 days, tighten the liability cap from 24 to 12 months of fees, and add a comment explaining why" on the user's own `.docx` agreement makes a revised copy derived from it whose Word file holds tracked insertions and deletions by SurfSense only and a SurfSense comment; its Clean download (accept all) reads 30 days and 12 months, Studio's reject-all version reads exactly as the source, and the source's bytes on disk are unchanged | about $0.07 on OpenRouter, 6 Oct 2026 |
| Budget revision | `test_budget_revision.py` | "raise the Marketing line by 10% and fix the total" on the user's own `.xlsx` budget, whose total leaves out a line and which holds a bar chart, makes a revised copy whose chart part is the source's byte for byte, whose Marketing cell works out to 52,800 and whose total to the sum of every line (as a value or a formula), with the other lines and the source's bytes unchanged | about $0.07 on OpenRouter, 6 Oct 2026 |
| PDF merge and form | `test_pdf_merge_and_form.py` | one turn asks to merge two PDF reports under a DRAFT watermark and to fill a PDF form with given details: a PDF made by `surfsense_pdf_pages` or `surfsense_pdf_stamp` holds the first report's pages then the second's, each with DRAFT; a copy filled by `surfsense_pdf_form` keeps its fields and holds every value, the date in any common spelling; the three uploads are byte for byte as they were | about $0.11 on OpenRouter, 6 Oct 2026 |
| Sales targets | `test_sales_targets.py` | "which regions missed their sales target last quarter, and by how much?" over a CSV of 347 orders and an `.xlsx` of quarterly targets runs `surfsense_analyze_data` and names each region that missed with its shortfall to within 1%, computed by the test from the same rows; "put that in a short Word report with a bar chart of each region's shortfall" then makes a Word file that names an analysis chart in its images and holds that chart's PNG byte for byte | about $0.18 on OpenRouter, 6 Oct 2026 |

The cases after the demo take one or two turns on sources the test writes, and read what the agent made the way a person would check it: [`word_file.py`](../../../surfsense_local/backend/tests/live/word_file.py) for a Word file's headings, tables and pictures, [`pdf_file.py`](../../../surfsense_local/backend/tests/live/pdf_file.py) for a PDF's pages, bold text and headings. With [`turn_renders.py`](../../../surfsense_local/backend/tests/live/turn_renders.py) they also check that the edit is the next version of the same document (same root and format, a higher number), and that in each turn every page preview of the last version it rendered reached the agent: sent inline with the render's result, matched by the exact JPEG in a request that came back 200, or opened with `read`. The demo checks the same pages in each of its three turns. The PDF tools keep their results as new artifacts, not versions, so the PDF case finds them by the `Made artifact <id>` line of each tool's result, and the run folder keeps every such file and each analysis run's tables and charts beside the versions.

The two revision cases take one turn on the user's own file and check the revised copy with [`revised_files.py`](../../../surfsense_local/backend/tests/live/revised_files.py), which reads a Word file's tracked changes and comments by author and works out a workbook cell from its value or a simple formula, written apart from the engines. [`revised_versions.py`](../../../surfsense_local/backend/tests/live/revised_versions.py) finds the copy a turn made, fetches its downloads, asks Studio for its reject-all version, and reads the source's file on disk. In the first budget run the agent guessed the cells from the source's text, which shows no sheet names or cell addresses: it sent `Sheet1!B5` and `B9`, one row low. The sheet name was refused, and its second call guessed the rows right. A workbook whose sheet is called `Sheet1` would have taken that edit on the wrong cells, so the case checks that every other line is unchanged.

The costs come from the usage Anthropic reported for a passing run, once the documents skill asked the agent to open every page and to look again after each fix. That self-check is most of the cost: page images stay in the model's context and nothing is cached, so the demo went from $0.71 to $1.50 (13 requests to 19) when the skill began asking for it.

**Running them.** They need the staged opencode (step 1 above), the embedding model and parser pack, and the backend synced. Word previews come from [`word_printer.py`](../../../surfsense_local/backend/tests/live/word_printer.py), a LibreOffice stand-in for Electron behind the same snapshot routes, so their layout is LibreOffice's, not docx-preview's; without LibreOffice, Word versions report no previews and the cases still run. The stand-in sends the snapshot key the test sets on the API, as any other stand-in for Electron must (`SURFSENSE_LOCAL_DOCX_SNAPSHOT_KEY`).

On Windows, where the key lives in the user's environment, load it into the one command and never print it:

```bash
cd surfsense_local/backend
ANTHROPIC_API_KEY="$(powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')" | tr -d '\r')" \
  PYTHON_DOTENV_DISABLED=1 SURFSENSE_LIVE_TESTS=1 uv run pytest tests/live -m live -q
```

To run one case alone, give its file in place of `tests/live`, as in `uv run pytest tests/live/test_pdf_brief.py -m live -q` with the same environment.

**Another model.** [`live_model.py`](../../../surfsense_local/backend/tests/live/live_model.py) reads the choice from the environment, so the [model ladder](05-model-ladder-and-evals.md) runs the same cases unchanged:

| Variable | Default | Effect |
|---|---|---|
| `SURFSENSE_LIVE_MODEL` | `claude-sonnet-5-5` | the model id the connection selects, as its provider names it (`anthropic/claude-haiku-4.5` on OpenRouter) |
| `SURFSENSE_LIVE_PROVIDER` | `anthropic` | `anthropic` (key `ANTHROPIC_API_KEY`) or `openrouter` (key `OPENROUTER_API_KEY`); the connection names the manifest's provider id, so the app reads the model's row and declares image input as it would for a user |
| `SURFSENSE_LIVE_STOP_DOLLARS` | `45` | the ledger total at which runs and requests are refused |
| `SURFSENSE_LIVE_RUNS_DIR` | `references/live-runs` | where run folders and `spend.json` go, so a sweep keeps its own budget; give each runner working at the same time its own, since the ledger is locked only within one process |

```bash
cd surfsense_local/backend
ANTHROPIC_API_KEY="$(powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')" | tr -d '\r')" \
  PYTHON_DOTENV_DISABLED=1 SURFSENSE_LIVE_TESTS=1 SURFSENSE_LIVE_MODEL=claude-haiku-4-5 \
  SURFSENSE_LIVE_RUNS_DIR=../../references/live-runs/ladder SURFSENSE_LIVE_STOP_DOLLARS=400 \
  uv run pytest tests/live/test_smoke.py -m live -q
```

For OpenRouter, load `OPENROUTER_API_KEY` the same way in place of `ANTHROPIC_API_KEY`, set `SURFSENSE_LIVE_PROVIDER=openrouter`, and name the model as OpenRouter does (`anthropic/claude-haiku-4.5`, `qwen/qwen3.8-27b`). A model the catalog lists without image input gets no page previews, so the cases check that it rendered and skip their preview checks (`sees_pages` in [`turn_renders.py`](../../../surfsense_local/backend/tests/live/turn_renders.py)). Leaving all four variables out runs Sonnet 5.5 on Anthropic into `references/live-runs` with the $45 stop, as before the ladder. Long cases take several minutes each; run one case at a time.

Claude is priced from [`model_prices.py`](../../../surfsense_local/backend/tests/live/model_prices.py), Anthropic's [pricing page](https://platform.claude.com/docs/en/about-claude/pricing) as read on 4 Oct 2026, per million tokens of input / output / cache read / 5-minute cache write: Sonnet 5.5 $2 / $10 / $0.20 / $2.50, Opus 5.5 $4 / $20 / $0.20 / $5, Haiku 4.5 $1 / $5 / $0.10 / $1.25. A Claude model missing from that table stops the run. The first results, all eight cases on Opus 5.5 and Haiku 4.5 beside Sonnet 5.5 and on eight open models through OpenRouter, are in [08](08-model-ladder-results.md). An OpenRouter model is priced from OpenRouter's public `https://openrouter.ai/api/v1/models` when the run starts; a model it lists without a cache price has its cached tokens charged as input.

**The key never reaches a file.** The connection the tests create points at a recording proxy on loopback ([`recording_proxy.py`](../../../surfsense_local/backend/tests/live/recording_proxy.py)) and stores a placeholder; the proxy adds the real key in memory, with the same headers the app sends that provider, and forwards to the base URL the app's catalog gives it (`https://api.anthropic.com/v1/` or `https://openrouter.ai/api/v1/`). It records each request's usage, asking the stream to include it, and redacts the key from everything it writes.

**The budget.** [`spend_ledger.py`](../../../surfsense_local/backend/tests/live/spend_ledger.py) keeps the cumulative dollars in `references/live-runs/spend.json`, which git ignores, with each model's tokens, dollars and prices, and each case's under it; each call is priced at its own model's rates as it is charged, so the total is right across models. The ledger from before the ladder, Sonnet's alone, is read with its total as written and converted on the next charge. The cap set for the first night of runs is $50: every case checks the ledger before it starts and refuses at $45 or more (or `SURFSENSE_LIVE_STOP_DOLLARS`), and the proxy refuses a single request whose worst case would reach it. A reply that ends without reporting its usage is charged its worst case, the whole request at the dearest input rate plus the full output cap, and marked estimated, so the ledger can read above the bill. When Anthropic dropped one request in a spreadsheet-report run and one in a memo-restructure run, the ledger charged those runs $1.44 and $2.20 for about $0.81 and $0.69 of the usage Anthropic reported. On 4 Oct 2026 the ledger stood at $13.78 of the $50. Prompt caching is reported as 0 through Anthropic's OpenAI-compatible API, so each request bills its whole context.

**What a run leaves.** Each run writes `references/live-runs/<UTC time>-<case>-<provider>-<model>/`: `transcript.md` (messages, tool calls and results, redacted), `frames.json` (the thread's frames), `model-requests.json` (each request's usage, whether it carried an image, where it went with the headers it carried, key redacted, and for OpenRouter which provider served it and what it billed), the generated `.docx` and `.pdf` of every version with its script, the sources, the preview PNGs, `cost.json` (with the model, provider and prices, and `reported_dollars`, OpenRouter's own bill when every request carried one) and `result.json` (with the model, provider and whether the app declared image input). Open these to see what the agent did and made.

## The demo video

Record from the dev build above. One run of the three turns costs about $1.50 with Sonnet 5.5 and takes a little over three minutes, most of it the model.

**Before recording:** the three sources ready in the sources panel; Sonnet selected; Studio open in the right rail with an empty artifact list; a fresh agent thread. Keep the window wide enough that the chat and Studio show side by side. Do not reload the thread while recording: a `[n]` the agent wrote for a file it read without searching streams but is dropped from the saved reply ([agent](../../architecture/agent.md#known-gaps)).

1. **"Draft a two-page client proposal from these sources as a Word document, with a pricing table."**
   - Show the steps as they stream: "Searched the sources for …", files read, "Looked for images in 3 sources" when it places a source image, then "Ran the document script for *Client proposal*", which turns into **"Created *Client proposal* v1"**.
   - The agent then opens its page previews with `read`, shown as steps reading `outputs/previews/<id>-v1/page-1.png`. Say what this is: it looks at the pages it made and fixes what looks wrong, so a run can make v2 itself before answering.
   - Click "Created *Client proposal* v1": the Word document opens in Studio's viewer, and the list shows one row with a "v1" badge.
2. **"Make the executive summary shorter, add a timeline table and a bar chart of the yearly costs, and put our logo on the cover."**
   - Show "Read the script behind a document": it changes its own script, not the file.
   - "Updated *Client proposal* to v2" appears, and v2 opens itself in the viewer.
   - Show the reply's line on what it assumed, such as the top of the first page as the cover, or the report's Figure 1 placed with its caption for the yearly costs.
   - Open the **version switcher** in the viewer and go v1 → v2 and back: the shorter summary, the new timeline table, the chart and the logo. This is the "what changed" view of the slice.
3. **"Now a PDF version for the client."**
   - "Created *Client proposal* v1" again: a PDF is a new document, so it starts at v1. It opens in the PDF viewer.
   - The Studio list now has two rows, the Word document at v2 and the PDF at v1. Download one to show it is a real file.

The agent often re-renders after checking its previews, so the version numbers above can run higher: in the 4 Oct 2026 live run the first turn ended on v2 and the second on v4. The switcher shows every version, which is worth showing rather than cutting. If a script fails, the step shows the error and the agent fixes it and renders again, and after a third failure it stops and says what failed.
