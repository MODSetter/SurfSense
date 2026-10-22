# Model endpoint

opencode keeps reaching every model through SurfSense's endpoint under the launch key. Its providers are now opencode's own, `@opencode/ai/providers/openai-compatible` for `/chat/completions` and `@opencode/ai/providers/openai` for `/responses`, in place of the AI SDK.

## What opencode now does itself

On `/chat/completions` ([`ai/src/protocols/openai-chat.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/ai/src/protocols/openai-chat.ts)):

| [`request_shaping.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/request_shaping.py) / [`relay.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/relay.py) today | 2.x |
|---|---|
| joins every system and developer message into one at the start | sends one system message; a later change arrives as a user `<system-update>` |
| drops empty assistant turns | skips them |
| adds `[DONE]` when a stream leaves it out | does not need it; a stream ending without `finish_reason` is retried |

These can go from the chat route. They stay harmless if kept, and the `/responses` route is unaffected.

## What SurfSense keeps

- Neutralising chat-template control tokens in user and tool text: 2.x does not.
- Passing the model's own status and error through: 2.x reads llama-server's "exceeds the available context size" among about 40 phrases and compacts ([`ai/src/provider-error.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/ai/src/provider-error.ts)).
- Tool schemas within llama.cpp's grammar, and tool calls a model writes as text: neither is handled by 2.x, as by 1.x. `<tool_call>` and `<function=` in a reply stay text and the turn succeeds; they remain [agent](../../architecture/agent.md)'s known gaps.
- `x-should-retry: false` on every error SurfSense raises itself. 2.x retries a 409 as a server fault, with backoff, until the turn is interrupted, which today would loop on `model_busy`, `wrong_route` and a missing selected model ([`error_replies.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/error_replies.py)). A 429 is still retried, every few seconds rising to about a minute, and `retry-after` is not honoured.

## The ChatGPT plan

Checked against a real plan (`gpt-5.6-luna`) through a dev build's endpoint, with 1.18.34 run the same way for comparison:

- 2.x sends the system prompt as `instructions`, not a `developer` item, plus `store: false`, `include: ["reasoning.encrypted_content"]`, `reasoning`, `text.verbosity`, `max_output_tokens` and the session id as `prompt_cache_key`. It sends no `tool_choice`. Tools are flat functions.
- The plan returns each call with `namespace: "surfsense"`; 2.x runs it and replays it without the namespace and with its `fc_…` id, and [`plan_request.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/responses_relay/plan_request.py) puts the namespace back, as it does for 1.x. Every step was accepted, parallel calls included.
- Reasoning items are replayed with their encrypted content within a turn and across turns, and accepted.
- Built-in `read`, a second turn, an image read by a tool and an interrupt all work; `max_output_tokens` is still dropped by the relay.
- A 403 ends the turn without a retry, so [`plan_refusal.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/responses_relay/plan_refusal.py) holds.
- The plan's error for an unsupported field reaches opencode as JSON inside `message`; the relay lifts out `detail` so the screen shows a sentence.
