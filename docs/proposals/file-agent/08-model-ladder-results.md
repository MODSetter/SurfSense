# Model ladder: first results

The eight live cases of the [create-and-edit slice](07-create-and-edit-mvp.md) were run on Claude Opus 5.5 and Claude Haiku 4.5, beside the Sonnet 5.5 runs that wrote them. Opus passed all eight on the first try. Haiku passed five. Its three failures had one cause: on the first turn it did not open every page preview of the document it ended on, which the skill asks for. The edit turns of those three cases were therefore never reached. This is the first measured row toward [05](05-model-ladder-and-evals.md)'s matrix. In 05's terms it is screening: one run per cell in the dev setup, not a committed row. Eight open models then ran the same cases through OpenRouter ([below](#open-models-through-openrouter)). Kimi K3 and Qwen3.8-27B passed all eight. The text-only GLM-5.3 and DeepSeek V4 Pro failed only the case that needs image input. From Gemma 4 31B and Qwen3.6-35B-A3B (about 3B active) down, the models stopped checking their pages, invented drawing APIs and lost track of versions, and no 8–14B model passed the document cases. Gemma 4 31B and Qwen3.5-9B then ran every case with the gate lifted, and neither passed a document case. Across the whole matrix, the most common way to fail was to answer without opening the page previews ([below](#what-the-failures-point-to)).

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

## Open models through OpenRouter

The same eight cases then ran on eight open models through OpenRouter. Kimi K3 and Qwen3.8-27B passed all eight, as Opus did. GLM-5.3 and DeepSeek V4 Pro are text-only, and each passed every case except the figure swap, which needs the model to read a chart image. Smaller models did worse. Qwen3.6-35B-A3B passed 4 of 8, Gemma 4 31B 2 of 8, Ministral 14B 3 of 8 and Qwen3.5-9B 1 of 8. Qwen3.5-9B's one pass, the images case, did not make the page it was asked for. Gemma and Qwen3.5-9B ran all eight cases because the gate was lifted for them (see "The gate" below). This is screening too: one run per cell, in the dev app. The models ran on the hosts OpenRouter chose, not as GGUF files on llama.cpp.

### What was run

- **When.** 4 to 5 Oct 2026, from 16:27 to 18:18 Pacific (23:27 to 01:18 UTC). The code was the Opus and Haiku code above, plus `8463f45be`'s demo check and the text-only change described below. Each model's cases ran one at a time, and several models ran at the same time. The cases Gemma 4 31B and Qwen3.5-9B ran with the gate lifted followed on the same code, from 18:30 to 19:29 Pacific (01:30 to 02:29 UTC).
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
  | Qwen3.5-9B | Venice, DeepInfra, SiliconFlow, Darkbloom |

  Each host runs its own quantization and has its own speed. Kimi's hosts ran fp4, fp8 and mxfp4. A cell measures the model as those hosts served it, not as llama.cpp would run it.
- **Image input.** The harness declared image input the way the app does, from the model's row under provider `openrouter` in the remote catalog. Kimi, Qwen3.8, Qwen3.6, Gemma, Ministral and Qwen3.5-9B read images. GLM-5.3 and DeepSeek V4 Pro are text-only, and `result.json` records `reads_images: false` for them. A text-only model gets no page previews. Each render result tells it "No page previews: the selected model cannot read images", and the skill tells it to check the script and the render's text instead. The cases now do the same: they skip the preview checks for a text-only model (`sees_pages` in [`turn_renders.py`](../../../surfsense_local/backend/tests/live/turn_renders.py)). A model that reads images, Claude included, is checked as before. The images case is n/a for a text-only model.
- **The gate.** Each column ran in this order:
  1. Smoke. If the model failed it, the column stopped there, and every other case is "not run".
  2. Images, only when the catalog declares image input.
  3. Demo flow, then PDF brief. If the model failed both, the rest are "not run".
  4. Otherwise memo restructure, figure swap, board pack and spreadsheet report.

  A failed case got a second attempt only when the failure looked transient: a 5xx, a 429 or an overload, a dropped stream, or a timeout with no output. No failure looked transient. The one second attempt in the matrix followed a harness fault.

  **The gate was lifted for Gemma 4 31B and Qwen3.5-9B** after the sweep, and their remaining cases ran in full. The gate had stopped Qwen3.5-9B on a missing citation label, which says nothing about document work, and had stopped Gemma before four of the six document cases. A gated column shows that a model fails, not how it fails on each kind of task. Running every case on both gives each model's failures on every case, which the grouping in [What the failures point to](#what-the-failures-point-to) needs. Nothing else changed: the same cases, checks, skill and prompt, and the same retry rule.
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

  The bracketed figure in the matrices is what OpenRouter billed: its own `usage.cost`, summed over the run's requests (`reported_dollars` in `cost.json`). The ledger and the bill differ for two reasons. The upstream that served a request may charge more or less than the listing. And a request cut off before its usage arrives is charged its worst case on the ledger, while OpenRouter bills nothing for it. Each model has its own ledger, `references/live-runs/ladder-open/<model>/spend.json`. The ledgers total $7.05, and OpenRouter billed about $4.36.

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
| Images reach the model | pass · 1 · $0.01 ($0.01) · 0.8 | pass · 1 · $0.01 ($0.01) · 0.9 | pass · 1 · $0.005 ($0.02) · 1.1 | pass · 1 · $0.005 ($0.005) · 1.1 | pass, hollow (see below) · 1 · $0.10 ($0.08) · 11.7 |
| Demo flow (3 turns) | pass · 2 · $0.33 ($0.17) · 10.6 | **fail** · 1 · $1.67 ($0.64) · 14.1 | **fail** · 1 · $0.008 ($0.04) · 2.8 | pass · 1 · $0.02 ($0.02) · 4.3 | **fail** · 1 · $0.06 ($0.06) · 27.8 |
| PDF brief | pass · 1 · $0.03 ($0.03) · 2.3 | pass · 1 · $0.05 ($0.05) · 3.9 | **fail** · 1 · $0.002 ($0.01) · 0.9 | **fail** · 1 · $0.003 ($0.003) · 0.7 | **fail** · 1 · $0.06 ($0.06) · 10.8 |
| Spreadsheet report | pass · 1 · $0.03 ($0.03) · 3.1 | **fail** · 1 · $0.005 ($0.005) · 0.5 | **fail** · 1 · $0.002 ($0.008) · 0.7 | **fail** · 1 · $0.002 ($0.002) · 0.8 | **fail** · 1 · $0.02 ($0.02) · 2.9 |
| Memo restructure | pass · 1 · $0.26 ($0.04) · 3.0 | pass · 1 · $0.02 ($0.02) · 1.8 | **fail** · 1 · $0.003 ($0.009) · 0.8 | **fail** · 1 · $0.002 ($0.002) · 0.8 | **fail** · 1 · $0.008 ($0.008) · 1.6 |
| Figure swap | pass · 1 · $0.02 ($0.02) · 1.8 | **fail** · 1 · $0.008 ($0.006) · 1.1 | **fail** · 1 · $0.009 ($0.04) · 2.2 | **fail** · 1 · $0.003 ($0.003) · 0.9 | **fail** · 1 · $0.01 ($0.01) · 1.3 |
| Board pack | pass · 1 · $0.04 ($0.04) · 2.3 | **fail** · 1 · $0.02 ($0.02) · 1.0 | **fail** · 1 · $0.002 ($0.01) · 0.4 | **fail** · 1 · $0.001 ($0.001) · 0.5 | **fail** · 1 · $0.002 ($0.002) · 0.5 |
| **All** | 8 of 8 · $0.72 ($0.34) · 24.2 | 4 of 8 · $1.79 ($0.75) · 23.5 | 2 of 8 · $0.03 ($0.14) · 9.3 | 3 of 8 · $0.04 ($0.04) · 9.5 | 1 of 8 · $0.27 ($0.25) · 56.9 |

The Qwen3.8-27B demo cell gives the passing second attempt only. The first attempt failed because of the harness and cost $0.34 ($0.12 billed). With that attempt, Qwen3.8-27B's ledger holds $1.06. Before the sweep, Qwen3.5-9B also failed the smoke twice while the OpenRouter path was being checked (`ladder-open/prove/`, $0.003).

Qwen3.5-9B's images pass is hollow. The case checks only that the answer names the triangle, its colour and the word ORBIT. The page images reached the model, and it described each preview correctly, including that the triangle was still only an outline. It made 25 versions and never filled the triangle, because every `drawPath` and `rect` call left out `fill=1`, and the turn ended mid-sentence with no tool call. The answer still contained the three words, so a page with no green on it passed. Its ledger cost has two requests cut off by the provider, so the bracketed bill sums the 38 requests OpenRouter priced. `qwen__qwen3.5-9b/20261005T013033Z-images-reach-the-model-openrouter-qwen_qwen3.5-9b`

Model requests per run, in the matrix's order:

| Model | Requests |
|---|---|
| Kimi K3 | 2, 4, 19, 10, 10, 10, 11, 13 |
| GLM-5.3 | 2, n/a, 11, 8, 8, 9, 9, 8 |
| DeepSeek V4 Pro | 2, n/a, 17, 8, 8, 9, 8, 10 |
| Qwen3.8-27B | 2, 4, 28, 9, 9, 17, 11, 10 |
| Qwen3.6-35B-A3B | 2, 12, 114, 18, 5, 13, 7, 11 |
| Gemma 4 31B | 2, 8, 11, 4, 4, 5, 13, 6 |
| Ministral 14B | 2, 11, 22, 6, 6, 4, 7, 3 |
| Qwen3.5-9B | 2, 40, 31, 27, 15, 8, 10, 3 |

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
- **Gemma 4 31B, memo restructure and spreadsheet report: `model`.** Both turn-1 documents were sound and rendered on the first try: a three-section A4 memo, and a report whose bar chart uses the workbook's revenue figures exactly. In both it answered without opening the page preview, so the edit turns never ran. The render result's preview list and the skill's "Checking what you made" section both reached it (`model-requests.json`). `google__gemma-4-31b-it/20261005T013030Z-memo-restructure-openrouter-google_gemma-4-31b-it`, `google__gemma-4-31b-it/20261005T013520Z-spreadsheet-report-openrouter-google_gemma-4-31b-it`
- **Gemma 4 31B, figure swap: `model`.** It picked the right figure, the chart 1-2, from the captions. Eight renders in a row then passed `images: []` while the script opened `IMAGES_DIR/1-2.png`, and each died with FileNotFoundError. It rewrote the path line and its comments each time and listed `1-2` only on the ninth. Every retry left out `artifact_id`, although the tool said to send it, so artifacts 1 to 8 are failed documents and the working one is artifact 9 v1. It also kept going past "stop after the third failed run". It then answered without opening the preview. The FileNotFoundError result does not say that the image was missing from `images`; that is worth knowing but did not decide the case. `google__gemma-4-31b-it/20261005T013140Z-figure-swap-openrouter-google_gemma-4-31b-it`
- **Gemma 4 31B, board pack: `model`.** Asked for "something I can send to the board", it read the three sources and wrote a Markdown file to `outputs/`. It never loaded the skill or rendered, and it did not say what format it chose or what it assumed. The agent prompt says a document with no format named is a Word file or a PDF; the model followed the prompt's catch-all line for other files instead. `google__gemma-4-31b-it/20261005T013424Z-board-pack-openrouter-google_gemma-4-31b-it`
- **Ministral 14B, PDF brief, memo restructure, figure swap and spreadsheet report: `model`.** In all four it rendered a sound first version, then pointed the user to the preview folder instead of opening the pages. In the figure swap, its first script also had a newline escape that arrived as a literal `n`; it fixed that on the next render. The four folders are under `mistralai__ministral-14b-2512/`:
  - `20261005T004923Z-pdf-brief-openrouter-mistralai_ministral-14b-2512`
  - `20261005T005022Z-memo-restructure-openrouter-mistralai_ministral-14b-2512`
  - `20261005T005123Z-figure-swap-openrouter-mistralai_ministral-14b-2512`
  - `20261005T005309Z-spreadsheet-report-openrouter-mistralai_ministral-14b-2512`
- **Ministral 14B, board pack: `model`.** Asked for "something I can send to the board", it wrote a sourced summary in the chat. It never loaded the skill or rendered, and it ended by asking whether to make a memo or a deck. `mistralai__ministral-14b-2512/20261005T005228Z-board-pack-openrouter-mistralai_ministral-14b-2512`
- **Qwen3.5-9B, smoke: `model`.** It searched, got the passage labelled `[1]` and gave the right date. It never wrote the label, which the agent prompt asks for. It failed this way in 3 of 3 runs. `qwen__qwen3.5-9b/20261005T003613Z-smoke-openrouter-qwen_qwen3.5-9b`, and two more in `prove/`.
- **Qwen3.5-9B, demo flow: `model`.** The check that failed was "v9 does not place our logo": the Word file holds no pictures. It never loaded the skill in any of the three turns. In turn 1 it wrote a tool call as plain Qwen-XML text, `<tool_call><function=surfsense-documents>`, naming the skill as if it were a tool, so turn 1 rendered nothing. In turn 2 it called `surfsense_read_document` with `artifact_id` 0, and gave the logo as `Kestrel logo.png`, then `2-1.png`, before the bare `2-1`; the tool's errors corrected each. It treated `OUTPUT_PATH` and `IMAGES_DIR` as literal folder names, which failed four renders. Its v9 script opened the images at the agent's own path, `sources/figures/2-1.png`, behind `os.path.exists` guards, so the logo and the chart were silently left out, and it reused the source chart instead of drawing a bar chart. It ran `read` on the previews folder rather than on a page. In turn 3 it tried to edit a file, `agent.py`, that does not exist. The PDF has the same guarded paths, and its answer says the logo and chart are included. `qwen__qwen3.5-9b/20261005T014227Z-demo-flow-openrouter-qwen_qwen3.5-9b`
- **Qwen3.5-9B, PDF brief: `model`.** Its ReportLab scripts used `Spacer(width, None)` throughout, which raised a TypeError (`+=` on None and an int) nine times; it never found why. It also hit NameErrors, a SyntaxError, a Paragraph where a string was needed, and an invented `PageSettings` import: 21 renders in turn 1, against "stop after the third failed run". Its last render dropped `artifact_id`, which started a new document (artifact 22 v1). It answered without opening either page, and gave the total as 40,800 EUR where the sources make it 39,800. `qwen__qwen3.5-9b/20261005T021028Z-pdf-brief-openrouter-qwen_qwen3.5-9b`
- **Qwen3.5-9B, memo restructure: `model`.** It loaded the skill, fixed two script errors (three values for a two-column row, and `.bold = True = True`) and kept `artifact_id` across versions, ending on v3. It answered without opening the preview. The rendered text shows a broken options table, an empty first row and doubled cell text ("OptionOption", "CostCost"), which a look at the page would have caught. It also wrote its Python script to `outputs/memo.docx`. `qwen__qwen3.5-9b/20261005T022134Z-memo-restructure-openrouter-qwen_qwen3.5-9b`
- **Qwen3.5-9B, figure swap: `model`.** It chose the chart 1-2, not the photo. Its first render left out `images` and failed with FileNotFoundError; the next, with `artifact_id` 1, made v2 over two pages. It opened page 1 only and called the result a one-page summary, though one footer bullet had run onto page 2. `qwen__qwen3.5-9b/20261005T022334Z-figure-swap-openrouter-qwen_qwen3.5-9b`
- **Qwen3.5-9B, board pack: `model`.** It read the three sources, then asked the user which format to use and offered PowerPoint, which SurfSense does not make. It never loaded the skill or rendered, against the agent prompt's line on documents with no format named. `qwen__qwen3.5-9b/20261005T022514Z-board-pack-openrouter-qwen_qwen3.5-9b`
- **Qwen3.5-9B, spreadsheet report: `model`.** Turn 1 passed every check: the skill first, the workbook read, a bar chart of the right revenue in a Word file, and the preview opened. In turn 2 it edited its own copy of the script, `outputs/temp_script.py`, instead of calling `surfsense_read_document`, fixed an IndexError and rendered v3 with `artifact_id` 2: a line chart and a trend paragraph. It answered without opening v3's preview. The paragraph puts average yearly growth at "9-10%"; the workbook's figures give about 11.8%. `qwen__qwen3.5-9b/20261005T022558Z-spreadsheet-report-openrouter-qwen_qwen3.5-9b`

**Provider drops.** Six runs, on Kimi, Qwen3.8, Qwen3.6 and Qwen3.5-9B, lost requests between the proxy and OpenRouter. The errors were "Server disconnected without sending a response" or an SSL bad-record-MAC read error. opencode retried each request, and no drop decided a case. All 11 of Qwen3.6's drops came during its demo loop, with more than 200K tokens of context. Qwen3.5-9B's two came in its images case. No 429 or 5xx was seen on any open column.

### Where the document work stops

As the models got smaller, things broke in this order:

1. **The self-check goes first.** Kimi K3 and Qwen3.8-27B opened every page of every version and rendered again when they saw a fault, as Opus did. In the demo, Kimi fixed column widths, made a table's header row repeat across the page break and kept rows whole. Qwen3.8 caught a doubled colon in its PDF. Haiku skipped previews on turn 1 (see above). Gemma 4 31B never opened a preview in any of its six document cases. Ministral 14B skipped them unless the user asked it to look. Qwen3.5-9B skipped them, opened one page of two, or ran `read` on the previews folder; in the images case, where it did look, it saw the fault and could not fix it. Qwen3.6-35B-A3B tried to open them but got the paths wrong. In 14 of the 24 model failures in the open columns, the check that failed was the one for unopened previews.
2. **Drawing scripts go next; Word scripts hold longest.** Down to 14B, python-docx scripts ran on the first or second try. Gemma's nine renders in the figure swap came from an empty `images` list, not from the script. At 9B Word scripts slipped too: Qwen3.5-9B treated `OUTPUT_PATH` as a literal folder name in four demo renders and needed three renders for the memo. ReportLab broke earlier. Asked for a triangle, Qwen3.6 needed 9 renders, Gemma 5 and Ministral 8, and Ministral ended on a rectangle, which it admitted. Qwen3.5-9B made 25 versions and never filled the triangle, because no `drawPath` or `rect` call passed `fill=1`. Most failed renders called an API that does not exist: `Canvas.triangle`, `Canvas.polygon`, `drawPolygon`, `reportlab.lib.shapes`, and from Qwen3.5-9B `reportlab.graphics.shapes.Rectangle` and a platypus `PageSettings`. Qwen3.5-9B's PDF brief failed 21 renders, nine on the same `Spacer(width, None)`. All four kept going past the "stop after the third failed run" rule, and Gemma did again in the figure swap. The frontier open models and Qwen3.8 had at most one script error per case.
3. **Then keeping a document's versions together.** Gemma never passed `artifact_id`, even when a tool result named it, so each retry or edit made a new document instead of a new version; in the figure swap that left eight failed documents. Qwen3.6 did the same in the images case. Qwen3.5-9B mostly passed the id the tool gave it, but sometimes dropped it, and its PDF brief ended on a new document. Ministral kept the demo's versions together.
4. **Then honesty about the result.** The text-only frontier models said plainly that they could not see images, and they would not make up chart values. DeepSeek built the demo's chart from the agreed prices and said so in the caption. Gemma told the user a logo was on the cover after its script had silently dropped it. Qwen3.5-9B did the same in the demo: `os.path.exists` guards dropped the logo and the chart, and its answer said both were in. Qwen3.6 reported work as done without having seen the pages. Qwen3.5-9B's answers also got the arithmetic wrong: a total of 40,800 EUR for 39,800, and yearly growth of 9-10% for about 11.8%.
5. **Plain question answering goes last.** Every model down to Ministral 14B cited its passage in the smoke. Only the 9B left the label out.
6. **Tool calls stayed well-formed down to 14B.** Across the other seven columns, one argument arrived malformed (Ministral's literal `n`), and no tool call failed its schema. Qwen3.5-9B once wrote a call as plain Qwen-XML text, which never reached a tool, and sent values the tool turned down: `artifact_id` 0, and file names where image names were asked for. It corrected each after the tool's error. Wrong but valid arguments were commoner: Gemma passed an empty `images` list eight times, and Qwen3.5-9B left `images` out once.

Three caveats apply when reading the tiers:

- **Size alone does not place a model.** Qwen3.8-27B, which has no active-parameter suffix in its name, behaved like the frontier models. Gemma 4 31B, about the same size and also without one, failed all six document cases, four of them by not looking at its pages. Qwen3.6-35B-A3B, with about 3B parameters active per token, behaved like the small tier. Active parameters account for Qwen3.6, not for Gemma.
- **Seeing is not what fails at the bottom.** Qwen3.5-9B read its previews and described them accurately, faults included. What it could not do was act on what it saw.
- **This skill needs image input.** A text-only model cannot do the figure swap. Without previews, it also has to judge layout from the render's text alone. DeepSeek took four PDF renders in demo turn 3 to bring the PDF from three pages to two.

**Speed and cost.** Prompt caching works through OpenRouter, unlike on the Claude runs above. On DeepSeek, the demo read 322K cached tokens against 35K fresh ones. The frontier open models cost a fraction of Opus: Kimi's eight cases were $2.26 on the ledger and $1.69 billed, against $7.97 for Opus. Speed depends on the host OpenRouter picks. Kimi's demo took 13.3 minutes because all 19 requests went to Makora, at about 42 seconds each. Its other cases ran at 12 to 18 seconds a request. GLM and DeepSeek each took about 12 to 13 minutes for their seven cases. Several models spent most of a turn on a large burst of output tokens before a render; GLM's first Word render was a single request with 20,537 output tokens. The smallest model was the slowest column: Qwen3.5-9B took 57 minutes for $0.27 on the ledger, most of it in failed renders, 28 minutes on the demo and 12 on the images case.

**The ledger against the bill.** The ledger is a spend stop, not an invoice, and it can be far off the bill:

- Where requests were cut off, it ran 2 to 6 times over the bill: Kimi's board pack $0.76 against $0.29, Qwen3.6's demo $1.67 against $0.64, Qwen3.8's memo $0.26 against $0.04.
- On DeepSeek it ran about twice over, because its Relace host charges less than the listing.
- On Gemma it ran about 4 times under, because its ModelRun host charges more.

To compare models, use the bracketed bill.

### The best candidate in each tier

- **Frontier open: Kimi K3.** It is the only open model here that reads images and passed all eight cases. It checked its pages the way Opus did, at under a third of Opus's cost. Its time depends on the host. GLM-5.3 is the faster and cheaper runner-up, but it is text-only. The catalog lists `z-ai/glm-5.3-flash` with image input, but it has not been tested.
- **27–35B: Qwen3.8-27B.** It passed all eight cases, the demo on its second attempt after the harness fix. It reads images and checks every page. For a committed row, it is the one to run as a GGUF on a 24–32 GB machine. Gemma 4 31B, run in full, passed only the smoke and the images case. Its Word scripts followed the skill's house style and ran on the first try when there was no image to place, and its content was faithful to the sources, but it never opened a preview and never passed `artifact_id`. It is not a candidate as it stands.
- **8–14B: none yet.** Ministral 14B did best here: it passed the smoke, the images case and the three-turn demo. But it fails the document cases the way Haiku did, by not looking at its pages, and it made no document for a vague request. Qwen3.5-9B, run in full, passed only the images case, and that pass did not make the page asked for. It reads images well, but it writes many script errors, keeps rendering past the stop rule, hides a dropped image behind a guard and gets its arithmetic wrong. At this size, 05's `workflow` rung, where SurfSense runs the plan, render and check steps itself, is the one to measure next.

### What to change next, for the open models

None of these changes was made here, for the same reason as above: the ladder measures and does not tune.

- **Tool: tell a text-only model the truth about images.** On a text-only model, opencode's `read` of a PNG returns "Image read successfully" and sends no image. A separate message says "Cannot read image (this model does not support image input)". GLM and DeepSeek worked out what had happened, but the first message is wrong.
- **Tool: make preview paths hard to retype.** The render result gives relative preview paths, and Qwen3.6 rewrote them as absolute paths and got them wrong. The `$` in this machine's user name (`$punk`) may make that more likely. A tool that opens a version's pages by id, or a `read` refusal that names the relative path to use, would take the retyping out.
- **Case: figure swap for text-only models.** Turn 2 cannot be done without image input. The case could be marked n/a when `reads_images` is false, like the images case.
- **Case: the demo's chart check.** Any two pictures pass it, so placing the source figure passes without drawing the requested chart. Kimi, GLM and Qwen3.8 each placed or kept the source figure.
- **Case: board pack's assumption check.** It looks for particular words. Qwen3.6 stated its format choice in other words and failed it.
- **Case: the images check.** It looks only for the words triangle, green and ORBIT in the answer. Qwen3.5-9B passed it with a page that has no green on it and an answer that ends mid-attempt.
- **Harness: the ledger's estimate for a cut-off request.** The estimate can charge more prompt than the model's window holds. On Qwen3.6 it charged 393K to 492K cache-write tokens on a 262K-token model. Capping the estimate at the window would bring the ledger closer to the bill.

## What the failures point to

This groups every model failure in the matrices above, Claude and open, by what the model did. Each failed cell is counted once, under the behaviour that decided it: the check that failed. The bracketed figure counts other runs in the matrices, passing or failing, where the behaviour showed up without deciding the case. Sonnet 5.5, Opus 5.5, Kimi K3 and Qwen3.8-27B had no model failure in their cells and are left out. The harness failure (Qwen3.8's first demo attempt) is not counted, and neither is Qwen3.5-9B's hollow images pass.

| Behaviour | Haiku 4.5 | GLM-5.3 | DeepSeek V4 Pro | Qwen3.6-35B-A3B | Gemma 4 31B | Ministral 14B | Qwen3.5-9B | All |
|---|---|---|---|---|---|---|---|---|
| Skipped the preview check | 3 | n/a | n/a | 0 | 4 (+1) | 4 | 4 (+1) | 15 (+2) |
| Retyped a preview path wrongly | 0 | n/a | n/a | 2 (+1) | 0 | 0 | 0 | 2 (+1) |
| Left out `artifact_id` | 0 | 0 | 0 | 0 (+1) | 1 (+1) | 0 | 0 (+1) | 1 (+3) |
| Malformed or wrong tool arguments | 0 | 0 | 0 | 0 | 0 (+2) | 0 (+1) | 0 (+2) | 0 (+5) |
| Made no document | 0 | 0 | 0 | 0 | 1 | 1 | 1 (+1) | 3 (+1) |
| No citation marker | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| Text-only limits | n/a | 1 | 1 | n/a | n/a | n/a | n/a | 2 |
| Left an image out silently | 0 | 0 | 0 | 0 | 0 (+1) | 0 | 1 | 1 (+1) |
| Looped without rendering | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| Did not say what it assumed | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| **Failed cells** | 3 | 1 | 1 | 4 | 6 | 5 | 7 | 27 |

What goes in each row:

- **Skipped the preview check.** The turn ended on a version whose pages it had not all opened. The decided cells are Haiku's memo, board pack and spreadsheet report, and the PDF brief, memo, figure swap and spreadsheet report of Gemma, Ministral and Qwen3.5-9B each. Also seen: Gemma's demo, which failed on its versions first, and Qwen3.5-9B's demo, which failed on its logo first. The skip took four forms: no `read` at all (most cells), page 1 of 2 only (Haiku's spreadsheet report, Qwen3.5-9B's figure swap), a `read` or listing of the previews folder instead of a page (Haiku's spreadsheet report, Qwen3.5-9B's demo), and pointing the user to the folder (Ministral). The instruction reached the model each time: the render result lists the pages "to check with `read`", and Gemma's `model-requests.json` shows the skill's section on checking in its context. 14 of these 15 came on turn 1, so the edit turns of those cases never ran. Qwen3.5-9B's spreadsheet report is the exception, on turn 2.
- **Retyped a preview path wrongly.** Qwen3.6's figure swap and spreadsheet report: it rewrote the relative path as an absolute one, dropped the `$` from `pytest-of-$punk` and had the read refused. Also seen in its demo's turn 1, where both preview reads were refused.
- **Left out `artifact_id`.** Gemma's demo: the read result named `artifact_id` 1 and the render went without it, so no Word v2 exists. Also seen in Gemma's figure swap (eight retries, eight new documents), Qwen3.6's images case and Qwen3.5-9B's PDF brief (its last render started artifact 22).
- **Malformed or wrong tool arguments.** None decided a case; the tool's errors led to each being corrected, at the cost of renders. Seen in Ministral's figure swap (a literal `n` for a newline), Gemma's demo (the logo left out of `images`) and figure swap (`images: []` eight times), and Qwen3.5-9B's demo (a call written as Qwen-XML text, `artifact_id` 0, file names for image names) and figure swap (`images` left out).
- **Made no document.** All three are the board pack, the one case that names no format. Gemma wrote Markdown to `outputs/`, Ministral answered in the chat and asked whether to make a memo or a deck, and Qwen3.5-9B asked which format to use and offered PowerPoint. None loaded the skill. Also seen in Qwen3.5-9B's demo, where turn 1 rendered nothing.
- **No citation marker.** Qwen3.5-9B's smoke: the right answer without the passage's `[1]`, in 3 of 3 runs counting `prove/`.
- **Text-only limits.** GLM's and DeepSeek's figure swaps: turn 2's numbers exist only inside a chart image, and both asked the user for them instead of guessing.
- **Left an image out silently.** Qwen3.5-9B's demo: `os.path.exists` guards around a wrong path dropped the logo and the chart, and the answer said both were in. Also seen in Gemma's demo, where `try/except: pass` dropped the logo and the answer said it was on the cover.
- **Looped without rendering.** Qwen3.6's demo: 82 `skill` calls in a row in turn 2, until the context reached the model's window.
- **Did not say what it assumed.** Qwen3.6's board pack named the format but not the assumption, in words the check did not take.

Two behaviours run under several rows and decided no case alone. Rendering past "stop after the third failed run" was seen in the images case on Qwen3.6, Gemma, Ministral and Qwen3.5-9B, in Gemma's figure swap, and in Qwen3.5-9B's PDF brief (21 renders). Script errors the model did not diagnose, an invented API or the same wrong call repeated, are behind most of those renders.

Outside the matrices, three more failed runs fit the same pattern: Sonnet's earlier board pack did not say what it assumed, one of Haiku's two extra memo runs skipped the preview check, and the other reached turn 2 and put an unnumbered "Summary" heading first, which no row covers.

By rows, the preview check decided 17 of the 27 failures, counting the retyped paths, and every model that reads images and did not pass every case failed it at least once. By columns, Haiku, GLM and DeepSeek each failed on one behaviour, Qwen3.6, Gemma and Ministral on two or three, and Qwen3.5-9B on four, the most of any model.

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
