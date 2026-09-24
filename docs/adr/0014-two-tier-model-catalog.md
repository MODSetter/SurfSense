# ADR 0014: The model catalog is a curated offline manifest plus Hugging Face search, and SurfSense downloads the files itself

- **Status:** Accepted; the `rank` decision is superseded by [ADR 0026](0026-curated-order-is-list-position.md), the two egress destinations by [ADR 0027](0027-egress-consent-per-host.md), and the manifest, the denylist and header reads on opening a search result by the [model catalog proposal](../proposals/model-catalog.md), in progress
- **Date:** 2026-09-19
- **Source:** [llama.cpp runtime plan L50–51](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/07-llamacpp-runtime.md#L50-L51), [llama.cpp runtime plan L59–65](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/07-llamacpp-runtime.md#L59-L65)

## Context

llama.cpp can run any GGUF, but the app has to work airgapped, a model file is gigabytes, and search reaches arbitrary repositories. `llama-server` is a second process that the API does not proxy. The renderer must not be able to name an arbitrary download. The catalog as built is in [catalog](../architecture/local-models/catalog.md) and [selection](../architecture/local-models/selection.md).

## Decision

- Two tiers. The curated manifest (now [`catalog/local/manifest/models.json`](../../surfsense_local/backend/modules/llm/catalog/local/manifest/models.json)) is the offline product and ships frozen. Hugging Face search is a network feature, and it is absent, not degraded, when egress is off.
- Every installable build in either tier carries a fit badge: exact from the committed shape for a curated entry, exact from the file's header for an opened search result, approximate from file size when a header cannot be read.
- `rank` exists only on curated entries, inside the variant, and never on the wire. It is a preference order over models tested for this app's job and is only ever a sort key; a searched model never carries one. The recommendation is the highest `rank` among builds whose speed tier is recommendable.
- SurfSense fetches the GGUF itself rather than through `llama-server`'s `POST /models`. An in-process fetch is the only place `egress.require()` can hold, and it buys resume, checksums and the header as the file lands ([`providers/llamacpp/download.py`](../../surfsense_local/backend/modules/llm/providers/llamacpp/download.py)).
- Install ids are opaque and minted by the server, for both tiers. The renderer sends a `catalog_id`, and whether to select the model, never a repo or file name (now [`catalog/local/search/tickets.py`](../../surfsense_local/backend/modules/llm/catalog/local/install/tickets.py)).
- One denylist, keyed by both the GGUF architecture and the repo's pipeline tag, refuses what cannot hold a conversation (now the classifier in [`catalog/local/classifier.py`](../../surfsense_local/backend/modules/llm/catalog/local/classifier.py), which answers a type rather than a refusal) (recorded 22 Sep 2026, replacing a generated allowlist).
- Headers are parsed by llama.cpp's own `gguf` package, pinned at `0.19.0`, because search parses bytes from arbitrary repositories and upstream's parser is the one that receives hardening (recorded 21 Sep 2026, replacing a hand-written header reader).
- Two egress destinations on one host, `model_download` and `model_search`, both `huggingface.co`. A user who allowed downloads allowed fetching a file they named; search sends text they are typing ([ADR 0017](0017-egress-off-by-default.md)).

## Consequences

- With egress off, the curated list and the installed models still work.
- The denylist ages the right way, since an unknown architecture is usually a chat model released last week, but it lets a few models install and then fail: 18 of 979 across the 1000 most downloaded GGUF repos, all of them recent architectures. That is accepted because curated is the default path, search is opt-in, and `MODEL_CANNOT_RUN` says the model will not run.
- A search result's install id lives for five minutes, so a stale screen cannot install something the user is no longer looking at.
- The catalog code is in [`modules/llm/catalog/`](../../surfsense_local/backend/modules/llm/catalog/).

## Where the code stands

- Adding a `.gguf` from disk has no screen. A file copied into the models directory by hand is picked up at the next start ([catalog](../architecture/local-models/catalog.md)).
