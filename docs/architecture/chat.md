# Chat

A chat thread belongs to a workspace. Each user message retrieves its own context from that workspace, the selected generation model streams an answer grounded in those passages, and each claim can cite the passage it came from. The server owns the conversation: both turns are stored before the reply streams and the assistant's text is written when it ends, citations are resolved to chunk ids before they are stored, and the frontend's live copy of a streaming reply gives way to the stored turns once they catch up.

**Code:** [`modules/chat/`](../../surfsense_local/backend/modules/chat/), [`shared/search.py`](../../surfsense_local/backend/shared/search.py), [`frontend/src/features/chat/`](../../surfsense_local/frontend/src/features/chat/)
**Decisions:** [ADR 0006](../adr/0006-hybrid-retrieval.md), [ADR 0011](../adr/0011-llama-cpp-local-runtime.md)

## Endpoints

| Method | Path | Does |
|---|---|---|
| `POST` | `/workspaces/{workspace_id}/chat/threads` | open a thread; the title defaults to "New chat" |
| `GET` | `/workspaces/{workspace_id}/chat/threads` | list, newest first |
| `PATCH` | `/chat/threads/{thread_id}` | rename, 1 to 200 characters |
| `DELETE` | `/chat/threads/{thread_id}` | delete; its messages cascade, and its artifacts stay with the thread cleared |
| `GET` | `/chat/threads/{thread_id}/messages` | the stored turns, oldest first |
| `POST` | `/chat/threads/{thread_id}/messages` | send a message; the reply streams back as `text/event-stream` |

A message body is `{"text": "...", "document_ids": [...]}`. `document_ids` is the retrieval scope for this turn: omitted, the whole workspace is searched; an empty list retrieves nothing; at most 1,000 ids. Each id must belong to the thread's workspace (`422`) and be `ready` (`409`).

## Grounding shape

The retrieved passages go into the system message, after a fixed instruction block:

```text
<instruction block for the model's tier>

<retrieved_context>
These are excerpts from the user's knowledge base, selected for this query. ...
<document title="Quarterly report" view="excerpt">
  [1] ...passage text...
  [3] ...passage text...
</document>
<document title="Meeting notes" view="excerpt">
  [2] ...passage text...
</document>
</retrieved_context>
```

- Hits are numbered 1 to N in rank order and grouped under their document, in the order each document first appears. The model cites `[n]`. The numbers are per message.
- The instruction block tells the model to answer from the sources, put a label right after the claim it supports, cite only what the sources back, say when the context does not hold the answer and then answer from its own knowledge if it can, and reply in the question's language, with a one-line example. Explicit rules earn their keep on small local models.
- It ships as three markdown files in [`modules/chat/prompts/`](../../surfsense_local/backend/modules/chat/prompts/): `compact.md`, `capable.md` and `frontier.md`. All three carry the same citation rules; `capable.md` adds a work order and `frontier.md` advice on how to shape an answer. `build_context(hits, tier)` loads the one for the selected model's prompt tier, which comes from the fingerprint recorded when the model was chosen, or from the model's name when none was recorded ([`local-models/selection.md`](local-models/selection.md)); it is not a user setting.
- A passage cannot forge a source. `<source>`, `<context>`, `<document>` and `<retrieved_context>` tags in its text are stripped before it goes between the tags, so a document cannot close its block early or inject a label, and the document title is escaped as an attribute.
- No hits, no context block: the system message is the instruction alone, and the model answers from its own knowledge.

## Message assembly

The list handed to the generator is `[system, *history within budget, user]`.

- **History** is the thread's stored turns in `created_at` order, flattened to role and text. Stored citations are for the UI, not the model.
- **Sliding window.** The system message and the new user message are pinned; the most recent prior turns that fit the history budget are kept and older ones dropped.
- **Budget** ([`budget.py`](../../surfsense_local/backend/modules/chat/budget.py)). One context window is shared by the system prompt (priced at 400 tokens), the excerpts (2,400: five hits of up to 480 tokens), the question (1,024) and a 1,024-token answer reserve, which is claimed first because llama.cpp stops a reply wherever the window runs out. History gets what remains of the model's window, floored at zero, so a narrow window means a shorter history rather than an overflowing turn. llama.cpp reports the window it actually allocated; an OpenAI-compatible endpoint reports none, and then history gets 3,000 tokens and `max_tokens` is left to the endpoint.
- Each prior turn is priced by the local runtime's own tokenizer when it answers, and by `len(text) // 4` otherwise.
- **Retrieval query** is the new user message.

## The stream

`POST .../messages` does, in order:

1. Resolve the generation selection. With none, it answers `409` "no chat model selected" before anything streams, and the frontend opens model setup. It also validates `document_ids`, answers `503` if the embedding model files are missing, loads the history and runs `retrieve()`.
2. Build the context and the message list, and read the model's context window.
3. Mark the model in use, so it cannot be deleted mid-answer; a deletion already in progress makes this a `409`.
4. Store the user turn and an empty assistant turn together. Their ids stay stable for the whole stream.
5. Stream the frames below.
6. When the generator closes, resolve citations and store the assistant turn with its `completed_at`, then send the tail.

| Frame | When | Carries |
|---|---|---|
| `accepted` | first | `user_message_id`, `assistant_message_id`, `user_created_at` |
| `citation-catalog` | second | every passage this turn may cite |
| `thread-title-update` | only on the turn that names an untitled thread | `title` |
| `delta` | per token chunk | `text` |
| `error` | on a generator failure | `kind`, `message`, `provider` |
| `citations` | once, if the reply cited anything | the cited passages, in first-cited order |
| `completed` | last | `assistant_completed_at`, the final `text` |

- Every frame is `data: {json}\n\n`, and the stream ends with `data: [DONE]\n\n` so a client can tell completion from a dropped connection. The response sends `Cache-Control: no-cache` and `X-Accel-Buffering: no` so nothing buffers it into one late blob.
- A turn that fails before producing any text is deleted, both halves, and the stream goes from `error` straight to `[DONE]`. A turn that fails midway keeps its partial text.
- Errors are sorted by exception type, HTTP status and provider, and for a 400 by the body's `error.type` ([`errors.py`](../../surfsense_local/backend/modules/chat/errors.py)), into `provider_auth`, `provider_not_found`, `provider_rate_limited`, `provider_unavailable`, `model_cannot_run`, `context_too_long`, `network`, `timeout` and `unknown`, each with a plain-language message.

## Citations

- The catalog frame arrives before any token, so the renderer can resolve a streamed `[n]` to its chunk the moment it appears.
- When the stream closes, `resolve_citations()` rewrites each `[n]`, and a stray `[citation:n]`, to `[citation:<chunk_id>]` in the stored text and drops numbers the model invented. Citation-shaped text inside code stays literal. What is stored points at a chunk, not at a per-message ordinal.
- A citation carries `source_id`, `chunk_id`, `document_id`, `start_line`, `end_line` and the document's `title`. An assistant turn's stored `content` is `{"text", "citations"}`; a user turn's is `{"text"}`, or `{"text", "citations": []}` when it was imported.

## Title generation

- On a thread's first turn, while its title is still "New chat", [`title.py`](../../surfsense_local/backend/modules/chat/title.py) asks the selected model for a 2 to 5 word noun phrase: temperature 0, reasoning off, at most 12 tokens and 100 characters, and validated as one line of 1 to 6 words, so raw model output is never shown.
- It has no timeout of its own. How long a model may take is the provider's concern, which applies one budget until the first token and a tighter one between tokens.
- It runs before the answer starts, so the first reply in a new thread waits for it.
- The title is announced mid-stream as `thread-title-update`, but the rename commits only in the branch that keeps the turn, so a turn that is discarded never renames its thread.

## Frontend runtime

- [`use-chat-runtime.ts`](../../surfsense_local/frontend/src/features/chat/use-chat-runtime.ts) uses assistant-ui's `useExternalStoreRuntime`. FastAPI is already the source of truth for threads and messages, and a local-runtime history adapter would add a second persistence path that could write a message twice.
- Threads and messages are TanStack Query data. While a reply streams, the view is a live copy: the stored turns plus an optimistic user turn and a draft assistant turn. `accepted` swaps in the real ids; when the stream ends the thread is refetched, and the live copy is dropped once the stored turns contain both ids.
- The runtime is scoped to the active thread; thread lists and workspaces stay application state. Sending from a new chat first creates a thread titled "New chat". The last open thread of each workspace is remembered in `localStorage`.
- [`sse.ts`](../../surfsense_local/frontend/src/features/chat/sse.ts) parses the stream chunk-safely: frames split on blank lines, and a partial frame waits for the next read. This token stream is separate from the `/events` channel.
- Sending is disabled without a usable model or while threads or messages load, and Stop aborts the request. A `409` "no chat model selected" opens model setup. An `error` frame attaches to its assistant turn: auth and not-found errors, and network errors from a remote endpoint, offer Model setup; a network error from the local runtime offers nothing, since no setting restarts it; the rest offer Retry, which resends the same text.
- Every turn sends the ids of the ready sources the user left included in the sources panel, so unticking a source takes it out of retrieval, and unticking all of them leaves the model with no context.

## Citation panel

- A citation renders as a chip showing the chunk id, and the chip is a real button. Clicking it opens the citation panel in the right rail.
- The panel loads `GET /workspaces/{id}/documents/by-chunk/{chunk_id}?chunk_window=5`: the cited chunk and up to five neighbours on each side in document order, scoped to the workspace, so another workspace's chunk is a `404`. It highlights the cited chunk, scrolls to it, says how many chunks lie outside the window, and for an uploaded file offers "Open file", which opens the original through the preload bridge.

## Accessibility

- Icon-only controls carry accessible names: send, stop, add sources, copy, scroll to the latest message, and the chat actions.
- The conversation, the sources list, the citation panel and the artifact panel are labelled regions.
- Citations are buttons, not clickable `div`s.
- A failed turn shows in an alert, which assistive technology announces.
- The composer follows assistant-ui's keyboard behaviour.
- The startup loader and the typed-in thread title respect `prefers-reduced-motion`.

## Non-goals

- A settings endpoint for chat: model choice lives in `/llm/selection` ([`local-models/selection.md`](local-models/selection.md)).
- Follow-up suggestions, regenerating a reply and branching a thread.
- Tools. The model cannot call anything; Studio jobs start from the Studio panel ([`studio.md`](studio.md)).

## Known gaps

- A stream that ends without an error but yields no text still renames the thread and stores an empty assistant turn; the discard guard is `failed and not parts`.
- `budget.py` prices the question at 1,024 tokens and says `MessageText` enforces that, but `MessageText` has no length limit, so a long question can push a turn past the model's window.
- The frontend's copy of the error kinds in `sse.ts` lacks `model_cannot_run` and `context_too_long`, so both offer Retry, which cannot fix either.
- No live region announces streamed text, and focus does not move to the conversation heading after a thread switch; the dashboard design asks for both.
- No test covers a client disconnecting mid-reply. The assistant's text is written only when generation ends, inside the stream, so whether a disconnected reply is kept is unverified.
