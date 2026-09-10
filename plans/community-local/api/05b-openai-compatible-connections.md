# API — Phase 5: OpenAI-compatible model connections

> Owns: `backend/modules/llm/connections/`, the remote-provider adapters,
> connection migrations, and the normalized remote-model API. Frontend:
> [`../frontend/05-install-ux.md`](../frontend/05-install-ux.md). Studio:
> [`04-studio.md`](04-studio.md), [`../worker/04-studio.md`](../worker/04-studio.md).

## Goal

Replace the single OpenRouter key with multiple named OpenAI-compatible
connections. An organization may expose one gateway containing many models or
separate endpoints for different vLLM deployments and image services. SurfSense
configures and selects those endpoints; it does not become their load balancer.

The durable state stays minimal:

- connection metadata and one secret per endpoint;
- one selected model per role;
- no persisted copy of remote `/models` responses.

## Non-goals

- OpenRouter compatibility, aliases, model-id migration, or catalogue metadata.
- Replica management, load balancing, failover, retries across connections, or
  routing policy. Replicas of one model belong behind the organization's
  gateway or load balancer.
- Persisted remote model catalogues, capability registries, pricing, billing,
  or background model synchronization.
- Embeddings through these connections.
- Custom headers, mTLS, private CA import, or non-OpenAI transports in this
  phase.

## Terms and boundaries

```text
provider             protocol implementation, e.g. ollama or openai_compatible
provider connection  one named remote endpoint and its optional bearer secret
model                 an id returned live by that endpoint, or entered manually
role                  the one active model for generation or image_generation
```

One connection can serve both roles when its gateway implements both APIs.
Different roles can point to different connections when chat and image
inference run on separate infrastructure.

```text
OpenAI-compatible connection
  ├── GET  /models                    live discovery and health
  ├── POST /chat/completions          generation role
  └── POST /images/generations        image_generation role, when implemented
```

Stock vLLM implements the chat branch, not image generation. “OpenAI-compatible”
means compatibility with a particular endpoint; it does not imply that every
route above exists.

## Data model

### `provider_connections`

| Column | Contract |
|---|---|
| `id` | INTEGER primary key; connection identity used by selections |
| `label` | TEXT, required; user-facing name unique case-insensitively |
| `provider` | TEXT, required; `openai_compatible` in this phase |
| `base_url` | TEXT, required; exact API root, normally ending in `/v1` |
| `api_key` | TEXT nullable until the Phase 6 keychain move; never returned by an API |
| `created_at`, `updated_at` | timestamps |

The URL is stored without a trailing slash. Accept only `http` and `https`;
reject credentials, query strings, and fragments. Private, loopback, and
link-local destinations are valid because the desktop API is loopback-only and
internal-network access is the feature. If the API ever binds externally, this
becomes an SSRF boundary and must be redesigned before that release.

The Phase 6 keychain work moves `api_key` behind a `ConnectionSecretStore`
without changing connection ids or HTTP DTOs. Until then, preserve the current
local-only plaintext limitation and never log or return a key.

### `selected_models`

Keep one table and one row per role:

| Column | Contract |
|---|---|
| `role` | primary key: `generation` or `image_generation` |
| `provider` | `ollama` or `openai_compatible` |
| `connection_id` | nullable FK to `provider_connections.id`, `ON DELETE CASCADE` |
| `name` | exact provider model id |
| `updated_at` | timestamp |

Invariants:

- `ollama` selections have `connection_id = NULL`;
- `openai_compatible` selections require a connection id;
- deleting a connection removes every role selection that uses it;
- onboarding requires only `generation`;
- clearing a later selection never clears onboarding completion.

Do not add a `connection_models` table. The application needs current endpoint
inventory and durable user choices, not a synchronized remote catalogue.

## Provider runtime

Keep the existing `Generator` protocol for chat. Replace
`OpenRouterProvider` with:

```python
OpenAICompatibleChatProvider(base_url, api_key)
```

It implements:

- `health()` and `models()` through `GET {base_url}/models`;
- `chat()` through streaming `POST {base_url}/chat/completions`;
- optional `Authorization: Bearer <api_key>`;
- the existing bounded connect/read timeouts and OpenAI SSE delta parser.

It must not send OpenRouter-only headers or request fields (`X-Title`,
`reasoning: {"enabled": ...}`), and it must not require
`architecture.output_modalities`.

Image generation is a separate runtime capability sharing the same connection
record:

```python
class ImageGenerator(Protocol):
    async def generate(self, model: str, prompt: str) -> GeneratedImage: ...

OpenAICompatibleImageProvider(base_url, api_key)
```

The image adapter calls `POST {base_url}/images/generations` and normalizes
`data[0].b64_json` or `data[0].url` into bytes plus MIME type. It enforces
response-size, download-size, MIME, scheme, and timeout limits before the
existing artifact storage writes the file. It never calls the old OpenRouter
Chat Completions image extension.

Centralize selection resolution:

```text
resolve generation selection
  ├── ollama + no connection_id → supervised Ollama provider
  └── openai_compatible + connection_id → load connection → chat provider

resolve image_generation selection
  └── openai_compatible + connection_id → load connection → image provider
```

Chat, title generation, and text Studio builders use the generation resolver.
The image Studio format uses the image resolver. No caller reads secrets or
constructs providers itself.

## HTTP contract

### Connections

```text
GET    /llm/connections
POST   /llm/connections
PUT    /llm/connections/{connection_id}
DELETE /llm/connections/{connection_id}
GET    /llm/connections/{connection_id}/models
```

Write body:

```json
{
  "label": "Engineering vLLM",
  "provider": "openai_compatible",
  "base_url": "https://qwen.internal/v1",
  "api_key": null
}
```

Read bodies expose `has_api_key`, never `api_key`.

Create and update validate a candidate before replacing durable state:

1. normalize and validate the URL;
2. call its `/models` endpoint with the candidate key;
3. when successful, require a valid OpenAI list envelope;
4. persist the verified candidate.

A failed update leaves the prior working connection and secret unchanged.
For endpoints that do not implement useful model discovery, return an
`unverified_connection` response and let the user explicitly choose **Save
anyway**. That second write sets `allow_unverified: true`, persists the
candidate, and requires manual model-id entry. Never turn an ordinary failed
probe into an implicit unverified save. Connection health failures never delete
configuration.

Deleting a connection and its selected-role rows is one transaction.

### Live models

`GET /llm/connections/{id}/models` calls the remote `/models` endpoint and
returns:

```json
[
  {
    "connection_id": 1,
    "connection_label": "Engineering vLLM",
    "name": "qwen3-32b",
    "capabilities": [],
    "capability_known": false
  }
]
```

Capability detection is progressive:

1. honor explicit recognized metadata returned by the endpoint;
2. recognize OpenAI-compatible extensions already supported by SurfSense;
3. otherwise return unknown rather than guessing.

The standard `/models` shape does not reliably identify chat, vision-input,
embedding, or image-generation support. Unknown models remain visible.

If discovery fails after a connection was saved, return a bounded provider
error and retain the connection. A manual model-id field may be used for an
image endpoint whose catalogue omits its image model; the selected role still
stores only that exact id.

### Selections

Keep:

```text
GET /llm/selection/{role}
PUT /llm/selection/{role}
```

Remote write body:

```json
{
  "provider": "openai_compatible",
  "connection_id": 1,
  "name": "qwen3-32b"
}
```

The API confirms that the connection exists and the live catalogue contains the
model when discovery is available. A manual id is accepted only for an
explicitly saved unverified connection or after discovery omitted that id.

Selection never runs inference implicitly. Image testing always requires an
explicit user action because it performs real inference and may cost money.
“Use without testing” is allowed for trusted internal deployments; the first
real chat or Studio request then reports the provider error normally.

## Frontend contract

The shared onboarding/settings model surface has two top-level choices:

```text
Local | OpenAI-compatible
```

The OpenAI-compatible tab contains multiple connection cards. Adding a
connection asks for label, base URL, and optional key. Saving one does not
silently change the active generation model.

Each card loads its models independently and progressively. A slow or failed
connection does not block local models or other connections. Model identity in
the renderer is `(connection_id, name)`, never `(provider, name)`.

Each model row shows detected capability labels when known and explicit role
actions:

```text
qwen3-32b       Chat detected       [Use for chat] [Assign as image]
company-model   Capability unknown  [Use for chat] [Assign as image]
```

The Image filter includes positively identified image models and the current
image selection. It must not hide unknown models or claim they are
incompatible. Assigning an unknown model as Image explains that the endpoint
must implement `/images/generations` and offers `Test image`,
`Use without testing`, and Cancel.

Onboarding requires one generation selection. Image setup is optional and stays
in the same OpenAI-compatible tab; there is no separate image-provider section.

## Studio contract

`image` remains an artifact format. It is available only when
`SelectedModel(IMAGE_GENERATION)` resolves to a configured connection.

```text
Artifact(format=image)
  → image_generation selection
  → connection URL + secret
  → POST /images/generations
  → normalized image bytes
  → existing ArtifactFile(primary)
```

`infographic` is not routed to an image model. The selected generation model
emits a strict infographic schema; a trusted deterministic builder renders
SVG/HTML and an optional PNG preview. This keeps labels and numbers accurate,
works with vLLM, and follows the existing “structured content → trusted
builder” Studio rule.

If no image model is selected, only the Image format is unavailable.
Infographic remains available whenever generation is available.

## Migration from OpenRouter

Hand-written Alembic revision `0004`:

1. create `provider_connections`;
2. rebuild `selected_models` with `connection_id`, the new role value, and the
   foreign key;
3. preserve valid Ollama generation selections;
4. remove stale rows whose provider is `openrouter`;
5. drop `provider_credentials`, which also removes residual OpenRouter keys;
6. keep `onboarding_completion`.

There is no `openrouter` registry alias and no attempt to map OpenRouter model
ids to an internal endpoint. Existing users remain onboarded but have no remote
selection until they configure a connection.

Delete:

- `modules/llm/providers/openrouter/`;
- `openrouter_base_url` and `openrouter_image_model`;
- OpenRouter credential routes, `/key` health, attribution headers, catalogue
  filtering, and image-response parsing;
- OpenRouter-specific frontend components and copy.

## Failure and operations

- Probe connections with bounded timeouts and load multiple connection cards
  concurrently; one outage must not create a page-wide failure.
- Keep provider error details bounded and redact URLs containing credentials
  even though URL validation rejects them.
- A missing/deleted connection is “no model selected”, not “unknown provider”.
- A model removed upstream makes its selection stale and disables its role; it
  is never silently replaced.
- Do not retry image generation automatically after a response may have been
  produced.
- vLLM's bearer-key option protects compatible routes, not the entire server.
  Production deployments still require organization-managed network controls.

## Tests

- Migration: OpenRouter credential/selection removed, Ollama selection and
  onboarding completion preserved, foreign-key cascade works.
- Connections: multiple rows of the same provider, duplicate-label rejection,
  optional key, key redaction, candidate-before-replace update, URL validation,
  independent health failures, and delete-selection transaction.
- Discovery: standard OpenAI list, richer capability metadata, duplicate model
  names on different connections, unknown capability, malformed response,
  timeout, and auth failure.
- Chat: selected connection resolves the correct URL/key and streams SSE;
  OpenRouter-only fields are absent.
- Image: selected connection resolves `/images/generations`; base64 and URL
  responses, MIME/size limits, timeout, missing selection, and explicit test.
- Frontend: add two connections, progressive independent loading, duplicate
  model ids remain distinct, role assignment, unknown-image confirmation,
  disconnect cleanup, keyboard access, and no secret rendering.

## Acceptance

- Two different OpenAI-compatible endpoints can be connected with different
  keys and identical model ids without collision.
- One gateway connection can supply both generation and image roles.
- A direct vLLM connection supplies generation and shows no false image claim.
- Remote model responses are never copied into a catalogue table.
- Disconnecting a connection immediately clears only the roles that reference
  it.
- Chat and all text Studio formats continue through the selected generation
  model.
- Image writes through existing artifact storage; infographic requires no image
  endpoint.
- No shipped code, schema, route, or user-facing copy depends on OpenRouter.
