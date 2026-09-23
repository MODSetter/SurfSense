# ADR 0026: Curated models are ordered by their position in the manifest, with no score

- **Status:** Accepted
- **Date:** 2026-09-23
- **Supersedes:** the `rank` decision in [ADR 0014](0014-two-tier-model-catalog.md), and the llmfit authoring decision in [ADR 0011](0011-llama-cpp-local-runtime.md)
- **Source:** [llama.cpp runtime plan L61–62](https://github.com/MODSetter/SurfSense/blob/a55d309e84534bbc91656afc7faf494b3d22a39b/plans/community-local/api/07-llamacpp-runtime.md#L61-L62), [llama.cpp runtime plan L1179–1195](https://github.com/MODSetter/SurfSense/blob/a55d309e84534bbc91656afc7faf494b3d22a39b/plans/community-local/api/07-llamacpp-runtime.md#L1179-L1195), commits [5a81b335b](https://github.com/MODSetter/SurfSense/commit/5a81b335b9bc448239bee4f93823c65520801630) and [bdc8e749d](https://github.com/MODSetter/SurfSense/commit/bdc8e749db03805ca2499e9c87ea15e362be989b)

## Context

Each curated build carried `rank`, an integer inside its variant, and `rank_basis`, naming what produced it, and the manifest refused two bases. The ranks were typed into the refresh script by hand while the basis credited llmfit. A number beside each build implied a measurement nobody had made, and it was a second representation of an order the list already had. The catalog as built is in [catalog](../architecture/local-models/catalog.md).

## Decision

- There is no score. A model's position in `ENTRIES` in [`scripts/refresh_curated_models.py`](../../surfsense_local/backend/scripts/refresh_curated_models.py), and so in the manifest's `models` list, is the only preference signal: smallest first, most preferred last.
- Curated rows sort by fit state, then position with later entries first. `recommend()` returns the recommendable build furthest down the list, a tie going to the smaller file.
- Neither the position nor any score is sent to the renderer.
- `Variant` has no `rank` or `rank_basis`. Authoring involves no llmfit: a person edits `ENTRIES`, and the script reads everything else from the GGUF header and the Hugging Face listing.

## Consequences

- Moving a model up or down the ladder is a one-line reorder that shows in review, with no second field to keep in step with it.
- The order still means good at this app's job, answering from the user's documents with citations that resolve, and a person sets it. Nothing measures it.
- The code is [`catalog/rows.py`](../../surfsense_local/backend/modules/llm/catalog/rows.py) and [`catalog/recommendation.py`](../../surfsense_local/backend/modules/llm/catalog/recommendation.py).
