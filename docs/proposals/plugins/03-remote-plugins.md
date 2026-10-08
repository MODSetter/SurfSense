# Remote plugins

> Owns: `surfsense_local/backend/modules/plugins/mcp_client/`, the OAuth callback route, the egress changes, `plugins/<id>/` and `plugins/proprietary/<id>/` servers SurfSense hosts.
> Gateway: [`01-architecture.md`](01-architecture.md). Trust: [`05-trust.md`](05-trust.md). Paid: [`06-paid.md`](06-paid.md).

## The MCP client

The API carries a small MCP client of its own, as Pi does with [`@earendil-works/pi-mcp`](https://github.com/earendil-works/pi/tree/main/packages/mcp), which does not depend on the official SDK. The app already serves MCP without a library ([agent](../../architecture/agent.md#surfsenses-tools)), and the frozen API stays small.

- **Transport:** Streamable HTTP only, answering both JSON and SSE responses, keeping the `Mcp-Session-Id` a server issues. The legacy SSE transport and stdio are not supported.
- **Protocol:** offers `2025-11-25` and accepts what a server answers down to `2025-03-26`.
- **Requests:** `initialize`, `tools/list` (following its cursor), `tools/call`, `ping`, and the notifications `notifications/cancelled`, `notifications/progress` and `notifications/tools/list_changed`. Resources, prompts, sampling and elicitation wait for [`07-later.md`](07-later.md).
- **Connecting:** on the first call after the app starts, kept while used, dropped after ten minutes idle. A dropped connection reconnects on the next call.
- **Time:** each call carries the caller's deadline ([`04-engines.md`](04-engines.md)). At the deadline the client sends `notifications/cancelled` and the call ends `failed` with `timeout`. Progress notifications are passed up for the step to show.
- **Retries:** connecting, listing and `ping` retry twice on a network error, 408, 429 or 5xx. `tools/call` is never retried, since the server may already have acted.
- **Tool list:** read at connect, on `list_changed`, and when the user opens the plugin's row. What changed is applied as [`02-registry.md`](02-registry.md#tools-added-later) says.

## Signing in

`auth` in the registry entry, or what a custom server's first `401` asks for, picks one of four.

| `auth` | What the user does | What the client sends |
|---|---|---|
| `none` | Nothing | Nothing |
| `token` | Pastes a key, labelled with the entry's `title` and `description` | `Authorization: Bearer <key>` |
| `oauth` | Signs in on the publisher's page in their browser | `Authorization: Bearer <access token>` |
| `license` | Nothing beyond holding a SurfSense license | `Authorization: License <key>` ([`06-paid.md`](06-paid.md)) |

OAuth follows MCP's authorization spec, as Pi's client does:

1. The client reads the server's protected resource metadata ([RFC 9728](https://www.rfc-editor.org/rfc/rfc9728)) and the authorization server's metadata ([RFC 8414](https://www.rfc-editor.org/rfc/rfc8414)), and checks the issuer.
2. It identifies itself with a Client ID Metadata Document when the server supports one, otherwise registers dynamically ([RFC 7591](https://www.rfc-editor.org/rfc/rfc7591)), and keeps the client it registered.
3. It opens the authorization URL in the user's browser through Electron, with PKCE and the resource indicator ([RFC 8707](https://www.rfc-editor.org/rfc/rfc8707)).
4. The redirect lands on the API's own loopback address, `http://127.0.0.1:<port>/plugins/oauth/callback`, which already listens there; no extra port.
5. Tokens are stored encrypted in `plugin_credentials` through `shared/secrets.py`, refreshed before they expire or when a call gets `401`. A refresh that fails marks the plugin "Sign in again".

Credentials never reach a model, a log line, a step, or `plugin_calls`.

## Egress

Every host in the entry's `hosts`, and for a custom plugin the URL's host and the authorization server's, needs the user's consent before connecting, one row per host as [ADR 0027](../../adr/0027-egress-consent-per-host.md) requires.

- `EgressDeniedError` and its `403` gain `hosts`, every host still to allow, so one prompt asks for them together. `destination` and `host` stay as the first of them, so today's callers do not change. [`egress.md`](../../architecture/egress.md) is updated in the same change.
- Settings → Network lists a plugin's hosts with its name beside them (`list_destinations()`), and a host already allowed stays listed after the plugin is disconnected.
- A host revoked in Settings → Network makes the plugin's next call a refusal, "Notion's host is not allowed", not a broken connection.
- Fetching the list adds SurfSense's plugin host to `BUILT_IN` ([`02-registry.md`](02-registry.md#how-the-app-gets-the-list)).

## SurfSense's own servers

SurfSense publishes plugins the same way anyone does, as remote MCP servers listed in the registry with `publisher: surfsense`, and hosts them.

| Where the server's code lives | License | Example |
|---|---|---|
| `plugins/<id>/` | Apache-2.0 | a free plugin, such as a search of a public API |
| `plugins/proprietary/<id>/` | Business Source License 1.1 ([ADR 0047](../../adr/0047-premium-plugins-are-source-available.md)) | `surfsense-scrapers` |

A server is a Python project with its own `pyproject.toml`, tests and `Dockerfile`, built on the official MCP Python SDK: unlike the app, a hosted server has no size limit worth the cost of a client of our own. `surfsense_mcp` is not reused; it stays the server outside clients such as Claude and Cursor connect to with a personal key.

### SurfSense Scrapers

The first paid plugin.

- `plugins/proprietary/surfsense-scrapers/`, a remote MCP server hosted by SurfSense.
- One tool per scraper verb the scraper API has today: web crawl, Google Search, Reddit, YouTube and its comments, Instagram and its details, TikTok and its comments, user search and trending, Google Maps and its reviews, Indeed, Amazon, Walmart and its reviews. Each declares `readOnlyHint: true` and `openWorldHint: true`.
- Each tool calls the hosted scraper API, `POST /workspaces/{id}/scrapers/{platform}/{verb}?mode=async`, with the caller's `Authorization: License <key>` passed through, follows the run's events, and returns a readable summary as text with the items as `structuredContent`. A result too large to return whole gives its run id, and a `get_scraper_run` tool pages through it.
- The scraping itself stays in [`surfsense_backend/app/proprietary/`](../../../surfsense_backend/app/proprietary/), behind the scraper API, with its proxies and captcha solving. The server imports none of it, which keeps it apart from the hosted code until the purge ([sunset](../../architecture/sunset.md)).
- A cancelled call cancels the scraper run (`POST .../runs/{run_id}/cancel`), so nothing keeps scraping after the user stopped it.

It needs license mode on the scraper API ([contract 2](../../contracts/02-scraper-api-auth.md)), which is not built, and an answer to how a license's scraper workspace is found ([README](README.md#open-questions)).

## Acceptance

- Against a test server: connect, list across two pages, call, receive progress, cancel at the deadline; the server sees `notifications/cancelled`.
- A `tools/call` that fails with a 503 is not retried; a `tools/list` that does is retried twice.
- OAuth against a test authorization server: discovery, dynamic registration, PKCE, the callback on the API's port, a stored token, a refresh on `401`, and "Sign in again" when the refresh fails.
- A plugin whose two hosts are not allowed raises one `403` naming both, and no connection opens.
- No credential appears in a log line, a step or `plugin_calls`.
- SurfSense Scrapers: a call with a valid trial license returns items; with an expired one, the scraper API's `reason` reaches the user as the refusal.
