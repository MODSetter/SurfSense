# Remote plugins: the MCP client

> Owns: `surfsense_local/backend/modules/plugins/mcp_client/`, the OAuth callback route, the egress changes.
> Gateway: [`../core/01-architecture.md`](../core/01-architecture.md). Trust: [`../core/04-trust.md`](../core/04-trust.md). Paid: [`../core/05-paid.md`](../core/05-paid.md). SurfSense's own servers: [`02-surfsense-servers.md`](02-surfsense-servers.md).

## The MCP client

The API carries a small MCP client of its own, as Pi does with [`@earendil-works/pi-mcp`](https://github.com/earendil-works/pi/tree/main/packages/mcp), which does not depend on the official SDK. The app already serves MCP without a library ([agent](../../../architecture/agent.md#surfsenses-tools)), and the packaged API binary stays small.

- **Transport:** Streamable HTTP only, answering both JSON and SSE responses, keeping the `Mcp-Session-Id` a server issues. The legacy SSE transport and stdio are not supported.
- **Protocol:** offers `2025-11-25` and accepts what a server answers down to `2025-03-26`.
- **Requests:** `initialize`, `tools/list` (following its cursor), `tools/call`, `ping`, and the notifications `notifications/cancelled`, `notifications/progress` and `notifications/tools/list_changed`. Resources, prompts, sampling and elicitation wait for [`../core/06-later.md`](../core/06-later.md).
- **Connecting:** on the first call after the app starts, kept while used, dropped after ten minutes idle. A dropped connection reconnects on the next call.
- **Time:** each call carries the caller's deadline ([`../core/03-engines.md`](../core/03-engines.md)). At the deadline the client sends `notifications/cancelled` and the call ends `failed` with `timeout`. Progress notifications are passed up for the step to show.
- **Retries:** connecting, listing and `ping` retry twice on a network error, 408, 429 or 5xx. `tools/call` is never retried, since the server may already have acted.
- **Tool list:** read at connect, on `list_changed`, and when the user opens the plugin's row. What changed is applied as [`../core/02-registry.md`](../core/02-registry.md#tools-added-later) says.

## Signing in

`auth` in the plugin's entry, or what a custom server's first `401` asks for, picks one of four.

| `auth` | What the user does | What the client sends |
|---|---|---|
| `none` | Nothing | Nothing |
| `token` | Pastes a key, labelled with the entry's `title` and `description` | `Authorization: Bearer <key>` |
| `oauth` | Signs in on the publisher's page in their browser | `Authorization: Bearer <access token>` |
| `license` | Nothing beyond holding a SurfSense license | `Authorization: License <key>` ([`../core/05-paid.md`](../core/05-paid.md)) |

OAuth follows MCP's authorization spec, as Pi's client does:

1. The client reads the server's protected resource metadata ([RFC 9728](https://www.rfc-editor.org/rfc/rfc9728)) and the authorization server's metadata ([RFC 8414](https://www.rfc-editor.org/rfc/rfc8414)), and checks the issuer.
2. It identifies itself with a Client ID Metadata Document when the server supports one, otherwise registers dynamically ([RFC 7591](https://www.rfc-editor.org/rfc/rfc7591)), and keeps the client it registered.
3. It opens the authorization URL in the user's browser through Electron, with PKCE and the resource indicator ([RFC 8707](https://www.rfc-editor.org/rfc/rfc8707)).
4. The redirect lands on the API's own loopback address, `http://127.0.0.1:<port>/plugins/oauth/callback`, which already listens there; no extra port.
5. Tokens are stored encrypted in `plugin_credentials` through `shared/secrets.py`, refreshed before they expire or when a call gets `401`. A refresh that fails marks the plugin "Sign in again".

Credentials never reach a model, a log line, a step, or `plugin_calls`.

## Egress

Every host in the entry's `hosts` needs the user's consent before connecting, one row per host as [ADR 0027](../../../adr/0027-egress-consent-per-host.md) requires. For a custom plugin, the URL's host is asked first, and the authorization server's hosts once discovery names them.

- `EgressDeniedError` and its `403` gain `hosts`, every host still to allow, so one prompt asks for them together. `destination` and `host` stay as the first of them, so today's callers do not change. [`egress.md`](../../../architecture/egress.md) is updated in the same change.
- Settings → Network lists a plugin's hosts with its name beside them (`list_destinations()`), and a host already allowed stays listed after the plugin is disconnected.
- A host revoked in Settings → Network makes the plugin's next call a refusal, "Notion's host is not allowed", not a broken connection.
- Fetching the registry adds SurfSense's plugin host to `BUILT_IN` ([`../core/02-registry.md`](../core/02-registry.md#how-the-app-gets-the-registry)).

## Acceptance

- Against a test server: connect, list across two pages, call, receive progress, cancel at the deadline; the server sees `notifications/cancelled`.
- A `tools/call` that fails with a 503 is not retried; a `tools/list` that does is retried twice.
- OAuth against a test authorization server: discovery, dynamic registration, PKCE, the callback on the API's port, a stored token, a refresh on `401`, and "Sign in again" when the refresh fails.
- A plugin whose two hosts are not allowed raises one `403` naming both, and no connection opens.
- No credential appears in a log line, a step or `plugin_calls`.
