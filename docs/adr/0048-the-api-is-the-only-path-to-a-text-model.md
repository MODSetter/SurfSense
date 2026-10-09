# ADR 0048: The API is the only path to a text model, so one gate can count everything that generates

- **Status:** Accepted
- **Date:** 2026-10-05
- **Source:** [Background chats proposal, the model route](https://github.com/MODSetter/SurfSense/blob/38f368088/docs/proposals/background-chats/05-model-route.md)

## Context

Chat replies became runs that keep generating in the background, several at once, and the local runtime serves up to four of them from one unified cache ([`local-models/admission.md`](../architecture/local-models/admission.md)). llama.cpp tells every slot it has the whole window, so two requests that together overflow the shared cache are both killed. Something has to count every request before it starts, and the counter is a variable in the API process.

Three callers generated text. Chat and titles ran in the API, and the agent already reached models through the API's model endpoint. Studio's worker is another process: it resolved its own model, held the key-decryption secret for remote ones, and called the provider directly, so a counter in the API could not see it. Two ways to make it seen were weighed. A permission step, where the worker asks the API for room and then calls the model directly, keeps today's call but is voluntary: every caller, including future ones and third-party plugins, has to remember to ask, and the API has to trust each caller's own estimate. A route through the API makes the safe path the only path.

## Decision

- Every process other than the API generates text through `POST /internal/models/text/generate`, which takes what `Generator.chat` takes plus the model and an admission class. The API resolves the model, checks egress, marks it in use, admits a local request and runs the real provider.
- Studio's text generation goes through it for every text model, local and remote, so Studio has one path, as chat does. Its pipelines do not change: `RoutedGenerator` implements `chat` over the route, and failures arrive as the types a direct call raises.
- Cost is worked out by the API from the request, never declared by the caller.
- Local image generation takes the runtime through `POST /internal/models/text/yield` before it unloads the text model, held open for the image, so nothing running is cut off and nothing new loads under it.
- The plugins' planned `model` domain calls the same route.

## Consequences

- Admission is a real global cap on the local runtime: nothing that generates there can bypass it, whoever wrote the caller.
- Retries, errors and deadlines for Studio's text live where chat's do; a subscription's retries reach Studio for free.
- Studio's text depends on the API at runtime, as its schema and events already did.
- The worker still holds the secret, for Studio's remote image and audio calls, which stay direct.

## Where the code stands

Image and audio generation do not go through a route yet, so the secret cannot leave the worker's environment. The plugins' `model` domain is not built.
