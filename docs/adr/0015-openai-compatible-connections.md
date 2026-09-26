# ADR 0015: Remote models come through named OpenAI-compatible connections, discovered live

- **Status:** Accepted; the per-role selection is revised by the [model catalog proposal](../proposals/model-catalog.md), in progress: a selection is keyed by model type, with no roles
- **Date:** 2026-09-10
- **Source:** [Connections plan L8–68](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/05b-openai-compatible-connections.md#L8-L68), [Connections plan L70–128](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/05b-openai-compatible-connections.md#L70-L128), [Connections plan L160–170](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/05b-openai-compatible-connections.md#L160-L170), [Connections plan L360–362](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/05b-openai-compatible-connections.md#L360-L362)

## Context

The app had a single OpenRouter key. Organizations expose either one gateway serving many models, or separate endpoints: core vLLM for chat, vLLM-Omni for images, and other image services. "OpenAI-compatible" describes a particular endpoint; it does not promise that every route exists. Connections as built are in [connections](../architecture/connections.md).

## Decision

- A connection is one named endpoint: a label unique regardless of case, an exact base URL (normally ending in `/v1`), and an optional bearer key. The same provider, `openai_compatible`, may have many connections. Only `http` and `https` URLs are accepted, with no credentials, query or fragment. Private, loopback and link-local hosts are valid, because reaching internal networks is the feature.
- Models are discovered live from `GET {base_url}/models` and never stored. There is no `connection_models` table.
- One model is selected per role, `generation` or `image_generation`. A remote selection stores its `connection_id`, so a model's identity is `(connection_id, name)` and the same model id on two endpoints stays two models.
- Chat uses `POST /chat/completions`. Images use `POST /images/generations` and fall back once to `POST /images`, only on a definitive `404` or `405`. There is no fallback after an auth, rate-limit, timeout, `5xx` or other ambiguous failure, because the endpoint may already have generated and billed an image.
- SurfSense selects endpoints. It does not load-balance, fail over or retry across replicas; replicas of one model belong behind the organization's gateway.

## Consequences

- Deleting a connection removes only the role selections that use it, through `ON DELETE CASCADE` on `selected_models.connection_id` ([`modules/llm/models.py`](../../surfsense_local/backend/modules/llm/models.py)).
- The app keeps no copy of a remote catalogue to synchronize, and a slow or failed endpoint does not block local models or other connections.
- Each connection's host is its own egress destination unless it is loopback ([ADR 0017](0017-egress-off-by-default.md)), and its key is stored encrypted ([ADR 0018](0018-keychain-envelope-encryption.md)).
- Embeddings do not go through connections ([ADR 0007](0007-bundled-embeddings.md)).
- The routes are in [`connections/`](../../surfsense_local/backend/modules/llm/connections/) and the adapters in [`providers/openai_compatible/`](../../surfsense_local/backend/modules/llm/providers/openai_compatible/).
