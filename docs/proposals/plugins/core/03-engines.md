# Engines

> Owns: `surfsense_local/backend/modules/agent/plugin_tools/` (what each turn gives opencode), the `@` mention in the agent composer, plugin steps in agent threads, Save to Sources.
> Later: the chat engine's router step, [below](#the-chat-engine-later), decided by [ADR 0052](../../../adr/0052-the-chat-model-never-calls-tools.md). Gateway: [`01-architecture.md`](01-architecture.md).

Plugins reach agent threads first. A thread opened in Agentic mode is opencode's, and opencode is an MCP client already, so it calls plugin servers itself. A thread in Basic mode is the chat engine's, which never calls tools; it gets plugins later, through a router step of its own ([below](#the-chat-engine-later)). The two engines stay as they are ([agent](../../../architecture/agent.md#which-threads-get-it), [chat](../../../architecture/chat.md)).

Agentic mode is offered only for models tested with opencode, so a user on a chat-only model has no plugins until the chat engine gets them. Settings → Plugins says so: "Plugins work in Agentic threads."

## opencode

opencode connects to plugin servers itself, through its own MCP client, and SurfSense decides everything it may do there. SurfSense is the controller, not a hop: it is in no call's path, so a call is as fast as opencode's own, its session stays open across calls, and progress, cancellation and images work as opencode handles them.

### Each turn

Before each turn, [`registration.py`](../../../../surfsense_local/backend/modules/agent/tool_endpoint/registration.py), which already gives the thread's opencode SurfSense's own tools, also gives it:

- **The ready plugins' servers.** Each plugin connected, switched on, with its hosts allowed and, if third-party, third-party plugins allowed, is given to opencode under its id: its URL, its sign-in as headers from the encrypted credential, opencode's own OAuth off, and a 200-second limit, as SurfSense's own tools have. It is given only when opencode's `GET /mcp` does not already show it connected, since giving a server again opens a new MCP session and a stateful plugin would lose its state. opencode keeps the credential in memory only. A plugin that is not ready is not given, so none of its tools reach the agent. With no ready plugin, nothing is given.
- **A rule per tool.** opencode names a server's tools `<plugin>_<tool>` and takes an `allow`, `ask` or `deny` rule per name, the last match winning. The rules are set on the thread's opencode session (`PATCH /session/{id}`) and apply from its next call, with no restart. SurfSense writes `<plugin>_*: deny` first, so a tool it has not reviewed is refused, then each recorded tool's own rule from the user's setting and the gateway's approval rules ([`04-trust.md`](04-trust.md#approval)). opencode leaves a denied tool out of what it lists to the model, so a blocked tool is neither called nor seen.
- **A check for changed tools.** SurfSense lists each ready plugin with its own MCP client ([`../remote/01-mcp-client.md`](../remote/01-mcp-client.md)) and records the listing in `plugin_tools`, so the rule for tools added later applies: a new tool starts blocked, and a tool whose description changes or whose annotations become less safe is blocked until the user allows it again ([`02-registry.md`](02-registry.md#tools-added-later)). It runs when the plugin is connected and before a turn, at most once per plugin every few minutes.

A plugin connected, or a tool's setting changed, mid-thread takes effect at the next turn, which misses the prompt cache once. SurfSense's own tools, and the test that pins their order, do not change. At most 24 plugin tools are given a turn, the plugins connected first winning.

### Asking and recording

- **Approval** is opencode's: a tool whose rule is `ask` is asked about on its step, inline in the reply, as the agent's other approvals are ([`04-trust.md`](04-trust.md#approval)).
- **The record is opencode's.** Each call, its arguments and its result are kept in the thread's opencode session, which SurfSense already reads to show the thread. SurfSense keeps no copy.
- **A server opencode could not reach.** After giving the servers, the turn reads opencode's `GET /mcp`. A plugin it reports as `failed` or `needs_auth` is named in the thread, "Couldn't reach Notion" or "Sign in to Notion again", so the agent's missing tools are explained. Settings → Plugins shows the result of SurfSense's own last listing, not this, since opencode knows only the servers a thread has been given, and only while it runs.
- **Its way out.** opencode reaches plugin hosts only through SurfSense's proxy, where its proxy variables point: a `CONNECT` tunnel to a ready plugin's host, checked on each connection, and nothing else, so TLS runs from opencode to the plugin and SurfSense sees the host, never the content. A host revoked or a plugin switched off mid-turn is refused at opencode's next connection; one already open runs until it closes. A remote plugin must therefore be on HTTPS.
- **Limits accepted for speed.** opencode reads a tool's description from its server, so the description is not cut to 2,000 characters for the agent; it reaches the model only once the tool has been reviewed, and a change to it blocks the tool.

## `@` mentions

The user can name a plugin rather than leave the choice to the agent.

- Typing `@` in the agent composer lists ready plugins, through assistant-ui's composer trigger popover, and picking one writes `@notion`, the plugin's id, into the message. A plugin is named, not a tool: the user thinks in apps, and the agent picks among a plugin's tools from their descriptions.
- The turn gives opencode every ready tool of the mentioned plugin, even beyond the 24, and a note beside the user's words, as the scope note goes, says: "The user asked you to use the Notion plugin for this." The turn's other tools stay offered, and a plugin that is not ready changes nothing.
- The agent fills the inputs and makes the calls, as with any tool, so a mention needs no form and no model call of its own.
- Approval is unchanged: the agent chose the inputs, not the user, so a call asks as [`04-trust.md`](04-trust.md#approval) says.

## Results

- A call is a step in the agent's message, from opencode's own record of the call. A plugin step, a tool named `<plugin>_<tool>`, shows the tool's title, the plugin's name, a one-line summary, and the whole result when expanded. [`step-label.tsx`](../../../../surfsense_local/frontend/src/features/agent/step-label.tsx), which labels an unknown tool "Used {tool}", gains the plugin's name and the tool's title.
- Progress the plugin reports shows on the running step, as opencode passes it on.
- Reopening a thread shows its steps from its opencode session, without calling anything again.

## Save to Sources

- A step has "Save to Sources". It writes a note with the step's result as markdown and `document_metadata` naming `plugin_id`, `tool`, the thread and opencode's id for the step, and `fetched_at` ([documents](../../../architecture/documents.md)).
- Saving the result of the same tool with the same arguments again updates that note in place and its `fetched_at`, rather than adding a copy.
- Nothing is saved without the user asking.

## Acceptance

- An agent thread with a test plugin connected: through the real opencode, the agent calls its tool on the plugin's server directly, the step shows the plugin and title, and reopening the thread shows it again from opencode's session. SurfSense's own tools are unchanged.
- A tool set to Block, and a plugin switched off or not ready, never reach the agent; with no ready plugin, the turn is given none.
- A tool the server adds after connect is refused until the user allows it, and so is a tool whose description changes.
- A tool set to Ask is asked about on its step in the reply, showing its inputs; Deny ends the call refused, and Allow once runs it.
- Two calls to a stateful test server in one turn share one session.
- A plugin on HTTPS is reached through SurfSense's proxy, and with the proxy refusing it, it is named unreachable.
- A plugin whose server stops answering after it was listed is named in the thread as unreachable, and the turn goes on without its tools.
- `@test` in an agent thread gives the agent every ready tool of the test plugin that turn, past the 24, and the agent calls one; a call that must be approved still asks.
- A thread in Basic mode is given no plugin tools, and Settings → Plugins says plugins work in Agentic threads.
- Save to Sources twice on the same call leaves one note, with the later `fetched_at`.

## The chat engine (later)

Not built until plugins reach Basic threads. The design is kept here so it can be picked up as it stands.

The chat engine has no opencode session to keep its calls, and calls plugin servers through SurfSense, so it brings with it what only it needs, restored from git history, where it was first built and tested:

- **`plugin_calls`**, in its first migration: one row per call, with its workspace, thread and message, its caller, the plugin and tool, the arguments, its status (`waiting_approval`, `running`, `succeeded`, `failed`, `denied`, `cancelled`), the whole result and any error. It keeps no foreign key to the plugin, so a past call stays in its thread after a disconnect, and the chat's steps, whole results and Save to Sources read from it.
- **The gateway's `call_tool`**: arguments checked against the tool's schema, approval taken from the caller, the call recorded, the result trimmed to 20 KB for the model and stored whole, a source's failure a sentence and never an exception.
- **The client's calls**: progress passed up, a deadline that tells the server to stop, and a call never resent, since the server may have acted.
- **Connections kept open** per plugin ([`06-later.md`](06-later.md)), so its calls skip a handshake each.

The chat model never calls a tool ([ADR 0052](../../../adr/0052-the-chat-model-never-calls-tools.md)). Before the answer, SurfSense asks it two small questions, each held to a JSON schema, then makes the call itself. Every text route the chat engine uses already takes a schema, ChatGPT plans included, so plugins add nothing model-specific.

The router runs when the thread is a chat thread, the workspace has a ready `direct` tool with a flat input schema that is not `destructiveHint: true`, and the router is on for the selected model ([below](#when-the-router-is-on)). In `modules/chat/plugin_router/`:

1. **Choose.** One call with the user's message, the last exchange, and each candidate tool's name, title and description, held to `{"tool": <enum of the candidates, plus "none">}`, thinking off. `none` ends the router.
2. **Fill.** One call held to the chosen tool's input schema. A required field it cannot fill ends the router.
3. **Call.** `call_tool` with `caller: chat_router`, a 60-second deadline, and the same approval as the agent.
4. **Answer.** The result joins the final user message as a labelled block after the retrieved passages, so the prompt grows only at its end ([ADR 0049](../../../adr/0049-prompts-grow-at-the-end.md)). Then the normal answer call runs.

A schema is not a guarantee: llama-server rejects one for some chat templates, and some endpoints ignore it. So each reply is validated before anything is called: a choose reply that does not match counts as `none`, a fill reply that does not match ends the router. A router call that fails skips the router. Whenever the router ends early, the turn answers as it does today.

Router calls are model requests like any other: they go through the same route and admission ([ADR 0048](../../../adr/0048-the-api-is-the-only-path-to-a-text-model.md)), and on a ChatGPT plan they count against the user's plan. Each costs one or two model calls when tools are ready, and how well small models choose is unmeasured.

### When the router is on

The [chat eval](../../chat-eval.md) gains a router test: questions with the right tool or `none` and the right inputs, run on every curated model. The first row that matches the selected model wins.

| The selected model | Router |
|---|---|
| `structured_output: false` in the catalog | Never |
| Three router replies in a row that did not match their schema | Off, with a notice; the user can turn it back on |
| Failed the router test | Off by default |
| Passed the router test | On by default |
| Remote, with `structured_output: true` in the catalog, or a ChatGPT plan's model | On by default |
| Anything else: local and not yet measured, unknown to the catalog, or a custom connection's model | Off by default |

Where it is off by default, Settings → Plugins offers "Let the chat use plugins on its own" for that model.

### `@` mentions in chat threads

A mention skips choose. Where the router is on for the model, the model fills the inputs; where it is off, or a fill reply fails its schema, the composer shows the tool's inputs as a form, filled from the message where it can be, for the user to complete, so a mention works on every model. The call's result joins the answer as in step 4. A mention whose inputs the user completed in the form is the user's approval for that one call, unless the tool is `destructiveHint: true`.

### Acceptance, when built

- A chat thread with the router on: a question that fits the test tool calls it and answers from its result; a question that does not gets `none` and a normal answer, with one extra model call.
- A model with `structured_output: false` never runs the router, and `@` on it opens the input form.
- A local model whose template rejects the schema, and an endpoint that ignores `response_format`, both end with no tool call and a normal answer.
- Three mismatched router replies in a row switch the router off for that model, with a notice.
- `@test search cats` in a chat thread on Qwen3-0.6B, with the router off, opens the form with `cats` filled in; sending it calls the tool without asking for approval.
