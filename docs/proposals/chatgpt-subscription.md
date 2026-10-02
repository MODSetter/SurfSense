---
status: proposed
code:
  - surfsense_local/backend/modules/llm/subscriptions/chatgpt/
  - surfsense_local/backend/modules/llm/providers/openai_responses/
  - surfsense_local/backend/modules/llm/models.py
  - surfsense_local/backend/modules/llm/resolution.py
  - surfsense_local/backend/modules/llm/connections/
  - surfsense_local/backend/modules/llm/catalog/remote/
  - surfsense_local/backend/scripts/remote_manifest/
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/electron/src/main/external-url.ts
  - surfsense_local/frontend/src/features/models/remote/connections/
---

# Using a ChatGPT subscription as a remote model

> A user with ChatGPT Plus or Pro signs in with their ChatGPT account instead of pasting an API key, and picks a model their plan includes. It is a connection like any other: it appears in the remote catalog, holds the chat slot, and is reached by chat, titles and Studio. What differs is how it signs in (OAuth, refreshed tokens) and how it is called (the Responses API, not `/chat/completions`).

Today every remote model is an OpenAI-compatible connection with a static key, called at `{base_url}/chat/completions` ([connections](../architecture/connections.md), [ADR 0015](../adr/0015-openai-compatible-connections.md)). Nothing in the app does OAuth, and nothing speaks the Responses API, so the 50 OpenAI models the [manifest](../../surfsense_local/backend/modules/llm/catalog/remote/manifest/models.json) marks `call.route: "responses"` are unusable even with a key.

## Decisions

- **Text generation only.** A subscription connection can hold the `text_gen` slot. Image, edit, video, audio and embedding selections refuse it with a reason.
- **Our own client ID, through OpenAI's [Sign in with ChatGPT](https://developers.openai.com/siwc/quickstart).** It is OAuth 2.0 with PKCE and plan-usage scopes for the Responses API. The alternative, reusing the Codex CLI's public client ID against `chatgpt.com/backend-api/codex`, works today and is how Unsloth Studio does it. It was rejected: it presents SurfSense as the Codex CLI to an endpoint OpenAI never published for other apps, and OpenAI can break it for every user at once. The client ID, the authorize and token URLs, and the inference host live in one constants file, so the source is a one-file change.
- **The API sidecar owns sign-in and tokens; the renderer never sees a token.** It returns an opaque flow id and a status. The workers read tokens from the database; they never sign in.
- **Two ways to sign in**, both from the start:
  - **Browser.** The API opens a short-lived loopback listener on a fixed port registered with OpenAI, separate from the API's own port, which is random ([`index.ts`](../../surfsense_local/electron/src/main/index.ts), `getFreePort`). Electron opens the authorize URL in the system browser. The listener closes on the callback or after five minutes.
  - **Device code.** No callback, so it works when the port is taken or the browser is on another machine.
- **SQLite stays the store.** Tokens sit next to API keys in `surfsense.db`, encrypted with the per-install secret ([ADR 0018](../adr/0018-keychain-envelope-encryption.md)). The keychain alone would not reach the workers.
- **One process refreshes at a time.** The API and both workers call [`resolve_generation`](../../surfsense_local/backend/modules/llm/resolution.py) and can find the same token expired at once. A refresh token is single-use, so two concurrent refreshes can sign the user out. SQLite's write lock serializes them; no file lock.
- **A dead refresh token clears the tokens.** `invalid_grant` sets the ciphertext to `NULL`, and a `chatgpt` connection with no tokens is the "Reconnect" state. No separate flag can drift from the tokens.
- **A plan's usage limit is terminal.** A 429 that says the plan limit is reached fails the request with that reason and is not retried. Other 429s and 5xxs retry as today.
- **The Responses generator is not ChatGPT-specific.** Given an API key instead of a token getter, it also serves the OpenAI models the manifest marks `responses`. That is a follow-up, not part of this work.

## Schema

One revision, `0023`. It adds columns with plain `ALTER TABLE … ADD COLUMN`, never a batch rebuild: SQLite cannot alter a CHECK in place, rebuilding `provider_connections` drops it, and with foreign keys on that cascades through `selected_models.connection_id` and deletes every remote selection ([ADR 0005](../adr/0005-hand-written-migrations.md), revisions `0014` and `0022`).

`provider` stays `openai_compatible` and comes to mean "remote connection". Changing it would force rebuilding both `provider_connections` and `selected_models` for a rename.

| Column on `provider_connections` | Type | Default | Holds |
|---|---|---|---|
| `auth_kind` | `TEXT NOT NULL`, `CHECK (auth_kind IN ('api_key', 'chatgpt'))` | `'api_key'` | how the connection signs in, and so which generator `resolution.py` builds |
| `oauth_ciphertext` | `BLOB NULL` | `NULL` | encrypted JSON `{access_token, refresh_token, expires_at, account_id}` |
| `token_version` | `INTEGER NOT NULL` | `0` | bumped on each refresh, so a process that lost the race uses the winner's token |

- One blob, not a column per field, mirroring `api_key_ciphertext`. Decrypting is cheap, and the account and expiry stay off disk in clear.
- No cross-column CHECK such as "a `chatgpt` row has no key": a table-level CHECK needs the rebuild above. The connections router enforces it.
- `base_url` stays `NOT NULL` and holds the inference URL the app sets, so the egress host check works unchanged.
- Existing rows default to `api_key`: no backfill. The downgrade drops the three columns in place, as `0014`'s does.

A refresh, in any process:

```
BEGIN IMMEDIATE
read oauth_ciphertext, token_version
token fresh, or version moved since this process read it → use it, COMMIT
else POST the token endpoint with the refresh token
     UPDATE … SET oauth_ciphertext = new, token_version = token_version + 1
       WHERE id = ? AND token_version = old
COMMIT
```

The write lock is held across one HTTP call, about once an hour per connection. A refresh starts five minutes before expiry, or once after a 401. It writes with a core `UPDATE` of the token columns only, so `updated_at` keeps meaning "the user edited this".

## Seams

```
frontend: connection form ─ "Sign in with ChatGPT" ─ flow status (poll)
   │ POST /llm/connections/chatgpt/sign-in    GET …/sign-in/{flow}    DELETE …/{id}/sign-in
   ▼
electron: opens the authorize URL (allowlisted host)
   ▼
api: modules/llm/subscriptions/chatgpt/
       sign_in.py   PKCE and device code, loopback listener, flow state in memory
       tokens.py    the token getter: read, refresh under the write lock, clear on invalid_grant
       models.py    the plan's live model list, falling back to the manifest's
       router.py    sign-in, flow status, disconnect
     modules/llm/providers/openai_responses/
       chat.py      a Generator over POST …/responses (SSE)
     resolution.py  branches on auth_kind
   ▲
workers: resolve_generation() → the same generator and token getter
```

- **Generator.** Implements the existing [`Generator`](../../surfsense_local/backend/modules/llm/providers/protocols.py) protocol, so chat, titles and Studio call it unchanged.
  - Messages become Responses `instructions` and `input` items; images become `input_image`.
  - `json_schema` maps to `text.format`, `reasoning` to `reasoning.effort`. It sends `store: false`.
  - `output_text.delta` becomes an answer `Delta`, `reasoning_summary_text.delta` a reasoning `Delta`.
  - `max_tokens` is sent only if the endpoint accepts it.
  - No tools: SurfSense's chat sends none today.
  - `context_tokens` and `sees_images` come from the plan's model list. `token_count` is `None`.
- **Auth headers.** The generator takes a token getter, not a key. [`key_headers.py`](../../surfsense_local/backend/modules/llm/connections/key_headers.py) stays for static keys.
- **Catalog.** The manifest generator adds one reviewed provider, `chatgpt`, with a new `connect.status` of `sign_in` ([`schema.py`](../../surfsense_local/backend/modules/llm/catalog/remote/manifest/schema.py)) and a curated model list. `/llm/connections/{id}/models` asks the plan for its live list and falls back to the manifest's. A model the plan stops listing shows as unavailable rather than vanishing from a saved selection.
- **Egress.** Signing in asks consent for the auth host and the inference host, one `host:` row each ([ADR 0027](../adr/0027-egress-consent-per-host.md)).
- **Electron.** [`external-url.ts`](../../surfsense_local/electron/src/main/external-url.ts) allows OpenAI's authorize and device-verification URLs, and nothing else from those hosts.
- **Frontend.** For the `sign_in` status, [`connection-form.tsx`](../../surfsense_local/frontend/src/features/models/remote/connections/connection-form.tsx) shows Sign in, the device code when that path is taken, and Reconnect on a connection with no tokens, in place of the URL and key fields.

## Open questions

- **Getting a client ID.** OpenAI's quickstart says open-source developers register themselves; its [request page](https://developers.openai.com/siwc/request-client-id) says Sign in with ChatGPT is for "a select group of commercial partners". Which applies decides when this can ship.
- **The plan-usage endpoint's exact shape**: its host, required headers, model-list call, and whether it takes `max_output_tokens`. The design assumes the Responses API; the details come with the client ID.
- **The loopback port** to register.

## Work

1. The Responses generator against an API key, which unlocks the manifest's `responses` models and needs no OAuth.
2. Revision `0023`, the token getter and its refresh, with a test that two processes refreshing at once both end with the same valid token.
3. Sign-in: both flows, the routes, the Electron allowlist, egress consent.
4. Catalog entry and live model list; the connection form's sign-in state.

The change that ships this amends [ADR 0015](../adr/0015-openai-compatible-connections.md), which says every remote model is an OpenAI-compatible connection, and updates [connections](../architecture/connections.md) and [data model](../architecture/data-model.md).

## Not in scope

- **A Claude subscription.** Anthropic's terms allow OAuth tokens from Free, Pro and Max plans only in Claude Code and Claude.ai. Using them in another product, the Agent SDK included, breaks the Consumer Terms, and third-party developers may not offer Claude.ai sign-in. Claude stays reachable with an API key through the existing `anthropic` connection.
- Reading the Codex CLI's `~/.codex/auth.json`, or running the `codex` binary.
- Tool calling, hosted tools, and image, audio or embedding models on a subscription.
- More than one ChatGPT account at once. A second connection signs in separately, but nothing is designed around it.
