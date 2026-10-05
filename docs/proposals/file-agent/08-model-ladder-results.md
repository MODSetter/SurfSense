# Model ladder: first results

The eight live cases of the [create-and-edit slice](07-create-and-edit-mvp.md) were run on Claude Opus 5.5 and Claude Haiku 4.5, beside the Sonnet 5.5 runs that wrote them. Opus passed all eight on the first try. Haiku passed five. Its three failures had one cause: on the first turn it did not open every page preview of the document it ended on, which the skill asks for. The edit turns of those three cases were therefore never reached. This is the first measured row toward [05](05-model-ladder-and-evals.md)'s matrix. In 05's terms it is screening: one run per cell in the dev setup, not a committed row. Eight open models then ran the same cases through OpenRouter ([below](#open-models-through-openrouter)). Kimi K3 and Qwen3.8-27B passed all eight. The text-only GLM-5.3 and DeepSeek V4 Pro failed only the case that needs image input. From Gemma 4 31B and Qwen3.6-35B-A3B (about 3B active) down, the models stopped checking their pages, invented drawing APIs and lost track of versions, and no 8–14B model passed the document cases. With the page previews then sent inline with the render's result ([below](#page-previews-inline)), every page drawn reached the model in all 58 runs, and the cells that had failed on it now fail, when they do, at later checks.

## What was run

- **When.** 4 Oct 2026, Pacific time. Sonnet ran from 06:38 to 11:22, Opus from 16:27 to 16:53 and Haiku from 16:54 to 17:08. The Haiku run folders carry 5 Oct in their UTC stamps.
- **Harness.** [`tests/live/`](../../../surfsense_local/backend/tests/live/), which runs the real path: SurfSense's model endpoint, the staged opencode 1.18.34, the tool endpoint, Studio's job and the script runner. Word previews come from the LibreOffice stand-in. Opus and Haiku ran on `dev_mod` at `6fd13c530` with the ladder's harness changes, which pick the model and provider from the environment ([07-dev-setup](07-dev-setup.md#live-tests)). The cases and their checks were the same for both models, except one demo check, loosened between the Opus and Haiku demo runs: it used to require Word v1 and v2 and a PDF v1, and now takes any two ready Word versions and a PDF, since a failed render keeps its version number. Haiku's demo made Word v1 to v3 and a PDF v1, which passes either check.
- **Sonnet's column is not a clean sweep.** Its runs were made while the cases were being written, on code from before `b61d458cb` (render results say whether they created the document, a reply's steps kept as paragraphs, long scripts read in pages) and `6fd13c530` (a turn kept to its ticked sources, a line added to the agent prompt). The matrix uses each case's last passing run. Its earlier failures that day came while the app's image input and the cases themselves were being fixed, apart from one board-pack run, listed under the failures.
- **Provider.** Anthropic only, through its OpenAI-compatible API at `https://api.anthropic.com/v1`, as the app calls it today. The app declared image input for Opus and Haiku (`reads_images: true` in every `result.json`), and Sonnet's passing images run shows it did for Sonnet too.
- **Runs.** One per cell (n=1). A failure caused by the provider would have been retried. None was needed: opencode retried the dropped requests listed below inside their runs, and those runs passed. Model failures were not retried.
- **Cost.** In the matrix, cost is the ledger's charge for the run. A request cut off before reporting its usage is charged its worst case, so where a run had one, the usage Anthropic reported is given in brackets. Prices are Anthropic's per million tokens of input / output: Sonnet 5.5 $2 / $10, Opus 5.5 $4 / $20, Haiku 4.5 $1 / $5. Minutes are wall time, from the run folder's stamp to its `result.json`.

## The matrix

Each cell gives the outcome, attempts, cost and minutes.

| Case | Sonnet 5.5 | Opus 5.5 | Haiku 4.5 |
|---|---|---|---|
| Smoke | pass · see note · $0.03 · 0.2 | pass · 1 · $0.06 · 0.3 | pass · 1 · $0.01 · 0.3 |
| Images reach the model | pass · see note · $0.09 · 0.4 | pass · 1 · $0.18 · 0.4 | pass · 1 · $0.05 · 0.4 |
| Demo flow (3 turns) | pass · see note · $1.50 · 3.6 | pass · 1 · $2.97 ($2.02) · 4.3 | pass · 1 · $0.40 · 2.7 |
| PDF brief | pass · see note · $0.34 · 1.2 | pass · 1 · $0.70 · 2.0 | pass · 1 · $0.17 · 1.5 |
| Spreadsheet report | pass · see note · $1.44 ($0.81) · 2.4 | pass · 1 · $1.23 · 2.5 | **fail** · 1 · $0.07 · 1.4 |
| Memo restructure | pass · see note · $2.20 ($0.69) · 2.0 | pass · 1 · $1.58 · 2.9 | **fail** · 1 · $0.05 · 1.0 |
| Figure swap | pass · see note · $0.30 · 1.0 | pass · 1 · $0.56 · 1.6 | pass · 1 · $0.31 ($0.12) · 1.9 |
| Board pack | pass · see note · $0.49 · 1.5 | pass · 1 · $0.69 · 1.8 | **fail** · 1 · $0.06 · 1.3 |
| **All eight** | 8 of 8 · $6.39 ($4.25) · 12.3 | 8 of 8 · $7.97 ($7.01) · 15.9 | 5 of 8 · $1.11 ($0.93) · 10.5 |

**Sonnet's attempts that day.** Smoke: 3 runs, and the failure made no model request. Images: 1 failure from before the app declared image input, a diagnostic run, then a pass. Demo: 6 failed runs, 3 of them diagnostics, while image input and the checks were fixed, then 3 passes. PDF brief: 3 passes. Spreadsheet report: 2 passes. Memo restructure and figure swap: 1 pass each. Board pack: 1 failure (below), then 2 passes.

Haiku's three failures stopped at turn 1, so their time and cost cover one turn, not two. Haiku's totals cannot be set against the others' for that reason. On the five cases it passed it cost about a fifth of Opus by reported usage ($0.76 against $3.52) and took 6.8 minutes against 8.7.

Model requests per run: Sonnet 2, 4, 19, 8, 15, 15, 10, 11; Opus 2, 4, 16, 9, 12, 15, 9, 9; Haiku 2, 5, 17, 11, 7, 5, 12, 5, in the matrix's order. Ready document versions per run: Sonnet 0, 1, 5, 2, 5, 4, 2, 3; Opus 0, 1, 4, 2, 3, 4, 2, 2; Haiku 0, 1, 4, 2, 1, 1, 2, 1.

## Failures

Run folders are under `references/live-runs/` (Sonnet) and `references/live-runs/ladder/` (Opus and Haiku), which git ignores. Each cause carries one of 05's triage labels ([05 section 5](05-model-ladder-and-evals.md#5-the-eval-matrix)).

- **Haiku, spreadsheet report: `model`.** Turn 1 drew the right revenue figures as bars in a two-page Word report. It then listed the previews folder, opened page 1 only and answered. `20261005T000728Z-spreadsheet-report-anthropic-claude-haiku-4-5`
- **Haiku, memo restructure: `model`.** Turn 1 made a sound two-page memo. The render result listed both previews "to check with `read`", and it opened neither. `20261005T000043Z-memo-restructure-anthropic-claude-haiku-4-5`
- **Haiku, board pack: `model`.** Turn 1 made a two-page PDF in one render and opened neither page. Its answer named the format but not what it assumed, so the next check would probably have failed as well. `20261005T000551Z-board-pack-anthropic-claude-haiku-4-5`
- **Sonnet, board pack (an earlier run): `model`.** The answer named the format but did not say what it assumed. It is not recorded whether the case or the skill changed before the two passes that followed. `20261004T180816Z-board-pack`

Haiku's memo case ran twice more in the same folder, outside this sweep: the Qwen3.8-27B runner's script in the shared scratchpad had been overwritten with the Haiku runner's, so two of its launches ran Haiku (launched 00:01:50 and 00:12:05 UTC; the sweep's own run was launched at 00:00:37). `20261005T000155Z-memo-restructure-anthropic-claude-haiku-4-5` failed the same way as above. `20261005T001209Z-memo-restructure-anthropic-claude-haiku-4-5` opened its previews, reached turn 2 and failed there: it put the new summary table under an unnumbered "Summary" heading above "1. Background" and "2. Options and Recommendation". Whether a summary heading must be numbered is the case's call as much as the model's. With those two runs, Haiku's memo case stands at 0 of 3.

**Provider drops.** One request in each of four runs got no reply. Sonnet's spreadsheet and memo runs and Opus's demo got "Server disconnected without sending a response". Haiku's figure swap got an SSL bad-record-MAC read error. opencode retried each request and every one of those runs passed. The worst-case charge for a drop is the full output cap plus the prompt at the cache-write rate. Opus's cap is 32,000 tokens, so its one drop was charged $0.95.

## What the results say

**Document scripts.** All three models write python-docx and ReportLab scripts that run. Across the Opus runs no script failed. Across the Haiku runs one failed: a wrong ReportLab polygon call in the images case, which Haiku fixed on its next render. Neither Opus nor Haiku made a malformed tool call. Both used `skill`, `surfsense_list_images` and `surfsense_read_document` as the skill describes, and Opus often sent independent calls together. Sonnet's runs were not read for this.

**Images.** All three see their own page previews. The images case passed on each, with the shape and the word described correctly. All three placed the right source figure: the chart, not the photo, in the figure swap, and the logo and chart in the demo. Opus and Haiku both redrew the swapped chart from the bar labels they read off a figure. Opus took the values from the preview of its own v1, without opening the source image. Opus also chose to leave out the assessment's yearly-cost chart because its totals did not match the agreed prices, and said why.

**Multi-turn editing.** Sonnet and Opus passed every edit turn. Haiku passed the edits it reached: three demo turns, the one-page bold-totals edit of the PDF brief and the chart swap. Its memo, spreadsheet and board-pack edits are untested, apart from the extra memo run above.

**The self-check separates them.** Opus opened every page of every version it rendered, found a fault in 4 of its 13 document turns and fixed it with a new render. The faults were a table split across pages, columns too wide, equal-width columns and a stranded recommendation, which it fixed with `keep_with_next`. Haiku never rendered again after looking at a preview. It skipped previews in 3 of the 6 first turns that ended on a multi-page document, and in the cases it passed, looking was all it did. A model that skips the look ships what the first render made. That is most of the gap between them here, and the documents Haiku made were sound regardless.

**Judgement.** Opus said what it assumed and made sensible calls without asking. In the PDF brief the brief was already one page and the total already bold, so it bolded the totals in the note and said so. In the board pack it chose a PDF without asking and gave its reason. When v1 already ended on "Decisions requested", it renamed that section instead of adding a second one.

**Speed and cost.** Opus took the longest on most cases and cost the most. By reported usage it used between about two thirds of Sonnet's tokens (demo, board pack) and a little more (memo), at twice the price per token. Haiku was faster than Opus on the demo and the PDF brief and slower on the figure swap; Sonnet's runs, on the older code, were the quickest on most cases. Haiku cost about a fifth of Opus on the cases both passed. Every run reported 0 cache reads, so each request paid for its whole context. That comes from the compatibility layer, not from the models.

**For [07](07-create-and-edit-mvp.md#after-the-slice)'s "strong model" rule.** On this evidence Opus 5.5 and Sonnet 5.5 can take the script path with the self-check as it is. Haiku 4.5 can write the documents but does not reliably check them. With n=1, that is a lead to follow up, not a verdict.

## What to change next

These are what the failures point to. None was made here: the ladder measures, and a change to the skill, the tools or the prompt is a separate task, followed by a re-run of Haiku's three failed cases on the same column (05's triage rule).

- **Tool: make the look part of the render.** `surfsense_render_document` returns "Page previews to check with `read`:" and a list ([`render_document.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/render_document.py)). Haiku read that and skipped it. Two options: return the page images in the tool result itself, if opencode passes images through MCP results (to be checked), or end the result with an instruction that names the count, such as "open all 2 pages before you answer".
- **App: notice a turn that ends unchecked.** The harness's `assert_pages_checked` knows when a turn ends with previews left unread. The app could notice the same and send the agent one follow-up asking it to look, at the cost of one more request. This holds for any model, whatever its prompt.
- **Skill: move the check next to the render.** "Checking what you made" in [`SKILL.md`](../../../surfsense_local/backend/modules/agent/skills/surfsense-documents/SKILL.md) comes after the edit steps. A one-line "then open every page it lists" in the create and edit steps puts it where the model acts.
- **Prompt: say it once in the agent prompt.** [`agent.md`](../../../surfsense_local/backend/modules/agent/prompts/agent.md) sends Word and PDF work to the skill and the render tool, but never mentions previews.
- **Reply shape.** The one-line plan Opus writes before a re-render ("I'll keep the table together and fix the widths.") ends up at the top of its final answer, because `b61d458cb` keeps a reply's steps as paragraphs. The next paragraph usually says it again. Showing text written before a tool call as a step, not as part of the answer, would fix it.
- **Caching.** 0 cache reads on every Claude run makes each run dearer and slower than it needs to be. 05's native Anthropic path ([section 2](05-model-ladder-and-evals.md#2-serving-claude-to-opencode)) is the fix, and a re-run of this matrix on that path measures it.
- **Harness.** `SpendLedger.add` guards its read-modify-write only within one process, and every process writes the same temporary file name. Concurrent runners sharing one `spend.json` could lose a charge. Each runner should get its own `SURFSENSE_LIVE_RUNS_DIR`, or the ledger should get a file lock.

**Since these runs, the previews are inline.** The first option of the tool change is built: `surfsense_render_document` and `surfsense_source_pages` return each page drawn as an image item after their text, a 750,000-pixel JPEG at quality 80, which opencode attaches to the next request, so there is no step to skip and no path to retype. The skill and the prompt say to look at every page the result shows. The harness counts a page as checked only when that exact image reached the model in a request that came back 200 ([agent](../../architecture/agent.md#documents-the-agent-makes)). The re-run of the failed cells, with Opus and Kimi K3 as controls, is [below](#page-previews-inline).

## Open models through OpenRouter

The same eight cases then ran on eight open models through OpenRouter. Kimi K3 and Qwen3.8-27B passed all eight, as Opus did. GLM-5.3 and DeepSeek V4 Pro are text-only, and each passed every case except the figure swap, which needs the model to read a chart image. Smaller models did worse. Qwen3.6-35B-A3B passed 4 of 8, Gemma 4 31B passed 2 of the 4 it reached, Ministral 14B passed 3 of 8, and Qwen3.5-9B failed the smoke. This is screening too: one run per cell, in the dev app. The models ran on the hosts OpenRouter chose, not as GGUF files on llama.cpp.

### What was run

- **When.** 4 to 5 Oct 2026, from 16:27 to 18:18 Pacific (23:27 to 01:18 UTC). The code was the Opus and Haiku code above, plus `8463f45be`'s demo check and the text-only change described below. Each model's cases ran one at a time, and several models ran at the same time.
- **Models, by tier.**
  - Frontier open: `moonshotai/kimi-k3`, `z-ai/glm-5.3`, `deepseek/deepseek-v4-pro-0813`.
  - 27–35B: `qwen/qwen3.8-27b`, `qwen/qwen3.6-35b-a3b` (mixture of experts, about 3B parameters active per token) and `google/gemma-4-31b-it`.
  - 8–14B: `mistralai/ministral-14b-2512` and `qwen/qwen3.5-9b`.
- **Hosts.** OpenRouter, with its default routing. The app sends no provider preference and no reasoning setting. Each request went to whichever upstream OpenRouter picked, and one run often used several. 05 asks for the provider order to be pinned and fallbacks turned off for a committed row; neither was done here. `model-requests.json` records which upstream served each request (`served_by`):

  | Model | Upstreams |
  |---|---|
  | Kimi K3 | Makora, InferenceNet, Parasail, Morph |
  | GLM-5.3 | Makora, Mistral, Decart, Wafer, InferenceNet |
  | DeepSeek V4 Pro | Relace (56 of 57 requests), StreamLake |
  | Qwen3.8-27B | Wafer |
  | Qwen3.6-35B-A3B | AkashML, Parasail |
  | Gemma 4 31B | CoreWeave, ModelRun |
  | Ministral 14B | Mistral |
  | Qwen3.5-9B | Venice, SiliconFlow |

  Each host runs its own quantization and has its own speed. Kimi's hosts ran fp4, fp8 and mxfp4. A cell measures the model as those hosts served it, not as llama.cpp would run it.
- **Image input.** The harness declared image input the way the app does, from the model's row under provider `openrouter` in the remote catalog. Kimi, Qwen3.8, Qwen3.6, Gemma, Ministral and Qwen3.5-9B read images. GLM-5.3 and DeepSeek V4 Pro are text-only, and `result.json` records `reads_images: false` for them. A text-only model gets no page previews. Each render result tells it "No page previews: the selected model cannot read images", and the skill tells it to check the script and the render's text instead. The cases now do the same: they skip the preview checks for a text-only model (`sees_pages` in [`turn_renders.py`](../../../surfsense_local/backend/tests/live/turn_renders.py)). A model that reads images, Claude included, is checked as before. The images case is n/a for a text-only model.
- **The gate.** Each column ran in this order:
  1. Smoke. If the model failed it, the column stopped there, and every other case is "not run".
  2. Images, only when the catalog declares image input.
  3. Demo flow, then PDF brief. If the model failed both, the rest are "not run".
  4. Otherwise memo restructure, figure swap, board pack and spreadsheet report.

  A failed case got a second attempt only when the failure looked transient: a 5xx, a 429 or an overload, a dropped stream, or a timeout with no output. No failure looked transient. The one second attempt in the matrix followed a harness fault.
- **Cost.** The ledger charges OpenRouter's listed price for the model, read from its public model list when the run starts:

  | Model | Input | Output | Cache read |
  |---|---|---|---|
  | Kimi K3 | $0.72 | $14 | $0.70 |
  | GLM-5.3 | $1.40 | $4.40 | $0.14 |
  | DeepSeek V4 Pro | $0.85 | $5.00 | $0.70 |
  | Qwen3.8-27B | $0.425 | $2.55 | $0.085 |
  | Qwen3.6-35B-A3B | $0.15 | $1.00 | $0.05 |
  | Gemma 4 31B | $0.09 | $0.34 | $0.05 |
  | Ministral 14B | $0.20 | $0.20 | $0.02 |
  | Qwen3.5-9B | $0.10 | $0.15 | none listed |

  Prices are per million tokens. Qwen3.5-9B has no listed cache price, so its cache reads were charged as input.

  The bracketed figure in the matrices is what OpenRouter billed: its own `usage.cost`, summed over the run's requests (`reported_dollars` in `cost.json`). The ledger and the bill differ for two reasons. The upstream that served a request may charge more or less than the listing. And a request cut off before its usage arrives is charged its worst case on the ledger, while OpenRouter bills nothing for it. Each model has its own ledger, `references/live-runs/ladder-open/<model>/spend.json`. The ledgers total $6.76, and OpenRouter billed about $4.04.

### The matrices

Each cell gives the outcome, attempts, ledger cost (OpenRouter's bill in brackets) and minutes. Minutes are wall time, from the run folder's stamp to its `result.json`.

| Case | Kimi K3 | GLM-5.3 (text-only) | DeepSeek V4 Pro (text-only) |
|---|---|---|---|
| Smoke | pass · 1 · $0.01 ($0.02) · 0.3 | pass · 1 · $0.01 ($0.01) · 0.3 | pass · 1 · $0.01 ($0.003) · 0.3 |
| Images reach the model | pass · 1 · $0.03 ($0.05) · 0.4 | n/a | n/a |
| Demo flow (3 turns) | pass · 1 · $0.87 ($0.71) · 13.3 | pass · 1 · $0.25 ($0.23) · 4.6 | pass · 1 · $0.44 ($0.22) · 5.7 |
| PDF brief | pass · 1 · $0.18 ($0.20) · 2.0 | pass · 1 · $0.09 ($0.09) · 1.9 | pass · 1 · $0.10 ($0.05) · 1.4 |
| Spreadsheet report | pass · 1 · $0.14 ($0.14) · 3.0 | pass · 1 · $0.05 ($0.03) · 1.0 | pass · 1 · $0.08 ($0.03) · 1.1 |
| Memo restructure | pass · 1 · $0.13 ($0.15) · 2.3 | pass · 1 · $0.08 ($0.08) · 1.4 | pass · 1 · $0.11 ($0.05) · 1.2 |
| Figure swap | pass · 1 · $0.13 ($0.14) · 2.1 | **fail** · 1 · $0.06 ($0.05) · 1.4 | **fail** · 1 · $0.06 ($0.03) · 1.1 |
| Board pack | pass · 1 · $0.76 ($0.29) · 2.8 | pass · 1 · $0.08 ($0.07) · 1.6 | pass · 1 · $0.17 ($0.08) · 2.1 |
| **All** | 8 of 8 · $2.26 ($1.69) · 26.2 | 6 of 7 · $0.62 ($0.56) · 12.2 | 6 of 7 · $0.97 ($0.47) · 12.9 |

| Case | Qwen3.8-27B | Qwen3.6-35B-A3B | Gemma 4 31B | Ministral 14B | Qwen3.5-9B |
|---|---|---|---|---|---|
| Tier | 27–35B | 27–35B | 27–35B | 8–14B | 8–14B |
| Smoke | pass · 1 · $0.005 ($0.001) · 0.3 | pass · 1 · $0.001 ($0.001) · 0.2 | pass · 1 · $0.001 ($0.001) · 0.3 | pass · 1 · $0.001 ($0.001) · 0.4 | **fail** · 1 · $0.001 ($0.001) · 0.4 |
| Images reach the model | pass · 1 · $0.01 ($0.01) · 0.8 | pass · 1 · $0.01 ($0.01) · 0.9 | pass · 1 · $0.005 ($0.02) · 1.1 | pass · 1 · $0.005 ($0.005) · 1.1 | not run |
| Demo flow (3 turns) | pass · 2 · $0.33 ($0.17) · 10.6 | **fail** · 1 · $1.67 ($0.64) · 14.1 | **fail** · 1 · $0.008 ($0.04) · 2.8 | pass · 1 · $0.02 ($0.02) · 4.3 | not run |
| PDF brief | pass · 1 · $0.03 ($0.03) · 2.3 | pass · 1 · $0.05 ($0.05) · 3.9 | **fail** · 1 · $0.002 ($0.01) · 0.9 | **fail** · 1 · $0.003 ($0.003) · 0.7 | not run |
| Spreadsheet report | pass · 1 · $0.03 ($0.03) · 3.1 | **fail** · 1 · $0.005 ($0.005) · 0.5 | not run | **fail** · 1 · $0.002 ($0.002) · 0.8 | not run |
| Memo restructure | pass · 1 · $0.26 ($0.04) · 3.0 | pass · 1 · $0.02 ($0.02) · 1.8 | not run | **fail** · 1 · $0.002 ($0.002) · 0.8 | not run |
| Figure swap | pass · 1 · $0.02 ($0.02) · 1.8 | **fail** · 1 · $0.008 ($0.006) · 1.1 | not run | **fail** · 1 · $0.003 ($0.003) · 0.9 | not run |
| Board pack | pass · 1 · $0.04 ($0.04) · 2.3 | **fail** · 1 · $0.02 ($0.02) · 1.0 | not run | **fail** · 1 · $0.001 ($0.001) · 0.5 | not run |
| **All** | 8 of 8 · $0.72 ($0.34) · 24.2 | 4 of 8 · $1.79 ($0.75) · 23.5 | 2 of 4 run · $0.02 ($0.07) · 5.1 | 3 of 8 · $0.04 ($0.04) · 9.5 | 0 of 1 run · $0.001 ($0.001) · 0.4 |

The Qwen3.8-27B demo cell gives the passing second attempt only. The first attempt failed because of the harness and cost $0.34 ($0.12 billed). With that attempt, Qwen3.8-27B's ledger holds $1.06. Before the sweep, Qwen3.5-9B also failed the smoke twice while the OpenRouter path was being checked (`ladder-open/prove/`, $0.003).

Model requests per run, in the matrix's order:

| Model | Requests |
|---|---|
| Kimi K3 | 2, 4, 19, 10, 10, 10, 11, 13 |
| GLM-5.3 | 2, n/a, 11, 8, 8, 9, 9, 8 |
| DeepSeek V4 Pro | 2, n/a, 17, 8, 8, 9, 8, 10 |
| Qwen3.8-27B | 2, 4, 28, 9, 9, 17, 11, 10 |
| Qwen3.6-35B-A3B | 2, 12, 114, 18, 5, 13, 7, 11 |
| Gemma 4 31B | 2, 8, 11, 4 |
| Ministral 14B | 2, 11, 22, 6, 6, 4, 7, 3 |
| Qwen3.5-9B | 2 |

### Failures in the open columns

Run folders are under `references/live-runs/ladder-open/`, which git ignores. Each failure carries one of 05's triage labels, as in the Claude failures above.

- **GLM-5.3, figure swap: `model`, because it has no image input.** Turn 1 placed the chart, not the photo. Turn 2 asks for the model's own chart of the same numbers, and the numbers exist only as bar labels inside the figure. GLM tried to `read` the figure and was told it cannot read images. It would not invent the numbers and asked the user for them, so it rendered no new version. `z-ai__glm-5.3/20261005T002853Z-figure-swap-openrouter-z-ai_glm-5.3`
- **DeepSeek V4 Pro, figure swap: `model`, because it has no image input.** It failed the same way as GLM. Turn 1 picked figure 1-2 by its caption, and in turn 2 it asked the user for the numbers instead of rendering. `deepseek__deepseek-v4-pro-0813/20261005T004621Z-figure-swap-openrouter-deepseek_deepseek-v4-pro-0813`
- **Qwen3.8-27B, demo flow, attempt 1: harness.** Its first PDF render failed because it imported `ListStyle` from `reportlab.platypus`, and that failed render took version number 1. Its fixed PDF was therefore v2, and the old check, which required a PDF v1, reported that no PDF was made. `8463f45be` fixed the check, and attempt 2 passed. Failed attempt: `qwen__qwen3.8-27b/20261004T233954Z-demo-flow-openrouter-qwen_qwen3.8-27b`. Pass: `qwen__qwen3.8-27b/20261004T235057Z-demo-flow-openrouter-qwen_qwen3.8-27b`
- **Qwen3.6-35B-A3B, demo flow: `model`.** In turn 2, three renders failed. It then called `skill` 82 times in a row, each time saying it would fix the cover page, and never rendered. The context grew to the 262,144-token limit and OpenRouter returned 400, so turn 3 failed at once with "Provider returned error". Turn 1 had gone wrong too: it made 3 pages when asked for 2, and both its preview reads were refused because it retyped their paths wrongly. `qwen__qwen3.6-35b-a3b/20261005T005412Z-demo-flow-openrouter-qwen_qwen3.6-35b-a3b`
- **Qwen3.6-35B-A3B, figure swap: `model`.** The render result gave a relative preview path, and the model retyped it as an absolute one. It dropped the `$` from the temp folder name `pytest-of-$punk`, so the read was refused as outside the allowed folders. It never tried the relative path, and it told the user the document was done. `qwen__qwen3.6-35b-a3b/20261005T011451Z-figure-swap-openrouter-qwen_qwen3.6-35b-a3b`
- **Qwen3.6-35B-A3B, spreadsheet report: `model`.** It made the same path mistake. The report itself was right: a Word file with a correct revenue chart. `qwen__qwen3.6-35b-a3b/20261005T011729Z-spreadsheet-report-openrouter-qwen_qwen3.6-35b-a3b`
- **Qwen3.6-35B-A3B, board pack: `model`.** It made a Word file and checked both previews. Its answer named the format ("A board report making a Word document makes sense here") but not what it assumed, which the case checks for. It also left three helper scripts in `outputs/`. `qwen__qwen3.6-35b-a3b/20261005T011612Z-board-pack-openrouter-qwen_qwen3.6-35b-a3b`
- **Gemma 4 31B, demo flow: `model`.** In turn 2 the read result told it to render the next version with `artifact_id` 1. It rendered without one, which made a new document instead of Word v2. It also left the logo out of `images` and wrapped `add_picture` in `try/except: pass`, so the logo was silently missing, yet it told the user the logo was on the cover. The turn 3 PDF has no logo either, and it made the same claim. It never opened a preview. `google__gemma-4-31b-it/20261005T003117Z-demo-flow-openrouter-google_gemma-4-31b-it`
- **Gemma 4 31B, PDF brief: `model`.** It rendered the brief on the first try and answered without opening the page preview. `google__gemma-4-31b-it/20261005T003422Z-pdf-brief-openrouter-google_gemma-4-31b-it`
- **Ministral 14B, PDF brief, memo restructure, figure swap and spreadsheet report: `model`.** In all four it rendered a sound first version, then pointed the user to the preview folder instead of opening the pages. In the figure swap, its first script also had a newline escape that arrived as a literal `n`; it fixed that on the next render. The four folders are under `mistralai__ministral-14b-2512/`:
  - `20261005T004923Z-pdf-brief-openrouter-mistralai_ministral-14b-2512`
  - `20261005T005022Z-memo-restructure-openrouter-mistralai_ministral-14b-2512`
  - `20261005T005123Z-figure-swap-openrouter-mistralai_ministral-14b-2512`
  - `20261005T005309Z-spreadsheet-report-openrouter-mistralai_ministral-14b-2512`
- **Ministral 14B, board pack: `model`.** Asked for "something I can send to the board", it wrote a sourced summary in the chat. It never loaded the skill or rendered, and it ended by asking whether to make a memo or a deck. `mistralai__ministral-14b-2512/20261005T005228Z-board-pack-openrouter-mistralai_ministral-14b-2512`
- **Qwen3.5-9B, smoke: `model`.** It searched, got the passage labelled `[1]` and gave the right date. It never wrote the label, which the agent prompt asks for. It failed this way in 3 of 3 runs. `qwen__qwen3.5-9b/20261005T003613Z-smoke-openrouter-qwen_qwen3.5-9b`, and two more in `prove/`.

**Provider drops.** Five runs, on Kimi, Qwen3.8 and Qwen3.6, lost requests between the proxy and OpenRouter. The errors were "Server disconnected without sending a response" or an SSL bad-record-MAC read error. opencode retried each request, and no drop decided a case. All 11 of Qwen3.6's drops came during its demo loop, with more than 200K tokens of context.

### Where the document work stops

As the models got smaller, things broke in this order:

1. **The self-check goes first.** Kimi K3 and Qwen3.8-27B opened every page of every version and rendered again when they saw a fault, as Opus did. In the demo, Kimi fixed column widths, made a table's header row repeat across the page break and kept rows whole. Qwen3.8 caught a doubled colon in its PDF. Haiku skipped previews on turn 1 (see above). So did Gemma 4 31B and Ministral 14B, unless the user asked them to look. Qwen3.6-35B-A3B tried to open them but got the paths wrong. In 7 of the 14 model failures in the open columns, the check that failed was the one for unopened previews.
2. **Drawing scripts go next; Word scripts hold.** At every size, python-docx scripts ran on the first or second try. ReportLab drawing did not. Asked for a triangle, Qwen3.6 needed 9 renders, Gemma 5 and Ministral 8, and Ministral ended on a rectangle, which it admitted. Each failed render called an API that does not exist: `Canvas.triangle`, `Canvas.polygon`, `drawPolygon`, `reportlab.lib.shapes`. All three kept going past the skill's "stop after the third failed run". The frontier open models and Qwen3.8 had at most one script error per case.
3. **Then keeping a document's versions together.** Gemma never passed `artifact_id`, even when a tool result named it, so each retry or edit made a new document instead of a new version. Qwen3.6 did the same in the images case. Ministral kept the demo's versions together.
4. **Then honesty about the result.** The text-only frontier models said plainly that they could not see images, and they would not make up chart values. DeepSeek built the demo's chart from the agreed prices and said so in the caption. Gemma told the user a logo was on the cover after its script had silently dropped it. Qwen3.6 reported work as done without having seen the pages.
5. **Plain question answering goes last.** Every model down to Ministral 14B cited its passage in the smoke. Only the 9B left the label out.
6. **Tool calls stayed well-formed at every size.** Across all eight columns, one argument arrived malformed (Ministral's literal `n`), and no tool call was rejected.

Two caveats apply when reading the tiers:

- **Active parameters matter more than total size.** Qwen3.8-27B, which has no active-parameter suffix in its name, behaved like the frontier models. Qwen3.6-35B-A3B, with about 3B parameters active per token, behaved like the small tier.
- **This skill needs image input.** A text-only model cannot do the figure swap. Without previews, it also has to judge layout from the render's text alone. DeepSeek took four PDF renders in demo turn 3 to bring the PDF from three pages to two.

**Speed and cost.** Prompt caching works through OpenRouter, unlike on the Claude runs above. On DeepSeek, the demo read 322K cached tokens against 35K fresh ones. The frontier open models cost a fraction of Opus: Kimi's eight cases were $2.26 on the ledger and $1.69 billed, against $7.97 for Opus. Speed depends on the host OpenRouter picks. Kimi's demo took 13.3 minutes because all 19 requests went to Makora, at about 42 seconds each. Its other cases ran at 12 to 18 seconds a request. GLM and DeepSeek each took about 12 to 13 minutes for their seven cases. Several models spent most of a turn on a large burst of output tokens before a render; GLM's first Word render was a single request with 20,537 output tokens.

**The ledger against the bill.** The ledger is a spend stop, not an invoice, and it can be far off the bill:

- Where requests were cut off, it ran 2 to 6 times over the bill: Kimi's board pack $0.76 against $0.29, Qwen3.6's demo $1.67 against $0.64, Qwen3.8's memo $0.26 against $0.04.
- On DeepSeek it ran about twice over, because its Relace host charges less than the listing.
- On Gemma it ran about 4 times under, because its ModelRun host charges more.

To compare models, use the bracketed bill.

### The best candidate in each tier

- **Frontier open: Kimi K3.** It is the only open model here that reads images and passed all eight cases. It checked its pages the way Opus did, at under a third of Opus's cost. Its time depends on the host. GLM-5.3 is the faster and cheaper runner-up, but it is text-only. The catalog lists `z-ai/glm-5.3-flash` with image input, but it has not been tested.
- **27–35B: Qwen3.8-27B.** It passed all eight cases, the demo on its second attempt after the harness fix. It reads images and checks every page. For a committed row, it is the one to run as a GGUF on a 24–32 GB machine.
- **8–14B: none yet.** Ministral 14B did best here: it passed the smoke, the images case and the three-turn demo. But it fails the document cases the way Haiku did, by not looking at its pages, and it made no document for a vague request. Qwen3.5-9B fails the smoke. At this size, 05's `workflow` rung, where SurfSense runs the plan, render and check steps itself, is the one to measure next.

### What these failures point to

None of these changes was made here, for the same reason as above: the ladder measures and does not tune.

- **Tool: tell a text-only model the truth about images.** On a text-only model, opencode's `read` of a PNG returns "Image read successfully" and sends no image. A separate message says "Cannot read image (this model does not support image input)". GLM and DeepSeek worked out what had happened, but the first message is wrong.
- **Tool: make preview paths hard to retype.** The render result gives relative preview paths, and Qwen3.6 rewrote them as absolute paths and got them wrong. The `$` in this machine's user name (`$punk`) may make that more likely. A tool that opens a version's pages by id, or a `read` refusal that names the relative path to use, would take the retyping out.
- **Case: figure swap for text-only models.** Turn 2 cannot be done without image input. The case could be marked n/a when `reads_images` is false, like the images case.
- **Case: the demo's chart check.** Any two pictures pass it, so placing the source figure passes without drawing the requested chart. Kimi, GLM and Qwen3.8 each placed or kept the source figure.
- **Case: board pack's assumption check.** It looks for particular words. Qwen3.6 stated its format choice in other words and failed it.
- **Harness: the ledger's estimate for a cut-off request.** The estimate can charge more prompt than the model's window holds. On Qwen3.6 it charged 393K to 492K cache-write tokens on a 262K-token model. Capping the estimate at the window would bring the ledger closer to the bill.

## Page previews inline

The first tool change above was built, and the cells whose models skipped or mistyped previews ran again, with Opus and Kimi K3 as controls. In 58 runs every page the agent drew reached the model, and no preview was opened with `read`, so no page went twice. Of the 10 cells the preview check had failed above, 9 passed at least once and 17 of their 30 runs passed. Haiku's spreadsheet report passed 3 of 3 and its memo 2 of 3, Qwen3.6-35B-A3B's figure swap 3 of 3, and Ministral 14B's spreadsheet report 3 of 3. The runs that still fail stop at later checks: a wrong sum, a lost `artifact_id`, an unnumbered heading, an answer with no stated assumption. The controls held, Opus at 3 of 3 and Kimi at 7 of 8, and they took fewer requests on most cases. A model that reads images now passes the preview check whenever delivery works, so the check no longer shows that it looked with care. Haiku still never rendered again after a look.

### What changed

- **The tool.** `surfsense_render_document` and `surfsense_source_pages` return each page they draw as an image item after their text: a JPEG of at most 750,000 pixels at quality 80, about 728×1030 and about 1,000 Anthropic tokens for an A4 page. The 1000-px PNGs stay on disk for a closer look with `read`. opencode sends the images to the model in a user message right after the tool call. The result says the pages "come with this result as images, in order" and no longer lists one path per page. A model that does not read images gets none.
- **The skill and the prompt.** Both say to look at every page the result shows before answering, and to render again when one is wrong ([agent](../../architecture/agent.md#previews)).
- **The check.** A page counts as checked when the exact JPEG the render made reached the model in a request that came back 200, or when the model opened it with `read` (`pages_sent_inline` in [`turn_renders.py`](../../../surfsense_local/backend/tests/live/turn_renders.py)). The images case now requires the inline page, and still checks the description.
- **Not changed.** Images piling up in a thread have no cap: every page stays in each later request until opencode compacts the turn.

### What was run

- **When.** 4 Oct 2026, 19:46 to 21:32 Pacific (02:46 to 04:32 UTC on 5 Oct).
- **Code.** `slice/inline-previews`: `af86482f2`, which is `slice/agent-formats` with the ladder's harness, plus the inline change. The columns above ran on `dev_mod` at `6fd13c530`. This base also has decks, workbooks and templates from sources, so the skill now offers PowerPoint and Excel as well. The harness, the providers and OpenRouter's routing were as above, with one `SURFSENSE_LIVE_RUNS_DIR` per model. No code changed during the runs.
- **Cells.**

  | Model | Cases | Runs |
  |---|---|---|
  | Haiku 4.5 | spreadsheet report, memo restructure, board pack | 3 each |
  | Ministral 14B | PDF brief, memo restructure, figure swap, spreadsheet report | 3 each |
  | Qwen3.6-35B-A3B | figure swap, spreadsheet report (not the demo, whose failure was an 82-call `skill` loop) | 3 each |
  | Gemma 4 31B | smoke and images; PDF brief, demo and the four cases it never reached | 1; 3 each |
  | Kimi K3 (control) | all eight | 1 |
  | Opus 5.5 (control) | images, PDF brief, demo | 1 |

  The rule was 3 runs on any cell whose outcome changed. Every Gemma document cell changed, the PDF brief and the demo from a failure and the other four from "not run", so all six ran twice more. Smoke and images, passes before and after, ran once. Ministral's board pack, which rendered nothing, was not re-run. No failure looked transient, so none was repeated.
- **Cost.** As above, the ledger charges the listing and the bill is the provider's. The ledgers total $6.13: Opus $4.20, Haiku $0.73, Kimi $0.88, Gemma $0.16, Qwen3.6 $0.09 and Ministral $0.06. The bill was about $5.33: Opus $2.64 by reported usage, Kimi $1.09, Haiku $0.73, Gemma $0.72 (its hosts charge about 4 times the listing, as above), Qwen3.6 $0.09 and Ministral $0.06. OpenRouter's Kimi K3 listing had dropped to $0.67 input and $0.22 cache read per million, so compare Kimi by the bill. Run folders are under `references/live-runs/ladder-inline/`, which git ignores, one folder per model with its own `spend.json`.

### Before and after

The first-run column is the outcome above (n=1, except Haiku's memo, 0 of 3 with the extra runs). Cost is the bill per run, averaged over the cell's runs; on Anthropic it is the reported usage. Requests are per run, averaged and rounded.

| Model | Case | First run | Inline | Bill a run, first → inline | Requests a run, first → inline |
|---|---|---|---|---|---|
| Opus 5.5 | Images | pass | 1 of 1 | $0.18 → $0.16 | 4 → 3 |
| Opus 5.5 | PDF brief | pass | 1 of 1 | $0.70 → $1.05 | 9 → 10 |
| Opus 5.5 | Demo | pass | 1 of 1 | $2.02 → $1.42 | 16 → 10 |
| Haiku 4.5 | Spreadsheet report | fail | **3 of 3** | $0.07 → $0.11 | 7 → 8 |
| Haiku 4.5 | Memo restructure | 0 of 3 | **2 of 3** | $0.05 → $0.10 | 5 → 7 |
| Haiku 4.5 | Board pack | fail | 0 of 3 | $0.06 → $0.04 | 5 → 3 |
| Ministral 14B | PDF brief | fail | 1 of 3 | $0.003 → $0.007 | 6 → 9 |
| Ministral 14B | Spreadsheet report | fail | **3 of 3** | $0.002 → $0.005 | 6 → 9 |
| Ministral 14B | Memo restructure | fail | 1 of 3 | $0.002 → $0.006 | 4 → 9 |
| Ministral 14B | Figure swap | fail | 1 of 3 | $0.003 → $0.004 | 7 → 7 |
| Qwen3.6-35B-A3B | Figure swap | fail | **3 of 3** | $0.006 → $0.012 | 7 → 11 |
| Qwen3.6-35B-A3B | Spreadsheet report | fail | **2 of 3** | $0.005 → $0.017 | 5 → 10 |
| Gemma 4 31B | Smoke | pass | 1 of 1 | $0.001 → $0.001 | 2 → 2 |
| Gemma 4 31B | Images | pass | 1 of 1 | $0.02 → $0.05 | 8 → 11 |
| Gemma 4 31B | Demo | fail | 1 of 3 | $0.04 → $0.07 | 11 → 16 |
| Gemma 4 31B | PDF brief | fail | 1 of 3 | $0.01 → $0.04 | 4 → 8 |
| Gemma 4 31B | Memo restructure | not run | 0 of 3 | $0.03 | 8 |
| Gemma 4 31B | Figure swap | not run | 1 of 3 | $0.03 | 10 |
| Gemma 4 31B | Board pack | not run | 0 of 3 | $0.02 | 6 |
| Gemma 4 31B | Spreadsheet report | not run | 2 of 3 | $0.03 | 7 |
| Kimi K3 | Smoke | pass | 1 of 1 | $0.02 → $0.01 | 2 → 2 |
| Kimi K3 | Images | pass | 1 of 1 | $0.05 → $0.03 | 4 → 3 |
| Kimi K3 | Demo | pass | 1 of 1 | $0.71 → $0.38 | 19 → 12 |
| Kimi K3 | PDF brief | pass | 1 of 1 | $0.20 → $0.17 | 10 → 7 |
| Kimi K3 | Spreadsheet report | pass | 1 of 1 | $0.14 → $0.18 | 10 → 8 |
| Kimi K3 | Memo restructure | pass | **0 of 1** | $0.15 → $0.09 | 10 → 8 |
| Kimi K3 | Figure swap | pass | 1 of 1 | $0.14 → $0.07 | 11 → 9 |
| Kimi K3 | Board pack | pass | 1 of 1 | $0.29 → $0.17 | 13 → 9 |

**Reading the cost.**

- **Cells that failed before cost more, because they now get further.** The first Haiku, Ministral and Qwen3.6 failures stopped at turn 1, and most of these runs reach turn 2. Haiku's passing spreadsheet report cost $0.11 a run; Opus's cost $1.23 the first time.
- **Models that already looked pay less.** The pages come with the render instead of in a `read` call each, and an A4 page is about 1,000 tokens instead of the PNG's 1,890. The bill fell on 9 of the 11 control cells. Opus's demo went from 16 requests and $2.02 to 10 and $1.42, and from 4.3 to 3.3 minutes. Kimi's went from 19 requests in 13.3 minutes to 12 in 3.7, though its hosts' speed varies: its images case took 4.8 minutes for 3 requests on slow upstreams (Makora, InferenceNet).
- **Opus's PDF brief rose,** from $0.70 to $1.05, with one more request and a re-render after its first look. Its ledger shows $2.62 because 2 dropped requests were charged at worst case.
- **What the images themselves cost.** Counted at Anthropic's rate of one token per 750 pixels, images were 2% to 34% of a run's input tokens, most in the demo. Opus's demo sent up to 8 JPEGs in one request (about 9.9K tokens), and images were about 15% of its input, about $0.16 of its $1.42. The most in one request was 12, in a Gemma demo (about 15.8K tokens).

### Failures

No run failed the preview check. Every render that drew pages had them matched by exact JPEG in a request that came back 200. Each failure carries one of 05's triage labels. The folders are under the model's folder in `ladder-inline/` and start with the stamp given.

- **A wrong sum. Ministral, PDF brief, runs 1 and 3: `model`.** The table total came out as 49,800 and 36,850 EUR, not 39,800, so the check that 39,800 is bold failed. Run 1 had 4 failed renders first. `20261005T030123Z`, `20261005T031123Z`
- **A lost `artifact_id`: `model`.** The edit rendered without `artifact_id`, so it made a new document instead of the next version.
  - Ministral, memo restructure, runs 1 and 3. Run 3 lost it after 3 failed renders. `20261005T030338Z`, `20261005T031425Z`
  - Qwen3.6, spreadsheet report, run 2. Turn 2 had 5 failed renders, one started a new document, and the line chart became v2 of that one. `20261005T032145Z`
  - Gemma: PDF brief runs 1 and 2, spreadsheet report run 1, demo run 3 and figure swap run 3 (below). `20261005T032624Z`, `20261005T040354Z`, `20261005T033727Z`
- **Gemma, demo, run 3: `model`.** Turn 2 made 8 renders, 4 of which failed with FileNotFoundError on the logo. None passed `artifact_id` or listed the images, so each made a new document (artifacts 2 to 9) and Word never reached v2. The answer said the logo was on the cover. `20261005T041800Z`
- **Gemma, figure swap, runs 2 and 3: `model`.** Run 2 failed 3 renders on the chart image, because it had not listed the chart in `images` or had given a wrong path. It stopped at the third failure, as the skill asks, and gave the summary as text. Run 3 made 10 renders, each without `artifact_id` and with `images` empty, so the chart was never placed. After seeing the page it rendered again 9 times, then said plainly that it could not insert the chart. `20261005T041225Z`, `20261005T042537Z`
- **Ministral, figure swap, runs 2 and 3: `model`.** Run 2 wrote its python-docx script into the answer and never called `surfsense_render_document`, so turn 1 has no version. Run 3 placed the report's photo, not its chart. `20261005T030904Z`, `20261005T031628Z`
- **No render, a question instead. Haiku, board pack, runs 2 and 3: `model`.** Run 2, in a single request and without reading the sources, asked which sources, which format (PDF, PowerPoint, Excel or Word) and what message. Run 3 listed the sources, then asked whether to make a PDF, slides or a Word document. The case wants a document without asking. Offering a deck or a workbook comes from this base's new formats, which the first runs did not have, so the cell is not a clean comparison. `20261005T025840Z`, `20261005T030050Z`
- **No stated assumption. Haiku, board pack, run 1, and Gemma, board pack, 3 of 3: `model`, and the case's wording.** Each made a one-page PDF, Haiku after one failed render, and the page was sent inline. The answers named the format but no assumption in the words the case looks for ("assum", "I chose" and so on), the check already questioned above for Qwen3.6. Haiku `20261005T025509Z`; Gemma `20261005T033555Z`, `20261005T041344Z`, `20261005T042915Z`
- **An unnumbered heading. Memo restructure: `model`, and the case's call.**
  - Gemma, 3 of 3. v2 has an unnumbered "Executive Summary" above "1. Background" and "2. Options and Recommendation", so "number the headings" fails. `20261005T033310Z`, `20261005T041102Z`, `20261005T042358Z`
  - Kimi. v2 puts the table at the top, then an unnumbered "Summary" heading above two numbered sections, so three sections sit under the table, not two. This is the call Haiku's extra memo run above failed on, and it has nothing to do with the previews. `20261005T035730Z`
  - Haiku, run 3. v1 has a Heading 1 title, "INTERNAL MEMORANDUM", above Background, Options and Recommendation, so the case counts 4 sections, not 3. Its page was sent inline. `20261005T030003Z`
- **An empty turn. Gemma, demo, run 1: `model`, or its host.** Turn 1 loaded the skill, then its next request came back 200 from CoreWeave with 859 output tokens and no text or tool call, so the turn ended without a render. Only one Word version was ready, v2, after a failed v1 in turn 2. `20261005T032835Z`

**Reported apart.** This change cannot fix Gemma's `artifact_id`. It decided Gemma's PDF brief twice, its demo once and its spreadsheet report once, and figure swap run 3 rendered 10 separate documents. Ministral's board pack, which rendered nothing the first time, was not re-run. Haiku's board pack now shows a related mode: 2 of 3 runs rendered nothing and asked which format.

**Provider drops.** Opus's PDF brief lost two requests ("Server disconnected without sending a response" and an SSL bad-record-MAC read error). opencode retried both inside the run, which passed, and the ledger charged them at worst case ($2.62 against $1.05 reported). No transient failure decided a case. The runner's free-memory gate held one run for about 2 minutes when free memory dipped to 2.2 GB.

### What the re-run says

- **Sending the pages removes the skipped look.** The first runs' most common failure, an unopened or mistyped preview, did not happen once in 58 runs, and no page was sent twice. The cells it decided now pass or fail on the document itself.
- **The failures that remain are the model's, past the look.** They are the kinds the open columns [found](#where-the-document-work-stops) further down the tiers, plus arithmetic: a wrong sum, a lost `artifact_id`, the wrong figure, a script pasted into the chat, images not listed. A page in front of the model fixes none of these.
- **Passing the check no longer shows a careful look.** Re-renders after a look are the remaining signal. Opus re-rendered twice (PDF brief and demo, turn 1), Kimi once (board pack), Ministral once (a memo turn 2) and Qwen3.6 once (spreadsheet run 2, among failed renders). Gemma re-rendered 15 times; the 9 in figure swap run 3 were futile, because `images` was never set. Haiku re-rendered 0 times in 9 runs. The pages now reach Haiku, and it still ships what its first render made.
- **The case wording now decides more runs than the previews.** The memo's unnumbered summary heading failed Gemma 3 of 3, Kimi and, in another form, Haiku. The board pack's assumption phrase failed Haiku once and Gemma 3 of 3. Whether a summary heading must be numbered, and what counts as stating an assumption, are the cases' calls to settle before the next sweep.
- **For the tiers.** Haiku 4.5 passes the edit turns it never reached the first time (spreadsheet 3 of 3, memo 2 of 3), at about a tenth of Opus's cost, but still does not revise after looking. Qwen3.6-35B-A3B passes the two cells it had failed on paths (5 of 6 runs). Ministral 14B passes the spreadsheet report every time and the other three cells once in three, so the 8–14B tier still has no reliable candidate. Gemma 4 31B passes 5 of 18 document runs, held back by `artifact_id`.
- **Image cost is modest at this length.** A run's images were at most a third of its input, and models that already looked got cheaper. Nothing here came near a per-request image cap. Long threads, where every page stays until compaction, are still unmeasured.

## Still to run

The columns are those of 05's [eval matrix](05-model-ladder-and-evals.md#5-the-eval-matrix). Each runs the same eight cases with `SURFSENSE_LIVE_PROVIDER` and `SURFSENSE_LIVE_MODEL` ([07-dev-setup](07-dev-setup.md#live-tests)).

| Rung | Models | How |
|---|---|---|
| Sonnet 5.5, again | a clean sweep on the same commit as Opus and Haiku | Anthropic |
| Frontier open models, the rest | Qwen3.5-397B-A17B and gpt-oss-120b (Kimi K3, GLM-5.3 and DeepSeek V4 Pro are [above](#open-models-through-openrouter)); then the best of them again with the provider order pinned and fallbacks off, as 05 asks | OpenRouter |
| 27–35B, the rest | Gemma 4 26B-A4B (Qwen3.8-27B, Qwen3.6-35B-A3B and Gemma 4 31B are above); committed rows need GGUF on a 24–32 GB machine (05's open question 1), Qwen3.8-27B first | OpenRouter for screening, then llama.cpp |
| 8–14B local | Qwen3 8B and 14B, the local catalog's rows at this size (text-only, 40,960-token window), and the best small model screened here, Ministral 14B, which has no local catalog row yet | llama.cpp. This needs a model download the maintainer approves: Qwen3 8B Q4_K_M is 5.0 GB and 14B Q4_K_M 9.0 GB. The harness has no local provider yet, so `live_model.py` needs one that points the connection at the llama.cpp server and charges nothing. The demo's largest request was 38K to 68K tokens on the models that passed it, above that window, so these runs will also test opencode's compaction. As text-only models they will be held to the render, not the previews, and cannot pass the figure swap |
| Other vendors | one OpenAI and one Gemini model | needs their providers in `live_model.py` |

The 8–14B results above come from OpenRouter's hosts. How the tier does on the machines it is meant for stays unmeasured until the llama.cpp runs are done. The machine these ran on has an RTX 3080 with 10 GB and 16 GB of RAM. 05's reference machines are the RTX 3050 6 GB and a 16 GB laptop.

A cell of the committed matrix needs at least three runs (05). Before a verdict, every Opus and Haiku cell needs two more runs, Haiku's three failed cases first.
