# Create and edit: running the slice from a dev build

How to run the [create-and-edit slice](07-create-and-edit-mvp.md) on `dev_mod` with Claude Sonnet, how the live tests spend real money on it, and the script for the demo video. The agent is off in every build until a model passes the agent test, so this needs two developer switches ([agent](../../architecture/agent.md)).

## Run it

**Before the first run:** the usual desktop setup from [`surfsense_local/`](../../../surfsense_local/)'s README (`uv sync` in `backend/`, `pnpm install` in `frontend/` and `electron/`), and an Anthropic API key of your own.

1. **Stage opencode and start the app with both switches**, in one shell. `pnpm dev` runs `predev`, which runs `build:opencode` again and removes the staged opencode when the first switch is not set, so set it where `pnpm dev` runs too. The API inherits Electron's environment, which is where the second switch must be.

   ```bash
   cd surfsense_local/electron
   export SURFSENSE_LOCAL_OPENCODE_ENABLED=1        # stage opencode 1.18.34 and ripgrep
   export SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1   # let a model off the empty tested list run the agent
   pnpm build:opencode
   pnpm dev
   ```

   In PowerShell, set them with `$env:SURFSENSE_LOCAL_OPENCODE_ENABLED = "1"` and `$env:SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS = "1"`. `electron/opencode/` then holds `opencode` and `rg`. `predev` also stages the embedding model and Docling's parser pack, which ingest and the figures need.

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

- *The thread answers as a chat:* `electron/opencode/` is empty (the first switch was not set when `pnpm dev` ran), the API did not get the second switch, or the thread was opened before Sonnet was selected.
- *"Word pages are drawn by the SurfSense desktop app, which is not running":* Electron serves Word previews only when it staged opencode at boot; restart `pnpm dev` with the switch.
- *The agent says it cannot see the previews:* the connection was saved as Local or custom server, so the catalog does not say the model reads images. Recreate it with Anthropic as the provider.
- *A `403` naming `api.anthropic.com`:* allow the host in Settings › Network.

## Live tests

[`surfsense_local/backend/tests/live/`](../../../surfsense_local/backend/tests/live/) runs the real path against Claude Sonnet 5.5: Anthropic's OpenAI-compatible API, SurfSense's model endpoint, the staged opencode, the tool endpoint, Studio's job and the runner. Every live test skips unless `SURFSENSE_LIVE_TESTS=1` and `ANTHROPIC_API_KEY` are both set, so CI and ordinary runs never call a paid model; the proxy, ledger, run folder and Word printer have unit tests that run without them.

| Case | File | Passes when | Cost of a run, 4 Oct 2026 |
|---|---|---|---|
| Smoke | `test_smoke.py` | one turn calls `surfsense_search_sources` and the answer cites a passage | about $0.03 |
| Images reach the model | `test_images_reach_the_model.py` | the agent renders a one-page PDF with a coloured shape and a word, opens its preview with `read`, and describes it correctly | about $0.09 |
| Demo flow | `test_demo_flow.py` | the three demo turns below on the generated sources make Word v1 and v2 and a PDF v1, the edit holds a timeline table, a chart and the logo, and the agent opened its previews | about $0.71 |

**Running them.** They need the staged opencode (step 1 above), the embedding model and parser pack, and the backend synced. Word previews come from [`word_printer.py`](../../../surfsense_local/backend/tests/live/word_printer.py), a LibreOffice stand-in for Electron behind the same snapshot routes, so their layout is LibreOffice's, not docx-preview's; without LibreOffice, Word versions report no previews and the cases still run. The stand-in sends the snapshot key the test sets on the API, as any other stand-in for Electron must (`SURFSENSE_LOCAL_DOCX_SNAPSHOT_KEY`).

On Windows, where the key lives in the user's environment, load it into the one command and never print it:

```bash
cd surfsense_local/backend
ANTHROPIC_API_KEY="$(powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')" | tr -d '\r')" \
  PYTHON_DOTENV_DISABLED=1 SURFSENSE_LIVE_TESTS=1 uv run pytest tests/live -m live -q
```

Add `-k smoke`, `-k images` or `-k demo` to run one case.

**The key never reaches a file.** The connection the tests create points at a recording proxy on loopback ([`recording_proxy.py`](../../../surfsense_local/backend/tests/live/recording_proxy.py)) and stores a placeholder; the proxy adds the real key in memory, with the same headers the app sends Anthropic, and forwards to `https://api.anthropic.com/v1/`. It records each request's usage, asking the stream to include it, and redacts the key from everything it writes.

**The budget.** [`spend_ledger.py`](../../../surfsense_local/backend/tests/live/spend_ledger.py) keeps the cumulative tokens and dollars in `references/live-runs/spend.json`, which git ignores, at Sonnet 5.5's prices per million tokens: $2 input, $10 output, $0.20 cache read, $2.50 cache write. The budget for these runs is $50: every case checks the ledger before it starts and refuses at $45 or more, and the proxy refuses a single request whose worst case would reach $45. A reply that ends without reporting its usage is charged its worst case and marked estimated. On 4 Oct 2026 the ledger stood at $5.68. Prompt caching is reported as 0 through Anthropic's OpenAI-compatible API, so each request bills its whole context.

**What a run leaves.** Each run writes `references/live-runs/<UTC time>-<case>/`: `transcript.md` (messages, tool calls and results, redacted), `frames.json` (the thread's frames), `model-requests.json` (each request's usage and whether it carried an image), the generated `.docx` and `.pdf` of every version with its script, the sources, the preview PNGs, `cost.json` and `result.json`. Open these to see what the agent did and made.

## The demo video

Record from the dev build above. One run of the three turns costs about $0.70 with Sonnet 5.5 and takes about two and a half minutes, most of it the model.

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

If the agent re-renders after checking its previews, the Word document reaches v3 within a turn; the switcher shows every version, which is worth showing rather than cutting. If a script fails, the step shows the error and the agent fixes it and renders again, and after a third failure it stops and says what failed.
