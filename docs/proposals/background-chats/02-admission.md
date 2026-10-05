# Admission

Once replies run in the background, several can want the local runtime at once, alongside Studio. Admission decides which generation request llama-server receives next. At one slot it is a visible queue with chat ahead of Studio; with the shared cache of [`03-parallel-slots.md`](03-parallel-slots.md) it is what keeps the cache from overflowing.

## Every caller passes through the API

Admission lives in the API and counts what passes through it. Every request that generates on llama-server does:

| Caller | Process | How it reaches the model | Admitted |
|---|---|---|---|
| Chat runs, thread titles | API | in process, through the provider | in process, interactive |
| Agent turns | opencode | the API's model endpoint, which relays to llama-server ([agent](../../architecture/agent.md), The model endpoint) | in the relay, interactive |
| Studio | `worker-studio` | the model route ([`05-model-route.md`](05-model-route.md)) | in the route, background |

Remote models are not admitted: they never queue, wherever the request comes from.

Image generation's unload of the text model is not a generation request, but it would cut off whatever is running, so it takes the runtime through admission too ([`05-model-route.md`](05-model-route.md), Local image generation gives up the runtime).

## Pools

One pool per loaded model on llama-server, because in router mode each model is its own child with its own cache. A pool's two limits come from what llama-server reports for that model through `/props`, not from the plan that asked for it:

- **Slots:** `total_slots`.
- **Token budget:** the cache's size in tokens, `default_generation_settings.n_ctx`, which the chat already reads ([runtime](../../architecture/local-models/runtime.md)).

A pool is dropped when its model unloads and rebuilt from `/props` when it loads again, since a reload can change both.

Whether `b11050` reports `total_slots` in `/props` is checked before the pool is written. If it does not, the pool takes the slot count the preset wrote for that model.

## The rule

A request is admitted when a slot is free and the tokens already committed plus its cost fit the budget. When nothing is committed it is admitted regardless, so one long request is never refused for being long. The window, not admission, is what refuses an oversize prompt.

**Cost** is what the request will hold in the cache, worked out by the API from the request itself, never declared by the caller:

- **Prompt:** an estimate that errs high. The chat's four characters a token ([`budget.py`](../../../surfsense_local/backend/modules/chat/budget.py)) undercounts dense scripts, and undercounting is the failure this exists to prevent, so admission uses a denser estimate than the chat budget. Images are priced as the chat budget prices them.
- **Output:** `max_tokens` when the request sets one below the window; a chat turn sets 1,024. Otherwise a default allowance, capped so that a short prompt plus its allowance does not exceed an equal share of the budget. Without the cap, an unstated allowance on a small cache admits fewer requests than there are slots.
- **No estimate:** an equal share of the budget, `budget ÷ slots`. Charging the whole budget would run such requests alone; charging nothing would overcommit.

**Order:** two classes, interactive (chat, titles, agent) ahead of background (Studio). Within a class, strictly first come, first served: the head of the line blocks smaller requests behind it, so a large one is never starved by a stream of small ones. A running request is never pre-empted.

**Release:** the slot and the tokens return when the response ends, errors, is stopped, or its caller disconnects. A request cancelled while generating closes its upstream stream, which is what makes llama-server stop the task. One cancelled while queued leaves the line without touching llama-server.

**An agent turn** is many requests: opencode calls the endpoint once per step. Each is admitted and released on its own, so a growing tool loop is re-priced every step for free, and a slot is not held while opencode runs a tool. Nothing re-prices a request mid-run.

**The line** is capped at 64 waiting requests per pool; past that a request is refused with `429`. One person does not reach it; it is a guard on a runaway caller.

## What the user sees

- A chat run that waits sends `run-state` with `queued` and its position, and the thread shows "Waiting for another reply". The thinking header does not start until it runs.
- Studio's jobs stay `processing` while they wait, as they do today while the model loads. The Studio panel does not change.
- llama.cpp's cache-full errors ("failed to find free space in the KV cache", "failed to find a memory slot") become a new chat error kind, `runtime_busy`, which says the replies running together ran out of room and offers Retry. Admission should make it rare; the error says what happened when it is not.

## Tests

In process, against a scripted llama-server whose `/props` sets the slots and the budget:

- Slots 1: a second chat reports `queued` with position 1, then runs when the first ends.
- Slots 2, budget smaller than both costs: the second waits though a slot is free.
- Nothing committed: a request costing more than the budget is admitted.
- A Studio request queued before a chat request runs after it.
- A queued request whose caller disconnects leaves the line and llama-server receives nothing.
- A generating request stopped mid-stream releases its slot and tokens.
- An agent step through the model endpoint is admitted as interactive and released when its response ends.
- A remote request is never queued.

The route's own tests are in [`05-model-route.md`](05-model-route.md).

## Decided

- **One pool, three doors.** Chat and titles take admission in process, the agent in its relay, Studio in the model route. All three run in the API, so one pool sees everything that generates on the runtime.
- **A prompt's cost is estimated, not counted.** `/tokenize` is exact, but it is one more request before every turn, while the model may still be loading. If the estimate admits too few requests in practice, counting replaces it.
- **Studio has no ageing.** Strict priority could starve it under constant chatting, which one person rarely does. If Studio jobs are seen waiting on chats, ageing is added then.
