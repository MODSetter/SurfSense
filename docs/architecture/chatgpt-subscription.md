# ChatGPT subscription

A user with ChatGPT Plus or Pro signs in with their ChatGPT account instead of pasting an API key, and picks a model their plan lists. The result is a connection like any other ([`connections.md`](connections.md)): it holds the chat slot and is reached by chat, titles and Studio. What differs is how it signs in (OAuth, refreshed tokens) and how it is called (the Responses API, not `/chat/completions`).

It follows OpenAI's "Sign in with ChatGPT" flow for open-source apps ([developers.openai.com/siwc/token-sharing-open-source](https://developers.openai.com/siwc/token-sharing-open-source)). It never reads the Codex CLI's `~/.codex/auth.json`, runs the `codex` binary, or reuses the Codex CLI's client id.

**Code:** [`modules/llm/subscriptions/chatgpt/`](../../surfsense_local/backend/modules/llm/subscriptions/chatgpt/), [`modules/llm/providers/openai_responses/`](../../surfsense_local/backend/modules/llm/providers/openai_responses/), [`modules/llm/connections/listing.py`](../../surfsense_local/backend/modules/llm/connections/listing.py), [`electron/src/main/external-url.ts`](../../surfsense_local/electron/src/main/external-url.ts), [`frontend/src/features/models/remote/connections/chatgpt/`](../../surfsense_local/frontend/src/features/models/remote/connections/chatgpt/)
**Decisions:** [ADR 0038](../adr/0038-chatgpt-plans-sign-in-through-openai-not-codex.md), [ADR 0015](../adr/0015-openai-compatible-connections.md), [ADR 0018](../adr/0018-keychain-envelope-encryption.md)

## What it reaches

Every URL is in one file, [`endpoints.py`](../../surfsense_local/backend/modules/llm/subscriptions/chatgpt/endpoints.py), overridable with `SURFSENSE_LOCAL_CHATGPT_AUTH_URL` and `SURFSENSE_LOCAL_CHATGPT_API_URL` (the tests point both at a fake).

| What | Where |
|---|---|
| Authorize | `https://auth.openai.com/api/accounts/authorize` |
| Token exchange and refresh | `https://auth.openai.com/api/accounts/oauth/token` |
| Revocation, on sign-out and delete | `POST https://auth.openai.com/api/accounts/oauth/revoke` |
| ID-token keys | `https://auth.openai.com/.well-known/jwks.json` |
| Plan's models | `GET https://api.openai.com/v1/models` |
| Answers | `POST https://api.openai.com/v1/responses` |

## Signing in

1. The renderer reads `GET /llm/connections/chatgpt`: `serves`, the slots a ChatGPT connection fills, and `hosts`, the hosts the sign-in reaches that egress has not allowed. It asks about each host in turn. A refused request asks about one host only and cannot tell a declined host from the next one, so the question is put up front ([`egress.md`](egress.md)).
2. `POST /llm/connections/chatgpt/sign-in` with `{label}` for a new connection or `{connection_id}` to sign one in again. It checks the hosts again, a free label (`409`) or a ChatGPT connection (`404`), then opens a loopback listener on `127.0.0.1` at a random port and answers `201 {flow_id, authorize_url}`. OpenAI allows any port as long as scheme, host and path (`/callback`) match.
3. The authorize URL asks for `client_id=dynamic_agent_client`, so OpenAI issues a client for this user on first sign-in, with `agent_name_hint=SurfSense`, an `ext_agent_host_id`, scopes `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct`, `resource=https://api.openai.com/v1`, `state`, `nonce` and an S256 PKCE challenge. The host id is `urn:uuid:` over an HMAC of the install secret, so it is stable for the install and stored nowhere ([`host_id.py`](../../surfsense_local/backend/modules/llm/subscriptions/chatgpt/host_id.py)).
4. The renderer opens it through Electron, which allows `auth.openai.com/api/accounts/authorize` only with a `redirect_uri` of `http://127.0.0.1:<port>/callback`, so a crafted link cannot send the code anywhere else.
5. The callback must carry the flow's `state`. The code is exchanged with the issued `client_id` and the PKCE verifier, and the result is refused unless it grants `chatgpt.tokens.use.direct` and carries a refresh token. The ID token's RS256 signature is checked against the JWKS, then its issuer, audience, expiry (two minutes of leeway) and nonce. Its `sub` and `email` are kept.
6. The tokens are saved on a new connection, or on the one being signed in again, and the flow reads `signed_in`. The renderer polls `GET /llm/connections/chatgpt/sign-in/{flow_id}` every second. A flow not finished in five minutes fails and frees its port. `DELETE` on the flow cancels it.

Flows live in the API's memory ([`flows.py`](../../surfsense_local/backend/modules/llm/subscriptions/chatgpt/flows.py)): only the API signs in, and a restart only abandons a sign-in in progress.

## The connection

A ChatGPT connection is a `provider_connections` row with `auth_kind = 'chatgpt'`, `provider = 'openai_compatible'`, `base_url` set to the API URL and `catalog_provider = 'openai'`, so the manifest's OpenAI entries say which plan models read images. `api_key_ciphertext` stays empty.

- `oauth_ciphertext` holds `{client_id, access_token, refresh_token, id_token, expires_at, account, email, earliest_refresh_at}` as one Fernet-encrypted JSON blob, under the same per-install secret as API keys ([ADR 0018](../adr/0018-keychain-envelope-encryption.md)). `NULL` is signed out.
- `GET /llm/connections` adds `auth_kind`, `signed_in` and `account_email`; no token leaves the API.
- `PUT` on a ChatGPT connection renames it and changes nothing else.
- `DELETE /llm/connections/{id}/sign-in` signs out: the tokens go, the connection and its selection stay. Signing in again registers a new client, since the issued one went with the tokens.
- Signing out, or deleting the connection, also revokes the refresh token at the issuer's `revocation_endpoint` (`/api/accounts/oauth/revoke`, RFC 7009, as a public client) once the local change has committed ([`revocation.py`](../../surfsense_local/backend/modules/llm/subscriptions/chatgpt/revocation.py)). It is best effort: a failure is logged and the sign-out stands. It is skipped when the sign-in host has been turned off since, and when this install can no longer decrypt the tokens (a keychain reset or a backup restored elsewhere), so a lost key never blocks the sign-out or delete that recovers from it.
- It serves `text_gen` only. What a connection serves is one rule, [`serves.py`](../../surfsense_local/backend/modules/llm/connections/serves.py), keyed by `auth_kind`: selection refuses any other slot even with `allow_unlisted`, the image and speech tests answer `422`, image and speech resolution refuse it, and `GET /llm/connections` reports it as `serves`.

## Tokens

[`tokens.py`](../../surfsense_local/backend/modules/llm/subscriptions/chatgpt/tokens.py) gives each generator an access-token getter bound to the database, not to a process, since the API and both workers resolve the chat model on their own.

- A token is used until five minutes before it expires, or until `earliest_refresh_at` if OpenAI set one later.
- A refresh runs inside one transaction, which `shared.db` opens with `BEGIN IMMEDIATE`, so it holds SQLite's write lock across its HTTP call. A second process waits, sees `token_version` moved, and uses the token the first stored. Refresh tokens rotate, and the same one sent twice would sign the account out. The call times out at 4 seconds, under the 5-second `busy_timeout` other writers wait.
- The write is a core `UPDATE` of the token columns and `token_version`, so `updated_at` keeps meaning the user's last edit.
- `invalid_grant`, `token_expired` or `refresh_token_invalidated` clears the tokens and raises `SignInRequiredError`. Any other failure leaves them for the next try.
- A `401` from `/responses` refreshes once and repeats the request. A second `401` is `SignInRequiredError`.

## Answering

[`ResponsesChatProvider`](../../surfsense_local/backend/modules/llm/providers/openai_responses/chat.py) implements the `Generator` protocol, so chat, titles and Studio call it unchanged.

- The body is `{model, input, store: false, stream: true}`, plus `prompt_cache_key` with the conversation's name, which routes its requests to the machine that cached its prompt. A chat names its thread, and Studio the system prompt and sources a job's calls share. OpenAI's [preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) list the fields the endpoint rejects, `prompt_cache_retention` among them, and not the key. Nothing else is sent. The plan's endpoint refuses `instructions`, `reasoning`, `text.format`, `max_output_tokens` and `tools`, so `max_tokens`, `reasoning`, `temperature` and `json_schema` are accepted and dropped. Studio parses an unconstrained reply as it does for any endpoint that ignores a schema.
- A `system` turn goes as a `developer` input item. A turn with images sends `input_text` then `input_image` data URLs.
- `response.output_text.delta` is answer text, and reasoning-summary deltas are reasoning. Only `response.completed` ends a reply: a stream that closes without it, or ends `incomplete`, raises. Its `usage` is logged as the input tokens the plan reused from its cache (`input_tokens_details.cached_tokens`).
- `subscription_sharing_usage_limit_exceeded`, as a `429` or inside `response.failed`, is `PlanLimitError`. `subscription_sharing_invalid_user` is `SignInRequiredError`. Anything else is an `httpx.HTTPStatusError` carrying OpenAI's message.
- The model list is the plan's `models` array, entries whose `visibility` is `list`, each a `text_gen` model with `capability_source: declared`. The manifest's "only on `/responses`" does not apply here.
- No context window or token count, so chat keeps its fixed history budget. The same deadlines as the OpenAI-compatible client: 300 seconds to the first token, 30 between.

A `429`, `500`, `502`, `503` or `504` before the reply starts is retried twice, after the wait the response asks for (`retry-after-ms` or `retry-after`, at most a minute) or one then two seconds, and a stop ends the wait at once ([`retry.py`](../../surfsense_local/backend/modules/llm/providers/openai_responses/retry.py)). A used-up plan is never retried. When the retries run out the status stands, so chat sorts it as it would any other.

Chat sorts `SignInRequiredError` into `subscription_sign_in`, which offers Model setup, and `PlanLimitError` into `subscription_limit`, which offers no retry ([`chat.md`](chat.md#the-stream)). The model list answers a signed-out connection with `409` and code `sign_in_required`, and the composer's notice says to sign in again.

## Frontend

Every model list reads `serves` rather than deciding: the Settings sections, their empty states and onboarding's server steps leave a ChatGPT connection out of every section but chat. The connection form lists **ChatGPT subscription** beside **Local or custom server**, only when the dialog was opened for a slot the sign-in's `serves` includes, with a hint built from that list ("Chat only"). Choosing it hides the URL and key fields and shows **Sign in with ChatGPT**, which asks about the hosts, opens the browser and waits, with **Open the sign-in page again** and Cancel. Editing a ChatGPT connection shows the account, and offers **Sign in again**, **Sign out**, and **Save changes** for a new name. Its provider cannot be changed, and an API-key connection cannot become one. The model groups show the account's email in place of the URL.

## Known gaps

- **Sign in again** on a connection still signed in overwrites its tokens through `save_sign_in()` without revoking the grant they replace.
- Built against OpenAI's documentation and a fake server; not yet run against a real ChatGPT account.
- Signing in again never uses the returning-user path (`id_token_hint` with the issued client), because signing out drops the client id with the tokens.
- When the plan's model list cannot be fetched there is no fallback list; the model group shows the failure.
- The context window of a plan model is unknown, so long chats are trimmed to the fixed history budget.
