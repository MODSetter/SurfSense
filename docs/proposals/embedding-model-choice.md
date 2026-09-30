---
status: proposed
code:
  - surfsense_local/backend/modules/embedding/
  - surfsense_local/backend/worker/ingestion/
  - surfsense_local/backend/shared/search.py
  - surfsense_local/backend/shared/migrations.py
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/backend/modules/llm/catalog/remote/
  - surfsense_local/backend/modules/llm/connections/
  - surfsense_local/frontend/src/features/onboarding/
  - surfsense_local/frontend/src/features/settings/
---

# Choosing the embedding model once

> The user picks the embedding model during onboarding: bge-small or another curated model, any ONNX embedder found on Hugging Face, or a remote model through a connection. The choice is fixed for the install. Changing it later means re-embedding the library, which is [future work](embedding-model-change.md). This proposal builds the data shape that work needs, so it adds code without changing a schema.

Today one model, bge-small-en-v1.5, is hard-coded in [`embedding.py`](../../surfsense_local/backend/worker/ingestion/embedding.py) ([ADR 0007](../adr/0007-bundled-embeddings.md)). It is English-only, so a question in one language does not find its answer in another ([search](../architecture/search.md), Known gaps). A multilingual or hosted model fixes that for the users who need it, and costs everyone else disk, memory, speed or privacy for nothing. So it is a choice, not a swap.

## Decisions

- **bge-small stays bundled, the default, and never deletable**, like the audio model audio.cpp ships ([`bundled.py`](../../surfsense_local/backend/modules/llm/catalog/local/engines/audiocpp/bundled.py)). It ships even to a user who picked another model, because it is the pick when anything else fails, and the way back once changing is possible.
- **Onboarding offers three sources**, in an optional step:
  - **Curated:** bge, preselected, and a short list SurfSense measured.
  - **Hugging Face:** any ONNX embedder, searched live.
  - **Remote:** an embedding model on a connection, through the same connections and [models.dev catalog](../../surfsense_local/backend/modules/llm/catalog/remote/manifest/models.json) as every other remote model.

  Skipping the step, being offline, refusing a download or a failed download all mean bge.
- **Finishing onboarding locks the choice** for the whole app, every workspace. Settings shows the model with every way to change it disabled.
- **Onboarding is the only place to choose.** An install that finished onboarding before this ships is locked to bge.
- **No fallback, ever.** If the locked model becomes unreachable, search and ingest stop and say why. Answering with bge would compare bge questions against another model's vectors, which returns nonsense rather than an error.
- **The risk is accepted, not solved.** A Hugging Face pick that ranks badly, or a remote model its provider retires, stays until [changing](embedding-model-change.md) ships. Onboarding says so in plain words before the user commits.

## The spec

Every source produces the same `EmbedderSpec`, and the index stores a snapshot of it:

| Field | Why the index depends on it |
|---|---|
| `source` | `curated`, `huggingface` or `remote`; decides what Settings and onboarding say about it |
| `runtime` | `onnx` for the first two, `openai_compatible` for remote |
| `repo`, `revision`, file hashes | local only: what to download, pinned, so a re-download is the same model |
| `connection_id`, `model_id` | remote only: where to call |
| `dimension` | the vector table's width |
| `pooling`, `normalize` | local only: the same model pooled another way is another space |
| `query_prefix`, `document_prefix` | asymmetric local models embed questions and passages differently |
| `input_mode` | remote only: a provider's own query and document switch, where it has one |
| `max_tokens` | a chunk past it is cut short |
| `semantic_weight` | the blend is a plateau measured per model: 0.65 for bge, 0.85 for granite ([retrieval](retrieval.md)) |
| `measured` | whether SurfSense measured `semantic_weight` and the chunk fit, or fell back |
| `size_bytes` | what onboarding shows before a download |

## Curated

A manifest in `modules/embedding/`. Not the [local catalog manifest](../../surfsense_local/backend/modules/llm/catalog/local/manifest/models.json): its validator requires a bundled engine for each entry, its files are GGUF, and it feeds the model slots this design keeps the embedder out of. It pins files the same way, by revision and sha256.

An entry is admitted only if:

- it ships an ONNX file, is ungated and permissively licensed;
- the [retrieval eval](../../surfsense_local/backend/scripts/run_retrieval_eval.py) measured its `semantic_weight`;
- every chunk of the eval corpus, cut at `CHUNK_TOKENS`, fits its `max_tokens` in its own tokenizer, in every language (see *Chunking* below);
- it is small enough to load once per embedding process: the API for questions, the ingest worker, and the Studio worker ([`persist.py`](../../surfsense_local/backend/worker/studio/shared/persist.py)).

The first candidate is `ibm-granite/granite-embedding-97m-multilingual-r2`, with the risks [retrieval](retrieval.md) lists still open.

## Hugging Face

A live search filtered to `sentence-similarity` and `feature-extraction`. The onboarding search that exists today ([`hugging-face-search.tsx`](../../surfsense_local/frontend/src/features/onboarding/model-step/hugging-face-search.tsx)) goes through the llama.cpp engine and reads GGUF files, so this is a second search beside it, reading different files.

- **Runnable means ONNX.** The API process ships onnxruntime without torch ([`api.spec`](../../surfsense_local/backend/bundling/api.spec)), so a repo with only safetensors is shown as not runnable. When a repo has several ONNX files, the full-precision `onnx/model.onnx` layout is preferred; the exact rule is an open question.
- **Refused:** gated repos, repos Hugging Face's security scan flags, and repos without a `tokenizer.json`.
- **The spec is read from the repo's own files:** pooling from `1_Pooling/config.json`, normalisation from `modules.json`, prompts from `config_sentence_transformers.json`, maximum length from `sentence_bert_config.json`, width from `config.json`. Anything missing takes the default bge uses, and the pick is labelled.
- **Pinned at pick time:** the revision, and each file's sha256 from the repo listing, as the chat model search already reads it ([`listing.py`](../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/search/listing.py)).
- **Probed after download:** one test string is embedded, and a vector of the wrong width refuses the pick.
- **Labelled not measured:** `semantic_weight` falls back to 0.65 and `measured` is false. Onboarding says the model has not been tested by SurfSense.

## Remote

The same connections as chat and images ([ADR 0015](../adr/0015-openai-compatible-connections.md)), including the onboarding server option ([`server-option.tsx`](../../surfsense_local/frontend/src/features/onboarding/model-step/server-option.tsx)). What is new is the call, `POST {base_url}/embeddings`, and what the pick writes.

- **Same catalog, read differently.** For chat, images and audio, [`classifier.py`](../../surfsense_local/backend/modules/llm/catalog/remote/classifier.py) decides the type from `modalities`. That cannot find an embedder: models.dev has no embedding output, and of the 81 entries in the snapshot whose ids look like embedders, 75 declare `text → text` exactly like a chat model; the other six add image, audio or video inputs, which a text index does not use. So the embedder reads other fields:

  | Field | Read for | How far it can be trusted |
  |---|---|---|
  | model id | detection, by the terms [`not_text_gen.py`](../../surfsense_local/backend/modules/llm/catalog/remote/not_text_gen.py) already refuses from chat (`embed`, `voyage`, `bge`, `e5-`, …) | 4 of the 81 describe themselves as chat models, so the terms need the same audit that list had |
  | `family` | detection, a second signal: `text-embedding`, `cohere-embed`, `mistral-embed`, `titan-embed`, `codestral-embed` | reliable when present, but many embedders carry `gemini`, `qwen`, `voyage` or none |
  | `context` | the longest passage the model accepts, against `CHUNK_TOKENS` | useful; seven are 512 |
  | `output_limit` | the width shown before the probe | not trusted: 1536 and 3072 appear, and so do 1, 32768 and none |
  | `status` | the deprecation warning in Settings | set on 1 of the 81 |

  Chat keeps refusing whatever the embedder admits, so no model lands in both. A model the catalog has never seen, such as a team's own server running bge, can be named by hand; the probe decides.
- **The probe is the truth.** One test string is embedded and the vector's length becomes `dimension`. A model that returns no vector is refused, which also catches a chat model the name terms let through.
- **Provider notes.** models.dev does not record a provider's query and document switch or its batch limit. A short table in `modules/embedding/` keyed by provider holds them; a provider not in it gets plain `/embeddings`, and the pick is labelled not measured.
- **Only OpenAI-compatible.** A provider whose own API is not, such as Cohere's, is reachable only through a gateway that is.
- **Consent covers the library.** Ingest runs in the background, where no consent dialog can appear ([ADR 0017](../adr/0017-egress-off-by-default.md)). The consent given in onboarding covers every passage of every document, and onboarding says exactly that: *"Every document you add, and every question, is sent to {host}."*

The pick writes the `embedding_indexes` row, never a `selected_models` row. Those rows are preferences the Settings model tabs change freely, and deleting a connection cascades them.

## Design

### The index is a row

A new `embedding_indexes` table:

| Column | Holds |
|---|---|
| `id` | primary key |
| `spec` | a JSON snapshot of the `EmbedderSpec`, so a later manifest edit cannot change what an existing index means |
| `vector_table` | the vec0 table holding this index's vectors |
| `state` | `active` now; `building` and `retired` arrive with [changing](embedding-model-change.md) |
| `created_at` | |

One row, `active`, enforced in code. Not a singleton with `CHECK (id = 1)` like `onboarding_completion`: a second row is how changing starts, and a constraint would make that a schema change.

### The vector table is created at lock time

Migration `0001` creates `chunk_vectors` at `SURFSENSE_LOCAL_EMBEDDING_DIMENSION`. On a fresh install it is empty at onboarding, so locking drops it and creates the table at `spec.dimension`, refusing if any chunk exists. The table name comes from the row and is checked against a fixed pattern before it reaches SQL; nothing else names `chunk_vectors`.

`_check_embedding_width()` in [`migrations.py`](../../surfsense_local/backend/shared/migrations.py) compares against the active row instead of the setting, and the setting is retired. This also closes [ADR 0007](../adr/0007-bundled-embeddings.md)'s gap: a same-width model is now detected, because the row names the model and not only the width.

### Each document records its index

`documents.embedding_index_id`, written when its chunks are embedded. With one index it is always the active one; with two it is how a re-embed knows what is done.

### Chunking does not depend on the embedder

[`chunking.py`](../../surfsense_local/backend/worker/ingestion/chunking.py) measures chunks with the embedder's tokenizer. If the embedder decides the boundaries, changing it re-cuts every document, chunk ids change, and every citation in every old chat breaks. The chunker gets its own pinned tokenizer, bge's file under its own name, which changes nothing today.

A curated model is admitted only if chunks fit it. A Hugging Face pick is not checked in advance, so ingest counts, with the model's own tokenizer, the passages longer than `max_tokens`; they are embedded cut short, and Settings shows the count. A remote model's tokenizer is not on the machine, so an overlong passage shows up only as the provider's error.

### One write path, one read path

- **Encode:** `embed(texts, purpose)`, where purpose is `QUERY` or `DOCUMENT`, built from a spec: an ONNX session with its pooling, normalisation and prefix, or a connection call with its input mode. Local files live in `models/<id>@<revision>/`, so two models can sit on disk at once.
- **Write:** `embed_chunks(index, chunk_ids)` embeds in batches and writes to that index's table. `write_vectors()` in [`indexing.py`](../../surfsense_local/backend/worker/ingestion/indexing.py) calls it for every index that is not retired: a list of one today, both indexes during a re-embed, with no change to ingest, Studio or import.
- **Read:** [`search.py`](../../surfsense_local/backend/shared/search.py) takes the encoder, the vector table and `SEMANTIC_WEIGHT` from `active_index()`. A question is always embedded by the index it is searched against.

`chunks.embedding` gains no new readers. One column cannot hold two models' vectors; each index's table is the store.

### Nothing embeds before the lock

The onboarding gate is in the UI ([`app-bootstrap.tsx`](../../surfsense_local/frontend/src/app/app-bootstrap.tsx)); the upload routes are not behind it, and the API is a product surface. Ingest refuses with `409 embedding_not_chosen` while no active index exists. The UI never sees it.

### What cannot be deleted

| Thing | Deletable |
|---|---|
| bge (bundled) | never |
| the active index's local model | not while it is active |
| the connection the active index calls | not while it is active; editing its key or URL stays allowed |
| a model downloaded but never locked | yes |

Checked against the active row, not a flag on the file, so a model retired by a re-embed becomes deletable with no change here. The connection's host stays switchable in Settings › Network, because that is a privacy control; turning it off warns that search and ingest stop.

### When the model is unreachable

| Source | Cause | What happens |
|---|---|---|
| curated, Hugging Face | folder deleted or corrupted | the pinned revision is downloaded again, which needs the network and the Hugging Face destination ([ADR 0027](../adr/0027-egress-consent-per-host.md)) |
| Hugging Face | repo deleted or made private since | no repair until [changing](embedding-model-change.md) ships |
| remote | offline, outage, key revoked, host turned off | chat answers `503` saying why, ingest fails with Retry |
| remote | provider retires the model | no repair until [changing](embedding-model-change.md) ships |
| remote | a models.dev refresh marks it `deprecated` | Settings warns before the provider turns it off; models.dev rarely sets it, so this is a bonus, not a guarantee |

bge is bundled and cannot become unreachable. Chat's check for missing files in [`chat/router.py`](../../surfsense_local/backend/modules/chat/router.py) reads the active spec, not bge's file list.

## Onboarding

1. A new step before the chat model. It is not a model slot: [`slot.ts`](../../surfsense_local/frontend/src/features/onboarding/model-step/slot.ts) is typed to `ModelType`, and the embedder is not a selection. The step list needs a kind of step that is not one.
2. Curated models come first, bge preselected, each with its size and one line on what it is for: *"Choose Multilingual only if your documents or questions are in more than one language."* Hugging Face search and remote models sit below.
3. A local pick not on disk resolves first (size, whether it is on disk, any error), then downloads with the hash check and the probe. A remote pick probes the connection. The click is a user action, so the egress dialog may appear once.
4. Before the user continues, the step says what cannot be undone: that the model is fixed for this library, whether SurfSense measured it, and for remote, where every document goes.
5. Finishing onboarding writes the `embedding_indexes` row and creates the vector table. Nothing chosen, or a download or probe not finished, writes bge.

## Settings

An *Embedding model* section in [`settings-dialog.tsx`](../../surfsense_local/frontend/src/features/settings/settings-dialog.tsx), read from `GET /embedding/index`, which returns `{active, building: null}`. It shows the model, its source (curated, Hugging Face, or remote with its host), its width, whether it was measured, the count of passages cut short, and any deprecation warning. Every control that would change or delete it is disabled, with a line saying changing it is coming. `building` is always null now; it carries progress once [changing](embedding-model-change.md) ships, with no contract change.

## Existing installs

Onboarding is already complete, so they never see the step. A migration writes a bge row pointing at their existing `chunk_vectors` and stamps every document with it. No vector moves.

## What each choice costs the user

| | Curated (granite) | Hugging Face | Remote |
|---|---|---|---|
| Disk | about 118 MB on top of bge's 63 MB | whatever the repo weighs | none |
| Memory | a copy per embedding process | the same | none |
| Ingest speed | slower than bge; granite has 3× the parameters and is not yet measured | unknown | the network and the provider's rate limit |
| Ranking | measured weight | 0.65, not measured | 0.65 unless the provider is in the notes |
| Privacy | stays on the machine | stays on the machine | every passage and question leaves it |
| Money | none | none | billed per passage indexed, retries included |
| Can break for good | no | if the repo disappears | if the provider retires the model |

A model with another width also changes storage: 1536 dimensions is 6 KB a vector instead of bge's 1.5 KB, and four times the work per question for the brute-force vector leg.

## Rejected

- **The embedder as a `selected_models` slot.** Those rows are preferences, changed freely through `choose_model()` and the model-slot Settings UI, and cascaded away with their connection. The embedder is a property of the index; putting it there offers exactly the swap that breaks search.
- **Change freely, repair by re-upload.** [Unsloth Studio](https://github.com/unslothai/unsloth/tree/main/studio) does this: any Hugging Face embedder at any time, identity stamped on each document, one vector table dropped outright on a width change, and *"Re-upload existing ones after changing the model."* After a switch, older documents drop out of meaning search without saying so. It suits a studio where RAG is a side feature; here the library is the product. Taken from it: the identity stamp on each document, a resolve step before saving, and pooling as part of the identity.
- **Locking at the first indexed chunk** rather than at onboarding. It lets Settings change the model while the library is empty, but most users add a source within minutes, so the window is short and the rule is harder to explain. One moment, onboarding, is simpler.
- **Curated local models only.** Safer, since every choice would be measured and none could vanish, but it leaves out users with a hosted embedder they already pay for and multilingual models not yet on the list. The risk is taken knowingly and stated in onboarding.
- **Falling back to bge when the locked model is unreachable.** It would keep search answering, with wrong answers.

## When this ships

- A new ADR amending [ADR 0007](../adr/0007-bundled-embeddings.md): the index records its model, the width comes from the row, bge is the default rather than the only model, and remote embedding is no longer a later opt-in.
- [ADR 0015](../adr/0015-openai-compatible-connections.md) says embeddings do not go through connections; the same ADR amends that.
- [search](../architecture/search.md), [documents](../architecture/documents.md), [data model](../architecture/data-model.md) and [egress](../architecture/egress.md) describe the index row, the spec, the lock and the background consent.
- [retrieval](retrieval.md) proposes granite as the bundled replacement for bge. This proposal keeps bge as the default and offers granite as a choice; that proposal's measurements carry over, and its migration section is superseded by [changing](embedding-model-change.md).

## Open questions

- Granite's `max_tokens`, and how many of its tokens a 480-token bge chunk becomes in Hindi, Japanese and Chinese.
- Whether granite is ready: [retrieval](retrieval.md) asks for the same-language slices to be hardened first.
- The size cap for a curated entry, and whether a Hugging Face pick above it is refused or warned, given three processes each load it.
- Which ONNX file a Hugging Face repo with several is read from, and whether a quantised one is ever preferred.
- The remote context floor: whether a model whose models.dev `context` is close to `CHUNK_TOKENS`, such as Cohere v3 at 512, is refused, since another tokenizer can count a chunk as more tokens.
- The smallest way to make a bad pick recoverable before full [changing](embedding-model-change.md): a blocking rebuild that pauses search and re-embeds every chunk into a new index row.
