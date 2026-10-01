# ADR 0037: Curated embedders are a fourth engine in the local catalog, and embedding is a type, never a slot

- **Status:** Accepted
- **Date:** 2026-10-01
- **Source:** [Choosing the embedding model once](../proposals/embedding-model-choice.md)

## Context

Onboarding offers a short list of embedders to download ([ADR 0036](0036-the-index-records-its-embedder.md)). Chat, image and audio models are already listed, pinned, licence-checked, downloaded and deleted by the local catalog. A second catalog for embedders would repeat all of it. But every model type the catalog knows is also a selection slot ([selection](../architecture/local-models/selection.md)), changed freely, and the embedder must not be: every vector in the library depends on it.

## Decision

- **One manifest.** Curated embedders live in the local manifest, run by a fourth engine, onnxruntime, whose `embedding` block holds what the index's spec needs and no file states, including the ranking weight the retrieval eval measured.
- **`EMBEDDING` is a catalog type and never a slot.** The classifier's embedder group answers it, so the manifest and the engine can describe one. `SLOTS` leaves it out: `selectable_for` never offers it, not even to a model nothing recognises, and the selection routes refuse it. The existing `selected_models` check lists the five slot types, so the database refuses it too.
- **A converted build must match the original.** A build pinned from someone else's conversion records its cosine to the original model's vectors, and the schema refuses one under 0.99 mean or 0.98 minimum. granite-97m's int8 build measured 0.961 and is not listed; its full-precision build is.
- **Rejected: a separate manifest for embedders.** It would keep `ModelType` purely a slot, at the price of a second refresh script, pinning and licence pipeline, and install and delete path.

## Consequences

- An embedder is downloaded under its catalog id, not its weights' file name: every ONNX repo calls its weights `model.onnx`.
- Downloads land in `embeddings/` under the data directory, not the models pack, which a packaged app ships read-only.
- The delete route refuses the embedder the active index names, as it refuses a model the app ships.
