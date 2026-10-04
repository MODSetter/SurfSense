# ADR 0034: Whether a chat model reads images is llama.cpp's own answer for a local model and the catalog's for a remote one, and it is stored nowhere

- **Status:** Accepted
- **Date:** 2026-09-30
- **Source:** [llama.cpp `update_caps()` L545–565](https://github.com/ggml-org/llama.cpp/blob/b11050/tools/server/server-models.cpp#L545-L565), [`/models` modalities L2043–2051](https://github.com/ggml-org/llama.cpp/blob/b11050/tools/server/server-models.cpp#L2043-L2051), [`concat_content_parts` L479–503](https://github.com/ggml-org/llama.cpp/blob/b11050/common/chat.cpp#L479-L503)

## Context

Chat can hand a model images, and the composer, the model badges and the send check all need to know whether the selected model reads them. Three answers were available and could disagree:

- the local catalog's prediction, from the projector a build's manifest entry names, which says yes for an installed build whose projector never reached the disk;
- `can_see`, which also required the chat template to take typed content, on the belief that a string-only template has nowhere to put an image;
- a per-model record of the runtime's answer, proposed so the badge could learn from a load.

At `b11050`, llama-server's router reads the header of the projector each preset gives a model and lists `image` in that model's `input_modalities`, loaded or not. It also replaces each image with a media marker before templating, and keeps the marker when it joins parts for a string-only template, so the template's content shape never decides vision.

## Decision

- An installed local model reads images when llama-server's `/models` lists `image` for it. The preset gives `--mmproj` only for a projector on disk that reads images and fits the model, so the local catalog's badge for an installed build uses that same rule; the manifest predicts only for builds not installed.
- `can_see` is `image` in the model's inputs, without the typed-content condition.
- A remote model reads images when the models.dev manifest lists `image` among its inputs, read through the connection's catalog provider. An id the manifest does not carry answers no.
- The answer is worked out where it is asked and stored nowhere. An unreadable `/models` is no answer: the composer offers nothing, and the send check lets the turn through for llama-server's own refusal.
- A turn's images are stored beside its thread, named by content hash, and never as workspace sources.

## Consequences

- The badge, the composer and the send check cannot disagree about a local model, because each reads what llama.cpp was given.
- A custom endpoint whose ids the manifest lacks never gets attach, even when its model reads images. Persisting the endpoint's declared input modalities at selection is the way past that.
- A projector that passes the header check but fails to load takes the whole model down with it; llama-server does not fall back to text.
- The typed-content fix rests on llama.cpp's source at `b11050`. A later pin that changes how parts are joined reopens it.
