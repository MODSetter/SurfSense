# ADR 0049: A remote text model answers on the route its manifest entry records, with its connection's credential, and SurfSense owns a ChatGPT plan's sign-in for both engines

- **Status:** Accepted
- **Date:** 2026-10-07
- **Supersedes:** [ADR 0038](0038-chatgpt-plans-sign-in-through-openai-not-codex.md) in part: its request body and the consequence that a plan model has no tools or structured output
- **Source:** [OpenAI, Sign in with ChatGPT: preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

## Context

Two choices were tied together. A ChatGPT connection answered on `/responses`; every other connection answered on `/chat/completions`. So models the remote manifest records as served only on `/responses` (16 on Neon, 3 on Sakana, 2 on Infer when this was written) were listed as unusable, and the agent could not run on a plan at all: opencode reached every model through SurfSense's `/chat/completions`, and nothing answered a plan there.

ADR 0038 also read the plan's endpoint as refusing tools, `instructions`, `reasoning` and `text.format`. OpenAI's preview limitations say otherwise: function tools are taken when grouped in a namespace, and the fields a plan refuses are `max_output_tokens`, `temperature`, `top_p`, `truncation`, `user` and a few more. opencode's own v2 branch signs in through the same flow and sends namespaced tools.

opencode 1.18.34, the pinned release, bundles `@ai-sdk/openai` 3.0.88, which calls `/responses`, reads a function call's `namespace` and sends it back with the call.

## Decision

- How a text model is called is the model's: `/responses` when its connection's manifest provider records `call.route: responses`, `/chat/completions` otherwise, including every model of a `custom` connection ([`call_route.py`](../../surfsense_local/backend/modules/llm/connections/call_route.py)). A ChatGPT connection answers only on `/responses`.
- The credential is the connection's: an API key, or a plan's token. The plan's limits (dropped fields, tools in one namespace, `system` turns as `developer`) apply to the plan only, never to `/responses` in general.
- A model recorded as `/responses`-only is usable. A model served through another protocol stays unusable.
- opencode's provider follows the selected model's route: `@ai-sdk/openai-compatible` at the model endpoint's `/chat/completions`, or `@ai-sdk/openai` at its `/responses`. Both are SurfSense's routes under the launch key.
- SurfSense owns a plan's sign-in and tokens for chat, titles, Studio and the agent. opencode never signs in itself and never holds a plan's token: a rotated refresh token sent twice signs the account out, and two sign-ins would register two clients with two usage caps.
- A plan's refusal reaches opencode in a status it does not retry (403 for a used-up plan, not 429) and coded as the chat's kind, so the agent's screen offers the chat's fix.

## Consequences

- The agent runs on a ChatGPT plan, and on API-key `/responses` models, with no new sign-in.
- API-key connections to every other model, OpenAI's own included, are unchanged.
- A chat on a plan budgets its history by the window the plan states for the model.
- When opencode moves to 2.x, its provider for a `/responses` model can stay pointed at SurfSense; nothing about sign-in or tokens changes.
- No Codex client, Codex backend or Codex app-server is used.

## Where the code stands

Built and tested against fakes of OpenAI's plan endpoints and the real opencode 1.18.34, not yet against a real ChatGPT account. A plan's refusal that arrives inside the stream (`response.failed`) still reaches the agent's screen as `unknown`.
