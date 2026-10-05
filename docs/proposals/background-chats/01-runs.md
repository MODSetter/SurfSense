# Runs

A run is one chat reply being generated. The API starts it as a background task and keeps it until it ends; any number of connections can follow it, and losing all of them does not stop it. Reloading the window, switching thread or switching workspace drops a follower, never the run.

## The run

- **Keyed by thread.** At most one active run per thread, held in an in-memory registry in the API process. A send to a thread with an active run is `409`.
- **What it runs.** The generator that `POST .../messages` drives today for a chat thread, unchanged. The run task reads it to the end; the response no longer does.
- **Agent threads are not runs.** Their turns stream as today and end when the stream closes. They keep their turns in opencode, so nothing below about stored endings, Retry or history applies to them.
- **What it holds.** Every frame the generator yields, in order, each with a sequence number starting at 1, plus its state: `queued` or `running`. A run is held only while it is active.
- **What it owns.** The model's in-use mark and the cleanup the response's shielded `finally` does today: storing the reply and how it ended, and releasing the mark. Moving them from the response to the run removes the reason for the shield.
- **It leaves the registry only after its reply is stored.** So there is no moment when the run is gone and the database does not yet hold its reply. A follower that arrives after that gets `404` and reads the stored turns, which hold everything the run sent.
- **Storage is unchanged otherwise.** Both turns are written before the run starts, the assistant turn when it ends ([chat](../../architecture/chat.md), The stream). Saving a live run's text is [`04-partial-replies.md`](04-partial-replies.md).

## How a turn ends

A chat thread's assistant turn stores how it ended in its content, as `ending`, beside `text` and `citations`, and every window builds the reply's state from it. Today the error notice and the stopped mark live only in the frontend's memory and vanish on a thread switch or a reload, which background runs would make the common case.

| Ending | `ending` | Shown |
|---|---|---|
| Completed | absent | the reply |
| Failed | `{"type": "error", "kind": …, "message": …}`, the `error` frame's fields | the reply's text, if any, then the error notice with its action, as the `error` frame shows it today |
| Stopped | `{"type": "stopped"}` | the reply's text, marked stopped |
| Cut off by a quit | `{"type": "interrupted"}`, written at startup ([`04-partial-replies.md`](04-partial-replies.md)) | the reply's text, marked "Interrupted when the app closed" |

`ending` lives in the JSON `content` column, so it needs no migration.

### A failed turn is kept

Today a turn that ends without answer text is deleted, both halves, and the `error` frame is all that says why ([chat](../../architecture/chat.md), The stream). With a run nobody is watching, nothing would ever say why: the user's question would vanish. So:

- **A failed turn is never deleted.** The question stays, and the reply stores its error, with or without text.
- **A turn stopped before any text is still deleted,** as today. The user chose to stop and there is nothing to show.
- **A turn that closes cleanly with no text** is stored as failed with kind `unknown`, the error the stream sends for it today, rather than deleted.

### Retry replaces the failed turn

```text
 Fails ──> You: Summarise Q3          Retry ──> You: Summarise Q3
           ⚠ Couldn't reach model.               AI:  The Q3 report…
             [Retry]                             (one copy of the question)
           (survives switch and reload)
```

- **Retry is offered on a failed or interrupted turn.** It sends the same message with `retry_of`, that reply's id. In the transaction that stores the new turns, the API deletes the failed pair and any image file no other turn of the thread points at, as `_discard_turn` and `_sweep_images` do today. The question appears once.
- **Only the latest turn can be retried,** as today. `retry_of` naming any other turn, or one that neither failed nor was interrupted, is `409`. An older failure stays as a record.
- **Keeping the failed attempt viewable after a retry** would need a message tree and a branch picker. Branching is a chat non-goal, and replacing can grow into it later without undoing anything.

### History skips a failed empty turn

History is every stored turn today ([`history.py`](../../../surfsense_local/backend/modules/chat/history.py)). A reply that failed with no text, or was cut off with none, is skipped together with its question, so the model never receives an empty assistant message, and never two user messages in a row. A failed or interrupted reply with text stays in history, as a partial reply does today.

## Routes

| Method | Path | Does |
|---|---|---|
| `POST` | `/chat/threads/{thread_id}/messages` | unchanged for the caller: starts the run and follows it from frame 1; takes an optional `retry_of` |
| `GET` | `/chat/threads/{thread_id}/run?after={seq}` | follows the active run: replays frames after `seq`, then streams live; `Last-Event-ID` works in place of `after`; `404` when the thread has no active run |
| `POST` | `/chat/threads/{thread_id}/run/stop` | cancels the run, queued or running; `204`, also when nothing runs |
| `GET` | `/chat/threads/{thread_id}/messages` | each assistant turn carries its `ending` |
| `GET` | `/workspaces/{workspace_id}/chat/threads` | adds `running: bool` to each thread |

- Every frame carries its sequence number as the SSE `id:` field, so a follower can resume where it was.
- A new frame, `run-state`, reports `queued` with a `position`, then `running`. Before admission ([`02-admission.md`](02-admission.md)) exists, a run goes straight to `running`. Existing clients ignore a frame they do not know.
- A follower that disconnects ends only itself. Stop, deleting the thread and deleting its workspace end the run.

## Telling other windows

The API publishes a `chat-runs` event on `/workspaces/{id}/events`, `{"ids": [thread ids], "status": "running" | "done"}`, when a run starts and ends, as it does for documents and artifacts ([overview](../../architecture/overview.md), Freshness). The thread list behind the Chats dialog and the Chats button reloads on it.

## The frontend

### State

- **Runs move out of the per-thread runtime** into a store keyed by thread id, which holds each followed run's live copy, its last sequence number and its state. The runtime of the active thread reads from it, so leaving a thread no longer drops its reply.
- **Opening a thread with `running: true`** follows its run with `after` set to what the store already has (0 if nothing), then folds into the stored turns as today, once both ids are stored. A `404` means the run ended in between, and the stored turns are read instead.
- **Reloading the window** loses the store, not the runs. Every running thread is followed again from `after=0` when opened, and the live copy is rebuilt from the replay.
- **A reply's error and stopped mark come from its stored `ending`,** and from live frames only while its run is followed. The per-thread error and stopped state that is cleared on every thread switch goes.
- **Retry** sends `retry_of` and is offered only on the latest turn.
- **Stop** calls `run/stop` instead of aborting the request, and works on a queued run as on a running one.
- **Unread replies** are the threads whose run ended while another thread was open. They are kept in `localStorage` per workspace, beside the remembered open thread, and a thread leaves the set when it is opened. Per machine is enough for one user on one machine; a cleared store only loses the dots.

### What the user sees

The sidebar's Chats button ([`left-sidebar.tsx`](../../../surfsense_local/frontend/src/features/dashboard/left-sidebar.tsx)) carries the count. The Chats dialog it opens is closed most of the time, so without the count nothing on screen says a reply is being written, or has arrived, elsewhere.

```text
 Nothing elsewhere          Two running elsewhere      One unread elsewhere
 ✎  New chat                ✎  New chat                ✎  New chat
 💬 Chats                   💬 Chats       ◌ 2         💬 Chats       ● 1
```

- It counts threads other than the open one: running and queued with a spinner, and unread with a dot once none is running. Nothing shows when there is neither, so the button looks as it does today.

The Chats dialog ([`chats-dialog.tsx`](../../../surfsense_local/frontend/src/features/chat/chats-dialog.tsx)) marks each row:

```text
 ┌─ Chats ─────────────────────────────────── ✕ ┐
 │ ◌  Q3 report summary          Writing…    ⋯  │  running
 │ ⧗  Refund policy questions    Waiting     ⋯  │  queued for the model
 │ ●  Pricing comparison         5 min ago   ⋯  │  finished or failed, not yet opened
 │    Marketing plan draft       just now    ⋯  │  open thread
 │    Casual greeting            2 h ago     ⋯  │  idle, as today
 └──────────────────────────────────────────────┘
```

- A running or queued row shows its state in place of the relative time. Rows keep their order, so a thread does not jump when it starts or ends.
- A failed reply is unread like a finished one, so a failure made in the background is not missed.

The open thread shows a queued run in the thinking header's place:

```text
 ┌──────────────────────────────┐        ┌──────────────────────────────┐
 │ You: Summarise Q3 report     │        │ You: Summarise Q3 report     │
 │ ⧗ Waiting for another reply  │  ───>  │ ⁘ Thinking                   │
 │   (2nd in line)     [■ Stop] │        │   …then the reply   [■ Stop] │
 └──────────────────────────────┘        └──────────────────────────────┘
```

- It is the same header that says "Thinking" and "Reading 42%", so it moves on to Thinking without restarting, and the position follows `run-state`.
- Everything else in the thread looks as it does today: the endings above render as today's error notice, stopped mark and Retry, now from what is stored.

All new text goes into the interface messages and is translated with the rest.

## Quitting

- **Electron asks** before quitting while any run is active, in a native dialog: "N replies are still being written. Quitting saves what they have so far.", with Cancel and Quit. It learns the count from the API, at quit time only, and asks nothing when no run is active.
- **What a quit keeps** (stopping runs before the sidecars, saving live text, settling turns at startup) is [`04-partial-replies.md`](04-partial-replies.md).

## Why runs are not stored

- **The API cannot outlive the app.** It is a child of Electron on loopback, so when it is gone there is no client left to replay to.
- **The database already holds the result.** The run stores its reply and its ending before it leaves the registry, so a follower that comes back later reads the stored turns.
- **Every write contends for one file.** Each transaction takes the lock with `BEGIN IMMEDIATE`, and ingest writes to the same file ([overview](../../architecture/overview.md), Layer boundary). Storing deltas would add a write stream per running reply for nothing the API does not already have.
- **The run sits above the provider,** so a remote connection gets background runs as a local model does.

## When this ships

[Chat](../../architecture/chat.md) changes with it: the stream section's "a turn that ends without any answer text is deleted" becomes the rules above, the frontend runtime section loses abort-based Stop and the per-thread error state, and Retry's description gains `retry_of`.

## Tests

At the HTTP seam, against a scripted generator:

- A run started, its follower disconnected, then followed with `after=0`: every frame once, in order, ending `[DONE]`.
- `after=n` replays exactly the frames after `n`.
- A follower arriving after the run ended gets `404`, and the stored turn holds the full reply.
- A second send to a running thread is `409`.
- Stop on a running run ends it, stores its text with `ending` stopped and releases the in-use mark; a disconnect does none of those.
- A run that fails before any text keeps both turns, with the error kind and message in `ending`.
- A run that fails after some text stores the text and the error.
- A run stopped before any text deletes both turns.
- `retry_of` on the latest failed turn deletes that pair and stores the new one; on any other turn it is `409`.
- History for the next turn skips a failed pair with no text and keeps a failed reply with text.
- Deleting a thread with a run ends the run.
- A send to an agent thread streams as today, and closing its stream stops the turn.

In the frontend, against a scripted stream:

- Switching away from a streaming thread and back shows the reply so far, then the rest live.
- A run that ends while another thread is open marks its row and the Chats button unread; opening the thread clears both.
- A queued run shows "Waiting for another reply" with its position, then Thinking, without the header restarting.
- A failed turn loaded from storage shows its error and Retry; Retry on any turn but the latest is not offered.
