# Chat

A chat thread belongs to a workspace. Each user message retrieves its own context from that workspace, the selected generation model streams an answer grounded in those passages, and each claim can cite the passage it came from. The server owns the conversation: both turns are stored before the reply streams and the assistant's text is written when it ends, citations are resolved to chunk ids before they are stored, and the frontend's live copy of a streaming reply gives way to the stored turns once they catch up.

**Code:** [`modules/chat/`](../../surfsense_local/backend/modules/chat/), [`shared/search.py`](../../surfsense_local/backend/shared/search.py), [`frontend/src/features/chat/`](../../surfsense_local/frontend/src/features/chat/)
**Decisions:** [ADR 0006](../adr/0006-hybrid-retrieval.md), [ADR 0011](../adr/0011-llama-cpp-local-runtime.md), [ADR 0034](../adr/0034-vision-is-the-runtimes-answer-stored-nowhere.md)

## Endpoints

| Method | Path | Does |
|---|---|---|
| `POST` | `/workspaces/{workspace_id}/chat/threads` | open a thread; the title defaults to "New chat" |
| `GET` | `/workspaces/{workspace_id}/chat/threads` | list, newest first |
| `PATCH` | `/chat/threads/{thread_id}` | rename, 1 to 200 characters |
| `DELETE` | `/chat/threads/{thread_id}` | delete; its messages cascade, its artifacts stay with the thread cleared, and its images' folder goes after the commit |
| `GET` | `/chat/threads/{thread_id}/messages` | the stored turns, oldest first |
| `POST` | `/chat/threads/{thread_id}/messages` | send a message; the reply streams back as `text/event-stream` |
| `GET` | `/chat/threads/{thread_id}/messages/{message_id}/images/{index}` | an image a stored turn carried |
| `POST` | `/chat/threads/{thread_id}/permissions/{request_id}` | answer an agent thread's request to run something, `{"reply": "once" \| "reject"}`; `204` ([Agent threads](#agent-threads)) |

A message body is `{"text": "...", "document_ids": [...], "images": [...], "thinking": true}`; `images` is covered in [Images](#images) and `thinking` in [The thinking switch](#the-thinking-switch). `document_ids` is the retrieval scope for this turn: omitted, the whole workspace is searched; an empty list retrieves nothing; at most 1,000 ids. Each id must belong to the thread's workspace (`422`) and be `ready` (`409`).

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
- It ships as three markdown files in [`modules/chat/prompts/`](../../surfsense_local/backend/modules/chat/prompts/): `compact.md`, `capable.md` and `frontier.md`. All three carry the same citation rules, except where the [chat eval](../proposals/chat-eval.md) measured `compact.md` on Qwen3 1.7B: when the sources fall short, it answers from its own knowledge only with general knowledge, never guesses a detail of the user's own documents, products or people, labels neither sentence, and shows an example of each. `capable.md` adds a work order and `frontier.md` advice on how to shape an answer. `build_context(hits, tier)` loads the one for the selected model's prompt tier, which comes from the fingerprint recorded when the model was chosen, or from the model's name when none was recorded ([`local-models/selection.md`](local-models/selection.md)); it is not a user setting.
- A passage cannot forge a source. `<source>`, `<context>`, `<document>` and `<retrieved_context>` tags in its text are stripped before it goes between the tags, so a document cannot close its block early or inject a label, and the document title is escaped as an attribute.
- No hits, no context block: the system message is a short instruction with no citation rules, the same for every tier. It asks the model to say the knowledge base does not cover the question, then answer from general knowledge if it can, never guessing about the user's own documents, products or people.

## Message assembly

The list handed to the generator is `[system, *history within budget, user]`.

- **History** is the thread's stored turns in `created_at` order, flattened to role and text. Stored citations and reasoning are for the UI, not the model. The newest earlier turn that carried images also carries them, unless the new turn brings its own ([Images](#images)).
- **Sliding window.** The system message and the new user message are pinned; the most recent prior turns that fit the history budget are kept and older ones dropped.
- **Budget** ([`budget.py`](../../surfsense_local/backend/modules/chat/budget.py)). One context window is shared by the system prompt (priced at 400 tokens), the excerpts (2,400: five hits of up to 480 tokens), the question (1,024, which `MessageText` enforces at the wire as 4,096 characters at the same four-characters-a-token estimate, refusing more with a 422 before any model is resolved) and a 1,024-token answer reserve, which is claimed first because llama.cpp stops a reply wherever the window runs out. History gets what remains of the model's window, floored at zero, so a narrow window means a shorter history rather than an overflowing turn. llama.cpp reports the window it actually allocated; an OpenAI-compatible endpoint reports none, and then history gets 3,000 tokens and `max_tokens` is left to the endpoint.
- Each prior turn is priced by the local runtime's own tokenizer when it answers, and by `len(text) // 4` otherwise, plus 1,400 tokens per image it carries. The new turn's images are paid for out of the history budget before any prior turn is priced.
- **Retrieval query** is the new user message.

## The stream

`POST .../messages` does, in order:

1. Resolve the generation selection. With none, it answers `409` "no chat model selected" before anything streams, and the frontend opens model setup. It also validates `document_ids`, answers `503` if the embedding model files are missing, loads the history and runs `retrieve()`.
2. Ask the generator whether the model reads images. A turn carrying images to a model that answers no gets a `409` and nothing is stored; images that are not an accepted image get a `422`.
3. Build the context and the message list, with any images and retrieved image sources, and read the model's context window.
4. Mark the model in use, so it cannot be deleted mid-answer; a deletion already in progress makes this a `409`.
5. Store the user turn, with its images' files, and an empty assistant turn together. Their ids stay stable for the whole stream.
6. Stream the frames below.
7. When the generator closes, resolve citations and store the assistant turn with its `completed_at`, then send the tail.

| Frame | When | Carries |
|---|---|---|
| `accepted` | first | `user_message_id`, `assistant_message_id`, `user_created_at` |
| `citation-catalog` | second | every passage this turn may cite |
| `thread-title-update` | only on the turn that names an untitled thread | `title` |
| `prompt-progress` | per batch of prompt the local runtime reads, before the first token; no other endpoint sends it | `processed` and `total`, in tokens it had left to read |
| `reasoning` | per chunk of a thinking model's trace, before its answer | `text` |
| `reasoning-end` | once, when the answer starts or the stream ends, if the model reasoned | `duration_ms`, from the trace's first chunk |
| `delta` | per token chunk of the answer | `text` |
| `error` | on a generator failure | `kind`, `message`, `provider` |
| `citations` | once, if the reply cited anything | the cited passages, in first-cited order |
| `completed` | last | `assistant_completed_at`, the final `text` |

- Every frame is `data: {json}\n\n`, and the stream ends with `data: [DONE]\n\n` so a client can tell completion from a dropped connection. The response sends `Cache-Control: no-cache` and `X-Accel-Buffering: no` so nothing buffers it into one late blob.
- A turn that ends without any answer text is deleted, both halves, with any image file no other turn of the thread points at, and the stream goes from `error` straight to `[DONE]`, even if the model had reasoned. That holds whether generation failed or closed cleanly with nothing to say; the clean case is sent as `unknown`, because discarding the turn also removes the person's own message and silence would hide that. A turn that fails midway keeps its partial text.
- A client that hangs up mid-reply still commits the partial text and releases the model's in-use mark. Both cleanup paths are shielded from Starlette cancelling the response task on `http.disconnect`.
- The trace comes from the provider's `chat_deltas()`, which marks each chunk as answer or reasoning ([`connections.md`](connections.md#runtime)). It never reaches `resolve_citations()`, so a `[n]` inside it is neither rewritten nor stored as a citation.
- Errors are sorted by exception type, HTTP status and provider, and for a 400 by the body's `error.type` ([`errors.py`](../../surfsense_local/backend/modules/chat/errors.py)), into `provider_auth`, `provider_not_found`, `provider_rate_limited`, `provider_unavailable`, `model_cannot_run`, `context_too_long`, `subscription_sign_in`, `subscription_limit`, `network`, `timeout` and `unknown`, each with a plain-language English message. The two `subscription_` kinds come from a ChatGPT connection: its account has to sign in again, or its plan's usage limit is reached, which no retry fixes ([`chatgpt-subscription.md`](chatgpt-subscription.md)). The frontend shows its own translated text per kind ([`chat-error-text.ts`](../../surfsense_local/frontend/src/features/chat/chat-error-text.ts)); a pre-stream `unknown` failure keeps an informative error message inside a translated sentence, and an unrecognized future kind falls back to the backend's message.

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
- The title is announced mid-stream as `thread-title-update`, but the rename commits only in the branch that keeps the turn, so a turn that is discarded never renames its thread.

## The thinking switch

`thinking` is a field of the turn, on unless the request says `false`; chat has no settings route to hold it. Off, the router passes `reasoning=False` to `chat_deltas`, as title generation does, and the local runtime adds its two request fields ([`local-models/runtime.md`](local-models/runtime.md#turning-thinking-off)), so a thinking model answers with no trace and none is stored. On, nothing is added and the model keeps its own default.

Only the local runtime has a way to be told. A remote endpoint has no portable field for it, so `thinking: false` changes nothing there, and an agent thread does not read the field.

The Thinking switch is a row of the composer's "+" menu ([`thinking-menu-item.tsx`](../../surfsense_local/frontend/src/features/chat/thinking-menu-item.tsx)), shown once a model is chosen. It holds the preference in `localStorage` under `surfsense:chat-thinking:v1`, for every thread and workspace, the way the last open thread is remembered. It is read when a message is sent, and only an off preference with a `llamacpp` selection puts `thinking: false` in the request. With any other selection the row stays in the menu, on and disabled, and its tooltip says "Only a local model can answer without thinking". The menu stays open when the row is clicked, so the switch is seen to move.

What it does not do:

- It does not change how a thinking model samples beyond that. A curated Qwen3 commits a temperature for thinking only, so with thinking off it answers at llama-server's default: a mode with no set of its own is not given the other mode's ([`local-models/runtime.md`](local-models/runtime.md)).
- On a local model that never thinks, such as Gemma 3, the button is enabled and changes nothing: the request carries `thinking: false` and the model answers as it would have.

## Frontend runtime

- [`use-chat-runtime.ts`](../../surfsense_local/frontend/src/features/chat/use-chat-runtime.ts) uses assistant-ui's `useExternalStoreRuntime`. FastAPI is already the source of truth for threads and messages, and a local-runtime history adapter would add a second persistence path that could write a message twice.
- Threads and messages are TanStack Query data. While a reply streams, the view is a live copy: the stored turns plus an optimistic user turn and a draft assistant turn. `accepted` swaps in the real ids; when the stream ends the thread is refetched, and the live copy is dropped once the stored turns contain both ids.
- The runtime is scoped to the active thread; thread lists and workspaces stay application state. Sending from a new chat first creates a thread titled "New chat". The last open thread of each workspace is remembered in `localStorage`.
- [`sse.ts`](../../surfsense_local/frontend/src/features/chat/sse.ts) parses the stream chunk-safely: frames split on blank lines, and a partial frame waits for the next read. This token stream is separate from the `/events` channel.
- From send until the first token, the assistant turn shows a shimmering "Thinking" beside an orbiting-dots indicator ported from surfsense_web ([`thinking-indicator.tsx`](../../surfsense_local/frontend/src/features/chat/thinking-indicator.tsx)), so a model load or a long prompt is never a blank reply. It is one header from send to answer, whose state moves from waiting to thinking to done, so the indicator and shimmer never restart when the trace arrives. While the local runtime reads a long prompt the label is "Reading 42%" instead, from the latest `prompt-progress` frame, shown only between the first token read and the last, so a prompt of one batch and a turn with no such frame stay "Thinking". The header's `role="status"` region follows by quarters ("Reading 25%"), not at every frame. The figure is kept with the live message only and is never stored. A thinking model's trace then streams open below it, above the answer, rendered as markdown by the same Streamdown setup and link and image restrictions as the answer, in a box 13rem tall that fades at its scrolled edges and follows the newest line until the reader scrolls up, and folds to "Thought for N seconds" when the answer starts, the indicator sliding away; the person's own open or close wins until the next reply, and holds the chat's scroll still while the trace slides, with assistant-ui's `useScrollLock` ([`reply-thinking.tsx`](../../surfsense_local/frontend/src/features/chat/reply-thinking.tsx)). The trace rides in the message's `metadata.custom`, beside the citations, not as a content part, so Copy takes the answer alone.
- Images use assistant-ui's own attachments ([`image-attachments.ts`](../../surfsense_local/frontend/src/features/chat/image-attachments.ts)). The runtime gets `SimpleImageAttachmentAdapter`, narrowed to the accepted formats, only while the selection's `reads_images` is true, so a model that cannot see has no adapter and the composer takes no image. The composer's "+" opens a menu ([`composer-add-menu.tsx`](../../surfsense_local/frontend/src/features/chat/composer-add-menu.tsx)) with separate "Attach images" and "Upload sources" items, plus the Thinking switch, so a file is never a guess between the two, and dropping a file onto the composer does nothing. "Upload sources" opens the same picker and upload as the sources panel's Add, and is disabled while an upload runs. Images come in two ways: pasting into the composer (`Input`'s `addAttachmentOnPaste`), and "Attach images", which is assistant-ui's `ComposerPrimitive.AddAttachment` and opens a picker limited to the adapter's formats. With a model that cannot see, the item stays in the menu, disabled but still hoverable, and its tooltip says "This model can’t read images". Each row's tooltip is also in the row as screen-reader text, since Base UI tooltips are visual only ([`menu-item-hint.tsx`](../../surfsense_local/frontend/src/features/chat/menu-item-hint.tsx)); `ComposerPrimitive.Attachments` draws the pending ones with `AttachmentPrimitive` and `MessagePrimitive.Attachments` the sent ones ([`attached-image.tsx`](../../surfsense_local/frontend/src/features/chat/attached-image.tsx)). Until a turn is stored its images show from what was picked; after, from the image route. Retry resends a failed turn's images.
- Sending is disabled without a usable model or while threads or messages load, and Stop aborts the request. A `409` "no chat model selected" opens model setup. An `error` frame attaches to its assistant turn: auth, not-found and model-cannot-run errors, and network errors from a remote endpoint, offer Model setup; a network error from the local runtime and a context-too-long error offer nothing, since no button fixes either; the rest offer Retry, which resends the same text.
- Every turn sends the ids of the ready sources the user left included in the sources panel, so unticking a source takes it out of retrieval, and unticking all of them leaves the model with no context.
- An agent thread uses the same runtime. Its ids are opencode's strings, so a live turn counts as stored once both ids are in the refetched thread, whatever their type; only the placeholders sent before `accepted` never do. Each `agent-step` frame adds or updates one step of the live reply, and a stored reply's `content.steps` carries the same. They ride in `metadata.custom` beside the citations and show above the answer as one line each, with a spinner while it runs and a mark when it fails, opening to the step's output or error ([`features/agent/agent-steps.tsx`](../../surfsense_local/frontend/src/features/agent/agent-steps.tsx)). A `permission-request` waits in the runtime until `permission-replied`, until it is answered or until the turn ends. The oldest waiting request opens an alert dialog with the full command and Deny and Allow once; Esc and Deny both answer `reject`, and when others are waiting the dialog says denying refuses them too, as opencode does ([`features/agent/approval-dialog.tsx`](../../surfsense_local/frontend/src/features/agent/approval-dialog.tsx)).

## Citation panel

- A citation renders as a chip showing the chunk id, and the chip is a real button. Clicking it opens the citation panel in the right rail.
- The panel loads `GET /workspaces/{id}/documents/by-chunk/{chunk_id}?chunk_window=5`: the cited chunk and up to five neighbours on each side in document order, scoped to the workspace, so another workspace's chunk is a `404`. It highlights the cited chunk, scrolls to it, says how many chunks lie outside the window, and for an uploaded file offers "Open file", which opens the original through the preload bridge.

## Accessibility

- Icon-only controls carry accessible names: send, stop, attach images, remove image, copy, scroll to the latest message, and the chat actions. An attached image is named "Attached image".
- The conversation, the sources list, the citation panel and the artifact panel are labelled regions.
- Citations are buttons, not clickable `div`s.
- A failed turn shows in an alert, which assistive technology announces.
- The composer follows assistant-ui's keyboard behaviour.
- The startup loader and the typed-in thread title respect `prefers-reduced-motion`.

## Agent threads

How the agent runs is in [agent](agent.md). A thread is opened for the agent instead of the chat when the selected model may run it: a model on the tested list, which is empty, or any model while `SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1`, and only one that calls tools as far as SurfSense can tell ([`modules/agent/engine_choice.py`](../../surfsense_local/backend/modules/agent/engine_choice.py), [agent](agent.md#which-threads-get-it)). Opening such a thread starts opencode if it is not running, waits until it serves SurfSense's configuration, and opens an opencode session under the thread's title; the session's id is stored on the thread, and `ThreadRead` reports `uses_agent`. When opencode is not part of the install or is not ready, the thread opens as a chat. A thread keeps the engine it was opened with ([agent proposal](../proposals/agent/01-which-engine.md)).

The same routes then reach the agent ([`modules/agent/agent_threads/`](../../surfsense_local/backend/modules/agent/agent_threads/)):

- **Sending** brings the workspace's sources folder in line, renames a thread still called "New chat" after its first message's first 60 characters, and streams the turn as opencode runs it. The frames are the chat's (`accepted`, `thread-title-update` after it, `delta`, `reasoning`, `reasoning-end`, `completed`, `error`, `[DONE]`) plus `agent-step` for each tool call as its status moves (`id`, `tool`, `status`, `title`, `input`, `output` up to 4,000 characters, `error`), `permission-request` (`id`, `permission`, `patterns`, `command`) and `permission-replied`. `completed` carries the reply as opencode stored it, with the passages it cites as `[citation:<chunk id>]`, after a `citations` frame listing them ([agent](agent.md#a-turn)). Message ids are opencode's: a user turn's own, and `<user message id>:reply` for its reply. Closing the stream stops the turn. `document_ids` means what it does for a chat, checked the same way: the ticked sources are the turn's whole scope, an empty list is none, and an omitted field is the whole workspace ([agent](agent.md#the-ticked-sources)). Images are refused with `409`, and so is any turn once the selected model can no longer run the agent.
- **Listing** reads the session from opencode: each user turn, then one assistant reply joining the text and the steps of every assistant message opencode wrote for it, with `content.steps` and `content.citations` beside `content.text`. A user turn sent with `document_ids` carries `content.scope`, `{document_ids, titles}`, the sources it was given that still exist, and its text holds only the user's words.
- **Deleting** stops the session's turn and deletes the session first, and deleting a workspace does the same for each of its agent threads before the rows go.

## Non-goals

- A settings endpoint for chat: model choice lives in `/llm/selection` ([`local-models/selection.md`](local-models/selection.md)).
- Follow-up suggestions, regenerating a reply and branching a thread.
- Tools in the chat. The chat's model cannot call anything, and a thread that needs tools is the agent's ([Agent threads](#agent-threads)); Studio jobs start from the Studio panel ([`studio.md`](studio.md)).

## Known gaps

- An agent thread ignores the thinking switch, and its composer still shows the button as if it applied.
- An agent thread's session is deleted only while opencode is running; one deleted before any turn has started opencode in this run of the app stays in opencode's database.
- An agent thread's first turn is named after its first words, not by the model as a chat's is.
- An agent thread refuses images.
- No live region announces streamed text, and focus does not move to the conversation heading after a thread switch; the dashboard design asks for both.
- A thinking model spends the 1,024-token answer cap on its reasoning too: `max_tokens` counts what goes to `reasoning_content`, as the title measurement in [`local-models/runtime.md`](local-models/runtime.md#turning-thinking-off) shows, so on the local runtime a long think can cut the answer short or leave it empty. The trace now shows, so an empty answer is no longer unexplained, but how often it happens is unmeasured.
- Nothing shows progress while a model loads beyond "Thinking": llama-server's prompt progress starts once the model is up ([`local-models/runtime.md`](local-models/runtime.md#prompt-progress)).
- Nothing refuses a turn whose images alone outgrow the window. History floors at zero, but four attached images at 1,400 tokens each overflow a small local window before any history is kept, and the turn fails as `context_too_long`.
- The per-image cost is priced, not measured: Gemma 3, the curated vision model, spends a fixed 256, and 1,400 covers Qwen2.5-VL at the 1,024 px cap. No measurement at the pinned build confirms either.
