# Engines

> Owns: `surfsense_local/backend/modules/agent/plugin_tools/`, `surfsense_local/backend/modules/chat/plugin_router/`, the `@` mention in the composer, plugin steps in both kinds of thread, Save to Sources, the router test in the [chat eval](../../chat-eval.md).
> Decision for the chat engine: [ADR 0052](../../../adr/0052-the-chat-model-never-calls-tools.md). Gateway: [`01-architecture.md`](01-architecture.md).

The two engines stay as they are: opencode for a model that passes the agent test, the chat engine for every model ([agent](../../../architecture/agent.md), [chat](../../../architecture/chat.md)). Both reach plugins only through the gateway.

## opencode

- Before each turn, [`registration.py`](../../../../surfsense_local/backend/modules/agent/tool_endpoint/registration.py) registers a second MCP server, `plugins`, beside `surfsense`, at `/agent/plugin-tools/workspaces/{workspace}/threads/{thread}`, with the same launch key, `Origin` refusal and 200-second limit.
- The endpoint works like [`tool_endpoint/`](../../../../surfsense_local/backend/modules/agent/tool_endpoint/). `tools/list` is the gateway's `list_tools`, with schemas flattened as SurfSense's own tools are, so small models do not send nested arguments as strings. `tools/call` is `call_tool` with `caller: agent` and a 190-second deadline.
- SurfSense's own tool list, and the test that pins its order, do not change.
- A plugin connected or a tool switched on mid-thread appears at the next turn, which misses the prompt cache once.
- Only `direct` tools are listed, at most 24 per thread, the plugins connected first winning.
- A call shows as a step. [`step-label.tsx`](../../../../surfsense_local/frontend/src/features/agent/step-label.tsx) already labels an unknown tool "Used {tool}"; it gains the plugin's name and the tool's title.
- A call that needs approval waits for it inside its deadline ([`04-trust.md`](04-trust.md#approval)).

## The chat engine: the router step

The chat model never calls a tool ([ADR 0052](../../../adr/0052-the-chat-model-never-calls-tools.md)). Before the answer, SurfSense asks it two small questions, each held to a JSON schema, then makes the call itself. Every text route the chat engine uses already takes a schema, ChatGPT plans included, so plugins add nothing model-specific.

The router runs when the thread is a chat thread, the workspace has a ready `direct` tool with a flat input schema that is not `destructiveHint: true`, and the router is on for the selected model ([below](#when-the-router-is-on)). In `modules/chat/plugin_router/`:

1. **Choose.** One call with the user's message, the last exchange, and each candidate tool's name, title and description, held to `{"tool": <enum of the candidates, plus "none">}`, thinking off. `none` ends the router.
2. **Fill.** One call held to the chosen tool's input schema. A required field it cannot fill ends the router.
3. **Call.** `call_tool` with `caller: chat_router`, a 60-second deadline, and the same approval as the agent.
4. **Answer.** The result joins the final user message as a labelled block after the retrieved passages, so the prompt grows only at its end ([ADR 0049](../../../adr/0049-prompts-grow-at-the-end.md)). Then the normal answer call runs.

A schema is not a guarantee: llama-server rejects one for some chat templates, and some endpoints ignore it. So each reply is validated before anything is called: a choose reply that does not match counts as `none`, a fill reply that does not match ends the router. A router call that fails skips the router. Whenever the router ends early, the turn answers as it does today.

Router calls are model requests like any other: they go through the same route and admission ([ADR 0048](../../../adr/0048-the-api-is-the-only-path-to-a-text-model.md)), and on a ChatGPT plan they count against the user's plan.

### When the router is on

The chat eval gains a router test: questions with the right tool or `none` and the right inputs, run on every curated model. The first row that matches the selected model wins.

| The selected model | Router |
|---|---|
| `structured_output: false` in the catalog | Never |
| Three router replies in a row that did not match their schema | Off, with a notice; the user can turn it back on |
| Failed the router test | Off by default |
| Passed the router test | On by default |
| Remote, with `structured_output: true` in the catalog, or a ChatGPT plan's model | On by default |
| Anything else: local and not yet measured, unknown to the catalog, or a custom connection's model | Off by default |

Where it is off by default, Settings → Plugins offers "Let the chat use plugins on its own" for that model.

## `@` mentions

- Typing `@` in the composer lists ready tools as `@<plugin> <tool>`.
- A mention skips choose. Where the router is on for the model, the model fills the inputs; where it is off, or a fill reply fails its schema, the composer shows the tool's inputs as a form, filled from the message where it can be, for the user to complete. So a mention works on every model.
- In a chat thread the call's result joins the answer as in step 4. In an agent thread the call is made before the turn, and its result is in the agent's prompt.
- The mention is the user's approval for that one call, unless the tool is `destructiveHint: true`.

## Results

- A call is a step in the message in both kinds of thread: the tool's title, the plugin's name, a one-line summary, and the result when expanded. A chat message gains steps the way an agent message has them today.
- The model gets the result trimmed to 20 KB ([`01-architecture.md`](01-architecture.md#results)); the step shows all of it.
- Reopening a thread shows its steps from `plugin_calls`, without calling anything again.

## Save to Sources

- A step has "Save to Sources". It writes a note with the result as markdown and `document_metadata` naming `plugin_id`, `tool`, `call_id` and `fetched_at` ([documents](../../../architecture/documents.md)).
- Saving the result of the same tool with the same arguments again updates that note in place and its `fetched_at`, rather than adding a copy.
- Nothing is saved without the user asking.

## Acceptance

- An agent thread with a test plugin connected: the agent calls its tool, the step shows the plugin and title, and SurfSense's own tool list is unchanged.
- A plugin tool switched off disappears from the next turn's `tools/list`.
- A chat thread with the router on: a question that fits the test tool calls it and answers from its result; a question that does not gets `none` and a normal answer, with one extra model call.
- A model with `structured_output: false` never runs the router, and `@` on it opens the input form.
- A local model whose template rejects the schema, and an endpoint that ignores `response_format`, both end with no tool call and a normal answer.
- Three mismatched router replies in a row switch the router off for that model, with a notice.
- `@test search cats` in a chat thread on Qwen3-0.6B, with the router off, opens the form with `cats` filled in; sending it calls the tool without asking for approval.
- Save to Sources twice on the same call leaves one note, with the later `fetched_at`.
