# Contract 2: scraper API auth

How the paid scraper plugin and MCP prove they hold an active license when calling the hosted scraper API. Frozen for the 2.0 launch; not implemented on either side yet. Until it is, the capabilities routes keep their PAT auth, and PATs are purged at T+30 (18 Oct 2026). The client side is a `paid` plugin rather than code in the app ([ADR 0025](../adr/0025-scraper-client-as-paid-plugin.md)).

## Request

Every request to a capabilities route carries:

```
Authorization: License <key>
```

`<key>` is `data.attributes.key` from the license file (contract 1), verbatim.

## Responses

| Status | When | Body |
|---|---|---|
| `401` | Header missing, wrong scheme, or empty key | `{"reason": "missing_license"}` |
| `403` | Key known to Keygen but not usable | `{"reason": "expired" \| "invalid" \| "revoked"}` |
| `2xx` | Key valid | the route's normal response |

The client passes `reason` on to the user verbatim. For the plugin, that means writing it to stderr, which the run keeps as its log tail and shows ([plugins protocol](../proposals/plugins/01-protocol.md)).

`revoked` covers Keygen `SUSPENDED` and `BANNED`. `invalid` covers unknown key and policy mismatch. `expired` is Keygen `EXPIRED`.

## Producer rules (`surfsense_backend` capabilities routes)

- Validate with Keygen `POST /licenses/actions/validate-key`. Cache the result per key for **5 minutes**.
- **Keygen unreachable:** a key validated successfully in the last **24 hours** is still accepted; a key never seen returns `503 {"reason": "license_service_unavailable"}`. Never fail closed for a key that was valid this morning.
- Count requests per license (instrumentation only, no cap yet).
- Resolve a valid key to a **synthetic user and workspace created for that license on first call** (email = the licensee email from Keygen metadata). Authz, run storage and rate limits then run unchanged against that workspace. Credit metering is off for license callers.
- **No account linking.** The synthetic user is keyed on the license, never matched to a hosted account that happens to share the email. Hosted user data is purged at T+30; these rows are not user data and survive it.

## Consumer rules (the paid scraper plugin and `surfsense_mcp`)

How the plugin receives the key is an open question in the [plugins proposal](../proposals/plugins/README.md).

- The app runs the plugin only while it holds an unexpired license, a trial included, and only after the user has allowed the scraper API's host. Otherwise no request is made.
- Treat `503 license_service_unavailable` as transient: retry later, and do not treat the license as bad.
- MCP sends the same `Authorization: License <key>` header, from `SURFSENSE_LICENSE_KEY`. It does not register the knowledge-base tools in license mode. PATs keep working until the T+30 purge, after which license mode is the only auth.

## Tests each side owns

- Backend: each Keygen status maps to the documented status and `reason`; the 24-hour fallback serves a cached key when the Keygen client raises; a first call for an unseen key creates exactly one synthetic user and workspace, and a second call reuses them.
- Plugin: a `401` or `403` makes the plugin exit non-zero with `reason` on stderr, so the run fails and its log tail shows the reason; a `503` is treated as transient.
