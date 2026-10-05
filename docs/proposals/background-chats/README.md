---
status: proposed
code:
  - surfsense_local/backend/modules/chat/
  - surfsense_local/backend/modules/agent/model_endpoint/
  - surfsense_local/backend/modules/llm/
  - surfsense_local/electron/src/main/
  - surfsense_local/frontend/src/features/chat/
---

# Background chats

> A reply keeps generating when the user switches thread or workspace or reloads the window, and several threads can be answering at once. The API owns every run; a browser connection only watches one. On the local runtime, every generation request passes one admission gate, so llama-server can serve up to four replies from one shared cache without one request's overflow killing another's.

Today a reply belongs to the HTTP request that asked for it. `POST /chat/threads/{id}/messages` streams from inside the response, and a client that hangs up ends the turn, keeping its partial text ([chat](../../architecture/chat.md), The stream). Stop works by aborting the request. An agent turn ends the same way: closing the stream stops it. The frontend's runtime is scoped to the active thread, so only one reply can be on screen.

The local runtime serves one request at a time: every preset pins `parallel = 1` ([runtime](../../architecture/local-models/runtime.md), The preset file). The fit estimate assumes the same: `n_seq_max` is 1 in [`kv_cells.py`](../../../surfsense_local/backend/modules/llm/fit/kv_cells.py) and `SLOTS = 1` in [`compute_buffers.py`](../../../surfsense_local/backend/modules/llm/fit/compute_buffers.py).

Facts are checked against this repo and llama.cpp `b11050` (the build the app pins) as of 5 Oct 2026.

## Parts

| Part | File | Delivers | Depends on |
|---|---|---|---|
| **Runs** | [`01-runs.md`](01-runs.md) | replies survive switching threads and reloads; running threads show in the sidebar; Stop is its own route | nothing |
| **Admission** | [`02-admission.md`](02-admission.md) | one queue in front of llama-server for chat, agent and Studio; a visible "waiting" state; chat ahead of Studio | runs |
| **Parallel slots** | [`03-parallel-slots.md`](03-parallel-slots.md) | up to four local replies at once from one shared cache | admission |
| **Partial replies** | [`04-partial-replies.md`](04-partial-replies.md) | a quit or crash keeps the reply's text and marks it cut off; an empty turn left by a crash is removed | runs, except removing empty turns |

Each part ships on its own. Parallel slots never ship without admission: with a shared cache, two requests that together overflow it are both killed by llama.cpp. Runs never ship without partial replies: once a disconnect stops ending a run, closing the window stops saving its text.

## Locked decisions

| Decision | Choice |
|---|---|
| Who owns a run | The API process. A connection follows a run; it never owns one. |
| Where runs live | In memory, in the API. The API dies with the app, so nothing a database adds would survive a restart that the run itself does not. The events broker already relies on one uvicorn process. |
| Runs per thread | One active run. A second send to a running thread is `409`. |
| What survives | Switching thread or workspace, and reloading the window. Not quitting: `window-all-closed` quits the app on every platform ([`index.ts`](../../../surfsense_local/electron/src/main/index.ts)), so closing the window is quitting. |
| Quitting with replies running | Electron asks first, then has the API stop and commit every run before it stops the sidecars. A live run also saves its text every 5 seconds, so a crash loses at most that. A cut-off reply is marked interrupted at the next start ([`04-partial-replies.md`](04-partial-replies.md)). |
| Existing clients | Unchanged. `POST .../messages` still starts a turn and streams it; everything new is added routes and frames. |
| Who reaches llama-server to generate | Only the API. The agent already does, through its model endpoint ([agent](../../architecture/agent.md), The model endpoint); Studio's worker moves behind the API too. |
| Admission | A slot and a token budget, both read from what llama-server reports it allocated. First come, first served, with interactive work ahead of Studio. |
| Remote connections | Run in the background like local ones, with no admission. |
| Slots | Ask for four, with one unified cache. When four are not resident even at an 8,192 window, step down one slot at a time, then widen the window as far as that count allows. A model that spills even at one slot keeps four. Metal keeps four. |

## Out of scope

- Surviving a quit, or resuming a generation after a restart.
- Pre-empting a running Studio job for a chat.
- Concurrency limits for remote connections.
- Regenerating or branching, which the chat's non-goals already exclude.

## Open questions

Each part lists its own. Across them:

- Whether the internal gateway for Studio ([`02-admission.md`](02-admission.md)) should also replace the agent's direct `ModelAddress` to llama-server, so there is one gated path instead of two gated callers.
- How often more than two replies actually overlap. Parts 1 and 2 can log it before part 3 decides how much measuring Metal deserves.

## On shipping

Each part folds what is then true into [chat](../../architecture/chat.md), [overview](../../architecture/overview.md) (the process diagram), [runtime](../../architecture/local-models/runtime.md) and [fit](../../architecture/local-models/fit.md). The decision that is costly to reverse, that the API is the only path to a local model for generation, is recorded as an ADR when part 2 ships.
