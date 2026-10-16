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
| `max_turns` | `1` |
| `system_prompt` | the first `system` message, whole. Claude Code's own prompt is not sent: 652 tokens were cached on a first request, against Claude Code's tens of thousands |
| `include_partial_messages` | `True`, so text streams |
| `extra_args` | `{"no-session-persistence": None}`: nothing written under `~/.claude/projects` |
| `cwd` | an empty directory under SurfSense's data folder, so no project file is near |
| `thinking`, `effort` | `reasoning` on: `{"type": "adaptive", "display": "summarized"}`; off: no `display`, so thinking is omitted. Thinking streams only with `summarized` |

Each `content_block_delta` of type `text_delta` becomes `Delta(text)`, and of type `thinking_delta` `Delta(text, reasoning=True)`. `chat()` drops the reasoning, as the ChatGPT provider does. The stream keeps the existing deadlines (`with_deadlines`): 300 seconds to the first token, 30 between.

`max_tokens` and `temperature` are dropped: Claude Code exposes neither. `json_schema` maps to the SDK's `output_format`, which is untested and listed under [Open questions](#open-questions); until it is tested, a caller asking for a schema on a Claude plan model gets the same refusal a ChatGPT plan gave before [ADR 0050](../../adr/0050-a-model-answers-on-its-own-route-with-its-connections-credential.md).

## History

The protocol is stateless: every call carries the whole conversation. A Claude Code client, once open, keeps its own. Both are honoured:

- **A new conversation, or one that changed.** The earlier turns go into the prompt as text, tagged by role, with the last user message after them. Measured: a remembered fact from two turns back answered correctly in 1.4 s.
- **The same conversation, one user message longer.** When `conversation` names an open client whose last call's messages are a prefix of this call's, only the new user message is sent. Measured: 0.9 s to the first token, against 2.3 s for a new client.

Anything else (an edited message, a retry, a regenerated reply, a changed system prompt) closes that client and starts again from text. A digest of the messages last sent is kept with the client to tell these apart.

## The client pool

Clients are kept per `conversation` key, closed after five minutes idle, and capped at four; the least recently used goes first. Three conversations at once took 1.7 s wall. A call with no `conversation` (a title, a Studio step) opens a client, answers and closes it. The pool closes every client when the API stops.

## The rest of the protocol

| Member | Answer |
|---|---|
| `name` | `"claude_plan"` |
| `health()` | the [status](01-connection.md#status); `ready` is healthy |
| `models()` | the cached model list |
| `context_tokens(model)` | the remote manifest's window for `resolvedModel` under `anthropic`; a `[1m]` value is 1,000,000 |
| `sees_images(model)` | `None` until image input through the SDK is tested |
| `token_count(model, text)` | `None` |

## Open questions

- Structured output through `output_format`, which Studio's workflows need for a schema.
- Image input: whether a streamed user message with `image` content blocks reaches the model unchanged.
- Whether one warm client can answer an unrelated call in a new session (`query(session_id=…)`), which would let titles skip the cold start.
