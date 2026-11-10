# Image models

> Each image model says whether it can take a picture in. One rule picks the model for any job that sends a picture: the user's edit model if they chose one, else the image model if it can, else none, and then the job redraws. One interface draws, edits and keeps references, and each provider's client knows its own routes.

## What a model can do

Each image model carries `takes_pictures`: whether it draws from a picture as well as from words.

- **Remote:** from what the connection's `/models` publishes, read live. Discovery already reads each entry's `output_modalities` to find image models ([`service.py`](../../../surfsense_local/backend/modules/llm/connections/service.py)); it reads `input_modalities` beside it, from the entry or its `architecture`, and `DiscoveredModel` gains `takes_pictures`. OpenRouter lists `text,image` for every model the spike drew with. The bundled manifest's `modalities.input` answers when the endpoint publishes nothing; it lacks most OpenRouter image models, so it is the fallback, not the source.
- **Local:** the sd.cpp catalog's `edit` type, which FLUX.2 klein has today ([selection](../../architecture/local-models/selection.md)).
- **Kept with the choice.** When the user chooses an image model, its `takes_pictures` is kept in the selection's existing `settings` JSON, and refreshed whenever that connection's model list is read again. No migration: the column is there ([`models.py`](../../../surfsense_local/backend/modules/llm/models.py)).
- **Unknown is no.** A model whose endpoint says nothing and that the manifest does not carry gets `takes_pictures: false`, so its edits redraw. Sending a picture to a model that ignores it would bill a picture that keeps nothing.

## Which model handles a picture

One function, `picture_model(session)`, beside the others in [`resolution.py`](../../../surfsense_local/backend/modules/llm/resolution.py), answers every job that sends a picture in, an edit or a comic page with references:

1. the `image_edit` selection, when the user chose one: the override;
2. else the `image_gen` selection, when it `takes_pictures`;
3. else none.

The API exposes the answer once, as `pictures_in: "edit_model" | "image_model" | null`, beside the selections it is worked out from. Studio, the agent's tool list and the skill all read that, so no two places can disagree.

## One interface

The two protocols, `ImageGenerator` and `ImageEditor` ([`protocols.py`](../../../surfsense_local/backend/modules/llm/providers/protocols.py)), become one:

```python
class ImageModel(Protocol):
    async def draw(
        self,
        model: str,
        prompt: str,
        *,
        shape: Shape | None = None,
        references: Sequence[GeneratedImage] = (),
    ) -> GeneratedImage: ...
```

An edit is a drawing with the picture as its one reference and the instruction as its prompt. `Shape` is `square`, `portrait` or `landscape`; left out, the model's default, as today.

## One client per provider

| Provider | No references | With references |
|---|---|---|
| **OpenRouter** (`catalog_provider` `openrouter`) | `POST /images/generations` with `size` | `POST /images` with `input_references` and `aspect_ratio` |
| **Any other OpenAI-compatible server** | `POST /images/generations` with `size`, then `/images` as today's route cache does | `POST /images/edits`, multipart, one `image[]` part per reference, and `size` |
| **Local sd-server** | native `POST /sdcpp/v1/img_gen` with `width` and `height` | the same, with `ref_images` holding every reference |

- **Sizes.** `square` is `1024x1024` or `1:1`, `portrait` `1024x1536` or `2:3`, `landscape` `1536x1024` or `3:2`. Locally, the launch's default pixel count at that proportion, each side a multiple of 64.
- **OpenRouter gets its own client** because it answers 404 on `/images/edits` and its pure image models refuse `/chat/completions` ([the spike](README.md#the-spike)). The client is chosen by the connection's `catalog_provider`, which every connection already records.
- **Local drawing moves to the native route** only when a shape is asked; a drawing with no shape keeps today's `/v1/images/generations`. The native route is the one the edit client already uses, because sd-server's OpenAI and A1111 edit routes re-noise the picture ([ADR 0077](../../adr/0077-an-image-edit-is-the-next-version.md)).
- **Retries, the same for every client.** A `400` to an optional field (`size`, `aspect_ratio`, `response_format`) is sent once more without it, remembered per connection, as `response_format` already is: a `400` comes before any drawing. A timeout or a `5xx` is never retried, since the provider may still be drawing and a second request bills a second picture.
- **Several references refused.** A server that answers `400` to several `image[]` parts gets the first alone, once, and the result says only one reached the model. The spike below decides whether that is kept.

## Edits and redraws

An edit of a picture, from Studio's Edit box or from the agent, stays the next version of the same document, with the recipe ADR 0077 gives it. What runs depends on the rule:

- **A model takes pictures:** the edit draws with the base version's picture as its one reference and the instruction as its prompt, at the base's proportions. The same as today, through the rule instead of the slot.
- **None does: a redraw.** The image model draws again from the prompt that drew the base and the instruction: `"<prompt>\n\nChange: <instruction>"`, at the base's proportions, with no chat model in between. The recipe records `"redrawn": true`, and the version's body starts with one line, "Drawn again with your change." It is billed as one picture, as an edit is.
- **The prompt a redraw starts from** is the one the base was drawn with. A picture the agent drew keeps it as `prompt` already. A Studio draft keeps it only in its body under the title ([`image/pipeline.py`](../../../surfsense_local/backend/worker/studio/media/visual/image/pipeline.py)); from now on every drawing also keeps it as `drawing_prompt` in its metadata, and a redraw of an older picture reads it from the body. A redraw of a redraw starts from the redrawn version's own prompt, so changes add up.
- **The `needs_image_edit` refusal goes.** No edit is refused for want of a model; only for want of an image model at all, which is `needs_image` as today.

## Spikes before code

Each runs in the scratchpad against the real endpoint or binary, and its result is posted on the implementation PR.

- **OpenAI's `/images/edits` with two and four `image[]` parts and `size=1024x1536`,** on gpt-image. Decides the one-reference fallback.
- **Local references:** the pinned sd-server with FLUX.2 klein, `ref_images` of one and two pictures at a portrait `width` and `height`: whether a face holds over four pages, and the seconds a page on a processor.
- **Local shape:** the native route's drawing at a portrait size against today's route's square one, for time and quality.
- **`input_modalities` across the providers the catalog connects to,** to see which publish it and how often the manifest must answer instead.

## Checks

- Discovery: an OpenRouter-shaped `/models` entry with `input_modalities` `text,image` gives `takes_pictures`; one with `text` alone does not; one with neither falls to the manifest, then to no.
- The rule: each of its three answers, and `pictures_in` in the API.
- Clients: the request each sends with and without a shape and references, the `400` retries, no retry on a timeout or a `5xx`, against a stand-in server.
- Edits: a real edit through the image model; a redraw through a model that takes no pictures, its recipe and its first line; a redraw of a Studio draft made before `drawing_prompt`; no `needs_image_edit` anywhere.
