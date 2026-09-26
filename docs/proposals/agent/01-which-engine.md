# Which engine a model gets

> A selected text model gets one of two engines: opencode, which needs native tool calling, or fixed workflows. Whether a model can call tools is read from its chat template or its catalog entry. Whether it calls them well enough for opencode is decided by testing, because the flag does not say.

## Tool support on the local runtime

- llama.cpp's parser rewrite, [PR #18675](https://github.com/ggml-org/llama.cpp/pull/18675) (merged 6 Mar 2026), removed the fallback that let any model emit tool calls. Its description says "a functional template with tool calling is required if someone wants tool calling".
- At `b11050`, llama-server reports a template's capabilities in `GET /props` under `chat_template_caps`. The keys include `supports_tools` and `supports_tool_calls` ([`common/jinja/caps.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/common/jinja/caps.cpp)). Tool calls are parsed only when `supports_tool_calls` is true ([`common/chat-auto-parser-generator.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/common/chat-auto-parser-generator.cpp)). The app reads `supports_tools` ([`capabilities.py`](../../../surfsense_local/backend/modules/llm/providers/llamacpp/capabilities.py)); the engine check needs `supports_tool_calls`.
- A request that carries `tools` to a model whose template has no tool support still succeeds, and the tools are dropped without a warning ([llama.cpp#27129](https://github.com/ggml-org/llama.cpp/issues/27129), open, reported against `b10423`).
- Among the curated manifest's seven chat models, `template.tools` is `true` for the six Qwen3 models and `false` for `gemma-3-4b`. Its three image models carry no `template` ([`models.json`](../../../surfsense_local/backend/modules/llm/catalog/local/manifest/models.json)).

## Structured output on the local runtime

- Any GGUF model can be held to a JSON schema. At `b11050`, a request with `response_format` gets a grammar that allows the model's reasoning block first, then the JSON, optionally inside a `json` code fence ([`common/chat-auto-parser-generator.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/common/chat-auto-parser-generator.cpp)).
- In the same file, a request with both `response_format` and `tools` gets the schema parser and no tool-call parsing. A request uses one or the other.
- Both chat providers accept a `json_schema`, and no caller passes one yet ([selection](../../architecture/local-models/selection.md), Known gaps).

## Tool support for remote models

The packaged remote manifest, built from models.dev and refreshed on 23 Sep 2026, records `tool_call` and `structured_output` for each model. `None` means models.dev never said ([`support.py`](../../../surfsense_local/backend/modules/llm/catalog/remote/support.py)). Across its 8,116 models from 223 providers ([`models.json`](../../../surfsense_local/backend/modules/llm/catalog/remote/manifest/models.json)):

| `tool_call` | `structured_output` | Models |
|---|---|---|
| true | true | 4,370 |
| true | not stated | 1,962 |
| true | false | 738 |
| false | not stated | 488 |
| false | false | 407 |
| false | true | 151 |

These describe a model as the providers models.dev lists serve it. A user's own endpoint can behave differently.

## Supporting tools is not using them well

Berkeley Function Calling Leaderboard v4 ([data_overall.csv](https://gorilla.cs.berkeley.edu/data_overall.csv), fetched 23 Sep 2026). "FC" is native function calling; "Prompt" means the tools are described in the prompt. None of these was measured on the 4-bit GGUF builds the app ships.

| Model | Mode | Overall | Multi-turn |
|---|---|---|---|
| Qwen3-0.6B | FC | 23.93% | 3.62% |
| Qwen3-1.7B | FC | 28.41% | 11.00% |
| Qwen3-4B-Instruct-2507, not the app's 4B build | FC | 35.68% | 22.12% |
| Qwen3-8B | FC | 42.57% | 41.75% |
| Qwen3-14B | FC | 41.03% | 34.75% |
| Qwen3-32B | FC | 48.71% | 47.87% |
| Gemma-3-4b-it | Prompt | 19.62% | 0.38% |
| Claude-Opus-4-5-20251101 | FC | 77.47% | 68.38% |
| Claude-Opus-4-5-20251101 | Prompt | 33.47% | 16.12% |

A rule based only on tool support would give Qwen3-0.6B, at 3.62% on multi-turn tasks, the same engine as Qwen3-32B.

## Decision

- **opencode** runs a model only if the model is on the tested list and its tool support is confirmed: `supports_tool_calls` from llama-server for a local model, `tool_call: true` for a remote one. The list starts empty.
- **Fixed workflows** ([`04-workflows.md`](04-workflows.md)) run every other model. The formatting step uses the model's own structured output where it has one. For a remote model without it, a local model does the formatting step. With no local text model installed, the workflow parses the reply the way Studio does today.
- Nanbeige4-3B-Thinking and xLAM-2 are not candidates for the list.

## Open questions

- Where the tested list lives, what counts as tested, and who maintains it.
- How a remote model's support is confirmed when models.dev says nothing, or when the user's endpoint differs from what models.dev lists.
- Whether the prompt tiers matter here. A remote model whose listing has no `hugging_face_id` is always classified `frontier` ([selection](../../architecture/local-models/selection.md), Known gaps), so every Featherless model gets frontier prompts today.
