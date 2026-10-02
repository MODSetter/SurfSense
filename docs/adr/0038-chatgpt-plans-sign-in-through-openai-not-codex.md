# ADR 0038: A ChatGPT plan is a connection signed in through OpenAI's open-source flow, not the Codex CLI's client

- **Status:** Accepted
- **Date:** 2026-10-02
- **Source:** [ChatGPT subscription proposal L22–34](https://github.com/MODSetter/SurfSense/blob/e9a1bd801fc9ac74a3c492fff40241701d6b9515/docs/proposals/chatgpt-subscription.md#L22-L34)

## Context

A ChatGPT Plus or Pro subscriber pays for model usage that a key connection ([ADR 0015](0015-openai-compatible-connections.md)) cannot reach: there is no API key, only an account. Two ways in exist. OpenAI's "Sign in with ChatGPT" for open-source apps issues each user a client on first sign-in and serves `POST https://api.openai.com/v1/responses`, but refuses `instructions`, `reasoning`, `text.format`, `max_output_tokens` and `tools`, and has no device-code flow. The Codex CLI's public client id reaches `chatgpt.com/backend-api/codex`, which takes all of those, lists richer model metadata and offers device code; Unsloth Studio ships it as its default. Anthropic's terms forbid the equivalent for Claude plans outright. The API and both workers each resolve the chat model, and OpenAI rotates refresh tokens. As built: [ChatGPT subscription](../architecture/chatgpt-subscription.md).

## Decision

- Sign in only through OpenAI's open-source flow: `client_id=dynamic_agent_client` on first sign-in, PKCE, a loopback redirect on `127.0.0.1` at any port, and the ID token verified against OpenAI's JWKS. The Codex CLI's client id and Codex's backend are not used: they present SurfSense as the Codex CLI on endpoints OpenAI never published for other apps, put users' accounts at the risk of OpenAI enforcing that, hide SurfSense from the per-app caps users set in ChatGPT, and can break with any Codex release.
- A plan is a `provider_connections` row with `auth_kind = 'chatgpt'`. `provider` stays `openai_compatible`, read as "remote connection", and revision `0023` adds `auth_kind`, `oauth_ciphertext` and `token_version` in place, because rebuilding the table cascades into every remote selection.
- Tokens are one Fernet blob under the install secret ([ADR 0018](0018-keychain-envelope-encryption.md)), in SQLite, so the workers reach them. `NULL` is signed out.
- A refresh holds SQLite's write lock across its HTTP call, so one process refreshes and the rest use its token: a rotated refresh token sent twice signs the account out.
- What a connection can fill is one backend rule, keyed by `auth_kind` ([`serves.py`](../../surfsense_local/backend/modules/llm/connections/serves.py)): a plan fills `text_gen` only. Selection, resolution and the model tests enforce it, and every picker reads it as `serves`.
- The request body is `{model, input, store: false, stream: true}`; a caller's token cap, reasoning switch and JSON schema are dropped.

## Consequences

- No client id is shipped in the repo, and nothing has to be applied for.
- Plan models have no reasoning control, structured output, tools or known context window, and there is no device code. A desktop app's browser is on the same machine, so the loopback redirect always works.
- A Codex route can still be added as its own `auth_kind`, opt-in and labelled unofficial, if the maintainers decide its capabilities are worth its risks; nothing here has to be reworked for it.
- A Claude subscription is not offered; Claude stays reachable with an API key.

## Where the code stands

The flow is tested against a fake built from OpenAI's documentation, not yet against a real ChatGPT account ([ChatGPT subscription](../architecture/chatgpt-subscription.md#known-gaps)).
