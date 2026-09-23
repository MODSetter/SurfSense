# Model selection and prompt tiers

One model is chosen per model type, local or remote, and the app records a few facts
about it at the moment it is chosen, so that every later request knows how to
prompt it without asking the network. The prompt tier those facts imply is
computed on read and never stored, so a threshold can move on evidence without a
migration or a re-selection. Finishing onboarding is a separate marker that
choosing or clearing a model never touches.

**Code:** [`surfsense_local/backend/modules/llm/selection.py`](../../../surfsense_local/backend/modules/llm/selection.py), [`surfsense_local/backend/modules/llm/model_type.py`](../../../surfsense_local/backend/modules/llm/model_type.py), [`surfsense_local/backend/modules/llm/selectable.py`](../../../surfsense_local/backend/modules/llm/selectable.py), [`surfsense_local/backend/modules/llm/models.py`](../../../surfsense_local/backend/modules/llm/models.py), [`surfsense_local/backend/modules/llm/profile/`](../../../surfsense_local/backend/modules/llm/profile/), [`surfsense_local/backend/modules/llm/prompting/`](../../../surfsense_local/backend/modules/llm/prompting/), [`surfsense_local/backend/modules/llm/resolution.py`](../../../surfsense_local/backend/modules/llm/resolution.py), [`surfsense_local/backend/modules/llm/router.py`](../../../surfsense_local/backend/modules/llm/router.py)
**Decisions:** [ADR 0011](../../adr/0011-llama-cpp-local-runtime.md), [ADR 0015](../../adr/0015-openai-compatible-connections.md)

## One row per model type

`ModelType` is what a model is for: `text_gen`, `image_gen`, `image_edit`,
`video_gen` or `audio_gen`. There are no separate roles; the type is the slot.
`SelectedModel` holds one row per type in `selected_models`, keyed by
`model_type`, so choosing again updates in place.

| Model type | Local | Remote | Read by |
|---|---|---|---|
| `text_gen` | `llamacpp`, the bundled runtime | `openai_compatible`, with a `connection_id` | chat, titles, Studio's writing |
| `image_gen` | `sdcpp`, the bundled sd-server | `openai_compatible`, with a `connection_id` | Studio's `image` and `infographic` |
| `image_edit`, `video_gen`, `audio_gen` | none | `openai_compatible`, with a `connection_id` | nothing yet |

A type no feature reads can still be chosen; the feature that first reads one
brings the client that calls it.

A row stores the provider, the connection when remote, the exact model id, and
three fingerprint facts. A check constraint requires a `connection_id` exactly
when the provider is `openai_compatible`, and deleting a connection cascades to
the rows that name it. `provider` is the SurfSense inference provider, never the
model's publisher.

`GET /llm/selection/{model_type}` returns the row with its computed `tier`, or
`404` when nothing is chosen. `PUT /llm/selection/{model_type}` takes
`provider`, `name`, `connection_id` and `allow_unlisted`, then validates,
fingerprints and stores:

- **Local text** (`llamacpp`): the type must be `text_gen`, there is no
  connection, and the router must list the model as installed with the
  `completion` capability.
- **Local image** (`sdcpp`): the type must be `image_gen`, and the model must be
  one of the bundled image models and downloaded.
- **Remote** (`openai_compatible`): a connection is required, and the model is
  checked against the endpoint's live `/models`. When the listing cannot be read
  or does not include the id, `allow_unlisted` is what lets a user save an exact
  id anyway. Otherwise the model must be able to fill the slot, by one rule in
  `selectable.py`: a model fills the slots of the types it is, and one nothing
  recognises fills every slot. The connection's model listing sends the same
  answer as `selectable_for`, so every picker offers what selection accepts. Remote
  inventory is discovered live and never synchronized into SQLite
  ([`../connections.md`](../connections.md)).

Choosing a `llamacpp` model also starts loading it, as a background task that
runs after the response, because the load blocks until the weights are resident
and choosing a model is when the user has said they are about to use it
([`runtime.md`](runtime.md#warming-listed-is-not-loaded)). Any other provider
loads nothing.

Installing with `select: true` goes through the same `choose_model()`
([`catalog.md`](catalog.md)). Deleting a local model clears the generation row
if it named that model and reports `selection_cleared`; nothing chooses another
model in its place. Revision `0012`, which replaced Ollama with llama.cpp,
cleared any generation selection pointing at Ollama rather than remapping it,
because its weights live in a blob format the app no longer manages.

## Fingerprint

Revision `0010` added `params_b`, `vendor` and `line` (`flagship` or `small`) to
`selected_models`, each nullable. `choose_model()` collects them once, so
generation never has to:

- **Remote**: `inspect()` reads the endpoint's `/models` row for the model. With
  a `hugging_face_id`, `params_b` is the largest size stated in the id or the
  repo name, and `line` defaults to `flagship`, because published weights with no
  size word are a vendor's full-size model. Without one, `vendor` is the row's
  `owned_by`, or the part of the id before its last `/`.
- **Anything else, or a failed read**: `from_name()` takes the largest `<n>b`
  count in the name, so a mixture of experts reads its total rather than its
  active size and `llama-3.3-70b` is not 3B, and failing that a line word such as
  `mini`, `flash`, `pro` or `max`.

A local model is fingerprinted from its filename. `LlamaCppProvider` has no
`inspect()`, so the call fails, the failure is caught, and `from_name()` reads
8 from `Qwen3-8B-Q4_K_M`. A row with all three facts null, such as one chosen
before tiering existed, is fingerprinted from its name on read.

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
| nothing, and the provider is `llamacpp` | `compact` |
| nothing, any other provider | `capable` |

The thresholds encode a claim about scaffolding, not about quality: below the
first a model loses accuracy when asked to follow a structure, between the two it
gains from one, and above the second it writes better from judgement than from
steps. The last two rows are the same bet: a hosted endpoint runs models too big
for a laptop, and a local one runs the laptop. `Fingerprint.local` decides which
applies, and it returns `provider == "llamacpp"`.

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
requires a persisted generation selection, answering `422 chat model required`
otherwise; an image model is optional. The marker means the user finished
choosing, and it is the one thing that must not become true early.

Two invariants, both easy to break from the frontend: selecting or clearing a
model never writes or resets the marker, and Settings' Use actions never call the
route. Only the onboarding page's "Start chatting" does, once a chat model is
persisted. Once the marker exists the app never shows onboarding again, and a
missing selection is fixed from Settings, which renders the same model screen.

## Resolution: local and remote

`resolve_generation()` reads the generation row. A `llamacpp` row resolves to the
bundled runtime ([`runtime.md`](runtime.md)). An `openai_compatible` row resolves
to its connection, and `egress.require()` checks the connection's host, which is
a no-op for a loopback host, so a local LM Studio or Ollama endpoint never
prompts. `resolve_image_generation()` does the same for sd-server or a
connection.

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

`vision` requires both halves: `image` among the accepted inputs and
`supports_typed_content` from the template. A model can accept images
architecturally while its template takes only string content, which leaves no
way to send it one. It is the only capability meant to reach a person;
`system_role`, `typed_content` and `tools` change how a request is built and mean
nothing to one. `Modality` carries only text and image, so an audio-capable model
is not detected as one; audio and video are deliberately not modelled, because
nothing can feed them.

A remote endpoint reports none of this. Its models' capabilities come from its
`/models` listing ([`../connections.md`](../connections.md)).

## Constrained decoding

Both chat providers accept a `json_schema` and send it as
`response_format: {"type": "json_schema", ...}`, which masks every token that
would produce invalid JSON, so a malformed answer stops being something to
repair and becomes something that cannot be emitted. On a local model, a 400 for
a `json_schema` request, which
[llama.cpp#29006](https://github.com/ggml-org/llama.cpp/issues/29006) produces on
some templates, is retried once unconstrained. Chat prose is deliberately
unconstrained.

## How it is tested

[`surfsense_local/backend/tests/unit/llm/profile/`](../../../surfsense_local/backend/tests/unit/llm/profile/)
covers `classify()` and fingerprinting, and
[`surfsense_local/backend/tests/unit/llm/prompting/`](../../../surfsense_local/backend/tests/unit/llm/prompting/)
asserts every case ships all three tiers and that slots fill.
`tests/integration/llm/test_routes.py` covers selection, onboarding and delete
over HTTP.

## Known gaps

- The tier fallback keys on the provider name, not on loopback: `Fingerprint.local` is `provider == "llamacpp"`, so a local endpoint reached through a connection falls to `capable` when nothing else is known; the decision is to key on `host_destination()`, which already computes loopback.
- A remote listing row with no `hugging_face_id` always sets `vendor` (to `owned_by`, or to the id's prefix even when that is empty) and never reads the size in the name, so such a model is classified `frontier`: a `qwen3-4b` from a local endpoint whose listing carries no `hugging_face_id` gets frontier prompts.
- Local fingerprints come from the filename only: `LlamaCppProvider` has no `inspect()`, so `from_llamacpp()`, which reads `general.parameter_count` from `/props`, is never called.
- No caller passes `json_schema`: the providers support constrained decoding, but no Studio format or chat call uses it, so format compliance still depends on the prompt.
- Chat cannot send an image: `Message.content` is a `str`, so even a model with `vision` has no way to receive one.
- Nothing measures whether three tiers are still needed; once constrained decoding carries format compliance, a tier would carry reasoning depth only, which plausibly collapses three tiers to two.
