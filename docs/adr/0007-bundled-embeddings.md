# ADR 0007: Embeddings come from a bundled bge-small model run in process on the CPU

- **Status:** Accepted
- **Date:** 2026-09-04
- **Source:** [Umbrella plan L106](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00-umbrella-plan.md#L106), [Data model L220–224](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00c-data-model.md#L220-L224)

## Context

Ingest and search both need embeddings, and the app has to produce them with no network and no model server for the user to install or keep running. The vector index's width is part of the schema: a `vec0` table stays at the width it was created with. Ingest as built is in [documents](../architecture/documents.md).

## Decision

- The embedder is bge-small-en-v1.5, int8 ONNX, 384 dimensions, about 66 MB. It is bundled with the app and runs in process on onnxruntime's CPU provider ([`worker/ingestion/embedding.py`](../../surfsense_local/backend/worker/ingestion/embedding.py)). Ingest and the query side use the same model.
- `SURFSENSE_LOCAL_EMBEDDING_DIMENSION` declares the width, 384 by default. Vectors from another model are not the wrong shape but unrelated numbers, so startup compares the width `chunk_vectors` was created with against the setting and refuses to open a database that no longer matches (`_check_embedding_width()` in [`shared/migrations.py`](../../surfsense_local/backend/shared/migrations.py)).
- Remote embedding is a later opt-in, not a launch dependency.

## Consequences

- Ingest and search need no network, no GPU and no model server.
- The model ships in the installer's `models/` resources, beside the voice and parser packs ([`electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml)).
- Changing the embedding model means reindexing. There is no migration between two embedding spaces. The API refuses to start, and says to reindex, when the index's vector width differs from the configured model's; a replacement model with the same width is not detected.
- OpenAI-compatible connections do not carry embeddings ([ADR 0015](0015-openai-compatible-connections.md)).
