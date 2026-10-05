---
status: proposed
code:
  - surfsense_local/backend/modules/chat/
  - surfsense_local/backend/modules/agent/model_endpoint/
  - surfsense_local/backend/modules/llm/
  - surfsense_local/backend/worker/studio/
  - surfsense_local/electron/src/main/
  - surfsense_local/frontend/src/features/chat/
  - surfsense_local/frontend/src/features/dashboard/
---

# Background chats

> Several chat sessions can run at once, on local and remote models alike, and each keeps generating when the user switches thread or workspace or reloads the window. The API owns every reply; a window only watches one. On the local runtime, every request that generates passes one admission gate in the API, Studio's included, so llama-server can serve up to four replies from one shared cache without one request's overflow killing another's.

Today a reply belongs to the HTTP request that asked for it. `POST /chat/threads/{id}/messages` streams from inside the response, and a client that hangs up ends the turn, keeping its partial text ([chat](../../architecture/chat.md), The stream). Stop works by aborting the request. An agent turn ends the same way: closing the stream stops it. The frontend's runtime is scoped to the active thread, so only one reply can be on screen.

The local runtime serves one request at a time: every preset pins `parallel = 1` ([runtime](../../architecture/local-models/runtime.md), The preset file), and the fit estimate assumes the same: `n_seq_max` is 1 in [`kv_cells.py`](../../../surfsense_local/backend/modules/llm/fit/kv_cells.py) and `SLOTS = 1` in [`compute_buffers.py`](../../../surfsense_local/backend/modules/llm/fit/compute_buffers.py). Studio's worker resolves its own model and calls it directly, so nothing in the API sees it.

Background runs cover chat threads on every chat model: the local runtime, remote connections and a ChatGPT subscription. Agent threads keep today's behaviour, where closing the stream stops the turn; their requests still pass admission, because they share llama-server's cache.

Facts are checked against this repo and llama.cpp `b11050` (the build the app pins) as of 5 Oct 2026.

## Parts

Two features, built together.

**Resumable chats.** A reply outlives the window watching it, on any model.

| Part | File | Delivers | Depends on |
|---|---|---|---|
| **Runs** | [`01-runs.md`](01-runs.md) | replies, local or remote, survive switching threads and reloads; running, queued and unread threads show in the Chats dialog and on the sidebar's Chats button; Stop is its own route; a turn stores how it ended | nothing |
| **Partial replies** | [`04-partial-replies.md`](04-partial-replies.md) | a quit or crash keeps the reply's text and the user's question, marked cut off | runs |

**Local replies in parallel.** Several local replies generate at the same moment instead of taking turns. Remote models need none of this.

| Part | File | Delivers | Depends on |
|---|---|---|---|
| **Admission** | [`02-admission.md`](02-admission.md) | one gate in the API for everything that generates on llama-server; a visible "waiting" state; chat ahead of Studio | runs |
| **The model route** | [`05-model-route.md`](05-model-route.md) | one internal route for generating text from another process; Studio's text generation moves onto it, local and remote, and its local image generation gives up the runtime through it | admission |
| **Parallel slots** | [`03-parallel-slots.md`](03-parallel-slots.md) | up to four local replies at once from one shared cache | admission, the model route |

All five ship in one change. The order inside it still matters: runs never ship without partial replies, because once a disconnect stops ending a run, closing the window stops saving its text; and parallel slots never ship without admission and the model route, because with a shared cache a request the gate cannot see can overflow it, and llama.cpp kills every request involved.

## Locked decisions

| Decision | Choice |
|---|---|
| Who owns a run | The API process. A connection follows a run; it never owns one. |
| Where runs live | In memory, in the API. The API dies with the app, so nothing a database adds would survive a restart that the run itself does not. The events broker already relies on one uvicorn process. |
| Runs per thread | One active run. A second send to a running thread is `409`. |
| What survives | Switching thread or workspace, and reloading the window. Not quitting: `window-all-closed` quits the app on every platform ([`index.ts`](../../../surfsense_local/electron/src/main/index.ts)), so closing the window is quitting. |
| Quitting with replies running | Electron asks first, then has the API stop and commit every run before it stops the sidecars. A live run also saves its text every 5 seconds, so a crash loses at most that. A cut-off reply is marked interrupted at the next start ([`04-partial-replies.md`](04-partial-replies.md)). |
| Existing clients | Unchanged. `POST .../messages` still starts a turn and streams it; everything new is added routes and frames. |
| Agent threads | Not runs. An agent turn still ends when its stream closes; moving it onto runs is separate work. |
| Who generates text | Only the API. Chat and titles run in it, the agent reaches it through its model endpoint, and Studio through the model route. A request cannot reach a model without being resolved, checked for egress, marked in use and admitted there ([`05-model-route.md`](05-model-route.md)). |
| Studio | One path for every text model, local or remote, through the model route. Its pipelines and its panel do not change. Its image and audio calls stay direct, and its local image generation takes the runtime through the API before it unloads the text model. |
| Admission | A slot and a token budget per loaded model, both read from what llama-server reports it allocated. Cost is worked out by the API from the request, never declared by the caller. First come, first served, with interactive work ahead of Studio and no ageing. |
| Remote models | Remote connections and a ChatGPT subscription run in the background like the local runtime, with no admission: they never queue, several can run against one provider at once, a `429` ends a run as `provider_rate_limited`, and a subscription retries a temporary failure twice first ([`01-runs.md`](01-runs.md), Remote models). |
| Slots | Ask for four on every backend, with one unified cache. When four are not resident even at an 8,192 window, step down one slot at a time, then widen the window as far as that count allows. A model that spills even at one slot keeps four. Metal keeps four. No per-machine measurement gates it: what slots change is llama.cpp's own arithmetic, and `--fit` spills rather than fails ([`03-parallel-slots.md`](03-parallel-slots.md)). |

## Out of scope

- Surviving a quit, or resuming a generation after a restart.
- Pre-empting a running Studio job for a chat.
- Concurrency limits for remote connections.
- Regenerating or branching, which the chat's non-goals already exclude.
- Agent threads as runs.
- Image and audio generation through routes like the model route, and dropping the key-decryption secret from the worker's environment, which waits on them.
- The plugins' `model` domain. The model route is the route it will call ([plugins, extending](../plugins/02-extending.md)); building the domain is the plugins proposal's.

## Before building

Nothing is left to decide. What remains is checked at a named point, each with the path to take. None is a measurement on one machine that would decide for others.

| Part | Check | When | Path |
|---|---|---|---|
| Admission | Whether `/props` reports `total_slots` at `b11050` | before writing the pool | if it does not, the pool takes the slot count the preset wrote |
| Admission | How often more than two replies overlap | logged from the first release | decides whether part 3 keeps asking for four slots |
| Parallel slots | Whether 8,192 at four slots instead of 16,384 at one shows in answers | once the [chat eval](../chat-eval.md) runs | ships regardless; the eval decides whether to revisit the order |
| Partial replies | Whether 3 seconds is enough for `stop-all` with four runs while ingest holds the lock | while building it | tune the bound; the quit waits no longer than it |
| Partial replies | Whether a crash today leaves a blank reply, and closing the window today keeps a partial one | before building the startup sweep | reproduce both by hand; both are read from the code |

## On shipping

The change folds what is then true into [chat](../../architecture/chat.md), [studio](../../architecture/studio.md), [overview](../../architecture/overview.md) (the process diagram), [runtime](../../architecture/local-models/runtime.md) and [fit](../../architecture/local-models/fit.md), and deletes this proposal. The decision that is costly to reverse, that the API is the only path to a text model for generation, is recorded as an ADR in the same change.
