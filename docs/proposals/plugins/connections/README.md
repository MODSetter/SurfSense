---
status: proposed
code:
  - surfsense_local/backend/modules/plugins/
  - surfsense_local/backend/modules/agent/plugin_tools/
  - surfsense_local/backend/modules/agent/opencode_client/
  - surfsense_local/backend/modules/agent/engines/claude_code/
  - surfsense_local/frontend/src/features/plugins/
  - plugins/registry/
  - .github/ISSUE_TEMPLATE/plugin-submit.yml
---

# Connections: any remote MCP server, with any sign-in it uses

> Plugins connect to remote MCP servers over Streamable HTTP, signed in with nothing, OAuth that registers itself, or one key sent as `Authorization: Bearer` ([plugins](../../../architecture/plugins.md)). This proposal lets a plugin connect to any remote server the MCP spec describes, and to the API-key servers it does not: a connection is a transport and one sign-in, detected from the server where it can be. Local servers started by a command are out of scope; they come with [bundles](../bundles/README.md) ([decision](../README.md#local-mcp-servers)).

## Why

Measured on 19 Oct 2026 against 35 public servers, with the discovery the app and the registry check use:

- **Keys in other headers.** Exa reads its key from `x-api-key`; others use `Authorization: Api-Key …`, Basic, or several headers. The app sends a key only as `Authorization: Bearer`, so these fail at connect.
- **OAuth that needs a registered app.** 24 of 29 OAuth servers let SurfSense register itself, by client ID metadata document (CIMD) or dynamic registration (DCR): Notion, Linear, Sentry, Stripe, Atlassian, Figma, Canva and the rest. Five do not: GitHub, Slack, HubSpot, Box and Asana. Each wants a client registered in advance, and each requires a client secret at the token step, which an app SurfSense ships cannot hold.
- **Legacy SSE.** A server that offers only the 2024-11-05 HTTP+SSE transport cannot be connected.
- **More access mid-session.** A server answering `403 insufficient_scope` once a tool needs more is reported as a failure, not as a sign-in to repeat.
- **One field for everything.** The Add custom plugin dialog has Name, URL and an optional Key, so the user cannot say how a key is sent.

## What the spec says

From the [authorization spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) and the [transports spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), 2025-11-25:

- Two standard transports, stdio and Streamable HTTP. A client supporting old servers POSTs an `InitializeRequest`, and on `400`, `404` or `405` GETs the same URL for an SSE stream.
- A client registers in this order: a pre-registered client it holds; CIMD (SHOULD); DCR (MAY, for backward compatibility); else **prompt the user for client information**, after they register an OAuth client themselves. Clients SHOULD support static client credentials, hardcoded or entered by the user.
- Discovery tries RFC 8414 and OpenID Connect metadata, both MUST.
- A token goes only in `Authorization: Bearer`, and MUST NOT go in the URL query.
- On `403` with `error="insufficient_scope"`, a client acting for a user SHOULD sign in again with the scopes the challenge names.
- Two opt-in [extensions](https://modelcontextprotocol.io/extensions/auth/overview): OAuth Client Credentials, machine to machine, and Enterprise-Managed Authorization, through a company's identity provider.

API keys in headers are not in the spec, but most keyed servers use them.

## Out of scope

| Left out | Why |
|---|---|
| Local servers started by a command (stdio) | [Decided](../README.md#local-mcp-servers): they come with bundles |
| A key in the URL, as a query parameter or a path segment | The spec forbids tokens in the URL; a URL is stored and shown in the clear. A custom plugin's URL is still kept as typed, with a warning ([below](#the-dialog)) |
| OAuth Client Credentials | For services and pipelines with no user, not a person on a desktop |
| Enterprise-Managed Authorization | Needs a company identity provider; belongs with [organisation policy](../README.md#organisation-policy) |
| Custom transports, such as WebSocket | Not standard; a server offering only one cannot be connected |
| An authorization server that allows only clients it lists | The server's choice; nothing on SurfSense's side gets in |
| Sign-in that is neither OAuth nor fixed headers: request signing (AWS SigV4, HMAC), client certificates, device code only | Every request carries the same headers |

## The model

A plugin's connection is a **transport** and **one sign-in**.

| Transport | Sent as |
|---|---|
| `streamable_http` | Today's |
| `sse` | The 2024-11-05 HTTP+SSE transport, chosen only by [detection](#detection) |

| Sign-in | For | Kept, encrypted | Sent |
|---|---|---|---|
| `none` | Open servers | Nothing | Nothing |
| `headers` | Any key: `Authorization: Bearer`, `x-api-key`, `Api-Key`, Basic, several at once | Each header's name and value | Exactly those headers on every request |
| `oauth` | A server naming an authorization server | Tokens, and the client the sign-in used | `Authorization: Bearer <access token>` |

`oauth` has two ways to register, chosen as the spec orders them:

- **Automatic**, today's: CIMD when packaged, DCR in a developer's build, or a listed entry's `client_id`.
- **Your own app**, new: the user registers an OAuth app with the provider, using the callback the dialog shows, and enters its client ID, a client secret if the provider gives one, and scopes if they want fewer. The secret is the user's, from their own registration, so it is kept like a key and never ships in the app.

Today's key becomes a `headers` sign-in holding one row, `Authorization: Bearer <key>`, so nothing changes for a plugin already connected.

## Detection

`POST /plugins/custom/probe` with a URL, before anything is stored, answers what the server needs. The dialog and the registry check use the same steps:

1. POST an `InitializeRequest`. `200` → **Streamable HTTP**, then list the tools: a list → **no sign-in**, with the tool count.
2. `401` → find an authorization server, by protected resource metadata (RFC 9728), then RFC 8414 and OpenID Connect metadata on the issuer.
   - Found, with CIMD or DCR → **OAuth, automatic**.
   - Found, with neither → **OAuth, your own app**.
   - None → **a key**, offered as one `Authorization: Bearer` row.
3. `400`, `404` or `405` → GET the URL for an SSE stream. An `endpoint` event → **SSE**, and the steps above repeat over it. Otherwise → "This address doesn't answer as an MCP server".
4. `403` → **a key**, as for `401` with no authorization server.
5. Unreachable → today's `plugin_unreachable`.

Detection only suggests. Every sign-in stays reachable in the dialog, because a server can take an optional key while answering `200`.

## The dialog

```
┌─ Add an MCP server ───────────────────────────────────────────┐
│ Name                                                          │
│ [ Team wiki                                             ]     │
│ Server URL                                                    │
│ [ https://mcp.example.com/mcp                           ]     │
│                                            [ Check ]          │
│ ───────────────────────────────────────────────────────────── │
│ No sign-in needed · 12 tools                                  │
│   ▸ Add headers                                               │
│                                                               │
│ — or —                                                        │
│ Signs in with your account                                    │
│   [ Sign in with browser ]                                    │
│   ▸ Use your own OAuth app                                    │
│       Client ID      [                                  ]     │
│       Client secret  [ ••••••••                         ]     │
│       Scopes         [ optional                         ]     │
│       Callback: https://plugins.surfsense.com/oauth/callback  │
│                                                               │
│ — or —                                                        │
│ Needs a key                                                   │
│   Header             Value                                    │
│   [ Authorization ]  [ Bearer ••••••••••••••          ]  ✕    │
│   + Add header                                                │
│                                                               │
│                                  [ Cancel ]  [ Connect ]      │
└───────────────────────────────────────────────────────────────┘
```

- **Check** runs [detection](#detection) and shows one panel. The other sign-ins stay one click away under it.
- Header values are password fields, and are never sent back to the screen once saved.
- A URL holding something shaped like a key, such as `key=`, `token=`, `apikey=` or `api_key=` in its query, shows: "This address looks like it contains a key. Keys in an address are stored in the clear; move it to a header if the server allows." Connecting is still allowed.
- The callback shown is the one the app signs in with: the plugin host's page when packaged, the loopback one in a developer's build ([OAuth client](../../../architecture/plugins.md#signing-in-with-oauth)).
- Leaving out Claude Code's form: a transport chosen by hand, which detection replaces, and a project or user scope, since SurfSense's plugins belong to the app.

A plugin's details gain **Edit headers** in place of **Replace key**, and **Use your own OAuth app** beside **Sign in again** for an OAuth plugin. **Needs more access** is a new status, with **Sign in again**.

## The app

### Storage

No new column. `installed_plugins` holds both parts already:

- `credential_kind` is `headers`, `oauth` or `license`. A row reading `token` is read as one `Authorization: Bearer` header and written back as `headers` the next time it changes.
- `credential_ciphertext` holds, encrypted: a `headers` list of `{name, value}`; or the OAuth credential, which gains the user's own client, `client_id`, `client_secret` and `scopes`, beside the tokens and the registered client it holds now.
- `entry.transport` is `streamable_http` or `sse`, recorded at connect. An entry without one is `streamable_http`.

### Sending

- `sign_in_headers()` returns the stored headers, or `Authorization: Bearer` with the access token. It returns a map already, so its callers do not change.
- The MCP client opens the transport the entry records: `streamable_http_client` today, the SDK's SSE client for `sse`.
- **opencode** is given `headers` as now, and `oauth: false`. It has no SSE type of its own in its documented config; whether its `remote` type connects to an SSE server is the first thing to measure ([open questions](#open-questions)).
- **Claude Code** is given `"type": "sse"` for an SSE plugin, in place of `"http"`.
- `stop_plugin_calls` finds a plugin's calls by its origin and `authorization` header. A `headers` plugin may send no `authorization`, so it matches by plugin id instead.

### OAuth

- **Your own app.** The sign-in uses the stored client as a pre-registered one, its token endpoint method being `client_secret_post` when the user gave a secret and `none` when they did not. Refreshing uses it the same way: `token_refresh.py` handles both methods already.
- **Discovery.** `oauth_discovery.py`, the first discovery that decides which hosts to ask about, also tries OpenID Connect metadata, as the spec requires and the SDK's own sign-in already does.
- **More access.** A `403` with `insufficient_scope` while listing or calling records `check_failure = needs_scope`, with the scopes the challenge names. Sign in again asks for those scopes as well as the ones held.

### Routes

| Route | Change |
|---|---|
| `POST /plugins/custom/probe` | New: `{url}` → `{transport, sign_in, tools?, oauth: {registration: "automatic" \| "own_app"}?}`. Stores nothing |
| `POST /plugins/custom` | `{name, url, sign_in}`. `sign_in` is `{kind: "none"}`, `{kind: "headers", headers: [{name, value}]}` or `{kind: "oauth", client?: {client_id, client_secret?, scopes?}}`. `token` is still accepted, as one Bearer header |
| `PUT /plugins/{id}/headers` | New, replacing the key route for a `headers` plugin; the values are never read back |
| `POST /plugins/{id}/sign-in` | Takes an optional `client`, to switch to your own app |

New refusals, each worded in [`refusal-message.ts`](../../../../surfsense_local/frontend/src/features/plugins/refusal-message.ts): `plugin_not_mcp`, for no MCP on either transport; `plugin_header_not_allowed`; and `plugin_oauth_needs_client`, when a sign-in can neither register itself nor use a client the user gave.

### Rules for headers

- A name is an HTTP token, at most 64 characters; a value is at most 4 KB with no line break. At most 10 headers.
- Names the transport owns are refused: `Host`, `Content-Length`, `Content-Type`, `Accept`, `Connection`, `Transfer-Encoding`, `Mcp-Session-Id`, `MCP-Protocol-Version`, `Last-Event-ID`, `Cookie`.
- Values are never logged, never returned by a route, and never in an error. A server's answer is never echoed into a refusal.
- Headers go only to the plugin's own URL. A sign-in's other hosts get OAuth requests, never the plugin's headers.

## The registry

The registry stays remote servers only. An entry gains, all optional, so today's list stays valid:

```json
"transport": "sse",
"auth": { "type": "headers",
          "headers": [ { "name": "x-api-key", "label": "Exa API key",
                         "description": "Create one under API keys on exa.ai." } ] }
```

```json
"auth": { "type": "oauth", "user_client": true }
```

- `auth.type` gains `headers`: a list of `{name, prefix?, label?, description?}`. The user types each value when connecting, so an entry names a header and never holds a value. `token` stays, read as one `Authorization` header with prefix `Bearer `.
- `oauth.user_client: true` marks a sign-in that takes only registered clients. Connecting it asks the user for their own app first. `client_id` stays, for a provider that registers SurfSense in advance as a public client.
- `transport` is `streamable_http`, the default, or `sse`.

The app's [`list_entry.py`](../../../../surfsense_local/backend/modules/plugins/lists/list_entry.py) and the check's entry rules read the same fields. An older app ignores fields it does not know, so a `headers` entry would show there as needing no sign-in; such an entry carries `min_app_version`.

### The submission bot and form

- **Detection** is the registry check's: the bot records `transport` and `auth`, and a sign-in that cannot register itself becomes `oauth` with `user_client: true`, in place of today's problem. The form's **OAuth client ID** question goes.
- **A key server** answers `401` the same whichever header it reads, so the bot cannot tell `x-api-key` from Bearer. The form gains one optional question, **Header your server reads its key from**, defaulting to `Authorization: Bearer`. It asks a header's name, never a key ([open questions](#open-questions)).
- `live` connects over the entry's transport, and for a `headers` entry expects what a key server answers: `401`, or another `4xx` as a warning.

## Security

- Every value a user types, header values and client secrets, is encrypted at rest as keys are now, and leaves the computer only for the plugin's URL, or the provider's token endpoint for a client secret.
- Egress consent is unchanged: a plugin's URL host and its sign-in hosts are asked about before any request reaches them.
- A client secret is the user's own app's. If it leaks, it reaches that app alone, which the user can revoke at the provider.
- SSE is the 2024-11-05 transport. Its endpoint event names the URL for posting messages, and that URL must be on the plugin's own host: a different host is refused, so a server cannot point SurfSense somewhere the user did not allow.

## Tests

- **Backend, seams at the routes and the MCP client:**
  - each sign-in stored, sent and never read back;
  - a `token` row read as a Bearer header;
  - header rules;
  - detection against loopback servers for each branch: open, keyed, OAuth automatic, OAuth with neither registration, SSE only, not MCP;
  - your own app's sign-in and refresh, with and without a secret;
  - `insufficient_scope` to `needs_scope`;
  - the SSE endpoint event refused off host;
  - the runtime handoff for both engines.
- **Frontend:** the dialog's three panels from a probe, header rows, your own app, the URL key warning, Edit headers, Needs more access.
- **Registry check:** the new entry rules, the bot's detection of each kind, `user_client` in place of the client-ID problem, `live` over SSE.
- **Live**, by a maintainer once, not in CI:
  - Exa with `x-api-key`;
  - an SSE-only server;
  - Notion, automatic;
  - GitHub with the maintainer's own OAuth app;
  - one DCR server that does not list `none` among its token endpoint auth methods, Supabase or Figma.

## Order

Each step works on its own:

1. **Headers.** Storage, sending, the custom route, Edit headers, `stop_plugin_calls`.
2. **SSE.** Detection's fallback, the transport recorded and sent to both engines.
3. **OAuth: your own app, OpenID discovery, more access.**
4. **The dialog**, with probe and every panel, translated.
5. **The registry:** entry fields, the app reading them, the bot, the form and `live`.
6. **Docs.** `plugins.md`, `plugin-registry.md` and the registry README, an ADR for the connection model, and the Known gaps each step closes.

## Open questions

- **opencode and SSE.** Whether opencode's `remote` type connects to an SSE-only server. If it does not, an SSE plugin reaches Claude Code threads only, or waits.
- **The key-header question on the submission form.** Kept as one optional question, or left to the reviewer to set in the pull request.
- **DCR without `none`.** Supabase, Vercel, Figma and GitLab list only client-secret methods for the token endpoint. Registering with `none` may be refused, or may return a secret for this install, which the app can already use. Measured once on a live sign-in.
- **A key in a custom plugin's URL.** Warned about and kept as typed, or refused for an address the server also accepts in a header.
