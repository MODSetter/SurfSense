# Remote plugins: the MCP client

> Owns: `surfsense_local/backend/modules/plugins/remote/`: `mcp_client/`, `sign_in/` with the OAuth callback route, and `source.py`; the egress changes.
> Gateway: [`../core/01-architecture.md`](../core/01-architecture.md). Trust: [`../core/04-trust.md`](../core/04-trust.md). Paid: [`../core/05-paid.md`](../core/05-paid.md). SurfSense's own servers: [`02-surfsense-servers.md`](02-surfsense-servers.md).

## The MCP client

SurfSense's own client lists a plugin's tools: when it is connected, and in the checks for changed tools before turns. It calls no tool today; the chat engine adds calling when it is built. The agent's calls go through opencode's own MCP client ([`../core/03-engines.md`](../core/03-engines.md#opencode)).

The API uses the client of the official MCP Python SDK, [`mcp`](https://pypi.org/project/mcp/), pinned to one minor version and used only inside `modules/plugins/remote/`, so a breaking release touches one folder and nothing above the gateway. It adds about 5 MB to the packaged API and brings the parts of MCP that keep growing: OAuth sign-in, new protocol revisions, notifications. The rules below are SurfSense's, whatever the SDK's defaults; where the SDK does not keep one, a thin layer in `remote/` does, and the client's tests check each against the SDK's own server.

- **Transport:** Streamable HTTP only, answering both JSON and SSE responses, keeping the `Mcp-Session-Id` a server issues. The legacy SSE transport and stdio are not supported.
- **Protocol:** the SDK's `auto` mode: it asks a server for `2026-07-28` first and falls back to the `initialize` handshake of `2025-11-25` down to `2025-03-26`, which most servers speak today.
- **Requests:** `initialize` and `tools/list`, following its cursor. `tools/call`, with its progress and cancel notifications, comes with the chat engine; resources, prompts, sampling and elicitation wait for [`../core/06-later.md`](../core/06-later.md).
- **Connecting:** each listing opens its own connection, since the SDK's tasks must close in the task that opened them. A server on the 2025 protocol that forgets the session gets the request again on a new one, which is safe because it handled nothing. Keeping one connection per plugin, dropped after ten minutes idle, waits for a holder task of its own.
- **Retries:** a listing is retried twice on a network error, 408, 429 or 5xx, since it changes nothing on the server. The chat engine's calls, when they come, are never retried, since the server may already have acted.
- **Tool list:** read at connect, on `list_changed`, and when the user opens the plugin's row. What changed is applied as [`../core/02-registry.md`](../core/02-registry.md#tools-added-later) says.

## Signing in

`auth` in the plugin's entry, or what a custom server's first `401` asks for, picks one of four.

| `auth` | What the user does | What the client sends |
|---|---|---|
| `none` | Nothing | Nothing |
| `token` | Pastes a key, labelled with the entry's `title` and `description` | `Authorization: Bearer <key>` |
| `oauth` | Signs in on the publisher's page in their browser | `Authorization: Bearer <access token>` |
| `license` | Nothing beyond holding a SurfSense license | `Authorization: License <key>` ([`../core/05-paid.md`](../core/05-paid.md)) |

OAuth follows MCP's authorization spec, through the SDK's OAuth client:

1. The client reads the server's protected resource metadata ([RFC 9728](https://www.rfc-editor.org/rfc/rfc9728)) and the authorization server's metadata ([RFC 8414](https://www.rfc-editor.org/rfc/rfc8414)), and checks the issuer.
2. It identifies itself with a Client ID Metadata Document when the server supports one, otherwise registers dynamically ([RFC 7591](https://www.rfc-editor.org/rfc/rfc7591)) and keeps the client it registered on the plugin's row. The document is served by SurfSense's plugin host, `plugins.surfsense.com/oauth/client.json`, so every install signs in as the same SurfSense app, and names one redirect URI, below. A provider that registers clients only in advance, as GitHub and Google do, gets SurfSense's app registered with it once, and the plugin's entry carries its `client_id` ([`../core/02-registry.md`](../core/02-registry.md)). Every client is public: PKCE protects the sign-in, and no client secret ships in the app.
3. It opens the authorization URL in the user's browser through Electron, with PKCE and the resource indicator ([RFC 8707](https://www.rfc-editor.org/rfc/rfc8707)).
4. The redirect goes to `https://plugins.surfsense.com/oauth/callback`, one fixed HTTPS address for every provider, which forwards the browser to the API's own loopback address, `http://127.0.0.1:<port>/plugins/oauth/callback`, with the port carried in `state`. The API already listens there, so no extra port, and a port that differs between runs breaks nothing. The page only ever sees a one-time code, useless without the PKCE verifier the app keeps. A sign-in under way when the app restarts fails, and Connect starts it again.
5. Tokens are stored encrypted on the plugin's row in `installed_plugins` through `shared/secrets.py`, refreshed before they expire or when a call gets `401`. A refresh that fails marks the plugin "Sign in again".

Connect asks consent for the plugin's hosts and the authorization server's, then opens the sign-in page; the plugin's row shows "Waiting for sign-in" until the callback arrives, and Cancel abandons it.

opencode can run MCP OAuth itself: on a `401` it discovers, registers, opens the browser and keeps the tokens in a plain file. SurfSense keeps that off (`oauth: false`) and signs in itself, because the user signs in at Connect rather than halfway through a reply, SurfSense's own client lists the tools with the same token, tokens stay encrypted with SurfSense's other credentials, and the authorization server's hosts get consent before any request. opencode only receives the result, as an `Authorization: Bearer` header ([`../core/03-engines.md`](../core/03-engines.md#opencode)).

Credentials never reach a model, a log line, or a step.

## Egress

Every host in the entry's `hosts` needs the user's consent before connecting, one row per host as [ADR 0027](../../../adr/0027-egress-consent-per-host.md) requires. For a custom plugin, the URL's host is asked first, and the authorization server's hosts once discovery names them.

- `EgressDeniedError` and its `403` gain `hosts`, every host still to allow, so one prompt asks for them together. `destination` and `host` stay as the first of them, so today's callers do not change. [`egress.md`](../../../architecture/egress.md) is updated in the same change.
- Settings → Network lists a plugin's hosts with its name beside them (`list_destinations()`), and a host already allowed stays listed after the plugin is disconnected.
- A host revoked in Settings → Network makes the plugin's next call a refusal, "Notion's host is not allowed", not a broken connection. The agent's opencode reaches a plugin only through SurfSense's proxy, which tunnels to a ready plugin's host and refuses the rest ([`../core/03-engines.md`](../core/03-engines.md#asking-and-recording)), so a server off this computer must be on HTTPS.
- Fetching the registry adds SurfSense's plugin host to `BUILT_IN` ([`../core/02-registry.md`](../core/02-registry.md#how-the-app-gets-the-registry)).

## Acceptance

- Against a test server: connect and list across two pages, in JSON and in SSE, with the sign-in on every request.
- A `tools/list` that fails with a 503 is retried twice, and one that keeps failing is refused with its status.
- A 2025 server that forgets the session gets the listing again on a new one.
- OAuth against a test authorization server: discovery, dynamic registration, PKCE, the callback on the API's port, a stored token, a refresh on `401`, and "Sign in again" when the refresh fails.
- A connect whose sign-in is abandoned leaves no plugin and no stored client.
- The callback forwarded from the fixed HTTPS address reaches the loopback port carried in `state`, and a `state` the app did not issue is refused.
- A token refreshed before a turn reaches opencode as the new header.
- A plugin whose two hosts are not allowed raises one `403` naming both, and no connection opens.
- No credential appears in a log line, a step, or an API response.
