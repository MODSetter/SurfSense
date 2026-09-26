# OpenAI-compatible connections

> **Partly built.** Classification from the remote manifest and the form's providers have shipped, and this page describes them. The [model catalog proposal](../proposals/model-catalog.md) still moves the model lists the cards and pickers read onto the remote catalog routes, and connections into a settings panel; connection storage, keys and the runtime stay.

A connection is one named remote endpoint that speaks the OpenAI API: a hosted provider, an organization's gateway, a vLLM server, or a local server such as Ollama or LM Studio. The user adds as many as they need, each with its own URL and optional key, and assigns a model from any of them to a model type, such as `text_gen` for chat or `image_gen` for images. SurfSense configures and selects endpoints; it does not load-balance them, and it never copies an endpoint's model list into the database. The keys are encrypted with a per-install secret that Electron keeps in the OS keychain.

**Code:** [`modules/llm/connections/`](../../surfsense_local/backend/modules/llm/connections/), [`modules/llm/providers/openai_compatible/`](../../surfsense_local/backend/modules/llm/providers/openai_compatible/), [`modules/llm/resolution.py`](../../surfsense_local/backend/modules/llm/resolution.py), [`modules/llm/selection.py`](../../surfsense_local/backend/modules/llm/selection.py), [`shared/secrets.py`](../../surfsense_local/backend/shared/secrets.py), [`electron/src/main/secret.ts`](../../surfsense_local/electron/src/main/secret.ts), [`frontend/src/features/models/remote/`](../../surfsense_local/frontend/src/features/models/remote/)
**Decisions:** [ADR 0015](../adr/0015-openai-compatible-connections.md), [ADR 0017](../adr/0017-egress-off-by-default.md), [ADR 0018](../adr/0018-keychain-envelope-encryption.md)

## Terms

```text
provider             a protocol implementation: llamacpp, sdcpp, audiocpp or openai_compatible
provider connection  one named remote endpoint and its optional bearer key
model                an id the endpoint lists live, or one entered by hand
model type           what a model is for, and the slot one selection fills: text_gen, image_gen, image_edit, video_gen or audio_gen
```

A connection is type-neutral: which slot it fills depends on the model assigned from it and the routes the endpoint implements. One gateway can hold several slots; chat and image models on separate infrastructure are two connections. "OpenAI-compatible" means compatible for a given route, not that every route exists. Core vLLM serves `/chat/completions` but no image output, while vLLM-Omni serves `/images/generations`, so a typical organization has one connection for each.

```text
OpenAI-compatible connection
  ├── GET  /models                  live discovery and health
  ├── POST /chat/completions        the text_gen selection
  └── POST /images/generations      the image_gen selection
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
| `catalog_provider` | the remote manifest provider this reaches, such as `openai` or `neon`, or `custom` for an endpoint the manifest does not list; stored as chosen, never read from the URL |
| `base_url` | the exact API root, normally ending in `/v1`, stored without a trailing slash |
| `api_key_ciphertext` | the Fernet-encrypted key, nullable, never returned by any route |
| `created_at`, `updated_at` | |

A base URL must be `http` or `https` with a host, and may not carry credentials, a query or a fragment. Private, loopback and link-local hosts are valid: the API binds to loopback, and reaching internal endpoints is the point. If the API ever binds externally, this becomes an SSRF boundary and has to be redesigned first.

`selected_models` holds one row per model type. An `openai_compatible` row names its `connection_id`, and the foreign key cascades, so deleting a connection clears exactly the selections that used it. Two endpoints serving the same model id stay distinct, because a selection's identity includes the connection. The full table is in [`data-model.md`](data-model.md); choosing a model and onboarding are in [`local-models/selection.md`](local-models/selection.md).

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
  "allow_unverified": false,
  "catalog_provider": "custom"
}
```

- `catalog_provider` defaults to `custom`; any other value must be a provider in the remote manifest, or the write is a `422`.
- On update, an omitted `api_key` keeps the stored key, a value replaces it, and `null` clears it. On create, omitted and `null` both mean no key. A key that is given must not be empty.
- Create and update check a candidate before touching stored state: normalise the URL, require egress to its host, call `GET {base_url}/models` with the candidate key, and require an OpenAI list envelope in reply. A failed update leaves the working connection and its key as they were.
- A probe that fails for any reason gets `422` with code `unverified_connection`, and nothing is saved. For an endpoint without useful model discovery the form offers "Save anyway", which repeats the write with `allow_unverified: true`; a model id then has to be entered by hand. A failed probe never becomes a silent unverified save.
- A duplicate label is a `409`. Health failures never delete a connection.
- Every route that reaches the endpoint checks egress for its host first; a loopback host is not egress ([`egress.md`](egress.md)).

## Live models

`GET .../models` calls `{base_url}/models` and, in parallel, `{base_url}/models?output_modalities=image`. A valid answer to the second is merged in and any failure of it is ignored: OpenRouter's default listing leaves out most of its image models, and an endpoint that ignores the parameter returns the same set, so no provider has to be recognised. Ids are deduplicated within the connection and sorted. A failed baseline call is a `502`, and the connection stays.

Each model's `types` come from the first of three sources that knows it, and nothing is guessed; `capability_source` says which:

1. `declared`: output modalities the endpoint publishes: text is `text_gen`, image `image_gen`, video `video_gen` and audio `audio_gen`.
2. `catalog`: the remote model manifest, [`catalog/remote/manifest/models.json`](../../surfsense_local/backend/modules/llm/catalog/remote/manifest/models.json). `scripts/refresh_remote_manifest.py` builds it offline from models.dev, keyed provider then model, with the evidence the classifier reads rather than a verdict; a person reviews the diff and commits it, and nothing fetches models.dev at runtime. A connection with a `catalog_provider` reads that provider's entry first. Otherwise, and for an id its provider does not carry, the lookup reads the maker's own entry when the id's prefix names one, otherwise the types every provider carrying the id agrees on, trying the full id and then its last path segment ([`lookup.py`](../../surfsense_local/backend/modules/llm/catalog/remote/manifest/lookup.py)). A model found with no types, such as an embedder, is known to fill no slot.
3. `unknown`: neither source knows the id.

Each listed model also carries `selectable_for`, the slots it can fill, decided by the one rule in [`selectable.py`](../../surfsense_local/backend/modules/llm/selectable.py): the types it is, or every type when it is unknown. The pickers read that field rather than deciding, and choosing a model applies the same rule. Neither reads the manifest's `call` or `connect.status`, so a model the remote catalog marks `unusable` is still offered here (Known gaps). A model the listing does not contain, or a connection whose listing fails, needs the choice repeated with `allow_unlisted: true`. The remote model list is fetched every time and never stored.

## The remote catalog

`catalog/remote/router.py` serves the manifest and the connections as rows ([`catalog.py`](../../surfsense_local/backend/modules/llm/catalog/remote/catalog.py)). All 8,000-odd remote rows at once would be several megabytes, so providers come first and a provider's rows when it is opened.

| Method | Path | Returns | Network |
|---|---|---|---|
| `GET` | `/llm/catalog/remote` | every provider: `connect`, its model count per type, and how many connections name it | none |
| `GET` | `/llm/catalog/remote/providers/{id}` | that provider's rows: `not_connected`, or one `unchecked` row per connection that names it | none |
| `GET` | `/llm/catalog/remote/connections/{id}` | that connection's rows checked against its live listing | that host |

- A row carries its `availability`: `not_connected`, `unchecked`, `available`, `not_served` (retired, or the key cannot reach it), `could_not_check`, or `unusable` with a `reason`. An unusable row, from an unreachable provider or a model served only on `/responses` or through another protocol, has an empty `selectable_for`.
- Each connection has its own rows, because two keys to one provider can reach different models.
- A listed id the provider's manifest entry lacks, one newer than the last refresh, is added as `available`. A `custom` connection's rows are its listing and nothing else.
- An endpoint that is down leaves the manifest rows `could_not_check` with a `200`, not a `502`: an endpoint being down is not its models disappearing.
- Deprecated models are left out unless `include_deprecated=true`.
- `GET /llm/connections/{connection_id}/models` still backs the server groups, the pickers, and the checks at boot and on the dashboard that the selected remote model is still listed. Nothing in the frontend reads the two row routes yet.

## Runtime

Chat goes through `OpenAICompatibleChatProvider(base_url, api_key)`:

- health and model listing through `GET /models`;
- a streaming `POST /chat/completions`, with an `Authorization: Bearer` header when there is a key and no provider-specific headers or fields;
- each chunk read as answer (`content`) or reasoning (`reasoning_content`, or `reasoning` as vLLM, Ollama and OpenRouter name it). `chat_deltas()` yields both, marked; `chat()` yields the answer alone, for titles, Studio and the connection check;
- 300 seconds to the first token, answer or reasoning, since a cold model may still be loading, then 30 seconds between tokens. A long think keeps the stream alive rather than counting as a model that never started. Model listings wait at most 120 seconds and connection discovery 10;
- no context window and no token count, so chat falls back to its fixed history budget ([`chat.md`](chat.md)).

Images go through `OpenAICompatibleImageProvider`:

1. Use the connection's last successful route from an in-process cache, else `POST {base_url}/images/generations`.
2. Only on `404 Not Found` or `405 Method Not Allowed`, retry once on the other route.
3. Cache the route that worked until the process restarts.

- There is no fallback or retry after any other failure: auth, rate limit, timeout, `5xx`, a connection error or a malformed success. The endpoint may already have generated, and billed, an image. These surface as `NonRetryableImageError`, which a Studio job does not retry either. Route negotiation is not a retry policy.
- Both routes send `model` and `prompt`. The first entry of the reply's `data` may be `b64_json`, a base64 data URL, or an `http(s)` URL, which is downloaded without the endpoint's bearer token and with at most three redirects. Replies are capped at 28 MB and images at 20 MB, under a 180-second timeout, and the bytes must be PNG, JPEG, GIF, WebP or SVG and match any MIME type the endpoint claims.

[`resolution.py`](../../surfsense_local/backend/modules/llm/resolution.py) turns a model type's selection into a provider for chat, titles and Studio; the connection routes build their own for discovery and tests:

```text
text_gen          llamacpp                   → the supervised llama-server
                  openai_compatible + id     → load the connection → chat provider
image_gen         sdcpp                      → the image provider at sd-server's loopback URL
                  openai_compatible + id     → load the connection → image provider
```

Loading a connection runs the egress check for its host. The bundled sd-server speaks `/images/generations`, so it is a new selection target rather than a new protocol; being loopback, it needs no key and takes no egress decision. Chat, thread titles and every step where Studio's `text_gen` model writes use the generation resolver; `image` and `infographic` also use the image resolver ([`studio.md`](studio.md)).

## Trying a model before assigning it

- `chat-test` streams one answer from the chosen model, by default to a prompt asking for one short sentence, capped at 1,024 tokens and 600 characters, so a model whose capability is `unknown` can be seen answering before it becomes the chat model. An empty reply is a `502`, which is what a reasoning model returns when it spends the whole budget thinking.
- `image-test` generates one image, by default a blue circle on white, through the real image client and returns the bytes with `Cache-Control: no-store`. It creates no artifact.
- Selecting a model never runs inference. The server group offers a test before the model is used, and "Use without testing" for a trusted internal endpoint, whose first real request then reports any error normally. Image tests run only on an explicit action, because they are real inference and may cost money.

## Where keys live

Keys are protected by envelope encryption ([ADR 0018](../adr/0018-keychain-envelope-encryption.md)):

- Electron keeps one per-install secret: 32 random bytes, hex-encoded, encrypted with Electron's `safeStorage` (the OS keychain) into `secret.bin` in its userData folder, `<data dir>/electron/`. If that file is missing or cannot be decrypted, after a reinstall or a keychain reset, Electron mints a new secret rather than refusing to start. `safeStorage` names its keychain item after the app, so development runs as "SurfSense Dev" and never reads or recreates the installed app's key.
- On Linux without a keyring, `safeStorage` falls back to plain-text encryption so the app still boots.
- Electron passes the secret as `SURFSENSE_LOCAL_SECRET` to the API and both workers, and to no other sidecar. The sidecars make the calls, so they need the keys, which is why the secret cannot stay inside Electron.
- [`shared/secrets.py`](../../surfsense_local/backend/shared/secrets.py) derives a Fernet key from the SHA-256 of the secret and encrypts each connection's key into `provider_connections.api_key_ciphertext`. Revision `0007` dropped the plaintext column. `ProviderConnection.api_key` encrypts on write and decrypts on read.
- A bare `uv run` with no secret in its environment creates `<data dir>/secret`, 32 random bytes hex-encoded with mode `0600`, and logs a warning. The secret then sits next to the database it protects.
- Ciphertext this install's secret cannot open, after a new secret was minted or a backup was restored on another machine, raises `UnreadableSecretError`. The API answers any route that hits it with `409` and code `unreadable_secret`: the request is valid, the server is healthy, and the stored key is what has to be entered again.
- Whether the saved chat model can be used has one answer, [`checkAvailability`](../../surfsense_local/frontend/src/features/models/selection/availability.ts), which startup and the dashboard both call: `available`, `gone` (no longer in its list), `needs-consent` (egress to its host is off) or `unusable` (an unreadable or rejected key, an unreachable endpoint, anything else). A failed check never fails startup, and never clears the saved choice: the model stays in the picker so it can be checked again once fixed.
- The dashboard checks again when the model changes, when Settings closes (a key entered again, egress switched, a connection edited) and after **Allow…**, so fixing the cause in Settings clears the notice without a reload. Startup's answer is its first status, so the same model is not checked twice.
- `unusable` holds the composer, and a notice attached above it names the reason from the error's code and opens Settings › Text gen ([`model-issue-notice.tsx`](../../surfsense_local/frontend/src/features/chat/model-issue-notice.tsx)). `needs-consent` holds it too, with a notice that names the host: **Allow…** opens the egress consent dialog and **Open settings** opens Settings › Network, so a send never raises the dialog. `gone` offers **Set up model** with no notice.
- `GET /llm/connections/{id}/models` answers an endpoint's failure with `502` and a code by exception type and status, never the message text: `provider_auth` (401, 403), `provider_rate_limited` (429), `provider_unreachable` (no connection or a timeout), otherwise `provider_error` ([`discovery_failure.py`](../../surfsense_local/backend/modules/llm/connections/discovery_failure.py)).
- A key is never logged or returned.

## Frontend

- Each model section in Settings, Chat and Image, shows every connection as a group under the local models. A group loads its models only when opened, so a slow or failed endpoint does not hold up the others, and lists only those whose `selectable_for` includes that section's slot; the model in use, if it comes from that server, stays shown above the list whether the group is open or closed. Open, its list scrolls inside its own capped-height area rather than lengthening the page. A model is assigned after an optional test; an exact ID the listing lacks can be typed in. A new connection is added from **Use a server** on the section's **Add model** page. Adding and editing a connection happen in a dialog over the page. Saving a new connection returns to the list with its group open on its models, since choosing one is why it was added; saving an edit only refreshes.
- Edit and Disconnect sit on each group. Edit opens the same form in that dialog. A connection serves every slot, so Disconnect names each model it will clear, Chat, Image or both, whichever section it is disconnected from.
- Onboarding's model steps use the same groups and the same dialog; with nothing connected yet, their **Connect** opens the dialog directly, and saving opens the server page on the new connection's models.
- A model type no server model can fill yet offers no servers anywhere, in Settings or onboarding, and its copy drops the mention: audio today, since no server model voices podcasts. The list is `serversCanServe()` in `features/models/remote/servers-can-serve.ts`.
- The connection form picks a provider from the remote manifest, through `GET /llm/catalog/remote`, or "Local or custom server". A ready provider fills its URL, which stays editable so a proxy in front of it still works; a provider that needs account details asks for each field and builds the URL from its template; a provider that needs a URL leaves it to the user; an unreachable one is listed, disabled, with its reason. A provider that takes no key, a loopback server, hides the key field. "Local or custom server" leaves the URL to the user, since its port is whatever its owner set, with `http://localhost:11434/v1` as placeholder text only; a loopback server the manifest lists, such as LM Studio, fills the manifest's URL like any ready provider. The save sends `catalog_provider`.

## Known gaps

- An image returned as a URL is downloaded from whatever host the endpoint names, with no egress decision for that host; the endpoint's key is withheld from the download.
- A model the remote catalog marks `unusable`, from an unreachable provider or served only on `/responses` or through another protocol, is still offered by `GET /llm/connections/{id}/models` and accepted by `choose_model()`, which ignore `call` and `connect.status`.
