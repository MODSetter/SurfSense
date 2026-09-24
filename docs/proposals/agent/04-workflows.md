# Fixed workflows and the text fallback

> A model that does not get opencode still gets real work done: SurfSense runs the steps itself and asks the model for one defined output per step. A JSON schema makes each output parseable, and writing before formatting keeps the schema from costing quality.

## Where Studio stands

- Seven of Studio's twelve formats parse a JSON reply with `parse_json` ([`worker/studio/shared/text.py`](../../../surfsense_local/backend/worker/studio/shared/text.py)): mind map, flashcards, quiz, HTML, image, infographic, and the podcast's outline and draft. It takes the first code fence if there is one, then the outermost braces, and calls `json.loads`. Invalid JSON, or JSON that is not an object, raises `ValueError`. It does not repair anything.
- Only the podcast draft sends a failed reply back to the model, through `generate.Repair` ([`generate.py`](../../../surfsense_local/backend/worker/studio/shared/generate.py), [`podcast/draft.py`](../../../surfsense_local/backend/worker/studio/media/audio/podcast/draft.py)). The Office pipeline uses the same mechanism for its Python scripts. The other JSON formats make one call; [`content/quiz/pipeline.py`](../../../surfsense_local/backend/worker/studio/content/quiz/pipeline.py) is an example.
- `run_model` passes no `json_schema` and no `reasoning` argument ([`generate.py`](../../../surfsense_local/backend/worker/studio/shared/generate.py)). So the llama.cpp provider adds no `THINKING_OFF`, and Qwen3 models think, which is their default ([runtime](../../architecture/local-models/runtime.md), Turning thinking off).

## What llama.cpp does with a schema

At `b11050`:

- The schema becomes a grammar. The parser accepts the model's reasoning block first, then the JSON, optionally inside a `json` code fence ([`common/chat-auto-parser-generator.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/common/chat-auto-parser-generator.cpp)).
- Required properties are generated before optional ones ([`common/json-schema-to-grammar.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/common/json-schema-to-grammar.cpp)).
- A trailing assistant message is continued rather than answered, through the request's `continue_final_message` or the server's `prefill_assistant` option ([`tools/server/server-common.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/tools/server/server-common.cpp)). A reply can therefore be started for the model.
- A request with both a schema and tools gets no tool-call parsing ([`01-which-engine.md`](01-which-engine.md)).

A grammar does not guarantee valid output for every schema. JSONSchemaBench ([arXiv 2501.10868](https://arxiv.org/abs/2501.10868), Tables 2 and 4) tested llama.cpp through llama-cpp-python 0.3.2 (November 2024) with Llama 3.2 1B:

- Its empirical coverage, the share of schemas it handled with valid output, ranged from 0.95 on the GlaiveAI set to 0.57 on GitHub Medium.
- Time per output token was 27–30 ms, against 15–16 ms unconstrained.

These numbers predate `b11050`.

## Decisions

1. Every JSON format passes `json_schema`. Schemas stay small and flat, inside what llama.cpp supports. When a schema has a reasoning field, it is required, so the model writes it before the answer fields.
2. Every JSON reply is checked against the full schema. A failure goes back to the model with the error through `generate.Repair`, in every JSON format rather than only the podcast draft.
3. A writing format takes two calls: the model writes the content as prose, then a second call puts it into the schema.
4. For a remote model without structured output, that second call runs on a local model under a grammar ([`01-which-engine.md`](01-which-engine.md)).
5. A workflow with several steps is planned in one constrained call, and SurfSense then runs the steps without asking the model between them.

## The evidence behind them

None of these studies ran 4-bit GGUF models. The [chat eval](../chat-eval.md) is where they get confirmed on the app's own models.

| Technique | What was measured | Source | Use |
|---|---|---|---|
| Write, then format (decision 3) | The two-call method significantly improved 42 of 72 reasoning comparisons (+6.8 points on average) and worsened 2. On WritingBench it partly recovered quality. Adding schema descriptions or examples to the prompt left most of the loss in place. Six open models from 3B to 32B, run on vLLM | "The Format Tax", [arXiv 2604.03616](https://arxiv.org/abs/2604.03616), a preprint from April 2026 with [public code](https://github.com/ivnle/the-format-tax) | Build |
| Think, then format | Thinking improved 43 of 72 reasoning comparisons (+9.2 points) but worsened 11. The paper says it "does not transfer to writing" | the same paper | Not a replacement for two calls on writing formats |
| Reason freely, constrain only the answer | Format restrictions degraded reasoning ([Tam et al.](https://aclanthology.org/2024.emnlp-industry.91/), EMNLP 2024). Unconstrained reasoning before a constrained answer gained up to 10 points ([CRANE](https://proceedings.mlr.press/v267/banerjee25a.html), ICML 2025) | peer reviewed | Supports decisions 1 and 3 |
| Plan once, then execute (decision 5) | On 1,000 HotpotQA questions with GPT-3.5, tokens per question fell from 9,795 to 1,986. Accuracy rose from 40.8 to 42.4, and exact match fell from 32.2 to 30.4 | ReWOO, [arXiv 2305.18323](https://arxiv.org/abs/2305.18323), a preprint | Build for cost; accuracy with a small planner is untested |
| Start the reply for the model | llama.cpp supports it (above); no quality measurement found | llama.cpp source | Try |
| Tune prompts against an eval set with GEPA | Beat GRPO by 6 points on average across six tasks and by up to 19, with up to 35× fewer rollouts | [GEPA](https://www.iclr.cc/virtual/2026/oral/10009494), ICLR 2026 oral | After the eval exists |
| Critique, then rewrite | Across Qwen3 and Gemma 3 sizes, the critic's size barely mattered, and an undersized refiner "can even harm performance" | [arXiv 2608.21345](https://arxiv.org/abs/2608.21345), a preprint | Later; only with the largest model rewriting |
| Route with yes/no answers in plain text (Natural Language Tools) | +18.4 points on tool choice across 10 models behind APIs. The test set was 32 made-up single-turn inputs with tools that take no arguments. A follow-up by other authors used the same two scenarios | [arXiv 2510.14453](https://arxiv.org/abs/2510.14453), [arXiv 2607.03953](https://arxiv.org/abs/2607.03953), both preprints | Do not use |

## The text fallback

- It is for remote models that state neither tool calling nor structured output. In the packaged catalog, 407 models say neither, and 488 more have no tool calling and do not say ([`01-which-engine.md`](01-which-engine.md)).
- The model writes prose, and the formatting call runs locally under a grammar. With no local text model installed, the reply is parsed as `parse_json` parses it today.
- No agent loop runs here. On the leaderboard used in [`01-which-engine.md`](01-which-engine.md), every model listed in both modes (Qwen3-0.6B, Qwen3-4B-Instruct-2507, Qwen3-8B, Qwen3-14B, Qwen3-32B and Claude Opus 4.5) scores lower on multi-turn tasks with tools described in the prompt than with native function calling. Claude Opus 4.5 falls from 68.38% to 16.12%.

## Open questions

- Which formats count as writing for decision 3: all seven JSON formats, or not the image prompt.
- Whether the formatting call uses the same model or a smaller local one.
- Which JSON Schema features llama.cpp handles at `b11050`, given that JSONSchemaBench predates it.
- How long a two-call Studio job takes on a CPU.
