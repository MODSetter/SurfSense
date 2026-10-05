# Model ladder: first results

The eight live cases of the [create-and-edit slice](07-create-and-edit-mvp.md) were run on Claude Opus 5.5 and Claude Haiku 4.5, beside the Sonnet 5.5 runs that wrote them. Opus passed all eight on the first try. Haiku passed five. Its three failures had one cause: on the first turn it did not open every page preview of the document it ended on, which the skill asks for. The edit turns of those three cases were therefore never reached. This is the first measured row toward [05](05-model-ladder-and-evals.md)'s matrix. In 05's terms it is screening: one run per cell in the dev setup, not a committed row.

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
| **All eight** | 8 of 8 · $6.39 ($4.25) · 12.3 | 8 of 8 · $7.97 ($7.01) · 15.9 | 5 of 8 · $1.12 ($0.94) · 10.5 |

**Sonnet's attempts that day.** Smoke: 3 runs, and the failure made no model request. Images: 1 failure from before the app declared image input, a diagnostic run, then a pass. Demo: 6 failed runs, 3 of them diagnostics, while image input and the checks were fixed, then 3 passes. PDF brief: 3 passes. Spreadsheet report: 2 passes. Memo restructure and figure swap: 1 pass each. Board pack: 1 failure (below), then 2 passes.

Haiku's three failures stopped at turn 1, so their time and cost cover one turn, not two. Haiku's totals cannot be set against the others' for that reason. On the five cases it passed it cost about a fifth of Opus by reported usage ($0.76 against $3.52) and took 6.8 minutes against 8.7.

Model requests per run: Sonnet 2, 4, 19, 8, 15, 15, 10, 11; Opus 2, 4, 16, 9, 12, 15, 9, 9; Haiku 2, 5, 17, 11, 7, 6, 12, 5, in the matrix's order. Ready document versions per run: Sonnet 0, 1, 5, 2, 5, 4, 2, 3; Opus 0, 1, 4, 2, 3, 4, 2, 2; Haiku 0, 1, 4, 2, 1, 1, 2, 1.

## Failures

Run folders are under `references/live-runs/` (Sonnet) and `references/live-runs/ladder/` (Opus and Haiku), which git ignores. Each cause carries one of 05's triage labels ([05 section 5](05-model-ladder-and-evals.md#5-the-eval-matrix)).

- **Haiku, spreadsheet report: `model`.** Turn 1 drew the right revenue figures as bars in a two-page Word report. It then listed the previews folder, opened page 1 only and answered. `20261005T000728Z-spreadsheet-report-anthropic-claude-haiku-4-5`
- **Haiku, memo restructure: `model`.** Turn 1 made a sound two-page memo. The render result listed both previews "to check with `read`", and it opened neither. `20261005T000155Z-memo-restructure-anthropic-claude-haiku-4-5`
- **Haiku, board pack: `model`.** Turn 1 made a two-page PDF in one render and opened neither page. Its answer named the format but not what it assumed, so the next check would probably have failed as well. `20261005T000551Z-board-pack-anthropic-claude-haiku-4-5`
- **Sonnet, board pack (an earlier run): `model`.** The answer named the format but did not say what it assumed. It is not recorded whether the case or the skill changed before the two passes that followed. `20261004T180816Z-board-pack`

Another runner ran Haiku's memo case twice more in the same folder, outside this sweep. `20261005T000043Z-memo-restructure-anthropic-claude-haiku-4-5` failed the same way as above. `20261005T001209Z-memo-restructure-anthropic-claude-haiku-4-5` opened its previews, reached turn 2 and failed there: it put the new summary table under an unnumbered "Summary" heading above "1. Background" and "2. Options and Recommendation". Whether a summary heading must be numbered is the case's call as much as the model's. With those two runs, Haiku's memo case stands at 0 of 3.

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

## Still to run

The columns are those of 05's [eval matrix](05-model-ladder-and-evals.md#5-the-eval-matrix). Each runs the same eight cases with `SURFSENSE_LIVE_PROVIDER` and `SURFSENSE_LIVE_MODEL` ([07-dev-setup](07-dev-setup.md#live-tests)).

| Rung | Models | How |
|---|---|---|
| Sonnet 5.5, again | a clean sweep on the same commit as Opus and Haiku | Anthropic |
| Frontier open models | GLM-5.x, Qwen3.5-397B-A17B, DeepSeek V4, Kimi (K2.6 in 05; K3 now listed), gpt-oss-120b | OpenRouter, priced from its listing; `model-requests.json` records which of OpenRouter's providers served each request and `cost.json` what OpenRouter billed |
| 27–35B | Qwen3.8-27B, Qwen3.6-35B-A3B, Gemma 4 26B-A4B and 31B | screened on OpenRouter; committed rows need GGUF on a 24–32 GB machine (05's open question 1) |
| 8–14B local | Qwen3.5-9B, Gemma 4 12B, Qwen3 8B and 14B | llama.cpp on the RTX 3050 6 GB and a 16 GB laptop; the harness has no local provider yet, so `live_model.py` needs one that points the connection at the llama.cpp server and charges nothing |
| Other vendors | one OpenAI and one Gemini model | needs their providers in `live_model.py` |

An OpenRouter sweep of Kimi K3 and Qwen3.8-27B, plus a Qwen3.5-9B smoke, was running from `references/live-runs/ladder-open/` while this was written. Its results are not reported here.

A cell of the committed matrix needs at least three runs (05). Before a verdict, every Opus and Haiku cell needs two more runs, Haiku's three failed cases first.
