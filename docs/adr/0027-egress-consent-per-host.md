# ADR 0027: Egress consent is per host, so model search and downloads share one

- **Status:** Accepted
- **Date:** 2026-09-23
- **Supersedes:** the two-destination decision in [ADR 0014](0014-two-tier-model-catalog.md), and the list of destinations in [ADR 0017](0017-egress-off-by-default.md)
- **Source:** [egress service L11–19](https://github.com/MODSetter/SurfSense/blob/a55d309e84534bbc91656afc7faf494b3d22a39b/surfsense_local/backend/modules/egress/service.py#L11-L19), [egress copy L38–46](https://github.com/MODSetter/SurfSense/blob/a55d309e84534bbc91656afc7faf494b3d22a39b/surfsense_local/frontend/src/features/egress/api.ts#L38-L46), commit [74ae1352f](https://github.com/MODSetter/SurfSense/commit/74ae1352f30cb6488a174843a882995e50bdd281)

## Context

Hugging Face was three named destinations, `model_download`, `model_search` and `image_model_pull`, all on `huggingface.co`. Search and downloads were kept apart on purpose: a download sends the name of a model the user picked, while search sends what they type as they type it, so allowing downloads did not allow search. Each remote connection was already one `host:<hostname>` row. Egress as built is in [egress](../architecture/egress.md).

## Decision

- A destination is `host:<hostname>`, one row per host by construction: the key is the hostname, so a destination cannot exist twice under two names ([`modules/egress/service.py`](../../surfsense_local/backend/modules/egress/service.py)).
- `host:huggingface.co` is built in and covers search, repo reads, GGUF downloads and sd-server weights.
- The dialog asks about the host and names every errand, search first as the widest: search sends typed text as it is typed, a download sends the chosen model's name, both send the IP address, and neither sends chats or documents.
- Model search asks when its box is focused, before any request, rather than after a refusal.

## Consequences

- Allowing downloads allows search, and the reverse. The dialog states both errands before either is allowed.
- Settings › Network shows one Hugging Face row instead of three.

## Where the code stands

- Grants stored as `model_download`, `model_search` or `image_model_pull` are not migrated and nothing reads them, so someone who allowed them is asked again.
