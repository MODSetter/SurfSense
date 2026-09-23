# OpenAI-compatible connections

> **Being redesigned.** The [model catalog proposal](../proposals/model-catalog.md) replaces how a connection lists and classifies its models, and where the form's presets come from; connection storage, keys and the runtime stay. This page describes the code as it is until that work ships.

A connection is one named remote endpoint that speaks the OpenAI API: a hosted provider, an organization's gateway, a vLLM server, or a local server such as Ollama or LM Studio. The user adds as many as they need, each with its own URL and optional key, and assigns a model from any of them to the chat role or the image role. SurfSense configures and selects endpoints; it does not load-balance them, and it never copies an endpoint's model list into the database. The keys are encrypted with a per-install secret that Electron keeps in the OS keychain.

**Code:** [`modules/llm/connections/`](../../surfsense_local/backend/modules/llm/connections/), [`modules/llm/providers/openai_compatible/`](../../surfsense_local/backend/modules/llm/providers/openai_compatible/), [`modules/llm/resolution.py`](../../surfsense_local/backend/modules/llm/resolution.py), [`modules/llm/selection.py`](../../surfsense_local/backend/modules/llm/selection.py), [`shared/secrets.py`](../../surfsense_local/backend/shared/secrets.py), [`electron/src/main/secret.ts`](../../surfsense_local/electron/src/main/secret.ts), [`frontend/src/features/model-selection/`](../../surfsense_local/frontend/src/features/model-selection/)
**Decisions:** [ADR 0015](../adr/0015-openai-compatible-connections.md), [ADR 0017](../adr/0017-egress-off-by-default.md), [ADR 0018](../adr/0018-keychain-envelope-encryption.md)

## Terms

```text
provider             a protocol implementation: llamacpp, sdcpp or openai_compatible
provider connection  one named remote endpoint and its optional bearer key
model                an id the endpoint lists live, or one entered by hand
role                 the one active model for generation or for image_generation
```

A connection is role-neutral: which role it serves depends on the model assigned from it and the routes the endpoint implements. One gateway can hold both roles; chat and image models on separate infrastructure are two connections. "OpenAI-compatible" means compatible for a given route, not that every route exists. Core vLLM serves `/chat/completions` but no image output, while vLLM-Omni serves `/images/generations`, so a typical organization has one connection for each.

```text
OpenAI-compatible connection
  ├── GET  /models                  live discovery and health
  ├── POST /chat/completions        the generation role
  └── POST /images/generations      the image_generation role
      └── POST /images              an alternate image route
```

Out of scope: a standalone OpenRouter provider or its legacy Chat Completions image contract; replica management, load balancing, failover and retries across connections; storing an endpoint's model list, pricing or billing, or syncing any of it in the background; embeddings through a connection; custom headers, mTLS, private CAs and non-OpenAI transports.

## Data model

`provider_connections`:

| Column | Contract |
|---|---|
| `id` | the connection's identity; selections point at it |
| `label` | required, unique case-insensitively |
| `provider` | `openai_compatible`, enforced by a CHECK |
| `base_url` | the exact API root, normally ending in `/v1`, stored without a trailing slash |
| `api_key_ciphertext` | the Fernet-encrypted key, nullable, never returned by any route |
| `created_at`, `updated_at` | |

A base URL must be `http` or `https` with a host, and may not carry credentials, a query or a fragment. Private, loopback and link-local hosts are valid: the API binds to loopback, and reaching internal endpoints is the point. If the API ever binds externally, this becomes an SSRF boundary and has to be redesigned first.

`selected_models` holds one row per role. An `openai_compatible` row names its `connection_id`, and the foreign key cascades, so deleting a connection clears exactly the roles that used it. Two endpoints serving the same model id stay distinct, because a selection's identity includes the connection. The full table is in [`data-model.md`](data-model.md); choosing a model and onboarding are in [`local-models/selection.md`](local-models/selection.md).

## HTTP

| Method | Path | Does |
|---|---|---|
| `GET` | `/llm/connections` | list, by label, with `has_api_key` and never the key |
| `POST` | `/llm/connections` | create; `201` |
| `PUT` | `/llm/connections/{connection_id}` | replace |
| `DELETE` | `/llm/connections/{connection_id}` | delete it and the selections that use it; `204` |
| `GET` | `/llm/connections/{connection_id}/models` | the endpoint's live model list |
| `POST` | `/llm/connections/{connection_id}/chat-test` | one short answer from a chosen model |
| `POST` | `/llm/connections/{connection_id}/image-test` | one image from a chosen model |

The write body:

```json
{
  "label": "Engineering vLLM",
  "provider": "openai_compatible",
  "base_url": "https://qwen.internal/v1",
  "api_key": null,
  "allow_unverified": false
}
```

- On update, an omitted `api_key` keeps the stored key, a value replaces it, and `null` clears it. On create, omitted and `null` both mean no key. A key that is given must not be empty.
- Create and update check a candidate before touching stored state: normalise the URL, require egress to its host, call `GET {base_url}/models` with the candidate key, and require an OpenAI list envelope in reply. A failed update leaves the working connection and its key as they were.
- A probe that fails for any reason gets `422` with code `unverified_connection`, and nothing is saved. For an endpoint without useful model discovery the form offers "Save anyway", which repeats the write with `allow_unverified: true`; a model id then has to be entered by hand. A failed probe never becomes a silent unverified save.
- A duplicate label is a `409`. Health failures never delete a connection.
- Every route that reaches the endpoint checks egress for its host first; a loopback host is not egress ([`egress.md`](egress.md)).

## Live models

`GET .../models` calls `{base_url}/models` and, in parallel, `{base_url}/models?output_modalities=image`. A valid answer to the second is merged in and any failure of it is ignored: OpenRouter's default listing leaves out most of its image models, and an endpoint that ignores the parameter returns the same set, so no provider has to be recognised. Ids are deduplicated within the connection and sorted. A failed baseline call is a `502`, and the connection stays.

Each model's capability comes from the first of three sources that knows it, and nothing is guessed:

1. `declared`: output modalities the endpoint publishes, text meaning `completion` and image meaning `image_generation`.
2. `catalog`: [`model-capabilities.json`](../../surfsense_local/backend/modules/llm/connections/model-capabilities.json), a reviewed snapshot built offline from models.dev by `scripts/fetch_model_capabilities.py` and committed, looked up by the full id and then by its last path segment. A row with no capabilities is a known "neither role".
3. `unknown`: neither source knows the id.

A known mismatch disables a role; `unknown` leaves both open. Choosing a model applies the same rule: a remote choice is refused only when its capability is known and lacks the role. A model the listing does not contain, or a connection whose listing fails, needs the choice repeated with `allow_unlisted: true`. The remote model list is fetched every time and never stored.

## Runtime

Chat goes through `OpenAICompatibleChatProvider(base_url, api_key)`:

- health and model listing through `GET /models`;
- a streaming `POST /chat/completions`, with an `Authorization: Bearer` header when there is a key and no provider-specific headers or fields;
- 300 seconds to the first token, since a cold model may still be loading, then 30 seconds between tokens. Model listings wait at most 120 seconds and connection discovery 10;
- no context window and no token count, so chat falls back to its fixed history budget ([`chat.md`](chat.md)).

Images go through `OpenAICompatibleImageProvider`:

1. Use the connection's last successful route from an in-process cache, else `POST {base_url}/images/generations`.
2. Only on `404 Not Found` or `405 Method Not Allowed`, retry once on the other route.
3. Cache the route that worked until the process restarts.

- There is no fallback or retry after any other failure: auth, rate limit, timeout, `5xx`, a connection error or a malformed success. The endpoint may already have generated, and billed, an image. These surface as `NonRetryableImageError`, which a Studio job does not retry either. Route negotiation is not a retry policy.
- Both routes send `model` and `prompt`. The first entry of the reply's `data` may be `b64_json`, a base64 data URL, or an `http(s)` URL, which is downloaded without the endpoint's bearer token and with at most three redirects. Replies are capped at 28 MB and images at 20 MB, under a 180-second timeout, and the bytes must be PNG, JPEG, GIF, WebP or SVG and match any MIME type the endpoint claims.

[`resolution.py`](../../surfsense_local/backend/modules/llm/resolution.py) turns a role's selection into a provider for chat, titles and Studio; the connection routes build their own for discovery and tests:

```text
generation        llamacpp                   → the supervised llama-server
                  openai_compatible + id     → load the connection → chat provider
image_generation  sdcpp                      → the image provider at sd-server's loopback URL
                  openai_compatible + id     → load the connection → image provider
```

Loading a connection runs the egress check for its host. The bundled sd-server speaks `/images/generations`, so it is a new selection target rather than a new protocol; being loopback, it needs no key and takes no egress decision. Chat, thread titles and every step where Studio's generation model writes use the generation resolver; `image` and `infographic` also use the image resolver ([`studio.md`](studio.md)).

## Trying a model before assigning it

- `chat-test` streams one answer from the chosen model, by default to a prompt asking for one short sentence, capped at 1,024 tokens and 600 characters, so a model whose capability is `unknown` can be seen answering before it becomes the chat model. An empty reply is a `502`, which is what a reasoning model returns when it spends the whole budget thinking.
- `image-test` generates one image, by default a blue circle on white, through the real image client and returns the bytes with `Cache-Control: no-store`. It creates no artifact.
- Selecting a model never runs inference. The connection card offers a test before the model is used, and "Use without testing" for a trusted internal endpoint, whose first real request then reports any error normally. Image tests run only on an explicit action, because they are real inference and may cost money.

## Where keys live

Keys are protected by envelope encryption ([ADR 0018](../adr/0018-keychain-envelope-encryption.md)):

- Electron keeps one per-install secret: 32 random bytes, hex-encoded, encrypted with Electron's `safeStorage` (the OS keychain) into `secret.bin` in its userData folder, `<data dir>/electron/`. If that file is missing or cannot be decrypted, after a reinstall or a keychain reset, Electron mints a new secret rather than refusing to start.
- On Linux without a keyring, `safeStorage` falls back to plain-text encryption so the app still boots.
- Electron passes the secret as `SURFSENSE_LOCAL_SECRET` to the API and both workers, and to no other sidecar. The sidecars make the calls, so they need the keys, which is why the secret cannot stay inside Electron.
- [`shared/secrets.py`](../../surfsense_local/backend/shared/secrets.py) derives a Fernet key from the SHA-256 of the secret and encrypts each connection's key into `provider_connections.api_key_ciphertext`. Revision `0007` dropped the plaintext column. `ProviderConnection.api_key` encrypts on write and decrypts on read.
- A bare `uv run` with no secret in its environment creates `<data dir>/secret`, 32 random bytes hex-encoded with mode `0600`, and logs a warning. The secret then sits next to the database it protects.
- Ciphertext this install's secret cannot open, after a new secret was minted or a backup was restored on another machine, raises `UnreadableSecretError`. The API answers any route that hits it with `409` and code `unreadable_secret`: the request is valid, the server is healthy, and the stored key is what has to be entered again.
- A key is never logged or returned.

## Frontend

- The model settings list connection cards. Each card loads its own models, so a slow or failed endpoint does not hold up the others, and a model can be assigned to chat or to image after an optional test.
- The connection form suggests base URLs for OpenAI, OpenRouter, Together AI, Groq, DeepSeek, Mistral, Fireworks, xAI, Cerebras and Google Gemini, and for local Ollama, LM Studio and vLLM servers.

## Known gaps

- `ProviderConnection.api_key` still catches `InvalidToken` to treat a rotated secret as "no key", but `decrypt()` now raises `UnreadableSecretError`, so the catch never fires and `tests/unit/shared/test_secrets.py::test_rotated_secret_reads_as_no_key` fails.
- An image returned as a URL is downloaded from whatever host the endpoint names, with no egress decision for that host; the endpoint's key is withheld from the download.
