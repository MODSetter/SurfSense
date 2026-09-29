---
status: proposed
tracking: https://github.com/MODSetter/SurfSense/issues/1991
code:
  - surfsense_local/backend/modules/llm/providers/
  - surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/
  - surfsense_local/backend/modules/chat/
  - surfsense_local/frontend/src/features/chat/
---

# Images in chat

> A person can attach an image to a chat turn, and a local model that reports `vision` receives it. Every other model receives exactly the request it gets today.

`vision` is the one capability the app shows a person ([`selection.md`](../architecture/local-models/selection.md), Capabilities and the system role), and nothing in the app can hand such a model an image, because `Message.content` is a `str`. This proposal settles the two decisions the issue leaves open, how a user turn with an image is stored and what history resends, plus the choices those two force.

## What changes

| | Today | With this |
|---|---|---|
| A stored user turn | `{"text"}` | `{"text"}`, or `{"text", "images": [...]}` when the turn carried any |
| Image bytes | nowhere | files under the workspace's folder, one folder per thread |
| `Message` | `role`, `content: str` | the same, plus `images: tuple[Image, ...] = ()` |
| The request a text-only model receives | string content | unchanged, byte for byte |
| The request a model that can see receives | string content | typed parts on a turn that carries images, string content on every other turn |
| Remote models | text only | text only; images are stripped (see Scope) |
| The `vision` badge | predicted from the projector | the runtime's recorded answer once the model has loaded, the prediction before that |
| Composer | text and document scope | adds attach, paste and drop, offered only when the selected model reads images |

## Decisions

### 1. The stored shape of a user turn

```json
{"text": "What does this chart show?",
 "images": [{"key": "workspaces/3/chats/41/9f86d0…png", "mime": "image/png", "size_bytes": 48213, "sha256": "9f86d0…"}]}
```

- `images` is present only when the turn carried at least one image. Every existing row stays valid, and `message_text()` keeps reading `content["text"]` unchanged.
- The bytes live in files at `workspace_dir(ws)/chats/{thread_id}/{sha256}.{ext}`. `key` is relative to `data_dir`, as `artifact_files.storage_key` is. Deleting a workspace already removes its folder. `delete_thread` gains the removal of its own `chats/{thread_id}` folder.
- Rejected: base64 inside the JSON column. SQLite carries the bytes, and so does every `GET …/messages`, which the UI refetches after every reply.
- Rejected: uploading the image as a workspace document. It would be parsed and indexed as a source, and deleting that source would break the thread's history.

### 2. What history resends

- The newest user turn that carried images sends them again on every later turn, until a newer turn carries images of its own. Every older image is dropped, and its turn's text stays. Follow-ups such as "and the left axis?" work without paying for every image the thread has ever seen.
- `_within_budget` prices a turn at `len(text) // 4`, or with the model's own tokenizer, and neither knows what an image costs. An image turn is priced at its text plus a fixed cost per image. The cost is measured at implementation on the curated vision models at the pinned llama.cpp build, and set at the largest of them, so the trim errs towards dropping a turn rather than overflowing the window.
- If the turn that carries the kept images falls outside the budget, the images go with it, as text would.
- Rejected: resending every image. The cost grows with the thread, and a small model's window fills with pictures it has already answered about.
- Rejected: sending an image only with the turn that attached it. A follow-up question about the same image would reach a model that no longer has it.

### 3. The request that sends a turn

```json
POST /chat/threads/{thread_id}/messages
{"text": "…", "document_ids": [...], "images": [{"mime": "image/png", "data": "<base64>"}]}
```

- At most 4 images per turn and 10 MB each, decoded. The magic bytes are checked the way `validate_upload()` already checks them.
- PNG and JPEG in v1. WebP waits on a check of what llama.cpp's image loader decodes at the pinned build. The backend has no Pillow to convert a format, so an unsupported one is refused with a `422` rather than converted.
- `text` stays required (`MessageText`, at least one character): retrieval and the thread title both need a query.
- `GET /chat/threads/{thread_id}/messages/{message_id}/images/{index}` serves a stored image to the UI.
- Rejected: multipart, and uploading first and then referencing the upload by id. Both split one turn across two requests, and a separate upload leaves orphaned files whenever the send never follows.

### 4. The `Message` type

- `Message` gains `images: tuple[Image, ...] = ()`, where `Image` is `mime` and `data: bytes`. `content` stays a `str`.
- Rejected: widening `content` to `str | list[Part]`. Every reader of `.content` would then handle a union: the system-role fold in `for_template()`, `generate.py`, history's pricing, the logging. The issue notes that this drags Studio into the change. With a separate field, Studio and every text-only path do not change at all.

### 5. Where the downgrade happens

The downgrade stays at the provider seam. `modules/chat` assembles one conversation and never learns that templates differ.

- **llama.cpp.** `for_template()` drops `images` from every message when `not capabilities.can_see`. The system-role fold carries `first.images` through to the folded turn.
- **Serialisation.** The OpenAI-compatible request body sends `content` as a string when `images == ()`, which is exactly today's request. Otherwise it sends `[{"type": "text", …}, {"type": "image_url", "image_url": {"url": "data:<mime>;base64,…"}}]`. The negative test sits here: a conversation with no images, sent to any model, produces a request byte-identical to today's.

### 6. The runtime decides; the catalog only predicts

The badge and the runtime can disagree today:

- The catalog's `reads_images` is `projector_reads_images()`: the projector carries a vision encoder.
- The runtime's `can_see` also needs the template to take typed content (`chat_template_caps.supports_typed_content`).
- The catalog cannot compute that half. At `b11050`, llama.cpp runs the template in its own Jinja engine and watches whether `content` is used as an array ([`common/jinja/caps.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/common/jinja/caps.cpp)). A regex or Python's `jinja2` would be a second opinion that can differ from it.
- Left alone, the composer would offer attach for a model whose runtime then strips the image, which is the silent failure the issue warns about.

So the runtime's answer is recorded and replaces the prediction:

- **Record.** Whenever the llama.cpp provider reads `/props` for a model, it records that model's `can_see`. This happens after an install (`become_ready()` loads the model) and on the first chat turn after a load. The answer is stored per installed model and survives restarts, like its preset.
- **Badge.** An installed model shows the recorded answer once it has one. A model that has never loaded, and every search result, shows the projector's prediction. The catalog doc says so in one line.
- **Composer.** The selection route reports `reads_images` from the same rule: the recorded answer, else the prediction. Attach, paste and drop appear only when it is true.
- **Send.** A turn with images for a model that cannot see gets a `409` with a sentence ("This model can't read images"), and nothing is stored. This is the backstop for a prediction that the first load proves wrong. It is a refusal, not a reshaping of the conversation, so the seam rule holds. The route asks the generator one question, `sees_images(model)`: llama.cpp answers `can_see`, and every other provider answers `False`.
- **History.** `for_template()` still strips images. A thread keeps its earlier images when the person switches to a text-only model, and the conversation continues as text.

### 7. Scope: local models first

- `OpenAICompatibleChatProvider` is both the generator for a remote connection and llama.cpp's inner client, so "remote strips images" cannot live in the shared serialisation. The strip lives where a remote connection's generator is resolved.
- No remote model reports `vision` today: `_classify()` maps output modalities only. The remote manifest already carries `modalities.input`, so remote vision is a follow-up: read `input` containing `image`, then let `sees_images()` answer from it.

### 8. The composer

- `submittedText()` keeps only text parts, and `ModelSelection` carries no capabilities. The frontend PR changes both: the selection route reports whether the selected model reads images, and attach, paste and drop appear only when it does.
- `toRuntimeMessage()` maps stored `images` to image parts, loaded from the route in decision 3.
- Built with the `frontend-workflow` skill. Interface strings follow the `translate` skill.

## Ship

Four implementation PRs once this is accepted:

1. `Message.images`, the llama.cpp downgrade and the serialisation, with the positive and negative tests. No behaviour a person can see changes.
2. Recording the runtime's `can_see`, and the badge reading it.
3. The chat API: the request's `images`, storage, history's resend and pricing, the `409`, the image route and the thread folder's removal.
4. The composer and the thread view.

The last of them deletes the Known-gaps lines in [`selection.md`](../architecture/local-models/selection.md) and [`catalog.md`](../architecture/local-models/catalog.md), rewrites the stored-content description in [`chat.md`](../architecture/chat.md), folds this design into `architecture/chat.md` and deletes this proposal. This proposal PR changes none of them.
