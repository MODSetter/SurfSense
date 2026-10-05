# Model capabilities

What a chat model may do follows from what SurfSense measured of it, never from its size or its prompt tier. A list shipped with the app gives each measured model one of four levels; one function reads it for the selected model and its connection; the engine choice and Studio's Word and PDF path follow the level. An unmeasured model keeps what it has today, labelled "Not measured"; only a measured failure takes something away ([05](../proposals/file-agent/05-model-ladder-and-evals.md), decision 7).

**Code:** [`surfsense_local/backend/modules/llm/capability/`](../../surfsense_local/backend/modules/llm/capability/), [`surfsense_local/backend/scripts/capability_list/`](../../surfsense_local/backend/scripts/capability_list/), [`surfsense_local/frontend/src/features/models/capability/`](../../surfsense_local/frontend/src/features/models/capability/)

## The levels

| Level | Means | New chats | Studio's Word and PDF |
|---|---|---|---|
| `agent` | measured, and passed the bar | the agent | a script |
| `agent_limited` | measured, near the bar | the agent, labelled "may need nudges" | a script |
| `studio_only` | measured, and failed | the chat | Markdown |
| `not_measured` | no row holds for it | the chat, or the agent once the user turns on "Try the agent" | Markdown served from this computer, a script from a remote host |

The bar, in [`verdict.py`](../../surfsense_local/backend/scripts/capability_list/verdict.py): the smoke and the multi-turn demo pass, at least 80% of the counted cases pass, and no failure was "made no document" or "looped". Near the bar is the same with at least 60%. Anything else measured is `studio_only`. A case that needs image input is not counted against a text-only model, and a case a gate stopped counts as not passed.

## The list

[`measured/capabilities.json`](../../surfsense_local/backend/modules/llm/capability/measured/capabilities.json), schema version 1 ([`schema.py`](../../surfsense_local/backend/modules/llm/capability/measured/schema.py)), is read once per process and never fetched; a list that fails to load makes every model `not_measured`. Each row holds the canonical key, its matching rules (`match.keys`, and `match.served`: where the model must be served for the row to hold), the level, the suite and its version, the date, the provider and host the runs went through, the id they sent, `reads_images`, the pass counts and a one-line English note. The whole list carries `provisional`.

Today's list is the 11 models of the first ladder results ([08](../proposals/file-agent/08-model-ladder-results.md)), suite `create-and-edit` v1, screening runs of one per cell, so it is provisional: Sonnet 5.5, Opus 5.5, Kimi K3, GLM-5.3, DeepSeek V4 Pro and Qwen3.8-27B are `agent`; Haiku 4.5 is `agent_limited`; Qwen3.6-35B-A3B, Gemma 4 31B, Ministral 14B and Qwen3.5-9B are `studio_only`.

The list is written, never edited: `python scripts/write_capability_list.py [results.json]` (from `surfsense_local/backend`, with `.` on the path) applies the bar to a ladder results file and rewrites it. The input's shape is in [`ladder_input.py`](../../surfsense_local/backend/scripts/capability_list/ladder_input.py): per model, the id sent, provider, host, where it was served, date, `reads_images`, a note, and one outcome per case (`pass`, `fail`, `fail:<behaviour>` from [08's grouping of failures](../proposals/file-agent/08-model-ladder-results.md#what-the-failures-point-to), `n/a`, `not_run`). The committed input is `capability_list/ladder/create-and-edit-v1.json`, and a test fails when the shipped list is not what the generator writes from it.

## Matching

`capability_of(model, connection)` in [`resolve.py`](../../surfsense_local/backend/modules/llm/capability/resolve.py) is synchronous and offline. It reduces the id to a canonical key ([`model_key.py`](../../surfsense_local/backend/modules/llm/capability/model_key.py)): lower case, the provider prefix and a `@` version dropped, OpenRouter's routing suffixes (`:free`, `:nitro`, `:floor`) dropped, a dot between digits made a hyphen, and an eight-digit snapshot date dropped. So `claude-haiku-4-5` and `claude-haiku-4-5-20251001` on Anthropic and `anthropic/claude-haiku-4.5` on OpenRouter are one model. An id starting with `~` or ending in `latest` is an alias and never measured (reason `alias`). Any other suffix, such as `:thinking`, keeps its own key.

A pass holds only where it was measured. Every row today was measured on a remote host, so a model served from this computer (llama.cpp, or a loopback connection such as Ollama or LM Studio) or from a server on the user's own network (a private, link-local or carrier-grade NAT address, a single-label name, or a `.local`, `.lan`, `.internal` or `.home.arpa` name) with a passing row is `not_measured`, reason `measured_elsewhere`: a quantized copy there is a measurement not yet made. Such a server counts as `local` for `match.served` only; Studio's rule for a model not measured still counts it remote. A failure holds everywhere, since a copy of one's own is the same model or a smaller one.

The result carries the level, a `Reason(code, values)` (`measured_pass`, `measured_near` or `measured_fail` with the pass counts, suite version and date; `measured_elsewhere` with the host; `alias`; `no_row`) and the row.

## What follows from it

- **Engine choice** ([`engine_choice.py`](../../surfsense_local/backend/modules/agent/engine_choice.py)): `agent` and `agent_limited` run the agent; `studio_only` never does; `not_measured` only with the user's opt-in. The model must then call tools and fit the agent: for a remote model the catalog's `tool_call` (a stated `false` refuses; unknown refuses an opted-in model, not a measured one) and `context` at or above 32,768 tokens; for a local model, llama-server's `supports_tool_calls` and loaded window ([`agent_gate.py`](../../surfsense_local/backend/modules/llm/capability/agent_gate.py)). `SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1` still lets every model in, held only to a stated no on tool calls.
- **Studio** ([`strength.py`](../../surfsense_local/backend/worker/studio/office/document/strength.py)): `writes_script()` is true for `agent` and `agent_limited`, false for `studio_only`, and the local or remote rule for `not_measured`.

## The opt-in

"Try the agent" is stored under `agent_trial` in the text selection's `settings` ([`agent_trial.py`](../../surfsense_local/backend/modules/llm/capability/agent_trial.py)), so it belongs to that model and is cleared when the slot takes another. It is offered only on a `not_measured` model whose catalog row does not rule it out; a local model's tool calls and window are checked when a chat starts, since reading them would load the model.

## API

- `SelectionRead.capability` on `GET` and `PUT /llm/selection/text_gen` (null for other slots): `level`, `label_key` (the ICU select branch), `reason` (`code`, `values`), `note`, `measured` (`key`, `suite_version`, `measured_on`, `provider`, `host`, `reads_images`, `passed`, `counted`, `provisional`, or null) and `agent_trial` (`offered`, `enabled`, `blocked`: `tool_calls_unconfirmed`, `window_below_floor` or null).
- `capability_level` on each row of `GET /llm/connections/{id}/models` and `GET /llm/providers/llamacpp/models` that can fill the chat slot.
- `PUT /llm/selection/text_gen/agent-trial` with `{"enabled": bool}` answers the selection's capability. Turning it on answers `409` with `code` `measured` for a measured model, or the `blocked` code; `404` when no chat model is chosen.

The model picker labels each chat model "Agent", "Agent, may need nudges", "Studio only" or "Not measured". Settings › Models shows the chat model's level, its evidence line and note, and for a model not measured the "Try the agent" switch with one sentence of warning.

## Known gaps

- Every row is screening (n=1) on OpenRouter's default routing or Anthropic's compatibility layer; 05's committed rows, three runs per cell with the provider order pinned, replace it.
- No row is measured on this computer, so every local model is `not_measured`; llama.cpp runs need a `served: local` row.
- The matrix runner writes per-run `result.json` files, not the ladder input; each column is mapped by hand, triage labels included.
- The row's note is English; the interface shows it untranslated.
