# Chat on a Claude plan

> `ClaudePlanProvider` implements the [`Generator`](../../../surfsense_local/backend/modules/llm/providers/protocols.py) protocol over Claude Code run with no tools and one turn per answer, so chat, titles and Studio use a Claude plan model exactly as they use any other. It runs only in the API process ([ADR 0048](../../adr/0048-the-api-is-the-only-path-to-a-text-model.md)); the workers reach it through `/internal/models/text/generate` as they reach every model.

Part of [Use your Claude plan](README.md). Launch options, errors and network are in [`01-connection.md`](01-connection.md).

## Wiring

- [`text_generator.py`](../../../surfsense_local/backend/modules/llm/connections/text_generator.py): `connection_generator()` returns `ClaudePlanProvider(connection)` for `auth_kind == "claude_plan"`, beside the ChatGPT branch.
- [`listing.py`](../../../surfsense_local/backend/modules/llm/connections/listing.py): `connection_models()` returns the cached [model list](01-connection.md#models).
- [`call_route.py`](../../../surfsense_local/backend/modules/llm/connections/call_route.py) is not consulted: a Claude plan has no HTTP route of SurfSense's.

## One answer

`chat_deltas(model, messages, *, max_tokens, temperature, reasoning, json_schema, conversation)` launches through `launch.py` with:

| Option | Value |
|---|---|
| `model` | the model's `value`, such as `sonnet` |
| `tools` | `[]` ([ADR 0052](../../adr/0052-the-chat-model-never-calls-tools.md)) |
| `max_turns` | `1`; `3` with a `json_schema` ([Structured output](#structured-output)) |
| `system_prompt` | the first `system` message, whole. Claude Code's own prompt is not sent: 652 tokens were cached on a first request, against Claude Code's tens of thousands |
| `include_partial_messages` | `True`, so text streams |
| `extra_args` | `{"no-session-persistence": None}`: nothing written under `~/.claude/projects` |
| `cwd` | an empty directory under SurfSense's data folder, so no project file is near |
| `thinking`, `effort` | `reasoning` on: `{"type": "adaptive", "display": "summarized"}`; off: no `display`, so thinking is omitted. Thinking streams only with `summarized` |

Each `content_block_delta` of type `text_delta` becomes `Delta(text)`, and of type `thinking_delta` `Delta(text, reasoning=True)`. `chat()` drops the reasoning, as the ChatGPT provider does. The stream keeps the existing deadlines (`with_deadlines`): 300 seconds to the first token, 30 between.

`max_tokens` and `temperature` are dropped: Claude Code exposes neither.

## Structured output

`json_schema` maps to the SDK's `output_format`, `{"type": "json_schema", "schema": …}`, and the answer is `ResultMessage.structured_output`, not streamed text. This is what the chat engine's router step and Studio's workflows ask for, so both run on a Claude plan model; each router call counts against the plan, as on a ChatGPT plan ([ADR 0052](../../adr/0052-the-chat-model-never-calls-tools.md)).

Claude Code returns structured output through a tool of its own, `StructuredOutput`, which its init message lists even with `tools=[]`. It is how the answer comes back, not a tool SurfSense gives the model, so ADR 0052 holds: the model still calls nothing SurfSense runs. The tool call and its result take a second turn, so a call with a schema allows three: with `max_turns=1` the call ended `error_max_turns`, and four of eleven calls used three turns.

Measured on haiku and sonnet with `permission_mode="default"` and `tools=[]`: picking one of three tools or `none` chose right in every case, `none` included for a request no tool fits; filling a flat input schema gave `{"city": "Pune", "days": 3}`; asked for 10 days against a `maximum` of 7, it returned 7. All eleven outputs validated against their schemas. A call took 1.6 to 2.4 s, and 3.4 to 6.7 s when the model thought first.

## History

The protocol is stateless: every call carries the whole conversation. A Claude Code client, once open, keeps its own. Both are honoured:

- **A new conversation, or one that changed.** The earlier turns go into the prompt as text, tagged by role, with the last user message after them. Measured: a remembered fact from two turns back answered correctly in 1.4 s.
- **The same conversation, one user message longer.** When `conversation` names an open client whose last call's messages are a prefix of this call's, only the new user message is sent. Measured: 0.9 s to the first token, against 2.3 s for a new client.

Anything else (an edited message, a retry, a regenerated reply, a changed system prompt, another model or schema) closes that client and starts again from text. The client keeps the messages it was last sent to tell these apart; the reply's own text is not compared, since the chat stores it after resolving citations. The newest message's images go beside its text as image blocks: measured, the model named the colour of a picture sent this way. Earlier turns are sent as text only. This is [`chat_prompt.py`](../../../surfsense_local/backend/modules/llm/subscriptions/claude/chat_prompt.py).

## The client pool

Clients are kept per `conversation` key in one pool for the API process ([`chat_runs.py`](../../../surfsense_local/backend/modules/llm/subscriptions/claude/chat_runs.py)), since a provider is made per request. They are closed after five minutes idle and capped at four; the least recently used idle one goes first, and a client answering is never closed. A client joins the pool when it opens, so a second message on the same conversation sent while it answers sees it busy and gets a client of its own, answered from the whole conversation and closed after. A call with no `conversation` (a title, a Studio step) opens a client, answers and closes it. Three conversations at once took 1.7 s wall. The pool closes every client when the API stops.

## The rest of the protocol

| Member | Answer |
|---|---|
| `name` | `"claude_plan"` |
| `health()` | the [status](01-connection.md#status); `ready` is healthy |
| `models()` | Claude Code's list, read live ([`01-connection.md`](01-connection.md#models)) |
| `context_tokens(model)` | the remote manifest's window for the model under `anthropic`; `None` for a model it does not carry, such as Haiku 5.5 today |
| `sees_images(model)` | the manifest's answer under `anthropic`, as for any Anthropic model |
| `token_count(model, text)` | `None` |

## Open questions

- Whether one warm client can answer an unrelated call in a new session (`query(session_id=…)`), which would let titles skip the cold start.
