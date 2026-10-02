---
status: in-progress
code:
  - surfsense_local/backend/modules/llm/subscriptions/chatgpt/
  - surfsense_local/backend/modules/llm/providers/openai_responses/
  - surfsense_local/backend/modules/llm/models.py
  - surfsense_local/backend/modules/llm/resolution.py
  - surfsense_local/backend/modules/llm/connections/
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/electron/src/main/external-url.ts
  - surfsense_local/frontend/src/features/models/remote/connections/
---

# Using a ChatGPT subscription as a remote model

> A user with ChatGPT Plus or Pro signs in with their ChatGPT account instead of pasting an API key, and picks a model their plan includes. It is a connection like any other: it appears in the remote catalog, holds the chat slot, and is reached by chat, titles and Studio. What differs is how it signs in (OAuth, refreshed tokens) and how it is called (the Responses API, not `/chat/completions`).

Built as described in [ChatGPT subscription](../architecture/chatgpt-subscription.md); what remains is running it against a real account. Where OpenAI's open-source docs differed from the first draft, the docs won: dynamic client registration, a loopback redirect on any port and no device-code flow, `api.openai.com` for inference, and a request body that may not carry `instructions`, `reasoning`, `text.format`, `max_output_tokens` or `tools`.

Before this, every remote model was an OpenAI-compatible connection with a static key, called at `{base_url}/chat/completions` ([connections](../architecture/connections.md), [ADR 0015](../adr/0015-openai-compatible-connections.md)). Nothing in the app does OAuth, and nothing speaks the Responses API, so the 50 OpenAI models the [manifest](../../surfsense_local/backend/modules/llm/catalog/remote/manifest/models.json) marks `call.route: "responses"` are unusable even with a key.

## Decisions

- **Text generation only.** A subscription connection can hold the `text_gen` slot. Image, edit, video, audio and embedding selections refuse it with a reason.
- **OpenAI's [Sign in with ChatGPT for open-source apps](https://developers.openai.com/siwc/token-sharing-open-source).** OAuth 2.0 with PKCE and the `chatgpt.tokens.use.direct` scope. The first sign-in sends `client_id=dynamic_agent_client` and OpenAI issues a client for that user, so there is nothing to apply for; every request names a stable `ext_agent_host_id`, derived from the install secret. The alternative, reusing the Codex CLI's public client ID against `chatgpt.com/backend-api/codex`, works today and is how Unsloth Studio does it. It was rejected: it presents SurfSense as the Codex CLI to an endpoint OpenAI never published for other apps, and OpenAI can break it for every user at once. The authorize, token and inference URLs live in one file.
- **The API sidecar owns sign-in and tokens; the renderer never sees a token.** It returns an opaque flow id and a status. The workers read tokens from the database; they never sign in.
- **One way to sign in: the browser.** The API opens a short-lived loopback listener on `127.0.0.1` at a random port, separate from its own; OpenAI allows any port as long as scheme, host and path match. Electron opens the authorize URL in the system browser. The listener closes on the callback or after five minutes. OpenAI's open-source flow has no device code.
- **SQLite stays the store.** Tokens sit next to API keys in `surfsense.db`, encrypted with the per-install secret ([ADR 0018](../adr/0018-keychain-envelope-encryption.md)). The keychain alone would not reach the workers.
- **One process refreshes at a time.** The API and both workers call [`resolve_generation`](../../surfsense_local/backend/modules/llm/resolution.py) and can find the same token expired at once. A refresh token is single-use, so two concurrent refreshes can sign the user out. SQLite's write lock serializes them; no file lock.
- **A dead refresh token clears the tokens.** `invalid_grant` sets the ciphertext to `NULL`, and a `chatgpt` connection with no tokens is the "Reconnect" state. No separate flag can drift from the tokens.
- **A plan's usage limit is terminal.** A 429 that says the plan limit is reached fails the request with that reason, and chat offers no retry. Other failures surface as they do for any connection.
- **The plan's body is minimal.** `{model, input, store: false, stream: true}`: the endpoint refuses `instructions`, `reasoning`, `text.format`, `max_output_tokens` and `tools`, so a system prompt goes as a `developer` turn and the caller's token cap, reasoning switch and JSON schema are dropped. Studio already parses replies an endpoint did not constrain.
- **The manifest describes the plan's models through `openai`.** A ChatGPT connection names `catalog_provider = 'openai'`, so which models read images comes from the entries already there; no hand-written provider is added to the generated manifest.
- **The Responses generator is not yet used with an API key.** Given a key instead of a token getter, it could serve the OpenAI models the manifest marks `responses`, but the API-key `/responses` endpoint takes the fields the plan refuses, so it is a follow-up.

## Schema

One revision, `0023`. It adds columns with plain `ALTER TABLE … ADD COLUMN`, never a batch rebuild: SQLite cannot alter a CHECK in place, rebuilding `provider_connections` drops it, and with foreign keys on that cascades through `selected_models.connection_id` and deletes every remote selection ([ADR 0005](../adr/0005-hand-written-migrations.md), revisions `0014` and `0022`).

`provider` stays `openai_compatible` and comes to mean "remote connection". Changing it would force rebuilding both `provider_connections` and `selected_models` for a rename.

| Column on `provider_connections` | Type | Default | Holds |
|---|---|---|---|
| `auth_kind` | `TEXT NOT NULL`, `CHECK (auth_kind IN ('api_key', 'chatgpt'))` | `'api_key'` | how the connection signs in, and so which generator `resolution.py` builds |
| `oauth_ciphertext` | `BLOB NULL` | `NULL` | encrypted JSON `{client_id, access_token, refresh_token, id_token, expires_at, account, email, earliest_refresh_at}` |
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
   │ GET …/chatgpt   POST …/chatgpt/sign-in   GET …/sign-in/{flow}   DELETE …/{id}/sign-in
   ▼
electron: opens the authorize URL (allowlisted host)
   ▼
api: modules/llm/subscriptions/chatgpt/
       flows.py     the sign-in: PKCE, loopback listener, ID token, flow state in memory
       tokens.py    the token getter: read, refresh under the write lock, clear on invalid_grant
       plan_models.py  the plan's live model list
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
- **Catalog.** `/llm/connections/{id}/models` asks the plan for its live list. A model the plan stops listing is a selection the availability check reports as gone, as for any connection.
- **Egress.** Before signing in, the renderer asks consent for the auth host and the inference host, one `host:` row each, from a list the API gives ([ADR 0027](../adr/0027-egress-consent-per-host.md)).
- **Electron.** [`external-url.ts`](../../surfsense_local/electron/src/main/external-url.ts) allows OpenAI's authorize and device-verification URLs, and nothing else from those hosts.
- **Frontend.** [`connection-form.tsx`](../../surfsense_local/frontend/src/features/models/remote/connections/connection-form.tsx) offers **ChatGPT subscription** beside **Local or custom server**, and shows Sign in, then Sign in again and Sign out on an existing one, in place of the URL and key fields.

## Open questions

- **Running it against a real ChatGPT account.** Everything is tested against a fake built from OpenAI's docs. The first live sign-in confirms the callback's `client_id`, the token response's `scope` and `earliest_refresh_at`, and the plan's `/v1/models` shape.

## Work

Built: the Responses generator, revision `0023`, the token getter and its refresh, sign-in and its routes, the Electron allowlist, egress consent, the connection form, and the two chat error kinds. Left: the live run above, then folding this into ADRs.

The change that ships this amends [ADR 0015](../adr/0015-openai-compatible-connections.md), which says every remote model is an OpenAI-compatible connection, and deletes this proposal. [Connections](../architecture/connections.md) and [data model](../architecture/data-model.md) already describe the code.

## Not in scope

- **A Claude subscription.** Anthropic's terms allow OAuth tokens from Free, Pro and Max plans only in Claude Code and Claude.ai. Using them in another product, the Agent SDK included, breaks the Consumer Terms, and third-party developers may not offer Claude.ai sign-in. Claude stays reachable with an API key through the existing `anthropic` connection.
- Reading the Codex CLI's `~/.codex/auth.json`, or running the `codex` binary.
- Tool calling, hosted tools, and image, audio or embedding models on a subscription.
- More than one ChatGPT account at once. A second connection signs in separately, but nothing is designed around it.
