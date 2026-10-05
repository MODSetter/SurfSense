# The model route

Studio's worker is a separate process, and today it resolves its own text model and calls the provider directly ([`resolution.py`](../../../surfsense_local/backend/modules/llm/resolution.py), `resolve_generation`). Admission ([`02-admission.md`](02-admission.md)) lives in the API and counts only what passes through the API, so a Studio request on the local runtime is invisible to it. With one slot that costs fairness; with a shared cache ([`03-parallel-slots.md`](03-parallel-slots.md)) an unseen request can overflow it and take the chats beside it down.

This part gives every process one way to generate text: an internal route in the API. Studio sends its text generation there, for every text model, local or remote, so it has one path as chat does. The route is also the one the plugins' planned `model` domain needs ([plugins, extending](../plugins/02-extending.md), Worked example).

## Why a route and not a permission step

A worker could ask the API for permission and then call the model directly. That keeps today's call, but safety then depends on every caller remembering to ask, and the API trusts each caller's own estimate of what it will spend. A route makes the safe path the only path: a request cannot reach a model without being resolved, checked for egress, marked in use and admitted by the API, whoever sends it. That holds for callers not written yet, plugins among them, which are third-party code.

## The route

`POST /internal/models/text/generate`, served by the API on loopback, beside `/internal/events`.

**Request:** the model to use, and what `Generator.chat` takes today ([`protocols.py`](../../../surfsense_local/backend/modules/llm/providers/protocols.py)):

```json
{
  "model": {"provider": "llamacpp", "name": "Qwen3-8B-Q4_K_M", "connection_id": null},
  "messages": [{"role": "system", "content": "…"}, {"role": "user", "content": "…"}],
  "max_tokens": 4096,
  "temperature": null,
  "reasoning": false,
  "json_schema": null,
  "class": "background"
}
```

- **`model` names the model, not "the current selection".** A Studio job picks its model and its prompt tier once, at the start, and keeps both; the route generates with that model even if the user changes the selection mid-job. A model that can no longer be resolved, deleted or with its connection gone, is `409`. A caller that leaves `model` out gets the current selection, which is what a plugin wants.
- **`class`** is the admission class: `background` for Studio. Interactive work runs in the API and never uses the route.

**What the API does,** with code it already has:

1. Resolve the model to a provider, checking egress for a remote host, as `resolve_generation` does today. Keys never leave the API for this call.
2. Mark the model in use, so it cannot be deleted mid-generation.
3. For the local runtime, take admission in the request's class. A remote model is not admitted.
4. Call the provider's `chat`. Its own start and stall deadlines apply here, from admission on, and the subscription's retries ([`01-runs.md`](01-runs.md), Remote models) live in its provider, so Studio gets them.
5. Release admission and the in-use mark when the stream ends, fails, or the caller disconnects. A disconnect closes the provider's stream, which is what makes llama-server stop.

**Response:** a stream in the chat's frame shape, `data: {json}` per frame and `data: [DONE]` at the end:

| Frame | When |
|---|---|
| `queued` | while it waits for admission, with `position`, first at once and then every 15 seconds |
| `text` | per chunk of the answer; a thinking model's trace is left out, as `chat` leaves it out |
| `error` | on a failure, with what the worker needs to raise it as today (below) |

The `queued` frames double as the keep-alive: the connection is never quiet long enough to look dead while a Studio request waits behind chats.

## The worker

- **`RoutedGenerator`** implements `Generator.chat` by posting to the route and yielding `text` frames. It reaches the API at the host and port the worker already has in its environment (`SURFSENSE_LOCAL_PORT`, [`python.ts`](../../../surfsense_local/electron/src/main/sidecars/python.ts)). Studio uses nothing else on `Generator`.
- **Studio's text model resolves to it** in `_choose_model` ([`job.py`](../../../surfsense_local/backend/worker/studio/job.py)), for every text model, local or remote. The selection is still read in the worker, for its prompt tier and for the request's `model`. The pipelines, `run_model` ([`generate.py`](../../../surfsense_local/backend/worker/studio/shared/generate.py)) and the Studio panel do not change.
- **Errors arrive as the types Studio handles today,** so its retries and its one-line reason (`_reason`) behave as before: a provider's HTTP status as `httpx.HTTPStatusError` with that status and message, a model that cannot be resolved as `ModelResolutionError`, a refused host as `EgressDeniedError`, a model that never started or stalled as `StreamTimeoutError`, and a ChatGPT subscription that has to be signed into again or whose plan is used up as `SignInRequiredError` or `PlanLimitError` ([`openai_responses/errors.py`](../../../surfsense_local/backend/modules/llm/providers/openai_responses/errors.py)), with the message each carries today.
- **Cancel is the connection.** Studio's `_collect` already stops reading within a poll of a cancel; closing the request is what releases admission and stops the model.
- **Deadlines live in the API.** The worker only gives up on a connection that sends nothing, frame or keep-alive, for longer than the provider's own stall budget, so a request waiting in the queue never trips the 300-second start timeout that a direct call has (`FIRST_TOKEN_SECONDS` in [`openai_compatible/chat.py`](../../../surfsense_local/backend/modules/llm/providers/openai_compatible/chat.py)).

## Local image generation gives up the runtime through the API

Before a local image is drawn, Studio unloads every text model llama-server holds, so sd-server can take the graphics card ([`sdcpp/generator.py`](../../../surfsense_local/backend/modules/llm/providers/sdcpp/generator.py)). Today that cuts off any chat generating at that moment, and with background chats one usually is.

So the unload goes through the API too: `POST /internal/models/text/yield`, held open for as long as the image job needs the card. The API stops admitting local text requests, waits for the ones running to finish, unloads the text models, and answers `yielded`. While it is held, local chats queue and show "Waiting for another reply"; when the image job closes it, admission opens and the router reloads the chat model on the next request, as it does today. A worker that dies while holding it drops the connection, which releases it. Remote chats are not affected.

The image request itself stays a direct call to sd-server or the remote image provider, as today.

## What stays as it is

- **Image and audio generation calls,** to sd-server, audiocpp or a remote provider, from the worker.
- **The worker's key-decryption secret.** Studio's remote image calls still decrypt a key in the worker. Moving image and audio onto routes like this one, and then dropping the secret from the worker's environment, is later work.
- **The agent.** opencode keeps calling its own OpenAI-shaped endpoint, which runs in the API and is admitted there ([`02-admission.md`](02-admission.md)).

## Plugins

The plugins proposal plans a `model` domain whose `generate(prompt)` makes "an HTTP call to an internal route we stay free to rename", so that "if the user switches from a local model to a remote provider, the plugin does not notice" ([plugins, extending](../plugins/02-extending.md)). This is that route. When the domain lands, the SDK posts a prompt as one user message, leaves `model` out to get the user's selection, and uses a `plugin` class that admission ranks with Studio. Nothing in this part builds the domain.

## Tests

At the route's HTTP seam, against a scripted local runtime and a scripted remote endpoint:

- A Studio request on the local runtime is admitted as background work: queued behind a waiting chat, `queued` frames with its position, then `text`.
- A request on a remote model is not admitted and streams at once.
- `model` names a model the user has since deselected: it generates with that model. Names one deleted: `409`.
- A disconnect while queued leaves the line, and the runtime receives nothing; a disconnect while generating releases the slot and the in-use mark and closes the stream.
- A provider `429` reaches the worker as `httpx.HTTPStatusError` with status `429`; a refused host as `EgressDeniedError`.
- On a ChatGPT subscription, a refused sign-in reaches the worker as `SignInRequiredError` and a used-up plan as `PlanLimitError`, each with the message Studio shows for it today.
- `yield` waits for a running local chat to finish, unloads, queues a chat sent while held, and admits it once the hold closes; a dropped hold connection releases it.

In the worker, against a scripted route:

- A Studio job generates through `RoutedGenerator` for a local and for a remote selection, with the same pipeline code.
- A request queued longer than 300 seconds still completes.
- A job cancelled mid-generation closes its request.
