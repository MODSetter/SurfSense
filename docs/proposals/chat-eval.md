---
status: in-progress
code:
  - surfsense_local/backend/scripts/chat_eval/
  - surfsense_local/backend/scripts/run_chat_eval.py
---

# Chat eval

> Scores the local chat's answers on every curated chat model, so a change to the prompts or the pipeline is measured before it ships. Models up to 8B run on the real files on our own machines. 8B, 14B and 32B run on Featherless, with every request built the way the local app builds it. 8B runs in both places, which measures how far Featherless scores sit from the real app.

## Why Featherless, and where it differs

Our machines run the models up to 8B, not 14B or 32B. We found no hosted service that runs GGUF through llama.cpp behind one API where the `model` field picks the model. The two llama.cpp hosts we found ([Hugging Face Inference Endpoints](https://huggingface.co/docs/inference-endpoints/engines/llama_cpp), [ModelsLab GGUF Cloud](https://modelslab.com/gguf-cloud)) put one model on each deployment, so switching models means deploying another one. [Featherless](https://featherless.ai/docs/models-model-compatibility) switches by model id and lists every Qwen3 size the manifest ships, but it serves a different copy of each model:

| | Local app | Featherless |
|---|---|---|
| Weights | the GGUF build, `UD-Q4_K_XL` by default ([catalog](../architecture/local-models/catalog.md)) | safetensors, quantized to FP8 at load; FP16 under 5B |
| Reasoning | split into `reasoning_content` by llama.cpp ([runtime](../architecture/local-models/runtime.md)) | on by default for Qwen3, returned apart from `content` ([chat template kwargs](https://featherless.ai/docs/chat-template-kwargs)) |

So Featherless serves a less compressed copy than users run. How far that moves scores on these models has not been measured; the 8B pair below measures it. The precision gap is widest on 0.6B to 4B, which Featherless serves at FP16 against the app's 4-bit files, and those are the sizes our machines run.

## Where each model runs

| Manifest model | Runs on | Default file |
|---|---|---|
| `qwen3-0.6b`, `qwen3-1.7b`, `qwen3-4b`, `gemma-3-4b` | our machines, in the app's llama.cpp runtime | 0.4 to 2.5 GB |
| `qwen3-8b` | both | 5.1 GB |
| `qwen3-14b`, `qwen3-32b` | Featherless | 9.2 and 20.0 GB |

The Featherless id is the manifest entry's `source_repo` (`Qwen/Qwen3-8B`, `Qwen/Qwen3-14B`, `Qwen/Qwen3-32B`), which is the id Featherless lists.

The eval needs Featherless's Developer plan: $50 a month in credits, billed per token. The flat-rate Chat plan ($25 a month) excludes "app or API traffic" and "benchmarking" ([pricing](https://featherless.ai/pricing), 23 Sep 2026). Featherless's model listing on the same day gave these rates and a 32,768-token context for each:

| Model | Input, per million tokens | Output, per million tokens |
|---|---|---|
| `Qwen/Qwen3-8B` | $0.117 | $0.455 |
| `Qwen/Qwen3-14B` | $0.12 | $0.24 |
| `Qwen/Qwen3-32B` | $0.102 | $0.493 |

## Building a request

The app's own Featherless connection cannot stand in for the local path, because SurfSense builds a different request for a remote endpoint:

- **Prompt tier.** `from_remote()` reads the endpoint's listing. Featherless rows carry `"owned_by": "Feather"` and no `hugging_face_id`, so every model there is classified `frontier` ([selection](../architecture/local-models/selection.md#known-gaps)). Locally, 8B to 32B get `capable` and anything under 7B gets `compact`.
- **Answer cap.** `answer_max_tokens()` caps the answer at 1,024 tokens only when the runtime reports its window. A remote endpoint reports none, so it gets no cap.
- **History.** A remote endpoint gets a flat 3,000 tokens of history. Locally it is whatever the model's window leaves ([chat](../architecture/chat.md#message-assembly)).
- **Reasoning off.** Only the llama.cpp provider says what `reasoning=False` means, so a title request to a remote Qwen3 still thinks.

So the script builds every request itself, on both sides, with the app's own functions rather than a copy, so the eval cannot drift from the app:

1. **Tier.** `classify(from_name("llamacpp", <local file stem>))`: the tier the app gives the local build, used for the Featherless run too.
2. **System message.** `build_context(hits, tier)` in [`modules/chat/prompt.py`](../../surfsense_local/backend/modules/chat/prompt.py).
3. **History.** `build_messages()` in [`modules/chat/history.py`](../../surfsense_local/backend/modules/chat/history.py), with `history_budget(CONTEXT_FLOOR_TOKENS)`. The app sizes the window per machine and never loads less than 8,192, so every machine and Featherless keep the same history.
4. **Answer cap.** `max_tokens` of 1,024 (`ANSWER_RESERVE_TOKENS`) on both sides.
5. **Sampling.** Sent explicitly and identically on both sides, from the manifest entry's `sampling` (`thinking`, or `non_thinking` for Gemma 3). The [model catalog](model-catalog.md) makes those the app's own. Until it does, the app's answer requests send none and run on llama-server's defaults, so its answers can differ from the eval's.
6. **Output.** `content` only. Both runtimes return reasoning separately, and the app never shows it.

Each case carries its retrieved passages, so every model answers from the same context. Retrieval does not depend on the chat model and is not scored here.

## Local runs

- Every machine runs the same file, the default `UD-Q4_K_XL`. On a machine short of memory the app recommends a smaller 4-bit build instead; install `UD-Q4_K_XL` from the model's other builds, which installs unless the app refuses it ([catalog](../architecture/local-models/catalog.md)). A machine that refuses it does not run the eval for that model.
- Each result records the llama.cpp build it ran on, because a release pins one ([packaging](../architecture/packaging.md)).
- The script asks a llama-server started the way the app starts it, normally the dev app's own, at the address given as `--base-url`, so a run uses the app's launch flags and model presets rather than a copy of them.

## Scoring

Rules only ([`score.py`](../../surfsense_local/backend/scripts/chat_eval/score.py)). Each case in [`cases.json`](../../surfsense_local/backend/scripts/chat_eval/cases.json) carries its passages, which of them hold the answer, and any facts a correct answer states, chosen to read the same in any language. A reply is marked for:

- stopping at the 1,024-token cap, and for coming back empty;
- a label that names no passage, read by chat's own `resolve_citations()`;
- citing every passage that holds the answer, and for citing one that does not, which on a case no passage answers is any citation;
- stating the expected facts;
- being written in the question's script, which stands in for its language.

## Reading the results

- Compare prompt or pipeline versions on the same model. A gap between a local model's score and a Featherless model's score mixes the difference between the models with the difference in precision.
- The 8B pair is the check on Featherless. Where its two scores agree, the 14B and 32B scores are good for comparing versions. Where they diverge, the diverging cases are the ones to confirm on a real file.
- A decision that rests on the exact 14B or 32B file runs that file on a Hugging Face llama.cpp endpoint, which serves any GGUF and bills by the minute.

## Rejected

| Option | Why not |
|---|---|
| Everything on Featherless | The precision gap is widest on the small models, which it serves at FP16 while users run 4-bit |
| Hugging Face Inference Endpoints for everything | Runs the exact GGUF, but one model per endpoint, so switching models means deploying or waking another endpoint |
| One rented GPU running llama.cpp's router mode | Switches by model id on the exact files, but it is a machine to operate, not a service |
| ModelsLab GGUF Cloud | llama.cpp on any GGUF, but a dedicated GPU billed monthly, from $249 as listed in September 2026 |
| OpenRouter, Together, DeepInfra, Chutes | Not compared in detail; none was found to serve GGUF through llama.cpp |
| Ollama Cloud | A small set of large models; it retired small ones such as `gemma3:4b` and `ministral-3:3b` on 15 Jul 2026 ([cloud docs](https://github.com/ollama/ollama/blob/cecd265d/docs/cloud.mdx)) |

## Open questions

- Whether a judge model scores what the rules cannot: admitting that the passages do not hold the answer, which the rules read only as citing nothing, and the language of a Latin-script question, which the script rule cannot tell from English.
- How often the 1,024-token cap cuts a thinking model's answer short ([chat](../architecture/chat.md#known-gaps)). The first thing to measure.
