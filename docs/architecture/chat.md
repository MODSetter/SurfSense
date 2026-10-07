# Chat

A chat thread belongs to a workspace. Each user message retrieves its own context from that workspace, the selected generation model streams an answer grounded in those passages, and each claim can cite the passage it came from. The server owns the conversation and every reply: a reply is a run in the API that keeps generating whoever watches it, both turns are stored before it starts and the assistant's text when it ends, citations are resolved to chunk ids before they are stored, and the frontend's live copy of a reply gives way to the stored turns once they catch up. Several threads can be answering at once, on any model.

**Code:** [`modules/chat/`](../../surfsense_local/backend/modules/chat/), [`modules/chat/runs/`](../../surfsense_local/backend/modules/chat/runs/), [`shared/search.py`](../../surfsense_local/backend/shared/search.py), [`frontend/src/features/chat/`](../../surfsense_local/frontend/src/features/chat/), [`electron/src/main/quit/`](../../surfsense_local/electron/src/main/quit/)
**Decisions:** [ADR 0006](../adr/0006-hybrid-retrieval.md), [ADR 0011](../adr/0011-llama-cpp-local-runtime.md), [ADR 0034](../adr/0034-vision-is-the-runtimes-answer-stored-nowhere.md), [ADR 0048](../adr/0048-the-api-is-the-only-path-to-a-text-model.md), [ADR 0049](../adr/0049-prompts-grow-at-the-end.md)

## Endpoints

| Method | Path | Does |
|---|---|---|
| `POST` | `/workspaces/{workspace_id}/chat/threads` | open a thread, with an optional `source_scope`; the title defaults to "New chat" |
| `GET` | `/workspaces/{workspace_id}/chat/threads` | list, newest first, each with `running` while a reply is being generated for it, and `run_state`, `{state, position}`: `queued` with its place in line, `running`, or `needs-approval` while an agent turn waits on the user; `null` when nothing runs |
| `PATCH` | `/chat/threads/{thread_id}` | rename, 1 to 200 characters |
| `DELETE` | `/chat/threads/{thread_id}` | delete; a running reply is stopped first, waiting up to 5 seconds, then its messages cascade, its artifacts stay with the thread cleared, and its images' folder goes after the commit |
| `GET` | `/chat/threads/{thread_id}/messages` | the stored turns, oldest first |
| `POST` | `/chat/threads/{thread_id}/messages` | send a message: starts the thread's run and follows it as `text/event-stream`; `409` while the thread is still answering |
| `GET` | `/chat/threads/{thread_id}/run?after={seq}` | follow the thread's running reply: replays the frames numbered above `after` (or `Last-Event-ID`), then streams live; `404` once it has ended |
| `POST` | `/chat/threads/{thread_id}/run/stop` | stop the reply, queued or generating; `204`, also when nothing runs |
| `GET` | `/chat/runs` | `{"active": n}`, the replies being generated; what Electron asks before quitting |
| `POST` | `/chat/runs/stop-all` | store and end every reply, marked interrupted, within 3 seconds; `204` |
| `GET` | `/chat/threads/{thread_id}/messages/{message_id}/images/{index}` | an image a stored turn carried |
| `GET` | `/chat/threads/{thread_id}/source-scope` | the thread's scope and its counts ([Source scope](#source-scope)) |
| `PUT` | `/chat/threads/{thread_id}/source-scope` | store ticks made between turns; answers the pruned scope and its counts |
| `POST` | `/workspaces/{workspace_id}/source-scope/resolve` | count a draft scope, for a new chat or a Studio job |
| `POST` | `/chat/threads/{thread_id}/permissions/{request_id}` | answer an agent thread's request to run something, `{"reply": "once" \| "reject"}`; `204` ([Agent threads](#agent-threads)) |

A message body is `{"text": "...", "source_scope": {...}, "document_ids": [...], "images": [...], "thinking": true, "retry_of": null}`; `images` is covered in [Images](#images), `thinking` in [The thinking switch](#the-thinking-switch) and `retry_of` in [Retry](#retry). A sent `source_scope` is validated, stored on the thread and used, in one transaction, so ticking a box and pressing Enter cannot race. With none, `document_ids` keeps its older meaning for plugins and older clients: an explicit list, at most 1,000 ids, each in the thread's workspace (`422`) and `ready` (`409`), an empty list retrieving nothing. With neither, the thread's stored scope is used. An agent thread resolves its turn's sources the same way, with no cap on the resolved ids ([agent](agent.md#the-ticked-sources)).

## Source scope

`{all, folder_ids, excluded_folder_ids, document_ids, excluded_document_ids}`, each list at most 50,000 ids, which bounds the request body rather than a workspace, and each reaches SQLite as one `json_each` parameter, so its 32,766-parameter limit never applies ([`modules/source_scope/`](../../surfsense_local/backend/modules/source_scope/)). The server resolves it to ids for every turn and Studio job, so there is no client-side cap on how many sources a chat uses.

- `all` takes every `FILE` and `NOTE` and every filed artifact, never an unfiled one. Ticked folders take their whole subtree, including files added later; excluded folders then come out; `document_ids` are added back, so one file can be ticked inside an unticked folder; `excluded_document_ids` come out last. A folder being deleted takes its subtree out at once.
- Only `ready` sources are searched. The counts are `{ready, indexing, failed, removed}`: a source still indexing is counted, not refused. An id in another workspace is `422`; one that no longer exists is counted as `removed` and pruned from the stored scope.
- A thread with no stored scope uses `{all: true}`.
- Each user turn grounded on a scope records `source_scope` and `resolved: {count, ids_sha256}` in its `content`, so a replay can tell whether it ran on the same sources.
- [`test_folder_scope_end_to_end.py`](../../surfsense_local/backend/tests/integration/chat/test_folder_scope_end_to_end.py) walks the whole path: it makes folders, uploads a folder of 62 files with relative paths, ticks the folder, and checks that chat cites only that folder's sources, the oldest past the 50 newest included, even with an id list sent beside the scope, and that a Studio job records and is grounded on exactly that folder.

## Grounding shape

The system message is a fixed instruction block, and the retrieved passages go into the new user message, ahead of the question:

```text
system: <instruction block for the model's tier>

user:   <retrieved_context>
These are excerpts from the user's knowledge base, selected for this query. ...
<document title="Quarterly report" view="excerpt">
  [1] ...passage text...
  [3] ...passage text...
</document>
<document title="Meeting notes" view="excerpt">
  [2] ...passage text...
</document>
</retrieved_context>

        Question: <the question>
```

- The passages change with every question, and llama-server reuses a prompt only up to its first changed token, so they come after the history rather than ahead of it. Earlier questions reach the model without their passages, as they did before. Measured on Qwen3 1.7B at an 8,192-token window, with answers of about 450 tokens: turn 7 read 3,873 tokens of its prompt instead of 6,304.
- The question is labelled. Unlabelled after the passages, Qwen3 1.7B answered the chat eval's "And the X300?" about the X200 its last passage named, in three runs of three. Labelled, it scored the expected facts and the supporting passage in 24 of 24 answers, against 23 and 24 with the passages in the system message.
- Hits are numbered 1 to N in rank order and grouped under their document, in the order each document first appears. The model cites `[n]`. The numbers are per message.
- The instruction block tells the model to answer from the sources, put a label right after the claim it supports, cite only what the sources back, say when the context does not hold the answer and then answer from its own knowledge if it can, and reply in the question's language, with a one-line example. Explicit rules earn their keep on small local models.
- It ships as three markdown files in [`modules/chat/prompts/`](../../surfsense_local/backend/modules/chat/prompts/): `compact.md`, `capable.md` and `frontier.md`. All three carry the same citation rules, except where the [chat eval](../proposals/chat-eval.md) measured `compact.md` on Qwen3 1.7B: when the sources fall short, it answers from its own knowledge only with general knowledge, never guesses a detail of the user's own documents, products or people, labels neither sentence, and shows an example of each. `capable.md` adds a work order and `frontier.md` advice on how to shape an answer. `build_context(hits, tier)` returns it with the excerpts and their citations, loading the one for the selected model's prompt tier, which comes from the fingerprint recorded when the model was chosen, or from the model's name when none was recorded ([`local-models/selection.md`](local-models/selection.md)); it is not a user setting.
- A passage cannot forge a source. `<source>`, `<context>`, `<document>` and `<retrieved_context>` tags in its text are stripped before it goes between the tags, so a document cannot close its block early or inject a label, and the document title is escaped as an attribute.
- No hits, no context block: the user message is the question alone, and the system message is a short instruction with no citation rules, the same for every tier. It asks the model to say the knowledge base does not cover the question, then answer from general knowledge if it can, never guessing about the user's own documents, products or people.

## Message assembly

The list handed to the generator is `[system, *history within budget, user]`.

- **History** is the thread's stored turns in `created_at` order, flattened to role and text. Stored citations and reasoning are for the UI, not the model. The newest earlier turn that carried images also carries them, unless the new turn brings its own ([Images](#images)).
- **Sliding window.** The system message and the new user message are pinned. History runs from where the last turn's started, `history_start_message_id` on the thread, while it fits the budget. Past it, the newest whole exchanges that fit under 75% of the budget are kept (`HISTORY_HEADROOM`), and the thread records the first one, so the turns after it start at the same message. Cut to the brim instead, every turn past the budget moved where history starts, and llama-server re-read all of it.
- **Budget** ([`budget.py`](../../surfsense_local/backend/modules/chat/budget.py)). One context window is shared by the system prompt (priced at 400 tokens), the excerpts (2,400: five hits of up to 480 tokens), the question (1,024, which `MessageText` enforces at the wire as 4,096 characters at the same four-characters-a-token estimate, refusing more with a 422 before any model is resolved) and a 1,024-token answer reserve, which is claimed first because llama.cpp stops a reply wherever the window runs out. History gets what remains of the model's window, floored at zero, so a narrow window means a shorter history rather than an overflowing turn. llama.cpp reports the window it actually allocated; an OpenAI-compatible endpoint reports none, and then history gets 3,000 tokens and `max_tokens` is left to the endpoint.
- Each prior turn is priced by the local runtime's own tokenizer when it answers, and by `len(text) // 4` otherwise, plus 1,400 tokens per image it carries. The new turn's images are paid for out of the history budget before any prior turn is priced. That 1,400 is a ceiling for the trim, not a limit: the turn is refused with a 409, before either of its messages is stored, only when a lower bound overflows a known window, the answer reserve plus the turn's own excerpts and question plus 256 per image, Gemma 3's fixed cost. The detail names how many images could fit; an unknown window lets the turn through.
- **Retrieval query** is the new user message.

## The stream

`POST .../messages` does, in order:

1. Refuse a thread that is still answering with `409`. Resolve the generation selection. With none, it answers `409` "no chat model selected" before anything streams, and the frontend opens model setup. It also resolves and stores the source scope (or validates `document_ids`), validates `retry_of`, answers `503` if the embedding model files are missing, loads the history and runs `retrieve()`.
2. Ask the generator whether the model reads images. A turn carrying images to a model that answers no gets a `409` and neither message is stored (a sent scope already is, in step 1), and so does one whose images overflow a known window even at 256 each ([Message assembly](#message-assembly)); images that are not an accepted image get a `422`.
3. Build the context and the message list, with any images and retrieved image sources, and read the model's context window.
4. Mark the model in use, so it cannot be deleted mid-answer; a deletion already in progress makes this a `409`.
5. Store the user turn, with its images' files, and an empty assistant turn together, deleting the turn a retry replaces in the same transaction. Their ids stay stable for the whole run.
6. Start the thread's run ([Runs](#runs)) and follow it from its first frame. The request only watches: hanging up ends the request, never the run.
7. The run generates the frames below. On the local runtime it waits for admission first ([`local-models/admission.md`](local-models/admission.md)). When the generator closes, it resolves citations and stores the assistant turn with its `completed_at` and how it ended, then sends the tail.

| Frame | When | Carries |
|---|---|---|
| `accepted` | first | `user_message_id`, `assistant_message_id`, `user_created_at` |
| `citation-catalog` | second | every passage this turn may cite |
| `run-state` | `queued` while admission holds a local reply back, with each change of place; `running` once it may generate, at once for a remote model | `state`, and `position` while queued |
| `thread-title-update` | only on the turn that names an untitled thread | `title` |
| `prompt-progress` | per batch of prompt the local runtime reads, before the first token; no other endpoint sends it | `processed` and `total`, in tokens it had left to read |
| `reasoning` | per chunk of a thinking model's trace, before its answer | `text` |
| `reasoning-end` | once, when the answer starts or the stream ends, if the model reasoned | `duration_ms`, from the trace's first chunk |
| `delta` | per token chunk of the answer | `text` |
| `error` | on a generator failure | `kind`, `message`, `provider` |
| `citations` | once, if the reply cited anything | the cited passages, in first-cited order |
| `completed` | last | `assistant_completed_at`, the final `text` |

- Every frame is `id: <seq>\ndata: {json}\n\n`, numbered from 1 within its run, and the stream ends with `data: [DONE]\n\n` so a client can tell completion from a dropped connection. The response sends `Cache-Control: no-cache` and `X-Accel-Buffering: no` so nothing buffers it into one late blob.
- The trace comes from the provider's `chat_deltas()`, which marks each chunk as answer or reasoning ([`connections.md`](connections.md#runtime)). It never reaches `resolve_citations()`, so a `[n]` inside it is neither rewritten nor stored as a citation.
- Errors are sorted by exception type, HTTP status and provider, and for a 400 by the body's `error.type` ([`errors.py`](../../surfsense_local/backend/modules/chat/errors.py)), into `provider_auth`, `provider_not_found`, `provider_rate_limited`, `provider_unavailable`, `model_cannot_run`, `context_too_long`, `subscription_sign_in`, `subscription_limit`, `runtime_busy`, `network`, `timeout` and `unknown`, each with a plain-language English message. `runtime_busy` is the local runtime's shared cache running out of room under replies running together, which llama.cpp reports as a `500` like a model that failed to load; admission makes it rare, and it offers Retry ([admission](local-models/admission.md)). The two `subscription_` kinds come from a ChatGPT connection, in a chat or an agent thread: its account has to sign in again, or its plan's usage limit is reached, which no retry fixes ([`chatgpt-subscription.md`](chatgpt-subscription.md)). A subscription's own `429` or 5xx is retried twice first, after the wait it asks for and at most a minute. The frontend shows its own translated text per kind ([`chat-error-text.ts`](../../surfsense_local/frontend/src/features/chat/chat-error-text.ts)); a pre-stream `unknown` failure keeps an informative error message inside a translated sentence, and an unrecognized future kind falls back to the backend's message.

## Runs

A run is one reply being generated, by either engine: a chat reply on any chat model (the local runtime, a remote connection or a ChatGPT subscription), or an agent turn ([Agent threads](#agent-threads)). The run layer knows threads and frames, not engines: each engine hands it a frame generator, a cleanup and where the run stands ([`modules/chat/runs/`](../../surfsense_local/backend/modules/chat/runs/)).

- **One per thread,** held in memory in the API process. The API dies with the app, so nothing a database adds would outlive the run, and the events broker already relies on one uvicorn process.
- **The run owns the reply.** It reads the generator to the end, numbers and keeps every frame for any number of followers, holds the model's in-use mark, and stores the reply and how it ended. Reloading the window, switching thread or workspace, or closing the request drops a follower and nothing else.
- **It leaves memory only after its reply is stored,** so a follower that arrives after the end gets `404` and finds the whole reply in the thread's turns.
- **A live save** writes the reply's text so far, citations resolved, to its assistant turn every 5 seconds, in its own task and session ([`live_text.py`](../../surfsense_local/backend/modules/chat/runs/live_text.py)). A save that cannot get the lock is skipped; the final write does not depend on it. A crash loses at most those 5 seconds.
- **Where it stands** is the run's state, set by its engine: `queued` with its place while admission holds a local chat reply back, `running`, or `needs-approval` while an agent turn waits on a `permission-request`. Setting it sends a `run-state` frame and tells every window; the thread list reports it as `run_state`.
- **Every window hears** a run start, change state and end as a `chat-runs` event on `/workspaces/{id}/events`, `{"ids": [thread id], "status": "running" | "queued" | "needs-approval" | "done"}` ([overview](overview.md#freshness)).
- **Deleting** a thread stops its run first, waiting up to 5 seconds for it to store what it has, and deleting a workspace does the same for each of its threads, so no reply writes into a thread that is gone.
- **At startup,** before anything is served, every assistant turn left without `completed_at` is settled as `interrupted`, with or without text ([`interrupted_turns.py`](../../surfsense_local/backend/modules/chat/interrupted_turns.py)).
- **Quitting.** Electron asks the API how many runs are active when the app is about to quit, by the menu or by closing the last window. With any, a native dialog asks "N replies are still being written. Quitting saves what they have so far.", in English like the application menu; Quit calls `stop-all`, which stores each reply as interrupted, before the sidecars stop ([`electron/src/main/quit/`](../../surfsense_local/electron/src/main/quit/)).
- **Remote models** are not admitted: they never queue, and several run against one provider at once. A provider's `429` ends a run as `provider_rate_limited`.

### How a turn ends

A chat thread's assistant turn stores how it ended in its content, as `ending`, beside `text` and `citations`:

| Ending | `ending` | When |
|---|---|---|
| Completed | absent | the reply finished |
| Failed | `{"type": "error", "kind", "message"}`, the `error` frame's fields | the generator failed, or closed cleanly with no answer text (`unknown`) |
| Stopped | `{"type": "stopped"}` | the person pressed Stop after some text |
| Interrupted | `{"type": "interrupted"}` | a quit, or the API going away, cut it off |

- **A failed turn is kept,** with or without text, so the question stays with the reason it failed. A turn stopped before any text is deleted, both halves, with any image file no other turn of the thread points at: the person chose to stop and there is nothing to show.
- **History skips** a failed or interrupted reply with no text, together with its question, so the model never receives an empty answer or two questions in a row ([`history.py`](../../surfsense_local/backend/modules/chat/history.py)). One with text stays, as a partial reply always did.
- **A thread is renamed** only when its first turn ends with answer text.

### Retry

`retry_of` names the thread's latest reply when it failed or was interrupted. In the transaction that stores the new turns, the API deletes that pair and any image file only it pointed at, so the question appears once; naming any other turn, or one that neither failed nor was interrupted, is `409`. An older failure stays as a record. Keeping the failed attempt viewable is branching, a non-goal.

## Citations

- The catalog frame arrives before any token, so the renderer can resolve a streamed `[n]` to its chunk the moment it appears.
- When the stream closes, `resolve_citations()` rewrites each `[n]`, and a stray `[citation:n]`, to `[citation:<chunk_id>]` in the stored text and drops numbers the model invented. Citation-shaped text inside code stays literal. What is stored points at a chunk, not at a per-message ordinal.
- A citation carries `source_id`, `chunk_id`, `document_id`, `start_line`, `end_line` and the document's `title`. An assistant turn's stored `content` is `{"text", "citations"}`, plus `"reasoning": {"text", "duration_ms"}` when the model reasoned; a user turn's is `{"text"}`, `{"text", "images"}` when it carried images, or `{"text", "citations": []}` when it was imported.

## Images

A turn can carry images, and a model that reads them receives them; every other model receives exactly the request a text turn sends.

- **Whether a model reads images** is one answer, worked out where it is asked and stored nowhere ([ADR 0034](../adr/0034-vision-is-the-runtimes-answer-stored-nowhere.md)). For a local model it is llama-server's `/models`, which lists `image` for a model whose preset gave it a projector that reads images ([`local-models/selection.md`](local-models/selection.md#capabilities-and-the-system-role)); for a remote one, the catalog's `modalities.input` ([`connections.md`](connections.md#the-remote-catalog)). The selection routes report it as `reads_images`, and the send asks the generator's `sees_images()`. An unreadable `/models` is no answer: the send lets the turn through, and llama-server's own "image input is not supported" becomes an ordinary chat error.
- **The request.** `images` is at most 4 of `{"mime", "data"}`, `data` being base64 of at most 10 MB decoded. `mime` is the client's word only; Pillow reads the bytes, and PNG, JPEG, WebP, GIF (its first frame), BMP and TIFF are accepted, anything else `422`. `text` stays required; the composer sends "What is in this image?" when a person attaches images and types nothing.
- **Normalised before it is stored or sent** ([`images/intake.py`](../../surfsense_local/backend/modules/chat/images/intake.py)): turned upright from its EXIF orientation, scaled to at most 1,024 px on its longest side, and re-encoded as PNG when it has transparency, JPEG otherwise. Every runtime and provider decodes the result, it stays under every per-image limit, and 1,024 px is about 1,340 tokens on Qwen2.5-VL, the most a small local window can give one picture.
- **Stored** at `data/workspaces/<workspace>/chats/<thread>/<sha256>.<ext>`, so a picture attached twice in a thread is one file ([`images/store.py`](../../surfsense_local/backend/modules/chat/images/store.py)). The turn keeps `images: [{"key", "mime", "size_bytes", "sha256"}]`, `key` relative to the data directory as an artifact's storage key is. SQLite never carries the bytes.
- **Resent.** The newest earlier turn with images carries them on every later turn until a newer turn brings its own, so a follow-up about the same picture works without paying for every picture the thread has seen. A missing file leaves its turn as text.
- **Image sources.** When the model reads images and retrieval returns chunks of an uploaded image, its original is read through `original_path()`, normalised the same way and attached to the new turn beside its OCR text: at most 2, the highest ranked, and only as many as fit the history budget once the person's own images are paid for ([`images/sources.py`](../../surfsense_local/backend/modules/chat/images/sources.py)). They are never stored with the turn, so image sources indexed before this need nothing.
- **Sent** as OpenAI typed parts, `[{"type": "text"}, {"type": "image_url", "image_url": {"url": "data:…"}}]`, on the turn that carries them; every other turn keeps string content. llama.cpp's `for_template()` strips images for a model that cannot see, so a thread switched to a text model carries on as text, and keeps them when it folds the system prompt into the first turn.

## Title generation

- On a thread's first turn, while its title is still "New chat", [`title.py`](../../surfsense_local/backend/modules/chat/title.py) asks the selected model for a 2 to 5 word noun phrase: temperature 0, reasoning off, at most 12 tokens and 100 characters, and validated as one line of 1 to 6 words, so raw model output is never shown.
- It has no timeout of its own. How long a model may take is the provider's concern, which applies one budget until the first token and a tighter one between tokens.
- It runs before the answer starts, so the first reply in a new thread waits for it.
- The title is announced mid-stream as `thread-title-update`, but the rename commits only when the turn ends with answer text, so a failed or stopped first turn never renames its thread. On the local runtime it is admitted like the reply, as interactive work.

## The thinking switch

`thinking` is a field of the turn, on unless the request says `false`; chat has no settings route to hold it. Off, the router passes `reasoning=False` to `chat_deltas`, as title generation does, and the local runtime adds its two request fields ([`local-models/runtime.md`](local-models/runtime.md#turning-thinking-off)), so a thinking model answers with no trace and none is stored. On, nothing is added and the model keeps its own default.

Only the local runtime has a way to be told. A remote endpoint has no portable field for it, so `thinking: false` changes nothing there, and an agent thread does not read the field.

The Thinking switch is a row of the composer's "+" menu ([`thinking-menu-item.tsx`](../../surfsense_local/frontend/src/features/chat/thinking-menu-item.tsx)), shown once a model is chosen. It holds the preference in `localStorage` under `surfsense:chat-thinking:v1`, for every thread and workspace, the way the last open thread is remembered. It is read when a message is sent, and only an off preference with a `llamacpp` selection puts `thinking: false` in the request. With any other selection the row stays in the menu, on and disabled, and its tooltip says "Only a local model can answer without thinking". The menu stays open when the row is clicked, so the switch is seen to move.

What it does not do:

- It does not change how a thinking model samples beyond that. A curated Qwen3 commits a temperature for thinking only, so with thinking off it answers at llama-server's default: a mode with no set of its own is not given the other mode's ([`local-models/runtime.md`](local-models/runtime.md)).
- On a local model that never thinks, such as Gemma 3, the button is enabled and changes nothing: the request carries `thinking: false` and the model answers as it would have.

## Frontend runtime

- [`use-chat-runtime.ts`](../../surfsense_local/frontend/src/features/chat/use-chat-runtime.ts) uses assistant-ui's `useExternalStoreRuntime`. FastAPI is already the source of truth for threads and messages, and a local-runtime history adapter would add a second persistence path that could write a message twice.
- Threads and messages are TanStack Query data. Replies in progress live outside React, in a store of one run per thread ([`runs/run-store.ts`](../../surfsense_local/frontend/src/features/chat/runs/run-store.ts)), so leaving a thread drops nothing: its reply keeps arriving in the background. The view is the stored turns with the run's live pair in place of their copies: an optimistic user turn and a draft assistant turn until `accepted` swaps in the real ids. One pure fold builds the pair from frames, whether they arrive from the send or from a replay ([`runs/apply-frame.ts`](../../surfsense_local/frontend/src/features/chat/runs/apply-frame.ts)). When a run ends the thread is refetched, and the live pair is dropped once the stored turns contain both ids.
- Opening a thread the list marks `running` that this window does not follow, after a reload or from another window, follows its run from frame 0 and rebuilds the reply from the replay; the question is the stored turn's. A `chat-runs` event refreshes the list; its `done` refreshes the open thread's turns, or marks another thread unread.
- A reply that ends while another thread is open marks its thread unread: a dot on its row in the Chats dialog and on the sidebar's Chats button, until the thread is opened. The set is per workspace in `localStorage` under `surfsense:unread-replies:<workspace>:v1`.
- The Chats dialog shows a spinner where the unread dot goes for a running thread, a clock for a queued one, and an alert in the accent colour for an agent turn waiting on the user's approval, each named to screen readers ("Writing a reply", the place in line, "Waiting for your approval"); each keeps its time, and rows keep their order. The states come from the thread list, so a window that follows none of them still shows them. The sidebar's Chats button shows one mark for the other threads: the alert when any waits on approval, else a dot when any is unread, else a spinner when any is writing or waiting, else nothing; the counts are read to screen readers only ([`left-sidebar.tsx`](../../surfsense_local/frontend/src/features/dashboard/left-sidebar.tsx)).
- Sending from a new chat first creates a thread titled "New chat". The last open thread of each workspace is remembered in `localStorage`.
- [`sse.ts`](../../surfsense_local/frontend/src/features/chat/sse.ts) parses the stream chunk-safely, with each frame's number: frames split on blank lines, and a partial frame waits for the next read. This token stream is separate from the `/events` channel.
- From send until the first token, the assistant turn shows a shimmering "Thinking" beside an orbiting-dots indicator ported from surfsense_web ([`thinking-indicator.tsx`](../../surfsense_local/frontend/src/features/chat/thinking-indicator.tsx)), so a model load or a long prompt is never a blank reply. It is one header from send to answer, whose state moves from waiting to thinking to done, so the indicator and shimmer never restart when the trace arrives. While a local reply waits for admission the label is "Waiting for another reply (2nd in line)", from the latest `run-state`. While the local runtime reads a long prompt the label is "Reading 42%" instead, from the latest `prompt-progress` frame, shown only between the first token read and the last, so a prompt of one batch and a turn with no such frame stay "Thinking". The header's `role="status"` region follows by quarters ("Reading 25%"), not at every frame. The figure is kept with the live message only and is never stored. A thinking model's trace then streams open below it, above the answer, rendered as markdown by the same Streamdown setup and link and image restrictions as the answer, in a box 13rem tall that fades at its scrolled edges and follows the newest line until the reader scrolls up, and folds to "Thought for N seconds" when the answer starts, the indicator sliding away; the person's own open or close wins until the next reply, and holds the chat's scroll still while the trace slides, with assistant-ui's `useScrollLock` ([`reply-thinking.tsx`](../../surfsense_local/frontend/src/features/chat/reply-thinking.tsx)). The trace rides in the message's `metadata.custom`, beside the citations, not as a content part, so Copy takes the answer alone.
- Replies, the trace, and Studio's Markdown documents and podcast transcripts render through one Streamdown setup ([`streamdown-config.ts`](../../surfsense_local/frontend/src/features/studio/viewers/streamdown-config.ts)) whose options keep their identity between renders, so a token re-parses only the block it changed and a page re-render around a finished reply or an open artifact parses nothing. The trace repairs an unclosed marker at its tail only, as the answer does, not across the whole trace at every token, so a marker left open in an earlier paragraph stays as written instead of closing at the trace's end. The live trace scrolls to its newest line at most once a frame, and only while open; the follow's own scroll, reported a frame later, never counts as the reader scrolling up. Code stays plain monospace while its reply or trace streams and takes its colours when that ends: highlighting each partial state of a growing block cost the main thread seconds and kept every state's tokens until reload. The highlighter ([`code-highlighter.ts`](../../surfsense_local/frontend/src/features/studio/viewers/code-highlighter.ts)) is @streamdown/code's, Shiki with the same themes, languages and tokens, keeping those of the last 100 blocks.
- Images use assistant-ui's own attachments ([`image-attachments.ts`](../../surfsense_local/frontend/src/features/chat/image-attachments.ts)). The runtime gets `SimpleImageAttachmentAdapter`, narrowed to the accepted formats, only while the selection's `reads_images` is true, so a model that cannot see has no adapter and the composer takes no image. The composer's "+" opens a menu ([`composer-add-menu.tsx`](../../surfsense_local/frontend/src/features/chat/composer-add-menu.tsx)) with separate "Attach images" and "Upload sources" items, plus the Thinking switch, so a file is never a guess between the two, and dropping a file onto the composer does nothing. "Upload sources" opens the same picker and upload as the sources panel's Add, and is disabled while an upload runs. Images come in two ways: pasting into the composer (`Input`'s `addAttachmentOnPaste`), and "Attach images", which is assistant-ui's `ComposerPrimitive.AddAttachment` and opens a picker limited to the adapter's formats. With a model that cannot see, the item stays in the menu, disabled but still hoverable, and its tooltip says "This model can’t read images". Each row's tooltip is also in the row as screen-reader text, since Base UI tooltips are visual only ([`menu-item-hint.tsx`](../../surfsense_local/frontend/src/features/chat/menu-item-hint.tsx)); `ComposerPrimitive.Attachments` draws the pending ones with `AttachmentPrimitive` and `MessagePrimitive.Attachments` the sent ones ([`attached-image.tsx`](../../surfsense_local/frontend/src/features/chat/attached-image.tsx)). Until a turn is stored its images show from what was picked; after, from the image route. Retry resends a failed turn's images, read back from the image route once the window no longer holds them.
- Sending is disabled without a usable model or while threads or messages load, and in a thread whose reply is still running. Stop calls `run/stop`, in either engine. A `409` "no chat model selected" opens model setup. A reply's error and stopped mark come from its stored `ending`, and from live frames only while its run is followed, so both survive a thread switch and a reload: auth, not-found and model-cannot-run errors, and network errors from a remote endpoint, offer Model setup; a network error from the local runtime, a context-too-long error and a used-up plan offer nothing, since no button fixes them; the rest, and an interrupted reply ("Interrupted when the app closed."), offer Retry, on the latest reply only, which sends the question again with `retry_of`.
- Every turn sends the sources panel's ticks as `source_scope`, so a ticked folder counts whole however many sources it holds, and beside it the ids of the ready sources those ticks include, which the server ignores when a scope comes with them; past the API's 1,000-id cap only the scope goes. Unticking a source takes it out of retrieval, and unticking all of them leaves the model with no context.
- An agent turn is a run like a chat reply: leaving its thread leaves it going, and it is followed again on return, marked unread when it ends elsewhere, and its stored ending is read back. Retry sends the question again without `retry_of`, which names a stored chat message. Its ids are opencode's strings, so a live turn counts as stored once both ids are in the refetched thread, whatever their type; only the placeholders sent before `accepted` never do. Each `agent-step` frame adds or updates one step of the live reply, and a stored reply's `content.steps` carries the same. They ride in `metadata.custom` beside the citations and show above the answer as one line each, with a spinner while it runs and a mark when it fails, opening to the step's output or error ([`features/agent/agent-steps.tsx`](../../surfsense_local/frontend/src/features/agent/agent-steps.tsx)). A `permission-request` waits in the runtime, kept per thread, until `permission-replied`, until it is answered or until the turn ends, so returning to a thread whose turn asked while another was open shows the request again. The oldest waiting request opens an alert dialog with the full command and Deny and Allow once; Esc and Deny both answer `reject`, and when others are waiting the dialog says denying refuses them too, as opencode does ([`features/agent/approval-dialog.tsx`](../../surfsense_local/frontend/src/features/agent/approval-dialog.tsx)).

## Citation panel

- A citation renders as a chip showing the chunk id, and the chip is a real button. Clicking it opens the citation panel in the right rail.
- The panel loads `GET /workspaces/{id}/documents/by-chunk/{chunk_id}?chunk_window=5`: the cited chunk and up to five neighbours on each side in document order, scoped to the workspace, so another workspace's chunk is a `404`. It highlights the cited chunk, scrolls to it, says how many chunks lie outside the window, and for an uploaded file offers "Open file", which opens the original through the preload bridge.

## Accessibility

- Icon-only controls carry accessible names: send, stop, attach images, remove image, copy, scroll to the latest message, and the chat actions. An attached image is named "Attached image".
- The conversation, the sources list, the citation panel and the artifact panel are labelled regions.
- Citations are buttons, not clickable `div`s.
- A failed turn shows in an alert, which assistive technology announces.
- The composer follows assistant-ui's keyboard behaviour.
- While the turn waits, the thinking header's `role="status"` region says "Thinking" or the reading quarter. A second region (`reply-announcer.tsx`) stays silent until it says "Reply finished" once, for a reply it watched run to completion. It is keyed by message, because messages render by index and an instance would otherwise watch one thread's reply and announce another's. Tokens are never fed to it, since a polite region read on every delta would interrupt without pause; a reply loaded from history, a turn that ended with no answer, and one that failed or was stopped after text arrived say nothing; its alert, or the stop, already does. A stopped reply is marked `incomplete` with reason `cancelled` by the runtime ([`use-chat-runtime.ts`](../../surfsense_local/frontend/src/features/chat/use-chat-runtime.ts)), since assistant-ui would otherwise call it complete once the run ends. A queued reply's header region says "Waiting for another reply" with its place. The Chats button's count is in its accessible name ("Chats, 2 replies being written"), and an unread row carries "New reply" as screen-reader text.
- The conversation has a heading, the thread's title, hidden visually because the visible title is the rename button. Focus does not move to it: on every thread switch the composer keeps the focus assistant-ui gives it, so someone can switch and type, and the composer is described by the heading (`aria-describedby`), so a screen reader names the conversation it writes into. A new chat has no heading until it is a thread.
- The startup loader and the typed-in thread title respect `prefers-reduced-motion`.

## Agent threads

How the agent runs is in [agent](agent.md). A thread is opened for the agent instead of the chat when the selected model may run it: a model measured at or near the agent's bar, a model not measured that the user opted in with "Try the agent" ([model capabilities](model-capabilities.md)), or any model while `SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1`, and only one that calls tools as far as SurfSense can tell ([`modules/agent/engine_choice.py`](../../surfsense_local/backend/modules/agent/engine_choice.py), [agent](agent.md#which-threads-get-it)). Opening such a thread starts opencode if it is not running, waits until it serves SurfSense's configuration, and opens an opencode session under the thread's title; the session's id is stored on the thread, and `ThreadRead` reports `uses_agent`. When opencode is not part of the install or is not ready, the thread opens as a chat. A thread keeps the engine it was opened with ([agent proposal](../proposals/agent/01-which-engine.md)).

The same routes then reach the agent ([`modules/agent/agent_threads/`](../../surfsense_local/backend/modules/agent/agent_threads/)):

- **Sending** refuses a thread whose session predates thread folders, or that opencode no longer has, with `409`, which the screen shows in the user's language under the unsent message with "Start a new chat" in place of Retry ([agent](agent.md#folders)), brings the thread's folder in line with its sources, renames a thread still called "New chat" after its first message's first 60 characters, and streams the turn as opencode runs it. The frames are the chat's (`accepted`, `thread-title-update` after it, `delta`, `reasoning`, `reasoning-end`, `completed`, `error`, `[DONE]`) plus `agent-step` for each tool call as its status moves (`id`, `tool`, `status`, `title`, `input`, `output` up to 4,000 characters, `error`), `permission-request` (`id`, `permission`, `patterns`, `command`) and `permission-replied`. `completed` carries the reply as opencode stored it, with the passages it cites as `[citation:<chunk id>]`, after a `citations` frame listing them ([agent](agent.md#a-turn)). Message ids are opencode's: a user turn's own, and `<user message id>:reply` for its reply. The turn runs as a run ([Runs](#runs)): a window that hangs up stops following it, not the turn, and `run/stop` and `stop-all` abort it in opencode, which keeps the text written so far. Each step it asks the model for is admitted on the local runtime as interactive work ([admission](local-models/admission.md)). `source_scope`, `document_ids` and the thread's stored scope mean what they do for a chat, resolved the same way: the resolved sources are the turn's whole scope and an empty result is none; only a thread that never stored a scope and a turn that sends neither gets the whole workspace. A sent `document_ids` is stored as the thread's scope. Every turn's stream opens with `agent-preparing`, `{count}`, before the thread's folder is brought in line, and a sync that fails ends it with an `error` frame. A turn whose scope is not every source then sends `agent-scope`, `{scope: {document_ids, titles}}`, or past 200 sources `{scope: {document_ids: [], titles: [], count}}` ([agent](agent.md#the-ticked-sources)). Images are refused with `409`, and so is any turn once the selected model can no longer run the agent, which the screen also answers with "Start a new chat" in place of Retry ([agent](agent.md#which-threads-get-it)).
- **Listing** reads the session from opencode: each user turn, then one assistant reply joining the text and the steps of every assistant message opencode wrote for it, with `content.steps` and `content.citations` beside `content.text`, and `content.ending` read from the reply's last step ([How an agent reply ended](#how-an-agent-reply-ended)). A user turn given a scope carries `content.scope`, `{document_ids, titles}`, the sources it was given that still exist, and its text holds only the user's words.
- **Deleting** stops the thread's run, then stops the session's turn, deletes the session and disposes its opencode instance first, then removes the thread's folder once the row is gone; deleting a workspace does the same for each of its agent threads before the rows go.

### How an agent reply ended

opencode 1.18.34 stores a Stop and a quit alike, as an abort: the reply's last step has `time.completed` and `error.name` `MessageAbortedError`, and keeps its text. A reply it never finished, because opencode exited on the quit's `SIGTERM` or crashed, has no `time.completed`, no error, and no text: opencode writes a reply's text only when it ends or is aborted. So Stop notes itself before it aborts, under the opencode session's own metadata, `surfsense.endings[<reply id>]`, which goes with the session ([`recorded_endings.py`](../../surfsense_local/backend/modules/agent/agent_threads/recorded_endings.py)). `PATCH /session/{id}` replaces the metadata whole, so the note is read, changed and written back with any other keys kept. The listing then reads ([`reply_ending.py`](../../surfsense_local/backend/modules/agent/agent_threads/reply_ending.py)):

| The reply's last step | Noted by Stop | `ending` |
|---|---|---|
| `MessageAbortedError` | yes | `stopped` |
| `MessageAbortedError` | no | `interrupted`: the app went away |
| any other `error` | either | `error`, with the kind and message the live stream showed: `subscription_limit` or `subscription_sign_in` for a ChatGPT plan's refusal the model endpoint coded ([`error_kind.py`](../../surfsense_local/backend/modules/agent/agent_threads/error_kind.py)), `unknown` otherwise |
| no `time.completed`, and the thread's run is over | either | `interrupted`: a crash, its text lost |
| no `time.completed`, and the thread's run is going | either | none: it is still being written |

A note that fails to save reads as `interrupted`, which offers Retry rather than hiding it.

## Non-goals

- A settings endpoint for chat: model choice lives in `/llm/selection` ([`local-models/selection.md`](local-models/selection.md)).
- Follow-up suggestions, regenerating a reply and branching a thread.
- Tools in the chat. The chat's model cannot call anything, and a thread that needs tools is the agent's ([Agent threads](#agent-threads)); Studio jobs start from the Studio panel ([`studio.md`](studio.md)).

## Known gaps

- The sources panel's ticks belong to the workspace for the session, not to a thread: opening a thread does not load its stored `source_scope`, and a new chat's draft is not kept across a reload. Each turn sends the ticks on screen, which the server then stores on that thread.
- The composer's and Studio's source counts come from the client's own listing, not from `POST /source-scope/resolve`, so they show ready sources only, never how many are still indexing or failed.
- A scope list past 50,000 ids is refused with `422`. The panel sends folders where it can, so only more than 50,000 sources ticked or unticked one by one reach it.
- The images `409` prices each image at Gemma 3's 256, so a dearer projector can still overflow unrefused: four Qwen2.5-VL images at the 1,024 px cap with five excerpts outgrow the 8,192 floor and fail as `context_too_long`.
- An agent thread ignores the thinking switch, and its composer still shows the button as if it applied.
- An agent thread's session is deleted only while opencode is running; one deleted before any turn has started opencode in this run of the app stays in opencode's database.
- An agent thread's first turn is named after its first words, not by the model as a chat's is.
- An agent thread refuses images.
- A thinking model spends the 1,024-token answer cap on its reasoning too: `max_tokens` counts what goes to `reasoning_content`, as the title measurement in [`local-models/runtime.md`](local-models/runtime.md#turning-thinking-off) shows, so on the local runtime a long think can cut the answer short or leave it empty. The trace now shows, so an empty answer is no longer unexplained, but how often it happens is unmeasured.
- Nothing shows progress while a model loads beyond "Thinking": llama-server's prompt progress starts once the model is up ([`local-models/runtime.md`](local-models/runtime.md#prompt-progress)).
- The per-image cost is priced, not measured: Gemma 3, the curated vision model, spends a fixed 256, and 1,400 covers Qwen2.5-VL at the 1,024 px cap. No measurement at the pinned build confirms either.
