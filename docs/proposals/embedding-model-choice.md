---
status: proposed
code:
  - surfsense_local/backend/modules/embedding/
  - surfsense_local/backend/worker/ingestion/
  - surfsense_local/backend/shared/search.py
  - surfsense_local/backend/shared/migrations.py
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/frontend/src/features/onboarding/
  - surfsense_local/frontend/src/features/settings/
---

# Choosing the embedding model once

> The user picks the embedding model during onboarding, from bge-small or a short curated list, and the choice is fixed for the install. Changing it later means re-embedding the library, which is [future work](embedding-model-change.md). This proposal builds the data shape that work needs, so it adds code without changing a schema.

Today one model, bge-small-en-v1.5, is hard-coded in [`embedding.py`](../../surfsense_local/backend/worker/ingestion/embedding.py) ([ADR 0007](../adr/0007-bundled-embeddings.md)). It is English-only, so a question in one language does not find its answer in another ([search](../architecture/search.md), Known gaps). A multilingual model fixes that for the users who need it, and costs everyone else disk, memory and speed for nothing. So it is a choice, not a swap.

## Decisions

- **bge-small stays bundled, the default, and never deletable**, like the audio model audio.cpp ships ([`bundled.py`](../../surfsense_local/backend/modules/llm/catalog/local/engines/audiocpp/bundled.py)). It ships even to a user who picked another model, because it is the pick when anything else fails, and the way back once changing is possible.
- **An optional onboarding step** offers the curated list. Skipping it, being offline, refusing the download or a failed download all mean bge.
- **Finishing onboarding locks the choice** for the whole app, every workspace. Settings shows the model and does not offer to change it.
- **Local models only.** No remote embedder and no open Hugging Face search until [changing](embedding-model-change.md) exists, because until then a bad pick or a dead provider cannot be undone.
- **No fallback, ever.** If the locked model's files go missing, the same revision is downloaded again. Answering with bge would compare bge questions against another model's vectors, which returns nonsense rather than an error.

## The curated list

A manifest in `modules/embedding/`, one entry per model, each an `EmbedderSpec`:

| Field | Why the index depends on it |
|---|---|
| `id`, `repo`, `revision`, file hashes | what to download, pinned, so a re-download is the same model |
| `dimension` | the vector table's width |
| `pooling`, `normalize` | the same model pooled another way is another space |
| `query_prefix`, `document_prefix` | asymmetric models embed questions and passages differently |
| `max_tokens` | a chunk past it is truncated without error |
| `semantic_weight` | the blend is a plateau measured per model: 0.65 for bge, 0.85 for granite ([retrieval](retrieval.md)) |
| `runtime` | `onnx` now; room for GGUF or remote later |
| `bundled`, `size_bytes` | the default, and what onboarding shows |

An entry is admitted only if:

- it ships an ONNX file, is ungated and permissively licensed;
- the [retrieval eval](../../surfsense_local/backend/scripts/run_retrieval_eval.py) measured its `semantic_weight`;
- every chunk of the eval corpus, cut at `CHUNK_TOKENS`, fits its `max_tokens` in its own tokenizer, in every language (see *Chunking* below);
- it is small enough to load once per embedding process: the API for questions, the ingest worker, and the Studio worker ([`persist.py`](../../surfsense_local/backend/worker/studio/shared/persist.py)).

The first candidate is `ibm-granite/granite-embedding-97m-multilingual-r2`, with the risks [retrieval](retrieval.md) lists still open. If it is not ready, the list ships with bge alone and the onboarding step hides itself when there is nothing to choose; everything below still ships, because it is what [changing](embedding-model-change.md) builds on.

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

[`chunking.py`](../../surfsense_local/backend/worker/ingestion/chunking.py) measures chunks with the embedder's tokenizer. If the embedder decides the boundaries, changing it re-cuts every document, chunk ids change, and every citation in every old chat breaks. The chunker gets its own pinned tokenizer, bge's file under its own name, which changes nothing today. The admission rule above keeps every model's `max_tokens` above what that tokenizer cuts.

### One write path, one read path

- **Encode:** `embed(texts, purpose)`, where purpose is `QUERY` or `DOCUMENT`, built from a spec: pooling, normalisation, prefix. Files live in `models/<id>@<revision>/`, so two models can sit on disk at once.
- **Write:** `embed_chunks(index, chunk_ids)` embeds in batches and writes to that index's table. `write_vectors()` in [`indexing.py`](../../surfsense_local/backend/worker/ingestion/indexing.py) calls it for every index that is not retired: a list of one today, both indexes during a re-embed, with no change to ingest, Studio or import.
- **Read:** [`search.py`](../../surfsense_local/backend/shared/search.py) takes the encoder, the vector table and `SEMANTIC_WEIGHT` from `active_index()`. A question is always embedded by the index it is searched against.

`chunks.embedding` gains no new readers. One column cannot hold two models' vectors; each index's table is the store.

### Nothing embeds before the lock

The onboarding gate is in the UI ([`app-bootstrap.tsx`](../../surfsense_local/frontend/src/app/app-bootstrap.tsx)); the upload routes are not behind it, and the API is a product surface. Ingest refuses with `409 embedding_not_chosen` while no active index exists. The UI never sees it.

### Deleting a model

| Model | Deletable |
|---|---|
| bge (bundled) | never |
| the active index's model | not while it is active |
| downloaded but never locked | yes |

Checked against the active row, not a flag on the file, so a model retired by a re-embed becomes deletable with no change here.

### Missing files

The active model's folder can be deleted by hand or corrupted. Its revision is downloaded again, which needs the network and the Hugging Face destination allowed ([ADR 0027](../adr/0027-egress-consent-per-host.md)). Until then chat answers `503` ([`chat/router.py`](../../surfsense_local/backend/modules/chat/router.py) reads the active spec, not bge's file list) and ingest fails with Retry. bge is bundled and cannot hit this.

## Onboarding

1. A new step before the chat model. It is not a model slot: [`slot.ts`](../../surfsense_local/frontend/src/features/onboarding/model-step/slot.ts) is typed to `ModelType`, and the embedder is not a selection. The step list needs a kind of step that is not one.
2. The list shows each entry's size and one line on what it is for: *"Choose Multilingual only if your documents or questions are in more than one language."* bge is preselected.
3. Picking a model that is not on disk resolves it (size, whether it is on disk, any error), then downloads with the hash check. The click is a user action, so the egress dialog may appear once.
4. Finishing onboarding writes the `embedding_indexes` row and creates the vector table. Nothing chosen, or a download not finished, writes bge.

Settings gets an *Embedding model* section in [`settings-dialog.tsx`](../../surfsense_local/frontend/src/features/settings/settings-dialog.tsx), read from `GET /embedding/index`, which returns `{active, building: null}`. It shows the model and says changing it is coming. `building` is always null now; it carries progress once [changing](embedding-model-change.md) ships, with no contract change.

## Existing installs

Onboarding is already complete, so they never see the step. A migration writes a bge row pointing at their existing `chunk_vectors` and stamps every document with it. No vector moves.

## What choosing another model costs the user

For granite, against bge:

- about 118 MB downloaded (94 MB model, 24 MB tokenizer), on top of bge's 63 MB, which stays;
- a copy in memory for each embedding process;
- slower ingest: bge is measured at about 8 minutes per 1,000 passages on a mid CPU, granite has 3× the parameters and is not yet measured;
- repairs need the network, and the pinned revision must still exist on Hugging Face;
- same-language ranking can move down while cross-language improves ([retrieval](retrieval.md), Risks);
- no way back until [changing](embedding-model-change.md) ships, short of clearing the app's data.

A model with another width also changes storage: 768 dimensions is 3 KB a vector instead of 1.5 KB, and twice the work per question for the brute-force vector leg.

## Rejected

- **The embedder as a `selected_models` slot.** Those rows are preferences, changed freely through `choose_model()` and the model-slot Settings UI. The embedder is a property of the index; putting it there offers exactly the swap that breaks search.
- **Change freely, repair by re-upload.** [Unsloth Studio](https://github.com/unslothai/unsloth/tree/main/studio) does this: any Hugging Face embedder at any time, identity stamped on each document, one vector table dropped outright on a width change, and *"Re-upload existing ones after changing the model."* After a switch, older documents drop out of meaning search without saying so. It suits a studio where RAG is a side feature; here the library is the product. Taken from it: the identity stamp on each document, a resolve step before saving, and pooling as part of the identity.
- **Locking at the first indexed chunk** rather than at onboarding. It lets Settings change the model while the library is empty, but most users add a source within minutes, so the window is short and the rule is harder to explain. One moment, onboarding, is simpler.
- **Remote embedders now.** Every passage and every question would leave the machine, ingest runs in the background where no consent can be asked, and a revoked key or a retired model would end search for good with no re-embed to recover. They come with [changing](embedding-model-change.md).
- **Open Hugging Face search now.** An arbitrary model arrives with no measured weight, unknown prefixes and an unchecked token limit, and the pick would be permanent.

## When this ships

- A new ADR amending [ADR 0007](../adr/0007-bundled-embeddings.md): the index records its model, the width comes from the row, and bge is the default rather than the only model.
- [search](../architecture/search.md), [documents](../architecture/documents.md) and [data model](../architecture/data-model.md) describe the index row, the spec and the lock.
- [retrieval](retrieval.md) proposes granite as the bundled replacement for bge. This proposal keeps bge as the default and offers granite as a choice; that proposal's measurements carry over, and its migration section is superseded by [changing](embedding-model-change.md).

## Open questions

- Granite's `max_tokens`, and how many of its tokens a 480-token bge chunk becomes in Hindi, Japanese and Chinese.
- Whether granite is ready: [retrieval](retrieval.md) asks for the same-language slices to be hardened first.
- The size cap for an entry, given three processes each load it.
