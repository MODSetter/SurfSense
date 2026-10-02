# ADR 0036: The index records which embedder built it, and the embedder is fixed once per install

- **Status:** Accepted
- **Date:** 2026-10-01
- **Amends:** [ADR 0007](0007-bundled-embeddings.md): the width comes from the index's own record rather than a setting, and bge-small is the default rather than the only embedder
- **Source:** [Choosing the embedding model once](../proposals/embedding-model-choice.md)

## Context

[ADR 0007](0007-bundled-embeddings.md) made one model, bge-small-en-v1.5, the embedder for every library, and declared its width in `SURFSENSE_LOCAL_EMBEDDING_DIMENSION`. Startup compared that setting with the width `chunk_vectors` was created at. Nothing recorded which model wrote the vectors, so a different model of the same width would have searched an index built by another one without anyone noticing, and the files were fetched from the repo's `main` branch, so a change upstream would have shipped a different vector space unannounced.

The [proposal](../proposals/embedding-model-choice.md) lets a new install choose its embedder during onboarding. Changing it afterwards means re-embedding the whole library, which is [deferred](../proposals/embedding-model-change.md). Whatever is chosen, the index has to say what it was built with.

## Decision

- **An index is a row.** `embedding_indexes` holds a snapshot of the embedder's spec (repo, pinned revision and file hashes, width, pooling, normalisation, prefixes, `max_tokens`, `semantic_weight`) and names the vec0 table holding its vectors. Search embeds the question with the active row's model and reads its table; ingest and Studio write to it; each document records the index it was embedded into.
- **The choice is fixed when onboarding finishes.** Until then a fresh install has no row, and the routes that queue embedding work answer `409 embedding_not_chosen`. Finishing onboarding with nothing chosen locks bge-small. Locking creates the vector table at the chosen width, and refuses once any chunk exists.
- **An existing library is recorded, not rebuilt.** Migration `0022` writes a bge-small row pointing at the `chunk_vectors` it already has, and stamps its documents. Nothing is re-embedded.
- **bge-small is pinned.** Its revision and the hashes of its weights and tokenizer are part of its spec, and the fetch script refuses a file that does not match.
- **Chunk boundaries do not follow the embedder.** The chunker measures with bge-small's tokenizer, pinned to the chunker, so a future change of embedder would not re-cut documents and move every chunk id that citations point at.
- **Rejected: the embedder as a `selected_models` slot.** Those rows are preferences, changed freely and cascaded away with their connection. The embedder is a property of the index.
- **Rejected: a singleton row.** A second row, `building`, is how changing the model would start; a `CHECK (id = 1)` would make that a schema change.

## Consequences

- `SURFSENSE_LOCAL_EMBEDDING_DIMENSION` is gone. `0001` creates the first table at 384, bge-small's width, and locking rebuilds it at the chosen one.
- A same-width replacement is now detected, because the row names the model, closing the gap ADR 0007 recorded.
- Locking is the one place outside migrations that emits DDL, safe only because it runs on an empty table.
- Workers wait until the API has migrated the database before taking a job. Electron starts them together, and a job queued before an update would otherwise run against the old schema.
- The bundled bge-small file can never change without a re-embed. Its FP16 weights stay, int8 or not ([search](../architecture/search.md), Known gaps).
