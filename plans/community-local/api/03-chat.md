# API — Phase 3: Chat — done

> Built in [`modules/chat/`](../../../surfsense_local/backend/modules/chat/).
> Schema: [`../00c-data-model.md`](../00c-data-model.md) (`chat_threads`, `chat_messages`).
> Retrieval: [`../worker/03-search.md`](../worker/03-search.md) (`retrieve()`).
> Provider: [`modules/llm/`](../../../surfsense_local/backend/modules/llm/) (`Generator.chat`).

## Goal

Threaded, retrieval-grounded chat: a user message in a workspace retrieves its own
context, streams a cited answer from the selected model, and both turns persist.

## Already built — this phase only orchestrates

- **Retrieval** — `retrieve(session, workspace_id, query, top_k)` returns `Hit`s
  (chunk id, document id, content, line span, score).
- **Provider** — `modules/llm/`: `SelectedModel` holds the chat model, the registry
  hands back a `Generator`, and `Generator.chat(model, messages) -> AsyncIterator[str]`
  already streams deltas. This phase reads the selection and turns that stream into
  SSE with citations — it does not re-add a provider client.
- **Tables** — `ChatThread` and `ChatMessage` exist in `0001`. `ChatMessage.content`
  is JSON: the answer text and its citations travel together, and only the UI reads
  the shape.

So the new code is a `modules/chat/` router plus the assembly around it — no schema,
no migration, no provider work.

## Grounding shape

The answer is grounded by putting retrieved chunks in a **system message**, each
wrapped so the model can cite it, then instructing the model to answer only from
that context and mark claims with `[id]`:

```
<context>
<source id="1" document="42" lines="10-24">…chunk text…</source>
<source id="2" document="7" lines="1-9">…chunk text…</source>
</context>
```

- **Sequential ids (1..N)** map to the `Hit`s in rank order. The model cites `[1]`,
  `[2]`; the frontend resolves each id back to its document and line span from the
  citation list we return alongside the stream. Ids are per-message, not global.
- **A fixed instruction block** (task + guidelines) precedes the context: answer
  from the context, say so when the answer isn't there, cite with `[id]`, match the
  question's language, don't emit the tags back, with a one-line citation example —
  the explicit rules earn their keep on small local models. A module constant, not
  a user setting, for v1.
- **A chunk cannot forge a source**: source/context tags found in a chunk's own
  text are stripped before it goes between the tags, so a document can't close its
  block early or inject a fake `id`.
- **No hits → no context block**: the system message degrades to the plain
  instruction, and the model answers from its own knowledge (and is told to).

`modules/chat/prompt.py` builds the context string and the system message from a
`list[Hit]`; `modules/chat/citations.py` (or the same file) returns the ordered
`[{id, document_id, chunk_id, lines}]` the SSE tail carries.

## Message assembly, per turn

The array handed to `Generator.chat` is:

```
[ system(instructions + <context>), *history_within_budget, user(new message) ]
```

- **History** is the thread's `chat_messages` in `created_at` order, flattened to
  `Message(role, content_text)` — the JSON content's text part only; stored
  citations are for the UI, not the model.
- **Sliding window** — the system message and the new user message are pinned; the
  most recent prior turns that fit a token budget are kept, older ones dropped. The
  budget is a fraction of the model's context length.
  - ponytail: estimate tokens as `len(text) / 4` rather than loading the model's
    tokenizer. Ceiling: fine for trimming a soft budget; if answers start getting
    truncated by the runtime, swap in the real tokenizer count.
- **Retrieval query** is the new user message text.

## Endpoints

Threads are workspace-scoped; messages hang off a thread.

- `POST /workspaces/{workspace_id}/chat/threads` → create, optional title → thread.
- `GET  /workspaces/{workspace_id}/chat/threads` → list, newest first.
- `GET  /chat/threads/{thread_id}/messages` → the flat history for the UI.
- `POST /chat/threads/{thread_id}/messages` → **the orchestrator**. Body: the user
  text. Response: `text/event-stream`.
- `DELETE /chat/threads/{thread_id}` → drop a thread (cascades its messages).

### The stream

`POST .../messages` does, in order:

1. Read `SelectedModel(role="generation")`; resolve its `Generator`. No model
   selected → `409`, so the frontend can send the user to setup. This happens
   before anything streams, so it stays a clean HTTP error.
2. Persist the user turn.
3. `retrieve()` on the user text → `Hit`s.
4. Build the system message; assemble `[system, *trimmed history, user]`.
5. Stream `Generator.chat` deltas as SSE.
6. Emit the citation list, then persist the assistant turn (text + citations) as
   one `ChatMessage`, written as the generator closes so the request session
   commits it on exit.

**The SSE frames** are `data: {json}\n\n`, ending on a `data: [DONE]\n\n` sentinel
so a client tells completion apart from a dropped connection:

- `{"type": "delta", "text": "..."}` — one per token chunk.
- `{"type": "citations", "items": [...]}` — once, when there were hits.
- `{"type": "error", "message": "..."}` — on a generator failure; the partial turn
  still persists and the stream still ends on `[DONE]`.

The response carries `Cache-Control: no-cache` and `X-Accel-Buffering: no` so a
proxy streams it through rather than buffering it into one late blob.

## Not in this phase

- **Settings endpoint** — model choice already lives in `GET/PUT /llm/selection`,
  and the Ollama URL comes from Electron via env. No separate `/settings` is added.
- **Title generation, follow-up suggestions, regeneration, branching** — not planned.
- **Reranker** — the retrieval opt-in tracked in [`../worker/03-search.md`](../worker/03-search.md).

## Tests

- **Unit** — `prompt.py`: N hits → N `<source id>` blocks with document and lines;
  zero hits → instruction-only system message. Sliding window: pins system + latest
  user, drops oldest over budget, keeps order.
- **Integration** — a stub generator (the `StubOllama` pattern from the llm tests)
  plus real `retrieve()` over an ingested doc: `POST` a message → SSE deltas arrive,
  the citation tail names the ingested document, and both turns land in
  `chat_messages`. No model selected → `409`.

## Acceptance

- Ollama + ingested doc → streamed reply whose citation payload points the frontend
  at the source document and lines.
- Second message in a thread sees the first as history within the budget.
- Empty workspace (no hits) → a plain streamed answer, no citations, no error.

## Interface to frontend

Consumed by [`../frontend/03-chat.md`](../frontend/03-chat.md): SSE deltas render as
they arrive, the citation tail resolves `[id]` markers to document links.
