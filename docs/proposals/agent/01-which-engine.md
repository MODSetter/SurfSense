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
- Both chat providers accept a `json_schema`, and only Studio's quiz and flashcards pass one yet ([selection](../../architecture/local-models/selection.md), Known gaps).

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

## When a thread gets its engine

- The agent sits in the chat panel: same thread list, same composer, no separate entry. With the list empty and most local models off it, a separate entry would do nothing for most users, and the engine is the model's to decide, not the user's.
- A thread gets its engine when it is created, from the model selected then, and keeps it. The text model is one setting for the whole app ([selection](../../architecture/local-models/selection.md)), so a thread cannot follow it: half its turns would sit in `chat_messages` and half in opencode's session, and neither engine would see the other half ([`03-opencode.md`](03-opencode.md), The conversation).
- In a thread that uses opencode, choosing another model on the list continues the thread, because opencode takes the model with each prompt ([`groups/session.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/server/routes/instance/httpapi/groups/session.ts)). Choosing a model that is not on the list makes the composer say this thread cannot continue with it, and offer a new thread.
- An agent turn shows its steps, such as searched, read and created, as lines the user can expand, and the permission dialog opens over the thread.
- With a model on the list, a quick question also goes through the agent: a few model calls instead of one.

## What tested means

- A model is tested, and runs opencode, at a window of 32,768 tokens or more. At 8,192, opencode starts compacting at 6,144 tokens ([`03-opencode.md`](03-opencode.md), Configuration), and its prompt and tool descriptions alone are about 20,000 characters.
- The test runs with a fixed seed and temperature 0, one instruction per turn. A model passes when it:
  - answers a one-word reply;
  - carries out a two-turn task through `search_sources` and `create_artifact`;
  - shows on its second turn that llama-server reused its prompt cache.
- Each run has a wall-clock limit, and a run that passes it has opencode's process group killed and counts as failed.

## Open questions

- Where the tested list lives and who maintains it.
- How a remote model's support is confirmed when models.dev says nothing, or when the user's endpoint differs from what models.dev lists.
- Whether the prompt tiers matter here. A remote model whose listing has no `hugging_face_id` is always classified `frontier` ([selection](../../architecture/local-models/selection.md), Known gaps), so every Featherless model gets frontier prompts today.
