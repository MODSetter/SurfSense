# Runs

A run is one reply being generated: a chat turn or an agent turn. The API starts it as a background task and keeps it until it ends; any number of connections can follow it, and losing all of them does not stop it.

## The run

- **Keyed by thread.** At most one active run per thread, held in an in-memory registry in the API process. A send to a thread with an active run is `409`.
- **What it runs.** The generator that `POST .../messages` drives today, for chat and agent threads alike, unchanged. The run task reads it to the end; the response no longer does.
- **What it holds.** Every frame the generator yields, in order, each with a sequence number starting at 1, plus its state: `queued`, `running` or `done`. The buffer stays for 60 seconds after the run ends. By then the reply is stored, and a later follower reads the stored turns; the buffer only spares one that reconnects at the end from refetching to get the tail and `[DONE]`.
- **What it owns.** The model's in-use mark and the cleanup the response's shielded `finally` does today: committing partial text, releasing the mark, deleting an empty turn. Moving them from the response to the run removes the reason for the shield.
- **Storage is unchanged.** Both turns are written before the run starts, the assistant turn when it ends ([chat](../../architecture/chat.md), The stream). Saving a live run's text is [`04-partial-replies.md`](04-partial-replies.md).

## Routes

| Method | Path | Does |
|---|---|---|
| `POST` | `/chat/threads/{thread_id}/messages` | unchanged for the caller: starts the run and follows it from frame 1 |
| `GET` | `/chat/threads/{thread_id}/run?after={seq}` | follows the active run: replays frames after `seq`, then streams live; `Last-Event-ID` works in place of `after`; `404` when the thread has no run |
| `POST` | `/chat/threads/{thread_id}/run/stop` | cancels the run, queued or running; `204`, also when nothing runs |
| `GET` | `/workspaces/{workspace_id}/chat/threads` | adds `running: bool` to each thread |

- Every frame carries its sequence number as the SSE `id:` field, so a follower can resume where it was.
- A new frame, `run-state`, reports `queued` with a `position`, then `running`. Before admission ([`02-admission.md`](02-admission.md)) exists, a run goes straight to `running`. Existing clients ignore a frame they do not know.
- A follower that disconnects ends only itself. Stop, deleting the thread and deleting its workspace end the run.

## Telling other windows

The API publishes a `chat-runs` event on `/workspaces/{id}/events`, `{"ids": [thread ids], "status": "running" | "done"}`, when a run starts and ends, as it does for documents and artifacts ([overview](../../architecture/overview.md), Freshness). The thread list reloads on it.

## The frontend

- **Runs move out of the per-thread runtime** into a store keyed by thread id, which holds each followed run's live copy, its last sequence number and its state. The runtime of the active thread reads from it, so leaving a thread no longer drops its reply.
- **Opening a thread with `running: true`** follows its run with `after` set to what the store already has (0 if nothing), then folds into the stored turns as today, once both ids are stored.
- **Stop** calls `run/stop` instead of aborting the request.
- **The thread list** shows running threads with a spinner and "Waiting" for a queued run.
- **Reloading the window** loses the store. Every running thread is followed again from `after=0` when opened, and the live copy is rebuilt from the replay.

## Quitting

- **Electron asks** before quitting while any run is active: "N replies are still being written. Quit anyway?" It learns the count from the API, at quit time only.
- **What a quit keeps** (stopping runs before the sidecars, saving live text, settling turns at startup) is [`04-partial-replies.md`](04-partial-replies.md).

## Why the buffer is not stored

- **The API cannot outlive the app.** It is a child of Electron on loopback, so when it is gone there is no client left to replay to.
- **The database already holds the result.** The API writes the assistant turn when the run ends, and a follower that comes back later reads the stored turns. The buffer only spares a follower that reconnects at that moment from refetching.
- **Every write contends for one file.** Each transaction takes the lock with `BEGIN IMMEDIATE`, and ingest writes to the same file ([overview](../../architecture/overview.md), Layer boundary). Storing deltas would add a write stream per running reply for nothing the API does not already have.
- **The run sits above the provider,** so a remote connection gets background runs as a local model does.

## Tests

At the HTTP seam, against a scripted generator:

- A run started, its follower disconnected, then followed with `after=0`: every frame once, in order, ending `[DONE]`.
- `after=n` replays exactly the frames after `n`.
- A second send to a running thread is `409`.
- Stop on a running run ends it, commits partial text and releases the in-use mark; a disconnect does none of those.
- Deleting a thread with a run ends the run.

## Open questions

- Whether the 60-second tail is long enough for a window reload on a slow machine, or the buffer should live until the next run in that thread.
- Whether an agent turn's `permission-request` should be answerable from a window that reattached after it was sent. The frame replays, so it should, but the dialog's state has to come from the replay.
