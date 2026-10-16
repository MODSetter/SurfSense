# Model selection and prompt tiers

One model is chosen per model type, local or remote, and the app records a few facts
about it at the moment it is chosen, so that every later request knows how to
prompt it without asking the network. The prompt tier those facts imply is
computed on read and never stored, so a threshold can move on evidence without a
migration or a re-selection. Finishing onboarding is a separate marker that
choosing or clearing a model never touches.

**Code:** [`surfsense_local/backend/modules/llm/selection.py`](../../../surfsense_local/backend/modules/llm/selection.py), [`surfsense_local/backend/modules/llm/model_type.py`](../../../surfsense_local/backend/modules/llm/model_type.py), [`surfsense_local/backend/modules/llm/selectable.py`](../../../surfsense_local/backend/modules/llm/selectable.py), [`surfsense_local/backend/modules/llm/models.py`](../../../surfsense_local/backend/modules/llm/models.py), [`surfsense_local/backend/modules/llm/profile/`](../../../surfsense_local/backend/modules/llm/profile/), [`surfsense_local/backend/modules/llm/prompting/`](../../../surfsense_local/backend/modules/llm/prompting/), [`surfsense_local/backend/modules/llm/resolution.py`](../../../surfsense_local/backend/modules/llm/resolution.py), [`surfsense_local/backend/modules/llm/router.py`](../../../surfsense_local/backend/modules/llm/router.py), [`surfsense_local/backend/modules/llm/transcription/`](../../../surfsense_local/backend/modules/llm/transcription/)
**Decisions:** [ADR 0011](../../adr/0011-llama-cpp-local-runtime.md), [ADR 0015](../../adr/0015-openai-compatible-connections.md)

## One row per model type

`ModelType` is what a model is for: `text_gen`, `image_gen`, `image_edit`,
`video_gen`, `audio_gen` or `speech_to_text`. There are no separate roles; the
type is the slot.
`SelectedModel` holds one row per type in `selected_models`, keyed by
`model_type`, so choosing again updates in place.

| Model type | Local | Remote | Read by |
|---|---|---|---|
| `text_gen` | `llamacpp`, the bundled runtime | `openai_compatible`, with a `connection_id` | chat, titles, Studio's writing |
| `image_gen` | `sdcpp`, the bundled sd-server | `openai_compatible`, with a `connection_id` | Studio's `image` and `infographic` |
| `image_edit` | `sdcpp`, a model whose entry names `edit` | `openai_compatible`, with a `connection_id` | nothing yet |
| `audio_gen` | `audiocpp`, the bundled audio.cpp server | `openai_compatible`, with a `connection_id` | Studio's `podcast` |
| `video_gen` | `sdcpp`, a model whose entry has a `video` block | `openai_compatible`, with a `connection_id` | nothing yet |
| `speech_to_text` | `audiocpp`, a recogniser, run on a second audio.cpp server | none: local only | the transcription routes ([admission](admission.md#speech-recognition)), which a recording's ingest calls ([documents](../documents.md#recordings)) |

A type no feature reads can still be chosen; the feature that first reads one
brings the client that calls it.

`embedding` is a `ModelType` too, and the one exception: a catalog type, so the
manifest and an engine can describe an embedder, never a slot. The embedder
belongs to the library's index, fixed when onboarding finishes
([search](../search.md), [ADR 0037](../../adr/0037-embedding-is-a-type-not-a-slot.md)). `SLOTS` in
[`selectable.py`](../../../surfsense_local/backend/modules/llm/selectable.py) is every type but it:
`selectable_for` never offers `embedding`, not even to a model nothing
recognises, and both `/llm/selection/{model_type}` routes answer `422` for it.

`speech_to_text` is a slot, since speech models change freely as voices do, but
a local-only one: no remote speech client exists to call a recogniser.
`LOCAL_ONLY` in the same file names it, so a model nothing recognises fills
every slot but it, and a connection serves `REMOTE_SLOTS`, every slot but it,
which a confirmed unlisted model does not get round.

A row stores the provider, the connection when remote, the exact model id, and
three fingerprint facts. A check constraint requires a `connection_id` exactly
when the provider is `openai_compatible`, a second (`local_runtime_type`) lets
`llamacpp` hold only `text_gen`, `sdcpp` only `image_gen`, `image_edit` and
`video_gen` (revision `0018`), and `audiocpp` only `audio_gen` and
`speech_to_text` (revision `0030`), and deleting a connection cascades to the
rows that name it. `provider` is the SurfSense inference provider, never the
model's publisher.

`GET /llm/selection/{model_type}` returns the row with its computed `tier`, or
`404` when nothing is chosen. `PUT /llm/selection/{model_type}` takes
`provider`, `name`, `connection_id` and `allow_unlisted`, then validates,
fingerprints and stores:

- **Local text** (`llamacpp`): the type must be `text_gen`, there is no
  connection, the router must list the model as installed, and its own header
  must make it `text_gen` ([`catalog.md`](catalog.md)). The provider drops a
  file whose header is not a model, and an unreadable header counts as `text_gen`.
- **Local image** (`sdcpp`): there is no connection, the name must be a
  curated image build installed in the images folder, named by its first
  weights file as a chat build is ([`catalog.md`](catalog.md)), and the type
  must be one its entry names: `image_gen` for `generate`, `image_edit` for
  `edit`, and `video_gen` for a model with a `video` block. FLUX.2 klein fills
  both image slots from the same files; SD 1.5 is refused for editing, and
  every image model for video.
- **Local audio** (`audiocpp`): there is no connection, and the name is a
  curated build named by its weights file as a chat build is. For `audio_gen`
  it must be a voice model, whose entry has an `audio` block, installed in the
  audio folder or shipped in the models pack; for `speech_to_text`, a
  recogniser, whose entry has a `transcription` block, installed in the audio
  folder. Nemotron is refused for voices and Kokoro for speech recognition.
- **Remote** (`openai_compatible`): a connection is required, and the model is
  checked against the endpoint's live `/models`. When the listing cannot be read
  or does not include the id, `allow_unlisted` is what lets a user save an exact
  id anyway. Otherwise the model must be able to fill the slot, by one rule in
  `selectable.py`: a model fills the slots of the types it is, and one nothing
  recognises fills every slot but `speech_to_text`. The connection's model listing sends the same
  answer as `selectable_for`, so every picker offers what selection accepts. Remote
  inventory is discovered live and never synchronized into SQLite
  ([`../connections.md`](../connections.md)).

Choosing a `llamacpp` model also starts loading it, as a background task that
runs after the response, because the load blocks until the weights are resident
and choosing a model is when the user has said they are about to use it
([`runtime.md`](runtime.md#warming-listed-is-not-loaded)). Any other provider
loads nothing.

Choosing a `speech_to_text` model, through the route or an install with
`select: true`, queues again every recording that failed for want of one, at
`PRIORITY_BULK` ([documents](../documents.md#no-speech-model-yet)).

Installing with `select: true` goes through the same `choose_model()`
([`catalog.md`](catalog.md)) and fills the row's own first slot unless the
request names another, so Nemotron's install fills `speech_to_text` though
audio.cpp's first type is `audio_gen`. Deleting a local model clears every row
of the types its engine fills that named it, `image_gen` and `image_edit` both for a
model chosen for each, and reports
`selection_cleared`; nothing chooses another
model in its place, except that at the next start an empty `audio_gen` row takes
the voice the app ships ([`default_voice.py`](../../../surfsense_local/backend/modules/llm/default_voice.py)).
That runs at every start, after the catalog settles, so a fresh install and an
upgrade from the Python Kokoro voice podcasts without a trip to Settings; a
model already chosen is left alone. Revision `0012`, which replaced Ollama with llama.cpp,
cleared any generation selection pointing at Ollama rather than remapping it,
because its weights live in a blob format the app no longer manages.

## Fingerprint

Revision `0010` added `params_b`, `vendor` and `line` (`flagship` or `small`) to
`selected_models`, each nullable. `choose_model()` collects them once, so
generation never has to:

- **Remote**: `inspect()` reads the endpoint's `/models` row for the model. With
  a `hugging_face_id`, `params_b` is the largest size stated in the id or the
  repo name, and `line` defaults to `flagship`, because published weights with no
  size word are a vendor's full-size model. Without one, `params_b` is the
  largest size stated in the id, and `vendor` is the row's `owned_by`, or the
  part of the id before its last `/`, when the id states no size.
- **Local text**: `inspect()` reads `general.parameter_count` from the
  llama.cpp router's `/props`; when the runtime states no count, the filename
  supplies it.
- **Anything else, or a failed provider read**: `from_name()` takes the largest `<n>b`
  count in the name, so a mixture of experts reads its total rather than its
  active size and `llama-3.3-70b` is not 3B, and failing that a line word such as
  `mini`, `flash`, `pro` or `max`.

A row with all three facts null, such as one chosen before tiering existed, is
fingerprinted from its name on read.

## Prompt tiers

`profile/classify.py` turns a fingerprint into one of three tiers, and the tier
names the prompt file.

| Known | Tier |
|---|---|
| `params_b` < `COMPACT_MAX_B` (7.0) | `compact` |
| `params_b` < `CAPABLE_MAX_B` (100.0) | `capable` |
| `params_b` ≥ 100.0 | `frontier` |
| no count, but a `vendor` | `frontier` |
| no count, `line` is flagship / small | `frontier` / `capable` |
| nothing, and the endpoint is on this machine (`llamacpp`, or a connection on a loopback host) | `compact` |
| nothing, and the endpoint is hosted | `capable` |

The thresholds encode a claim about scaffolding, not about quality: below the
first a model loses accuracy when asked to follow a structure, between the two it
gains from one, and above the second it writes better from judgement than from
steps. The last two rows are the same bet: a hosted endpoint runs models too big
for a laptop, and a local one runs the laptop. `Fingerprint.local` decides which
applies: true for `llamacpp`, which has no URL of its own, and for a connection
whose host `host_destination()` reports as loopback, such as LM Studio or Ollama
on `localhost`. `SelectedModel.fingerprint` sets that from its connection, which
the row loads joined so reading the tier never queries lazily.

The tier is not stored. `SelectedModel.tier` calls `classify()` on read, and
`ResolvedGeneration.tier` hands it to chat and to every Studio format, so
retuning a threshold changes behaviour on the next request with no migration and
no re-selection. That is the property to preserve. A wrong tier degrades prompt
quality; it never fails a request, because `classify()` always falls through to
an answer.

## Prompt loading

Every prompt lives as markdown beside the code that uses it.
`prompting.load(package, tier, case="", **slots)` reads
`{package}/prompts/{tier}.md`, or `{package}/prompts/{case}/{tier}.md` when a
package hosts more than one prompt, and fills `$slot` placeholders through
`string.Template`, because every prompt carries a JSON schema whose braces must
reach the model as written. A slot nobody filled is a `ValueError` naming the
file. `focus()` turns the user's steer into one line, `Focus on: …`, or nothing.

There are 33 prompt files, 11 cases with three tiers each: chat, and in Studio
the summary, flashcards, mindmap, quiz, office, `web/html`, image and
infographic formats, with the podcast outline and draft as separate cases. A unit
test asserts that every case ships all three tiers, because a missing file fails
the job on the user's machine, where nobody can fix it. No `import` names a
prompt, so the PyInstaller specs collect them by path: `api.spec` takes chat's
three, and `worker.spec` takes those plus every `*.md` under `worker.studio`.

## Onboarding

`GET /llm/onboarding` returns `{"completed": bool}`, true once the singleton
`onboarding_completion` row exists. `POST /llm/onboarding` writes that row and
requires a persisted `text_gen` selection, answering `422 chat model required`
otherwise; image, image editing, video and audio models are optional. Its body
may name `embedding_model`, a curated embedder already downloaded; the route
locks it as the library's embedder before writing the marker, refusing `409` one
not yet downloaded and leaving onboarding unfinished. No name locks the bundled
bge-small ([`choose.py`](../../../surfsense_local/backend/modules/embedding/choose.py)). The marker means the user finished
choosing, and it is the one thing that must not become true early.

Two invariants, both easy to break from the frontend: selecting or clearing a
model never writes or resets the marker, and Settings' Use actions never call the
route. Only the onboarding page's last step does, once a chat model is
persisted. Once the marker exists the app never shows onboarding again, and a
missing selection is fixed from Settings' Chat section.

The onboarding page opens on a welcome screen, then six steps: chat, image, image editing, audio, video and search model. The welcome is not counted as a step, but it is part of onboarding and gated by the same marker, so it is never shown again once onboarding is done.

The embedding step comes last and is not a slot, but it is the same component
as the model steps below, with one more entry in their tables
([`model-step/`](../../../surfsense_local/frontend/src/features/onboarding/model-step/)).
What a step does on Use is its own hook: a slot's saves the selection, and the
embedding step's ([`use-embedding-step.ts`](../../../surfsense_local/frontend/src/features/onboarding/model-step/kinds/use-embedding-step.ts))
only marks a choice, In use until another is used, bge-small by default and again
if the chosen one is deleted. Its downloads install with `select: false`; a
Hugging Face pick is labelled not tested by SurfSense; the bundled bge-small has
no Delete. Its search is `ModelSearch` given the embedding endpoints, which answer
in the GGUF search's shapes, with a note that larger models are slower. A notice
above the list says the choice can't be changed later and that the default suits
English. It offers no server until remote embedders exist. Being last, its
Finish sends the choice with the call that ends onboarding; Skip and finish, or
Finish with the choice untouched, sends none, which means bge-small
([embedding](../embedding.md)).

The model steps are one component for any slot
([`frontend/src/features/onboarding/model-step/`](../../../surfsense_local/frontend/src/features/onboarding/model-step/)),
built on the same hooks as Settings but with its own screens. Each lists every
model this computer can run at once: in the chat step, models downloaded from Hugging Face first, then the curated list with its starred row first, with
Download, Use and Delete as in Settings, and no Delete on a model the app ships; a download's progress shows under its
row and never moves the page. The chat step also offers Settings' Hugging Face
search, closed until asked for; the image, image editing, audio and video steps have none, since
sd.cpp's and audio.cpp's models are the few the catalog ships. The image editing step lists first the model chosen for images earlier when it edits too, so FLUX.2 klein is one Use away, and its downloads fill `image_edit`. A server sits one line below the list and names
any connected earlier. Once the slot has a model, the footer names it beside
Continue. Onboarding installs with `select: true`, so a download is also the
choice; Settings installs with `select: false`. The chat step's Continue is
enabled only once a chat model is selected, local or from a server. The image,
image editing, audio and video steps are optional, and each enables its Continue or Finish only once
its slot has a model. Each step's Skip and Continue move on to the next, image
to image editing to audio to video. The last step's buttons read Skip and finish and Finish, and both post the marker.

## Resolution: local and remote

`resolve_generation()` reads the `text_gen` row. A `llamacpp` row resolves to the
bundled runtime ([`runtime.md`](runtime.md)). An `openai_compatible` row resolves
to its connection, and `egress.require()` checks the connection's host, which is
a no-op for a loopback host, so a local LM Studio or Ollama endpoint never
prompts. `resolve_image_generation()` does the same for sd-server or a
connection. `resolve_speech_to_text()` reads the `speech_to_text` row and
returns it with its installed recogniser: the file, the family the server
dispatches on, and the entry's languages and locales. With no row, or one whose
model is gone, it raises `NoSpeechModelError`, which a route answers as `409`
with the code `needs_speech_model`.

## The speech model's language

`GET /llm/selection/speech_to_text/language` answers `{language, languages,
detects_language}`: the language the user says they speak, `auto` or an ISO
639-1 code; the codes the model is listed for, best first; and whether `auto`
detects. `PUT` takes `{language}` and answers the same. A code the model is not
listed for is `422`, Estonian included, which Nemotron detects at lower
accuracy. A model that cannot detect, Canary, has no `auto`: told no language
it translates into English, so with nothing set its intent is its first
language, English, and `auto` is `422`. Both answer `409` `needs_speech_model` without a speech model.

The intent lives in the row's `settings` under `transcription`, as
`{"language": "ja"}`, read and written only by
[`language_intent.py`](../../../surfsense_local/backend/modules/llm/transcription/language_intent.py).
A kept language the model no longer lists reads as `auto`, and nothing rewrites
it from a detection. A request names the language's locale from the entry's
`family_codes` (`ja-JP` for Nemotron), and `auto` names none, so the model
detects it. Like voices, it is dropped when the slot takes another
model; choosing the same model again keeps it.

## Capabilities and the system role

For a local model, two sources report two kinds of fact, and only one of them is
meant for a person:

```text
GET /models  -> architecture.input_modalities    what the model can accept
GET /props   -> chat_template_caps               what the template supports
```

Template-derived rather than guessed from a name: a regex over model names is how
an app ends up telling someone a model reads images when nothing can hand it one.

`supports_system_role` is read generously, defaulting to true when absent,
because a runtime that does not report it is more likely old than incapable, and
dropping the system message takes the grounding and the citation instructions
with it while the model answers exactly as confidently as before. Where a
template genuinely has no system role, `for_template()` folds the system content
into the first non-system turn, keeping that turn's role, rather than losing it. The adapter downgrades at that
seam, so `modules/chat` assembles one conversation and never learns that
templates differ.

`vision` is `image` among the accepted inputs, llama.cpp's own answer: the
router reads the header of the projector the preset gave a model and lists
`image` whether or not the model is loaded. The template's
`supports_typed_content` does not decide it, because at `b11050` llama-server
swaps each image for a media marker before templating and keeps the marker when
it joins parts for a string-only template ([ADR
0034](../../adr/0034-vision-is-the-runtimes-answer-stored-nowhere.md)).
`sees_images()` reads it from `/models` alone, so nothing is loaded to ask; an
unreadable `/models` is no answer rather than no. It is the only capability
meant to reach a person;
`system_role`, `typed_content` and `tools` change how a request is built and mean
nothing to one. `Modality` carries only text and image, so an audio-capable model
is not detected as one; audio and video are deliberately not modelled, because
nothing can feed them.

A remote endpoint reports none of this. Its models' capabilities come from its
`/models` listing, and whether one reads images from the catalog
([`../connections.md`](../connections.md)).

`GET` and `PUT /llm/selection/{model_type}` add `reads_images` to the choice,
worked out per read from those two answers and stored nowhere, so the composer
knows before anything is sent ([`../chat.md`](../chat.md#images)).

## Constrained decoding

Both chat providers accept a `json_schema` and send it as
`response_format: {"type": "json_schema", ...}`, which masks every token that
would produce invalid JSON, so a malformed answer stops being something to
repair and becomes something that cannot be emitted. On a local model, a 400 for
a `json_schema` request, which
[llama.cpp#29006](https://github.com/ggml-org/llama.cpp/issues/29006) produces on
some templates, is retried once unconstrained. Chat prose is deliberately
unconstrained.

Studio passes a schema through `run_model()`
([`generate.py`](../../../surfsense_local/backend/worker/studio/shared/generate.py)),
each format's beside its prompts, as the quiz's
([`schema.py`](../../../surfsense_local/backend/worker/studio/content/quiz/schema.py)).
A reply that arrives unconstrained, from an endpoint that ignores
`response_format` or from the 400 retry, is still read by `parse_json()`.

## How it is tested

[`surfsense_local/backend/tests/unit/llm/profile/`](../../../surfsense_local/backend/tests/unit/llm/profile/)
covers `classify()` and fingerprinting, and
[`surfsense_local/backend/tests/unit/llm/prompting/`](../../../surfsense_local/backend/tests/unit/llm/prompting/)
asserts every case ships all three tiers and that slots fill.
`tests/integration/llm/test_routes.py` covers selection, onboarding and delete
over HTTP; `test_speech_catalog_routes.py` and `test_speech_language_routes.py`
beside it cover the speech recognition slot, which model fills it and its
language, and `test_connections.py` that no connection fills it.

## Known gaps

- Only the quiz and flashcards pass `json_schema`: mind map, HTML, image, infographic and the podcast's outline and draft still ask for JSON in the prompt alone, so their format compliance depends on it.
- Nothing measures whether three tiers are still needed; once constrained decoding carries format compliance, a tier would carry reasoning depth only, which plausibly collapses three tiers to two.
