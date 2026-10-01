---
status: proposed
code:
  - surfsense_local/backend/modules/embedding/
  - surfsense_local/backend/modules/llm/catalog/local/
  - surfsense_local/backend/modules/llm/model_type.py
  - surfsense_local/backend/modules/llm/selectable.py
  - surfsense_local/backend/modules/llm/selection.py
  - surfsense_local/backend/scripts/local_manifest/
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

> The user picks the embedding model during onboarding: bge-small or another curated model, an ONNX embedder found on Hugging Face, or a remote model through a connection. Every pick SurfSense did not measure is tested before it is accepted, and the choice is fixed for the install. Changing it later means re-embedding the library, which is [future work](embedding-model-change.md). This proposal builds the data shape that work needs, so it adds code without changing a schema.

Today one model, bge-small-en-v1.5, is hard-coded in [`embedding.py`](../../surfsense_local/backend/worker/ingestion/embedding.py) ([ADR 0007](../adr/0007-bundled-embeddings.md)). It is English-only, so a question in one language does not find its answer in another ([search](../architecture/search.md), Known gaps). A multilingual or hosted model fixes that for the users who need it, and costs everyone else disk, memory, speed or privacy for nothing. So it is a choice, not a swap.

## Decisions

- **bge-small stays bundled, the default, and never deletable**, like the audio model audio.cpp ships ([`bundled.py`](../../surfsense_local/backend/modules/llm/catalog/local/engines/audiocpp/bundled.py)). It ships even to a user who picked another model, because it is the pick when anything else fails, and the way back once changing is possible.
- **Onboarding offers three sources**, in an optional step:
  - **Curated:** bge, preselected, and a short list SurfSense measured.
  - **Hugging Face:** an ONNX embedder, searched live.
  - **Remote:** an embedding model on a connection, through the same connections and [models.dev catalog](../../surfsense_local/backend/modules/llm/catalog/remote/manifest/models.json) as every other remote model.

  Skipping the step, being offline, refusing a download, or a pick that fails its checks all mean bge.
- **Finishing onboarding locks the choice** for the whole app, every workspace. Settings shows the model with every way to change it disabled.
- **Onboarding is the only place to choose.** An install that finished onboarding before this ships is locked to bge.
- **Stricter than the other model types.** Chat, image and audio admit a model nothing recognises, because the user sees it answer before trusting it ([`selectable.py`](../../surfsense_local/backend/modules/llm/selectable.py)). A wrong embedder never fails where the user can see it: it returns vectors, and search ranks badly. And the pick is permanent. So an embedder is refused unless evidence says it is one, and every pick SurfSense did not measure is tested before it is accepted.
- **No fallback, ever.** If the locked model becomes unreachable, search and ingest stop and say why. Answering with bge would compare bge questions against another model's vectors, which returns nonsense rather than an error.
- **The risk is accepted, not solved.** A pick that passes its checks and still ranks badly, or a remote model its provider retires, stays until [changing](embedding-model-change.md) ships. Onboarding says so in plain words before the user commits. A smaller way back, a blocking rebuild that pauses search and re-embeds every chunk, was considered and deferred with the rest of [changing](embedding-model-change.md).

## How a pick is admitted

Every source goes the same way:

```
evidence ─► download or connect ─► probe ─► sanity check ─► label ─► locked when onboarding finishes
```

- **Evidence** that the model is built to embed, and what decides it differs by source: the manifest for curated models, the repo for Hugging Face, the server and the catalog for remote. Each section below says which. A model with no evidence is refused, except a remote model the user names by hand.
- **Probe.** One test string is embedded. A vector proves the model runs and gives its width; an error or no vector refuses the pick.
- **Sanity check.** A fixed paraphrase pair and a fixed unrelated pair are embedded, and the paraphrase must score clearly closer. A probe alone is not enough, because a chat model can return vectors: Ollama embeds with any model, llama-server does with `--embeddings`, and vLLM can run a chat model as an embedder. Those vectors put everything close together, so the gap collapses. The check costs one call and needs nothing from the provider. Curated models skip it; the retrieval eval already measured them.
- **Label.** How the model was identified, stored in the spec and shown wherever the model is:

  | Label | Meaning | Onboarding and Settings say |
  |---|---|---|
  | `measured` | curated; the [retrieval eval](../../surfsense_local/backend/scripts/run_retrieval_eval.py) measured it | recommended |
  | `declared` | the server, the catalog or the repo says it is an embedder, and it passed the probe and the check | nothing extra |
  | `inferred` | only its name says so, and it passed the probe and the check | not tested by SurfSense |
  | `unverified` | named by hand with no evidence, and it passed the probe and the check | may not be an embedding model |

Nothing is admitted on its name alone, and nothing on a probe alone.

## The spec

Every source produces the same `EmbedderSpec`, and the index stores a snapshot of it:

| Field | Why the index depends on it |
|---|---|
| `source` | `curated`, `huggingface` or `remote` |
| `identified` | the label above |
| `runtime` | `onnx` for the first two, `openai_compatible` for remote |
| `repo`, `revision`, file hashes | local only: what to download, pinned, so a re-download is the same model |
| `connection_id`, `model_id` | remote only: where to call |
| `dimension` | the vector table's width, from the probe |
| `pooling`, `normalize` | local only: the same model pooled another way is another space. `in_model` when the build pools inside its own graph and returns one vector per text, so the encoder does not pool twice |
| `query_prefix`, `document_prefix` | asymmetric local models embed questions and passages differently |
| `input_mode` | remote only: a provider's own query and document switch, where it has one |
| `max_tokens` | a chunk past it is cut short |
| `semantic_weight` | the blend is a plateau measured per model: 0.65 for bge, 0.85 for granite ([retrieval](retrieval.md)); 0.65 for anything not measured |
| `size_bytes` | what onboarding shows before a download |

## Curated

### The list

Ordered by preference, as every curated list is, each shown with its download size. All are ONNX, ungated and permissively licensed; numbers are from each model's card and the int8 build that would be pinned.

| Model | Licence | Params | Width | Languages | Int8 build | Pooling, prefix | Status |
|---|---|---|---|---|---|---|---|
| `BAAI/bge-small-en-v1.5` | MIT | 33M | 384 | English | bundled | CLS, none | the default |
| `ibm-granite/granite-embedding-97m-multilingual-r2` | Apache-2.0 | 97M | 384 | 200+, 52 strong | 98 MB | CLS, none | first to add: same width as bge, runs on today's encoder |
| `ibm-granite/granite-embedding-311m-multilingual-r2` | Apache-2.0 | 311M | 768 | 200+, 52 strong | 313 MB | CLS, none | for machines with more memory |
| `microsoft/harrier-oss-v1-270m` | MIT | 270M | 640 | multilingual | 344 MB | in the model, instruction on queries | after the open questions below |

The cards do not report the same benchmark: granite gives multilingual retrieval (60.3 and 65.2), harrier the multilingual MTEB v2 average across task types (66.5). The retrieval eval decides, cross-language slice included.

Left out: harrier-oss-v1-0.6b (too slow and heavy for most machines), EmbeddingGemma-300m (gated), jina-embeddings v3 and v5 (non-commercial), Qwen3-Embedding-0.6B (behind harrier at the same size, and as heavy), bge-m3 (2.2 GB, older and weaker), the multilingual-e5 family (older), nomic-embed-text-v1.5 and mxbai-embed-large (English only), and anything with no ONNX build or a licence of its own.

An entry is admitted only if:

- it ships an ONNX file, is ungated and permissively licensed;
- the retrieval eval measured its `semantic_weight`;
- every chunk of the eval corpus, cut at `CHUNK_TOKENS`, fits its `max_tokens` in its own tokenizer, in every language (see *Chunking* below);
- its pinned build matches the original model (see *Builds* below).

There is no size or memory cap. As in [Unsloth Studio](https://github.com/unslothai/unsloth/tree/main/studio), the size is shown and the choice is the user's; the list stays short because SurfSense chooses what goes on it. A model too heavy for most machines is simply not listed.

### Builds

A curated entry pins a generic int8 build, not one tuned for a single CPU such as granite's own `model_quint8_avx2.onnx`. Most come from a conversion someone else made, so a build is pinned at a revision and admitted only if its vectors match the original model's on a sample of the eval corpus. A build that fails is replaced by an export of our own.

A build may pool inside its own graph and return one vector per text, as the harrier conversions do, or return every token's output and leave pooling to the encoder, as bge and granite do. The spec's `pooling` says which.

Every curated pick is `measured`.

### Where the list lives

In the same [local manifest](../../surfsense_local/backend/modules/llm/catalog/local/manifest/models.json) as chat, image and audio models, run by a fourth engine. It is then refreshed, pinned, licence-checked, downloaded, shown and deleted by the code that already does all of that for the other types.

- **An ONNX embedding engine** in the [engine registry](../../surfsense_local/backend/modules/llm/catalog/local/engines/registry.py), beside llama.cpp, sd.cpp and audio.cpp. Its entry block, `embedding`, holds what the spec needs and the header cannot give: `dimension`, `pooling`, `normalize`, `query_prefix`, `document_prefix`, `max_tokens` and `semantic_weight`, and `batch`, the passages embedded at once, which a larger model keeps smaller because the batch rather than the weights sets its peak memory. It sits where `image` and `audio` sit for their engines.
- **File roles** `tokenizer` and `config` join `weights` in [`build.py`](../../surfsense_local/backend/modules/llm/catalog/local/build.py), and `validated` gains `onnxruntime` beside `llama_cpp`, `sd_cpp` and `audio_cpp`.
- **`ModelType.EMBEDDING`.** The [classifier](../../surfsense_local/backend/modules/llm/catalog/local/classifier.py)'s embedder group, which today calls these models not runnable, gives this type instead. A GGUF embedder found through the llama.cpp search still cannot run, because the engine reads ONNX, so it stays refused there.
- **The refresh keeps what it cannot read.** `semantic_weight` and the chunk fit come from the retrieval eval, not from Hugging Face, so [`refresh_local_manifest.py`](../../surfsense_local/backend/scripts/refresh_local_manifest.py) carries them over from the hand-authored entry, as it does every hand-authored field.

### A type, not a slot

[`model_type.py`](../../surfsense_local/backend/modules/llm/model_type.py) says a type is also a slot. `EMBEDDING` is the exception: a catalog type, so the manifest and the engines can describe it, and never a selection, so nothing can swap it. Three places enforce that, each with a test:

- [`selectable_for()`](../../surfsense_local/backend/modules/llm/selectable.py), which offers every type to a model nothing recognises, leaves `EMBEDDING` out;
- `choose_model()` in [`selection.py`](../../surfsense_local/backend/modules/llm/selection.py) refuses it;
- the `selected_models` check constraint excludes it.

Missing any one of them would make the embedder swappable, which is the failure this whole design exists to prevent. Only the curated list is in the manifest; a Hugging Face or remote pick never touches it, and every source still ends in the spec stored on the index row.

## Hugging Face

A live search filtered to `sentence-similarity` and `feature-extraction`. The onboarding search that exists today ([`hugging-face-search.tsx`](../../surfsense_local/frontend/src/features/onboarding/model-step/hugging-face-search.tsx)) goes through the llama.cpp engine and reads GGUF files, so this is a second search beside it, reading different files.

- **Runnable means ONNX.** The API process ships onnxruntime without torch ([`api.spec`](../../surfsense_local/backend/bundling/api.spec)), so a repo with only safetensors is shown as not runnable.
- **Which file.** A generic int8 file (`model_int8.onnx`, `model_quantized.onnx`) first, then the full-precision `onnx/model.onnx` or `model.onnx`; otherwise the repo is refused. A file's external data (`.onnx_data`) downloads with it. Never a file tuned for one CPU (`*avx2*`, `*avx512*`, `*arm64*`), an `O1` to `O4` optimised variant, or an `fp16`, `q4` or `bnb4` build: fp16 runs slowly on a CPU and the rest are made for other hardware or runtimes. A bad quantisation is caught by the probe and the sanity check.
- **Refused:** gated repos, repos Hugging Face's security scan flags, and repos without a `tokenizer.json`.
- **Evidence:** the repo's pipeline tag and its sentence-transformers files. A repo that ships them is `declared`; one with only the tag is `inferred`.
- **The spec is read from those files:** pooling from `1_Pooling/config.json`, normalisation from `modules.json`, prompts from `config_sentence_transformers.json`, maximum length from `sentence_bert_config.json`, width from `config.json`. Anything missing takes bge's default.
- **Pinned at pick time:** the revision, and each file's sha256 from the repo listing, as the chat model search already reads it ([`listing.py`](../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/search/listing.py)).
- **Then the probe and the sanity check**, on the downloaded files. A width that disagrees with `config.json` refuses the pick.

## Remote

The same connections as chat and images ([ADR 0015](../adr/0015-openai-compatible-connections.md)), including the onboarding server option ([`server-option.tsx`](../../surfsense_local/frontend/src/features/onboarding/model-step/server-option.tsx)). What is new is the call, `POST {base_url}/embeddings`, how an embedder is recognised, and what the pick writes.

### Recognising an embedder

For chat, images and audio, [`classifier.py`](../../surfsense_local/backend/modules/llm/catalog/remote/classifier.py) decides the type from `modalities`. That cannot find an embedder: models.dev has no embedding output, and of the 81 entries in the snapshot whose ids look like embedders, 75 declare `text → text` exactly like a chat model; the other six add image, audio or video inputs, which a text index does not use. So evidence is read in this order, and the first source that answers decides, to admit or to refuse:

1. **The server.** Where the connection points at a server SurfSense recognises, an adapter asks it directly. `declared`. See *Server adapters* below.
2. **The catalog's `family`.** `text-embedding`, `cohere-embed`, `mistral-embed`, `titan-embed`, `codestral-embed`. Reliable where present, but many embedders carry `gemini`, `qwen`, `voyage` or none. `declared`.
3. **The model id,** by the terms [`not_text_gen.py`](../../surfsense_local/backend/modules/llm/catalog/remote/not_text_gen.py) already uses to keep embedders out of chat (`embed`, `voyage`, `bge`, `e5-`, …), with an audited list of exceptions: 4 of the 81 describe themselves as chat models. `inferred`.
4. **Nothing.** The model is not listed. The user can still name one by hand, such as a team's own server running bge. `unverified`.

The catalog supplies two more things: `context`, the longest passage the model accepts, checked against `CHUNK_TOKENS` (seven of the 81 are 512); and `status`, which raises the deprecation warning in Settings, though it is set on only 1 of the 81. `output_limit` is shown as the width before the probe and never trusted after it: it holds 1536 and 3072, and also 1, 32768 and nothing.

Chat keeps refusing whatever this admits, so no model lands in both.

### Server adapters

Several servers say what a model is through an API of their own, read from their source and documentation:

| Server | Recognised by | Where it says | What marks an embedder | Also gives |
|---|---|---|---|---|
| Ollama | `GET /api/version` answers | `POST /api/show`, per model | `capabilities` holds `"embedding"`, which Ollama derives from the GGUF header's `pooling_type` | the width, as `<arch>.embedding_length` in `model_info` |
| LM Studio | `GET /api/v1/models` answers, or `/api/v0/models` before 0.4.0 | the same list | `type` is `"embedding"` in v1, `"embeddings"` in v0 | `max_context_length` |
| Hugging Face TEI | `GET /info` holds `model_type` | `/info`, for the one model it serves | `model_type` is `{"embedding": {"pooling": …}}`, not `classifier` or `reranker` | `model_sha`, the exact revision; `max_input_length`; `POST /tokenize` |
| OpenRouter | its host | `GET /api/v1/embeddings/models` | `output_modalities` is `["embeddings"]` | `expiration_date`, `hugging_face_id`, `context_length` |

Three things follow from how these servers behave:

- **An adapter can list, not only classify.** Discovery today reads `GET {base_url}/models` ([ADR 0015](../adr/0015-openai-compatible-connections.md)). TEI has no such route, so its connection would find nothing, and OpenRouter's `/models` leaves every embedder out. For both, the adapter's own list is the listing.
- **Adapters reach past `/v1`.** A connection's base URL ends in `/v1`; Ollama's `/api/*`, LM Studio's `/api/*` and TEI's `/info` sit at the server's root, so the adapter strips it. Same host, so no consent beyond the connection's own.
- **Older versions are expected.** Ollama has reported `capabilities` on `/api/show` since April 2025 but on `/api/tags` reliably only since 0.34.1 in September 2026, so the adapter asks `/api/show`. LM Studio's v1 API arrived in 0.4.0; the adapter falls back to v0 and accepts both spellings.

llama-server and vLLM say nothing: llama-server's `/props` and `/v1/models` carry no kind, its router mode reports every model's output as `text`, and vLLM's `/v1/models` has no task. Both, and Ollama, also return vectors from a chat model: Ollama's embed route asks for no capability, llama-server embeds with any model once started with `--embeddings`, and vLLM can run a chat model as an embedder. They get no adapter, and the catalog, the name, the probe and the sanity check decide. LiteLLM's `/model/info` (`mode` is `"embedding"`) and Infinity's `/models` (`capabilities` holds `"embed"`) can join the table later.

### Calling it

- **Provider notes.** models.dev does not record a provider's query and document switch or its batch limit. A short table in `modules/embedding/` keyed by provider holds them; a provider not in it gets plain `/embeddings`.
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

A curated model is admitted only if chunks fit it. A Hugging Face pick is not checked in advance, so ingest counts, with the model's own tokenizer, the passages longer than `max_tokens`; they are embedded cut short, and Settings shows the count. A remote model's tokenizer is not on the machine, so an overlong passage shows up only as the provider's error, unless the server counts tokens itself, as TEI's `/tokenize` does.

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
| remote | OpenRouter gives it an `expiration_date`, or a models.dev refresh marks it `deprecated` | Settings warns before the provider turns it off; OpenRouter's date is real, models.dev's status is rarely set, so neither is a guarantee |

bge is bundled and cannot become unreachable. Chat's check for missing files in [`chat/router.py`](../../surfsense_local/backend/modules/chat/router.py) reads the active spec, not bge's file list.

## Onboarding

1. A new step before the chat model. It is not a model slot: [`slot.ts`](../../surfsense_local/frontend/src/features/onboarding/model-step/slot.ts) is typed to `ModelType`, and the embedder is not a selection. The step list needs a kind of step that is not one.
2. Curated models come first, bge preselected, each with its download size and one line on what it is for: *"Choose Multilingual only if your documents or questions are in more than one language."* Hugging Face search and remote models sit below.
3. A local pick not on disk resolves first (size, whether it is on disk, any error), then downloads with the hash check. A remote pick connects. Then the probe and the sanity check run, and the pick gets its label. The click is a user action, so the egress dialog may appear once.
4. Before the user continues, the step says what cannot be undone: that the model is fixed for this library, what its label means, and for remote, where every document goes. A Hugging Face pick shows its download size with one line: *"Larger models make adding documents slower and use more memory, and this choice can't be changed later."*
5. Finishing onboarding writes the `embedding_indexes` row and creates the vector table. Nothing chosen, or a pick whose download or checks did not finish, writes bge.

## Settings

An *Embedding model* section in [`settings-dialog.tsx`](../../surfsense_local/frontend/src/features/settings/settings-dialog.tsx), read from `GET /embedding/index`, which returns `{active, building: null}`. It shows the model, its source (curated, Hugging Face, or remote with its host), its label, its width, the count of passages cut short, and any deprecation warning. Every control that would change or delete it is disabled, with a line saying changing it is coming. `building` is always null now; it carries progress once [changing](embedding-model-change.md) ships, with no contract change.

## Existing installs

Onboarding is already complete, so they never see the step. A migration writes a `measured` bge row pointing at their existing `chunk_vectors` and stamps every document with it. No vector moves.

## What each choice costs the user

| | Curated (granite) | Hugging Face | Remote |
|---|---|---|---|
| Disk | 98 MB for the 97M model, 313 MB for the 311M, on top of bge's 63 MB | whatever the repo weighs | none |
| Memory | a copy per embedding process | the same | none |
| Ingest speed | depends on the build: an int8 build can run faster than the bundled FP16 bge, a larger model runs slower | depends on the model and its build | the network and the provider's rate limit |
| Ranking | measured weight | 0.65, not measured | 0.65, not measured |
| Privacy | stays on the machine | stays on the machine | every passage and question leaves it |
| Money | none | none | billed per passage indexed, retries included |
| Can break for good | no | if the repo disappears | if the provider retires the model |

A model with another width also changes storage: 1536 dimensions is 6 KB a vector instead of bge's 1.5 KB, and four times the work per question for the brute-force vector leg.

## Rejected

- **The embedder as a `selected_models` slot.** Those rows are preferences, changed freely through `choose_model()` and the model-slot Settings UI, and cascaded away with their connection. The embedder is a property of the index; putting it there offers exactly the swap that breaks search. It is a model type in the catalog, and nothing more.
- **A separate manifest for embedders.** It would keep `ModelType` purely a slot, at the price of a second refresh script, a second pinning and licence pipeline, and a second install, download and delete path, all duplicating what the local catalog already does. Three guarded places are cheaper than a second catalog.
- **Admitting an unknown model, as the other types do.** Their rule is that the user sees the model answer before trusting it. An embedder never answers where the user can see it, so the sanity check stands in for that look.
- **Trusting the name alone, or the probe alone.** The name terms let chat models through, and a probe succeeds on a chat model served as an embedder.
- **Change freely, repair by re-upload.** [Unsloth Studio](https://github.com/unslothai/unsloth/tree/main/studio) does this: any Hugging Face embedder at any time, identity stamped on each document, one vector table dropped outright on a width change, and *"Re-upload existing ones after changing the model."* After a switch, older documents drop out of meaning search without saying so. It suits a studio where RAG is a side feature; here the library is the product. Taken from it: the identity stamp on each document, a resolve step before saving, and pooling as part of the identity.
- **Locking at the first indexed chunk** rather than at onboarding. It lets Settings change the model while the library is empty, but most users add a source within minutes, so the window is short and the rule is harder to explain. One moment, onboarding, is simpler.
- **Curated local models only.** Safer, since every choice would be measured and none could vanish, but it leaves out users with a hosted embedder they already pay for and multilingual models not yet on the list. The risk is taken knowingly and stated in onboarding.
- **A size or memory cap.** It would need measuring every model on some reference machine, and would still say little about the user's own. The curated list is ours to keep light, and a Hugging Face pick shows its size and says what a larger model costs.
- **Falling back to bge when the locked model is unreachable.** It would keep search answering, with wrong answers.

## When this ships

- A new ADR amending [ADR 0007](../adr/0007-bundled-embeddings.md): the index records its model, the width comes from the row, bge is the default rather than the only model, and remote embedding is no longer a later opt-in.
- [ADR 0015](../adr/0015-openai-compatible-connections.md) says embeddings do not go through connections; the same ADR amends that.
- [search](../architecture/search.md), [documents](../architecture/documents.md), [data model](../architecture/data-model.md) and [egress](../architecture/egress.md) describe the index row, the spec, the lock and the background consent.
- The [local catalog](../architecture/local-models/catalog.md) describes the fourth engine, the `embedding` entry block, and `EMBEDDING` as a type that is not a slot.
- [retrieval](retrieval.md) proposes granite as the bundled replacement for bge. This proposal keeps bge as the default and offers granite as a choice; that proposal's measurements carry over, and its migration section is superseded by [changing](embedding-model-change.md).

## Open questions

- The sanity check's threshold and its fixed strings. Measured, not guessed: run it on known embedders (bge, granite, OpenAI, Cohere) and on chat models served as embedders, and set the bar between them. Whether English strings are enough for a multilingual model.
- What the adapters could not be checked for without a running server: whether LM Studio's `/v1/embeddings` refuses an `llm` model, whether its v1 `key` equals the id its `/v1/models` returns, and Infinity's default URL prefix.
- How many tokens a 480-token bge chunk becomes in each curated model's tokenizer, in Hindi, Japanese and Chinese. Every candidate takes 32,768, so the question is the admission check, not a likely failure.
- Whether granite is ready: [retrieval](retrieval.md) asks for the same-language slices to be hardened first.
- How close a pinned build's vectors must be to the original model's to count as a match.
- Harrier's licence lineage: harrier-270m is a Gemma 3 architecture under an MIT card, so whether Gemma's terms reach it needs checking before it is listed.
- The remote context floor: whether a model whose models.dev `context` is close to `CHUNK_TOKENS`, such as Cohere v3 at 512, is refused, since another tokenizer can count a chunk as more tokens.