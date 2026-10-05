# Partial replies

A reply cut off by a quit or a crash keeps the text it had, and is shown as cut off. Today that holds only when the client disconnects first. Once runs ([`01-runs.md`](01-runs.md)) stop ending on a disconnect, it would not hold at all without this part.

## Today

- **The assistant row starts empty.** It is stored as `{"text": "", "citations": []}` with `completed_at` null before the reply streams, and `_complete` writes its text in the stream's shielded `finally` ([`router.py`](../../../surfsense_local/backend/modules/chat/router.py)). Nothing writes it in between.
- **That `finally` runs on a disconnect, not on a kill.** Electron stops the API with SIGTERM and SIGKILL 5 seconds later on macOS and Linux, and with `taskkill /t /f` on Windows ([`supervisor.ts`](../../../surfsense_local/electron/src/main/sidecars/supervisor.ts)). A crash or a forced kill runs no Python at all.
- **Closing the window quits the app** on every platform (`window-all-closed`, [`index.ts`](../../../surfsense_local/electron/src/main/index.ts)). The renderer goes first, so its disconnect most likely commits the partial text before the API is stopped. Quitting from the menu stops the sidecars with the window still open.
- **A crash leaves the empty row behind.** The "no answer, no turn" deletion lives in the same `finally`, so it does not run either. The thread then shows a blank reply that looks finished, since a stored turn is marked incomplete only for an error or a stop (`toRuntimeMessage` in [`use-chat-runtime.ts`](../../../surfsense_local/frontend/src/features/chat/use-chat-runtime.ts)). The next turn sends it to the model as an empty assistant message, because history is every stored turn, with no filter on `completed_at` ([`history.py`](../../../surfsense_local/backend/modules/chat/history.py)).

## What runs change

A follower that disconnects no longer ends its run. Closing the window therefore stops saving the partial reply, and every quit becomes a kill of a live reply. Background runs also make it likelier that one is live when the app goes: several can run, for longer, in threads nobody is looking at.

## Stopping runs before a quit

The main fix. After the quit confirmation ([`01-runs.md`](01-runs.md), Quitting), and before it stops any sidecar, Electron calls an internal `POST /chat/runs/stop-all`. The API cancels every run and answers once each has committed, or after 3 seconds, whichever is first. Electron then stops the sidecars as today. It works the same on every platform, the Windows kill included, because the commit happens before anything is killed rather than in a signal handler.

## Saving while a run is live

The backstop, for a crash, and for a stop-all that runs out of time. While a run has answer text, it writes that text to its assistant row every 5 seconds, so a reply that dies loses at most the last 5 seconds.

- **Never on the streaming path.** `transact()` takes the write lock with `BEGIN IMMEDIATE` and waits up to 5 seconds for it ([`dependencies.py`](../../../surfsense_local/backend/api/dependencies.py)), and the ingest worker writes to the same file. A save on the path that yields frames could hold a reply's tokens for as long. The save runs in its own task, with its own session.
- **A failed save is skipped.** A lock it cannot get, or any other error, skips that save. The run and its final write do not depend on it.
- **Citations resolved, as at the end.** The stored text has `[n]` rewritten to `[citation:<chunk id>]`, and history sends that text to the model. A save runs the same `resolve_citations()` on the partial text, so a reply that dies never stores a raw `[1]`.
- **Only once there is answer text.** A turn with none is still deleted at the end, so a save never makes a turn that would otherwise have been discarded.

`_complete` overwrites the whole content at the end, so the last save never conflicts with the final write. The window following a run renders its live copy while the run is going and ignores stored turns until it ends (`usesLiveMessages`), so a save never shows twice there. A window that reopens a running thread must show the run's replay rather than the saved text, which [`01-runs.md`](01-runs.md) owns.

Agent turns are stored by opencode, not in this row, and are not affected.

## At startup

Before it serves anything, the API settles every assistant turn left without `completed_at`:

- **No text:** deleted with its user turn and any image file no other turn of the thread points at, as `_discard_turn` and `_sweep_images` do at the end of a turn today.
- **Text:** kept, with `completed_at` set and `"interrupted": true` in its content. The frontend renders it as stopped with "Interrupted when the app closed".

Worker jobs already settle the documents a quit left processing the same way ([`interrupted_documents.py`](../../../surfsense_local/backend/worker/interrupted_documents.py)).

## Shipping

The deletion of empty turns at startup fixes today's blank reply and does not need runs, so it can ship first, as a bug fix. Stopping runs before a quit and saving while a run is live need the run task, and ship with [`01-runs.md`](01-runs.md) or straight after it, before a release carries runs without them.

## Tests

- An assistant turn left empty at startup is deleted with its user turn; one left with text is kept, marked interrupted.
- With two live runs, `stop-all` answers after both have committed their partial text.
- `stop-all` answers within 3 seconds when a run cannot commit.
- A live run's row holds its text, citations resolved, within 5 seconds; a save that cannot get the lock is skipped and the run's final write still lands.
- A run with no answer text writes nothing before it ends.

## Open questions

- Whether closing the window today does commit the partial reply before the API is stopped. The order is read from the code, not observed.
- Whether 3 seconds is enough for `stop-all` with four runs and ingest holding the lock, and whether Electron's quit should wait on a progress indicator instead of a fixed bound.
