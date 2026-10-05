---
status: proposed
code:
  - surfsense_local/backend/modules/agent/agent_threads/
  - surfsense_local/backend/modules/chat/router.py
  - surfsense_local/backend/modules/chat/runs/
  - surfsense_local/backend/modules/workspaces/router.py
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/frontend/src/features/chat/
  - surfsense_local/frontend/src/features/dashboard/
---

# Agent turns in the background

> An agent thread's turn keeps working when the user switches thread or reloads the window, as a chat reply already does. The agent hands its turn to the existing run layer, which stays engine-free and gains one generic thing: where a run stands.

Today an agent turn belongs to the HTTP request that sent it. `agent_turn` returns its own `StreamingResponse`, and when the client hangs up Starlette cancels the stream, whose `finally` aborts the opencode session ([`turn.py`](../../surfsense_local/backend/modules/agent/agent_threads/turn.py)). `send_message` hands agent threads off before it reaches the run registry ([`router.py`](../../surfsense_local/backend/modules/chat/router.py)), and the frontend abandons an agent turn when its thread is left ([`use-chat-runtime.ts`](../../surfsense_local/frontend/src/features/chat/use-chat-runtime.ts)). So none of what [chat](../architecture/chat.md) says about runs applies to an agent thread: no replay, no Stop route, no running mark, no unread.

Both engines stay: opencode answers threads on tested models, the chat answers every other model ([agent proposal](agent/README.md), [file agent 05](file-agent/05-model-ladder-and-evals.md) decision 7). Nothing here assumes either replaces the other.

Facts are checked against this repo and opencode `v1.18.34` as of 6 Oct 2026.

## Behaviour

Watched from start to end, an agent turn behaves as it does today: the same refusals before it starts, the rename, the preparing line and folder sync, steps, text, citations, errors, the approval dialog, admission of each model call, Retry sending the question again, and Stop aborting opencode with the text kept. What changes:

| When | Today | After |
|---|---|---|
| the user switches thread or reloads | the turn stops | it keeps going, and is followed again on return |
| another thread is open | nothing shows | the Chats dialog and sidebar show it running, needing approval, or unread once done |
| the user quits with it running | it stops without asking | Electron asks first, as for a chat |
| a stopped or quit reply is reopened | its text, unmarked | its text, marked stopped or interrupted |
| a second send while it runs | blocked by the screen only | `409` from the API too |
| a seventh agent turn at once | allowed | refused ([Decisions](#decisions)) |
| its thread is deleted mid-turn | opencode aborts the turn | the run is stopped first, then the thread goes |

One property is given up: `turn.py`'s "nothing works on unseen". A background agent turn keeps calling its model, a paid one included, until it ends. SurfSense sets no `steps` limit in [`opencode_config.py`](../../surfsense_local/backend/modules/agent/opencode_config.py), so today a watched turn is not bounded either; what bounds an unseen one is Stop in its thread, the quit prompt, and opencode's `doom_loop` ask, which now reaches the user as "needs approval".

## The run layer stays engine-free

[`modules/chat/runs/`](../../surfsense_local/backend/modules/chat/runs/) knows threads and frames, not engines. `ChatRuns.start(thread_id, frames, on_end)` drives any frame generator in a task; `Run` numbers and replays frames and can be stopped or interrupted; the follow, stop, count and stop-all routes look a run up by thread id; `notify_run` announces running and done. On the frontend, [`apply-frame.ts`](../../surfsense_local/frontend/src/features/chat/runs/apply-frame.ts) already applies `agent-preparing`, `agent-scope` and `agent-step`.

An engine that wants background turns supplies:

| An engine supplies | The chat today | The agent, after this |
|---|---|---|
| a frame generator that survives its request | `stream(run)` in `send_message` | `_stream` in `turn.py` |
| its own database session | `session_factory()` inside the run | the same |
| cleanup that runs on cancel | releases the model, stores the ending | aborts the session, `turn_ended`, closes the client (already in `finally`) |
| how the reply survives a crash | `live_text.py` saves every 5 s | nothing: opencode writes a reply's text only when it ends or is aborted, so a crash loses it |
| how the turn ended | `content.ending` on the stored message | read from opencode, plus a recorded interruption ([How an agent reply ended](#how-an-agent-reply-ended)) |
| where the run stands | queued with its place, then running | running, or needing approval |

`live_text.py` sits in `runs/` but writes `ChatMessage` rows, so it is the chat engine's, not the layer's. Moving it is not part of this work.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Where a quit's interruption is recorded | A table, `agent_reply_endings`: `thread_id` (cascades with the thread), `reply_id` (opencode's), `ending` (JSON). Read by `replies.py`. | Agent replies have no `chat_messages` row. A list on the thread's row would move its `updated_at`, the time the Chats dialog shows, on every quit. |
| A window reloading a thread mid-turn | No change. `composed()` hides stored messages with the live pair's ids while the run is live, and the run is dropped only after it ends and a fresh read holds its text. | opencode's stored copy is empty until the reply ends, but it is never shown over the live one. A test pins it. |
| A turn waiting on an approval nobody sees | Each run carries a state its engine sets: `queued` with a position, `running`, or `needs-approval`. The thread list reports it, `notify_run` sends it, and the Chats dialog and sidebar show it. | `doom_loop` and `*.env` reads are the asks left, so this is rare but would otherwise spin forever. The chat gains too: a reply's place in line shows in every window, not only the one following it. |
| How many agent turns run at once | Six. A seventh send is refused with `409` before anything is sent, with a message the frontend translates. | Each running turn pins an opencode instance of about 30 MB, which `LIVE_INSTANCES` never disposes. The agent serves tested models only, so six at once is rare; a line can build on `queued` later if use shows the need. |
| Deleting a thread whose turn runs | Stop its run, waiting up to `STOP_SETTLE_SECONDS`, then delete. Deleting a workspace does the same for each of its threads. | One path for both engines. A chat run today keeps going after its thread is deleted and its last write finds no row. |

## How an agent reply ended

What opencode `v1.18.34` stores for a reply cut off after it streamed text, then read back after a restart:

| Cut off by | The stored reply | Its text | The session's next turn |
|---|---|---|---|
| an abort (`client.abort`) | `time.completed` set, `error.name` `MessageAbortedError` | kept | answers |
| `SIGTERM`, as Electron's supervisor sends at quit | no `time.completed`, no `error` | lost | answers |
| `SIGKILL`, or `taskkill /f` on Windows | no `time.completed`, no `error` | lost | answers |

opencode exits on `SIGTERM` at once (exit code `-15`) without aborting its sessions, and until a reply ends its stored text is empty. Checked on macOS by starting the staged binary on a scripted model that stalls mid-reply, cutting the turn off each way, restarting, and reading the session.

So a quit aborts as a stop does, which keeps the text, and SurfSense records the interruption in `agent_reply_endings`, since the abort is the same either way. The ending is then:

| The stored reply | Recorded interrupted | `ending` |
|---|---|---|
| `MessageAbortedError` | yes | `interrupted` |
| `MessageAbortedError` | no | `stopped` |
| any other `error` | either | `error`, with the reason `turn_frames.py` already gives |
| no `time.completed` and no run for the thread | either | `interrupted`: a crash, its text lost |

Recording the quit rather than the stop leaves the common case, a stop, to opencode alone; a record lost in the 3 s quit window reads as stopped, which is still a cut-off reply.

## Backend

1. **One busy check for both engines.** Move the `409` "this thread is still answering" above the `uses_agent` branch in `send_message`.
2. **The turn becomes a run.** `agent_turn` keeps every refusal it makes before sending (no session, images, opencode not ready, legacy thread, model cannot run the agent), adds the six-turn refusal, and keeps the rename. Then, instead of returning a `StreamingResponse`, it calls `runs.start(thread.id, frames, on_end)` and returns `event_stream(run.follow())`, as the chat does. The count of running agent turns comes from `live_instances`, which already counts turns per folder.
3. **Its own session.** `_stream` takes a `session_factory` and opens a session inside the run for the folder sync, `link_live_render`, `load_citations` and the ending record; the request's session closes when the request does.
4. **Where the run stands.** `Run` gains a state its engine sets, and setting it notifies every window through `notify_run`. `list_threads` reports it beside `running`, which stays for existing clients. The agent sets `needs-approval` on a `permission-request` frame and `running` on `permission-replied`; the chat sets `queued` and `running` where it sends its `run-state` frames now.
5. **Stop and quit.** `Run.stop()` and `interrupt_all()` cancel the task, and the cancel runs `_stream`'s `finally`, which already aborts the session; both keep aborting. On a quit (`run.stop_requested` false) the `finally` first writes `interrupted` to `agent_reply_endings` for the turn's reply.
6. **The ending, read back.** [`replies.py`](../../surfsense_local/backend/modules/agent/agent_threads/replies.py) sets `content.ending` on an agent reply from opencode's message and `agent_reply_endings`, as above.
7. **Deleting.** `delete_thread` in [`router.py`](../../surfsense_local/backend/modules/chat/router.py), and the workspace delete in [`workspaces/router.py`](../../surfsense_local/backend/modules/workspaces/router.py), stop each running thread's run before anything is removed.
8. **A migration** adds `agent_reply_endings`.
9. **The module docstring** of `turn.py` ("Closing the stream stops the turn: nothing works on unseen") is replaced with what is then true.

## Frontend

In [`use-chat-runtime.ts`](../../surfsense_local/frontend/src/features/chat/use-chat-runtime.ts):

- `leaveAgentTurn` goes: leaving a thread no longer abandons its run.
- The follow effect drops its `uses_agent` exception, so an agent thread reported running is reattached with `followRun`.
- `cancel` calls `stopRun` for both engines instead of `abandonRun` for the agent.
- Retry keeps its agent exception: opencode's ids are strings and `retry_of` takes a stored chat message's number.
- `runStates` reads each thread's state from the list, so a thread no window follows still shows its place in line or that it needs approval.

`RunState` in [`run-store.ts`](../../surfsense_local/frontend/src/features/chat/runs/run-store.ts) gains `needs-approval`, and the comment on `abandonRun` loses its agent clause. In the Chats dialog a thread needing approval shows its own mark in the slot the dot, spinner and clock share, with a screen-reader label; the sidebar's Chats button shows it ahead of the unread dot, since it is the one thing waiting on the user. The approval dialog needs no change: `permission-request` and `permission-replied` are frames, so a reattached window replays them in order. The six-turn refusal is shown in the user's language under the unsent message, as the legacy-thread refusal is ([`outdated-thread.ts`](../../surfsense_local/frontend/src/features/agent/outdated-thread.ts)). New strings are translated into every language in `LOCALES`.

## Out of scope

- **The ChatGPT subscription on the agent.** The agent's model endpoint does not share the chat's retry on `429` and `5xx`. That is the agent model route's work, not this one's.
- **A step limit on agent turns.** opencode's `steps` caps a turn's model calls; SurfSense sets none today, for watched turns as much as unseen ones. Whether to set one is the agent configuration's decision.

## Tests

One failing test first, at the public seam: a client that sends an agent turn and hangs up, then `GET /chat/threads/{id}/run` replays the turn through `completed`, against a stubbed opencode client. Then:

- a second send while it runs is `409`, and so is a seventh agent turn while six run;
- `run/stop` aborts the opencode session and the reply reads back `stopped`;
- `stop-all` aborts every agent session within `QUIT_SETTLE_SECONDS`, and each reply reads back `interrupted` with its text;
- a reply opencode left unfinished reads back `interrupted`;
- a `permission-request` puts the thread's state at `needs-approval` in the thread list, and `permission-replied` puts it back at `running`;
- deleting a thread mid-turn, chat or agent, stops its run before the thread goes.

Frontend: switching away from an agent thread and back shows the live text, not opencode's empty copy; a turn that ends elsewhere marks the thread unread; a thread needing approval shows its mark in the dialog and on the sidebar.

## Docs

The change that ships this updates [chat](../architecture/chat.md) (Agent threads, the frontend line that says an agent thread "is not a run", the run states, and deleting), [agent](../architecture/agent.md) and [data model](../architecture/data-model.md), and deletes this file.
