# Engines

> Owns: `surfsense_local/backend/modules/agent/plugin_tools/`, `surfsense_local/backend/modules/chat/plugin_router/`, the `@` mention in the composer, plugin steps in both kinds of thread, Save to Sources, the router test in the [chat eval](../chat-eval.md).
> Decision for the chat engine: [ADR 0052](../../adr/0052-the-chat-model-never-calls-tools.md). Gateway: [`01-architecture.md`](01-architecture.md).

The two engines stay as they are: opencode for a model that passes the agent test, the chat engine for every model ([agent](../../architecture/agent.md), [chat](../../architecture/chat.md)). Both reach plugins only through the gateway.

## opencode

- Before each turn, beside `surfsense`, [`registration.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/registration.py) registers a second MCP server, `plugins`, at `/agent/plugin-tools/workspaces/{workspace}/threads/{thread}`, with the same launch key, the same refusal of any request carrying an `Origin` header, and the same 200-second call limit.
- That endpoint answers `initialize`, `tools/list`, `tools/call` and `ping` as [`tool_endpoint/`](../../../surfsense_local/backend/modules/agent/tool_endpoint/) does, stateless and JSON only. `tools/list` is the gateway's `list_tools` for the thread's workspace, each tool's schema flattened the way SurfSense's own tools are, so small models do not send nested arguments as strings. `tools/call` is `call_tool` with `caller: agent` and a 190-second deadline.
- SurfSense's own tool list, and the test that pins its order, do not change. A second server keeps plugin tools from shifting it.
- A plugin connected or a tool switched on mid-thread appears at the next turn. That changes the tools opencode sends, so that turn misses the prompt cache once.
- Only tools with `exposure: direct` are listed, at most 24 per thread, the plugins connected first winning. Finding the rest through a search tool is later work ([`07-later.md`](07-later.md)).
- A call shows as a step. [`step-label.tsx`](../../../surfsense_local/frontend/src/features/agent/step-label.tsx) already labels an unknown tool "Used {tool}"; it gains the plugin's name and the tool's title.
- When a call needs approval, the gateway raises SurfSense's own permission request on the thread ([`05-trust.md`](05-trust.md#approval)), and the call waits inside its deadline.

## The chat engine: the router step

The chat model never calls a tool. Before the answer, SurfSense asks it two small questions under a JSON schema, then calls the tool itself. Every text provider already takes a schema, local and remote ([below](#models-and-routes)), so no tool-calling support is needed.

It runs when all hold:

- the thread is a chat thread;
- the workspace has at least one ready tool with `exposure: direct`, a flat input schema, and is not `destructiveHint: true`;
- the router is on for the selected model ([below](#when-the-router-is-on)).

Steps, in `modules/chat/plugin_router/`:

1. **Choose.** One call with the user's message, the last exchange, and each candidate tool's qualified name, title and description. The schema is `{"tool": <enum of the candidates, plus "none">}`. Thinking is off for this call. `none` ends the router, and the turn goes on as today.
2. **Fill.** One call with the user's message and the chosen tool's input schema as the response schema. A required field it cannot fill ends the router with no call.

Each reply is validated against its schema before anything is called. A choose reply that does not match counts as `none`; a fill reply that does not match ends the router with no call. Nothing is guessed or repaired. A router call that fails skips the router, and the turn answers as today.
3. **Call.** `call_tool` with `caller: chat_router` and a 60-second deadline, through the same approval as the agent.
4. **Answer.** The result joins the turn as a labelled block in the final user message, after the retrieved passages and before the question, so the prompt still grows only at its end ([ADR 0049](../../adr/0049-prompts-grow-at-the-end.md)). Then the normal single answer call runs.

The router's calls go through the same model route and admission as every other call ([ADR 0048](../../adr/0048-the-api-is-the-only-path-to-a-text-model.md)).

### When the router is on

The chat eval gains a router test: questions with the right tool or `none`, and the right inputs, run on every curated model.

| The selected model | Router |
|---|---|
| Passed the router test | On by default |
| Remote, with `structured_output: true` in the catalog, or a ChatGPT plan's model | On by default |
| Local and not yet measured, or any model the catalog says nothing about (`None`), or a custom connection's model | Off by default; Settings → Plugins offers "Let the chat use plugins on its own" for that model |
| `structured_output: false` in the catalog | Never |
| Three router replies in a row that do not match their schema | Switched off for that model, with a notice; the user can turn it back on |

`@` mentions work on every model either way ([below](#-mentions)).

## Models and routes

Plugins add nothing model-specific. The router uses the chat engine's existing JSON-schema support, which every text route already has, local, OpenAI-compatible and `/responses`, ChatGPT plans included; how each route sends the schema is the provider's concern ([chat](../../architecture/chat.md), [ChatGPT subscription](../../architecture/chatgpt-subscription.md)). opencode reaches plugin tools as MCP tools and handles each model as it already does ([agent](../../architecture/agent.md)).

What plugins do own:

- A schema is not a guarantee: llama-server rejects one for some chat templates, and some endpoints ignore it. So every router reply is validated ([above](#the-chat-engine-the-router-step)).
- Whether the router runs depends on the model ([above](#when-the-router-is-on)).
- Each router call is a model request like any other, so on a ChatGPT plan it counts against the user's plan.

## `@` mentions

- Typing `@` in the composer lists ready tools as `@<plugin> <tool>`.
- A message with a mention skips the choose step: the router runs fill, call and answer for the named tool, in a chat thread on any model, and the agent gets the same call made before its turn in an agent thread, with the result in its prompt.
- Filling still needs a schema. On a model whose router is off, or when a fill reply does not match the schema, the composer shows the tool's inputs as a small form, filled from the message where it can be, which the user completes and sends. So a mention works on every model, local or remote.
- The mention counts as the user's approval for that one call, unless the tool is `destructiveHint: true`.

## Results

- A call is a step in the message in both kinds of thread: the tool's title, the plugin's name, a one-line summary, and the result when expanded. A chat message gains steps the way an agent message has them today.
- The model gets the result trimmed to 20 KB ([`01-architecture.md`](01-architecture.md#results)); the step shows all of it.
- Reopening a thread shows its steps from `plugin_calls`, without calling anything again.

## Save to Sources

- A step has "Save to Sources". It writes a note with the result as markdown and `document_metadata` naming `plugin_id`, `tool`, `call_id` and `fetched_at` ([documents](../../architecture/documents.md)).
- Saving the result of the same tool with the same arguments again updates that note in place and its `fetched_at`, rather than adding a copy.
- Nothing is saved without the user asking.

## Acceptance

- An agent thread with a test plugin connected: the agent calls its tool, the step shows the plugin and title, and SurfSense's own tool list is unchanged.
- A plugin tool switched off disappears from the next turn's `tools/list`.
- A chat thread with the router on: a question that fits the test tool calls it and answers from its result; a question that does not gets `none` and a normal answer, with one extra model call.
- A model with `structured_output: false` never runs the router, and `@` on it opens the input form.
- A local model whose template rejects the schema, and an endpoint that ignores `response_format`, both end with no tool call and a normal answer.
- Three mismatched router replies in a row switch the router off for that model, with a notice.
- `@test search cats` in a chat thread on Qwen3-0.6B calls the tool with `cats` without asking for approval.
- Save to Sources twice on the same call leaves one note, with the later `fetched_at`.
