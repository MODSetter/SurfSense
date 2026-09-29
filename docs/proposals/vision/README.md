---
status: accepted
tracking: https://github.com/MODSetter/SurfSense/issues/1991
code:
  - surfsense_local/backend/modules/llm/
  - surfsense_local/backend/modules/chat/
  - surfsense_local/frontend/src/features/chat/
  - surfsense_local/frontend/src/features/models/
---

# Vision

> A chat model that reads images receives them, local or remote: images a person attaches to a turn, and image sources that retrieval finds. Every other model receives exactly the request it gets today.

Nothing in the app can hand a model an image today: `Message.content` is a `str` ([`types.py`](../../../surfsense_local/backend/modules/llm/providers/types.py)), and the composer sends text only ([chat](../../architecture/chat.md)). The local catalog already predicts which models read images, downloads their projectors and counts them in the memory fit ([catalog](../../architecture/local-models/catalog.md)); the remote manifest already records each model's input modalities, and 4,714 of its 8,116 entries list `image` ([connections](../../architecture/connections.md)). This proposal connects both to chat.

It replaces `chat-images.md`, which covered local models only.

## Layers

```text
UI            composer: attach, paste, drop · thread: images · pickers: Vision badge
  │  text + images (base64)
Chat API      check · normalise · store · add image sources · build the conversation
  │  Message(role, content, images)
Model layer   local: strip for a model that cannot see · both: image parts in the request
  │
llama-server (local)  ·  OpenAI-compatible provider (remote)

Beside all of them: "does the selected model read images?", one answer
```

## Decisions

### 1. One answer to "does this model read images?"

Every layer reads the same answer for the selected chat model.

| Model | Answer |
|---|---|
| Local, installed | llama-server's `/models` lists `image` in the model's `architecture.input_modalities`. |
| Local, not installed | The catalog's `reads_images`, for browsing and search only: the build's projector carries a vision encoder. |
| Remote | The manifest's `modalities.input` contains `image`, read as `Supports.reads_images` ([`support.py`](../../../surfsense_local/backend/modules/llm/catalog/remote/support.py)) through the connection's catalog provider. An id the manifest does not carry answers no. |

For an installed local model, llama.cpp is the only source:

- The preset gives a model `--mmproj` only when its projector is on disk, reads images and fits the model (`_pairs()` in [`preset.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/models_folder/preset.py)).
- At `b11050` the router reads that same projector's header for every preset model, loaded or not, and publishes the result as `input_modalities` ([`server-models.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/tools/server/server-models.cpp), `update_caps()` calling `mtmd_get_cap_from_file()`). Nothing is loaded and nothing is stored.
- The badge in Your models, the selection route and the send check all read it, so none of them can say yes while another says no. The catalog's prediction stops at install.

Around that answer:

- `can_see` becomes `Modality.IMAGE in inputs` ([`capabilities.py`](../../../surfsense_local/backend/modules/llm/providers/llamacpp/capabilities.py)). It also requires the template to take typed content today, on the belief that a string-only template has nowhere to put an image. At `b11050` that is not so: the server replaces each `image_url` part with a media marker before templating, and for a string-only template joins the parts into one string with the marker kept ([`server-common.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/tools/server/server-common.cpp), [`chat.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/common/chat.cpp) `concat_content_parts`). Unsloth Studio, on the same llama.cpp behaviour, checks no template capability either. The fix is confirmed once against a real vision model whose template is string-only.
- The selection routes report the answer as `SelectionRead.reads_images` ([`schemas.py`](../../../surfsense_local/backend/modules/llm/schemas.py)), so the composer knows before anything is sent.
- The chat route asks the generator at send time, `await generator.sees_images(model)`. llama.cpp answers from `/models`; the OpenAI-compatible provider answers what resolution passed it from the manifest ([`resolution.py`](../../../surfsense_local/backend/modules/llm/resolution.py)).
- A turn carrying images to a model that answers no gets a `409`, "This model can't read images", and nothing is stored.
- An unreadable `/models` is not an answer. The route treats it as unknown and lets the turn through; if the model truly cannot see, llama-server refuses with "image input is not supported" and that reaches the person as any chat error does.
- Rejected: recording a per-model answer. llama.cpp answers live for every installed model, so a stored copy could only fall behind it.
- A remote model's answer is the same wherever it is shown: the connection's model list, the selection route and the send check all call one lookup. Discovery's `_classify()` returns early for a model whose endpoint declares its output modalities, as OpenRouter's listing does, and never consults the manifest ([`service.py`](../../../surfsense_local/backend/modules/llm/connections/service.py)). Such a model keeps the types it declares and still takes `reads_images` from the manifest: the two answer different questions.
- Rejected for now: the endpoint's own declared input modalities as a first source. Discovery reads only output modalities ([`service.py`](../../../surfsense_local/backend/modules/llm/connections/service.py)) and nothing is persisted at selection, so a custom endpoint the manifest lacks answers no. See Known limits.

### 2. The `Message` type and the request

- `Message` gains `images: tuple[Image, ...] = ()`, where `Image` is `mime` and `data: bytes`. `content` stays a `str`, so Studio, titles and every text-only path do not change.
- Rejected: widening `content` to `str | list[Part]`. Every reader of `.content` would handle a union.
- The OpenAI-compatible request body ([`chat.py`](../../../surfsense_local/backend/modules/llm/providers/openai_compatible/chat.py)) sends `content` as a string when `images == ()`, byte for byte today's request. Otherwise it sends `[{"type": "text", …}, {"type": "image_url", "image_url": {"url": "data:<mime>;base64,…"}}]`. One builder serves llama.cpp and remote connections alike.
- `for_template()` ([`messages.py`](../../../surfsense_local/backend/modules/llm/providers/llamacpp/messages.py)) drops `images` from every message when `not can_see`, and its system-role fold carries `first.images` into the folded turn instead of losing them.

### 3. Attachments: the request, the checks, the cleanup

```json
POST /chat/threads/{thread_id}/messages
{"text": "…", "document_ids": [...], "images": [{"mime": "image/png", "data": "<base64>"}]}
```

- At most 4 images per turn, each at most 10 MB decoded. The magic bytes decide the type, not the claimed `mime`.
- Accepted: PNG, JPEG, WebP, GIF (first frame), BMP and TIFF. Anything else gets a `422`.
- Every image is normalised with Pillow before it is stored or sent: EXIF orientation applied, the longest side scaled down to a cap set at implementation (about 2048 px), and re-encoded as PNG when it has transparency, JPEG otherwise. That keeps every image in a format llama.cpp and every provider decode, under Anthropic's 5 MB per-image limit, and cheap in tokens.
- Pillow becomes a direct dependency. It is in the lock and the frozen API today only through python-pptx, reportlab and Docling, and no API code imports it.
- HEIC is out: Pillow cannot decode it without a plugin. Browsers paste screenshots as PNG.
- `text` stays required (`MessageText`): retrieval and the thread title both need a query.
- Rejected: multipart, and uploading first then referencing by id. Both split one turn across two requests, and a separate upload leaves orphans whenever the send never follows.

### 4. Storage

```json
{"text": "What does this chart show?",
 "images": [{"key": "data/workspaces/3/chats/41/9f86d0….png", "mime": "image/png", "size_bytes": 48213, "sha256": "9f86d0…"}]}
```

- `images` is present only when the turn carried any, so every existing row stays valid and `message_text()` keeps reading `content["text"]`.
- The normalised bytes live at `workspace_dir(ws)/chats/{thread_id}/{sha256}.{ext}`; `key` is relative to `data_dir`, as `artifact_files.storage_key` is.
- Content addressing means one file can back two turns of the same thread. Discarding a failed turn removes only files no other turn of the thread references.
- `delete_thread` removes the thread's folder after the commit, as `delete_workspace` does for its tree.
- `GET /chat/threads/{thread_id}/messages/{message_id}/images/{index}` serves a stored image to the UI.
- Rejected: base64 inside the JSON column. SQLite carries the bytes, and so does every `GET …/messages`, which the UI refetches after every reply.
- Rejected: storing an attachment as a workspace document. It would be parsed and indexed as a source, and deleting that source would break the thread.

### 5. What history resends

- The newest user turn that carried images sends them again on every later turn, until a newer turn carries its own. Older turns keep their text and lose their images. Follow-ups such as "and the left axis?" work without paying for every image the thread has seen.
- `_within_budget` ([`history.py`](../../../surfsense_local/backend/modules/chat/history.py)) prices an image turn at its text plus a fixed cost per image, and the current turn's images are reserved out of the history budget ([`budget.py`](../../../surfsense_local/backend/modules/chat/budget.py)). The cost is measured at implementation on the curated vision models at the pinned llama.cpp build and set at the largest, so the trim errs towards dropping a turn rather than overflowing the window.
- If the turn carrying the kept images falls outside the budget, its images go with it.
- Switching to a model that cannot see keeps the thread's images on screen; the conversation continues as text.
- Rejected: resending every image, whose cost grows with the thread; and sending an image only with its own turn, which breaks follow-ups.

### 6. Image sources found by retrieval

- When the model reads images and retrieval returns chunks of a document whose `mime_type` is `image/*`, the original is loaded through `original_path()` ([`original_file.py`](../../../surfsense_local/backend/modules/documents/original_file.py)), normalised as in decision 3, and attached to the current user turn beside its OCR text.
- At most 2 per turn, the highest ranked distinct documents, priced like attachments.
- Not stored in the message row: they come from sources, not the person, and are loaded again whenever retrieval returns them. A missing original is skipped and the turn goes on as text.
- Needs nothing from indexing: the original is read at question time, so image sources indexed before this work unchanged, in either on-disk layout ([documents](../../architecture/documents.md)), and nothing is re-indexed.

### 7. The UI

- Attachments are assistant-ui's own, nothing built from scratch. At the installed `@assistant-ui/react` 0.15.18:
  - the runtime takes `adapters.attachments`, set to `SimpleImageAttachmentAdapter` only when `reads_images` is true, so a model that cannot see has no adapter and the composer accepts no image;
  - `ComposerPrimitive.AddAttachment` opens the picker, `ComposerPrimitive.AttachmentDropzone` takes a drop, and `ComposerPrimitive.Input` adds a pasted file itself (`addAttachmentOnPaste`, on by default);
  - `ComposerPrimitive.Attachments` lists pending images, each drawn with `AttachmentPrimitive.Root`, `Thumb`, `Name` and `Remove`;
  - `MessagePrimitive.Attachments` draws a sent turn's images in the user bubble.
- Our own code is the styling of those primitives and the mapping between assistant-ui's attachments and the request in decision 3.
- `submittedText()` stops dropping image parts, and retry resends a failed turn's images.
- The thread renders stored images in the user bubble through the route in decision 4.
- A Vision badge marks remote models that read images, as local ones already have. The connection's model list ([`schemas.py`](../../../surfsense_local/backend/modules/llm/schemas.py) `ConnectionModelRead`) gains `reads_images`, and the row shows a Vision chip beside its type chip, reusing the existing `models_your_models_vision_label` string.
- Built with the `frontend-workflow` skill; interface strings follow the `translate` skill.

### 8. Egress

A remote model receives images over the connection the person already consented to ([egress](../../architecture/egress.md)); resolution already calls `egress.require()`. Images add no destination.

## Known limits

- A custom endpoint whose ids the manifest lacks never gets attach, even when its model reads images. The fix is persisting the endpoint's declared input modalities at selection.
- Remote providers whose manifest entry names a non-OpenAI protocol are out of scope, as they are for text.
- A projector that passes the header check but fails to load takes the whole model down with it: the router marks the model failed, and chat is lost along with vision. Unsloth Studio restarts such a model text-only and says why (an older llama.cpp, memory, or the projector moved to the CPU); that fallback is runtime work beyond this proposal.

## Later

Each builds on decision 1's answer and decision 2's image parts, and each changes ingest or adds tools, so each needs its own design. Documents indexed before one of them ships stay as they were indexed: nothing re-parses them in the background, and a document gains the new data only when it is ingested again.

- **Figures at indexing.** Docling's picture description (`PictureDescriptionApiOptions`) pointed at llama-server's local vision model, so charts and diagrams in PDFs and slides become searchable text for every model. Opt-in, since it slows ingest.
- **Page per chunk.** Record each chunk's page and region at ingest, for citations that open the page and, with a vision model, for showing the page itself.
- **Looking at a page on demand.** An agent tool that renders one page for a model that reads images ([agent](../agent/README.md), where figure understanding is out of scope today).

Not planned: sending whole PDFs natively to providers that accept them, which is provider-specific, costly per turn and no help to local models.

## Ship

One implementation pull request, built in this order so each step stands on the one before:

1. `Message.images`, the request body and `for_template()`, with the byte-identical negative test; `can_see` without the typed-content condition, with a test for a string-only template.
2. The answer: `sees_images()` on both generators, `Supports.reads_images` and the catalog lookup for declared models, `SelectionRead.reads_images`, `ConnectionModelRead.reads_images`, and the installed-model badge reading `/models`.
3. The chat API: the request's `images`, checks and Pillow normalisation, storage, the `409`, history's resend and pricing, the image route and the thread folder's removal.
4. Image sources in retrieval.
5. The composer, the thread view and the remote Vision badge.

The same pull request folds what is then true into [`chat.md`](../../architecture/chat.md), [`connections.md`](../../architecture/connections.md), [`selection.md`](../../architecture/local-models/selection.md), [`catalog.md`](../../architecture/local-models/catalog.md) and [`data-model.md`](../../architecture/data-model.md), deletes their Known-gaps lines about images, and deletes this proposal.

## Open questions

- Where attach sits in the composer. The `+` button already adds workspace sources, and images are valid sources: a separate attach button, or one menu with "Attach to message" and "Add to sources".
- The per-image token cost and the pixel cap, measured on the curated vision models.
