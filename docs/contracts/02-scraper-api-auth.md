# Contract 2: scraper API auth

How a caller proves it holds an active SurfSense license to the servers that sell scraping: SurfSense's paid plugins on the plugin host, and the hosted scraper API. Frozen for the 2.0 launch.

| Side | Who | Built |
|---|---|---|
| Producer | The plugin host, for every paid plugin ([plugin host](../architecture/plugin-host.md#the-license-check)) | Yes |
| Producer | `surfsense_backend` capabilities routes | No: they keep their PAT auth, and PATs are purged at T+30 (18 Oct 2026) |
| Consumer | The desktop app, calling SurfSense's plugins ([plugins](../architecture/plugins.md#surfsenses-own-plugins)) | Yes |
| Consumer | `surfsense_mcp`, calling the scraper API | No |

The scrapers were to be a paid plugin calling the scraper API ([ADR 0025](../adr/0025-scraper-client-as-paid-plugin.md)); they now run as plugins on the plugin host ([ADR 0054](../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md)), which applies the same rules itself.

## Request

Every request to a producer carries:

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

The client tells the user `reason`, never a bare status.

`revoked` covers Keygen `SUSPENDED` and `BANNED`. `invalid` covers unknown key and policy mismatch. `expired` is Keygen `EXPIRED`.


### The plugin host's `GET /license`

The plugin host also answers the license alone, once for every paid plugin it serves: the same request header, and `200 {"status": "valid"}` in place of the route's normal response, or the refusal above. A host without a paid plugin has no such route and answers `404`.
## Producer rules

Both producers:

- Validate with Keygen `POST /licenses/actions/validate-key`. Cache the result per key for **5 minutes**.
- **Keygen unreachable:** a key validated successfully in the last **24 hours** is still accepted; a key never seen returns `503 {"reason": "license_service_unavailable"}`. Never fail closed for a key that was valid this morning.

The plugin host answers a refusal itself, before the request reaches the plugin. The capabilities routes also:

- Count requests per license (instrumentation only, no cap yet). The plugin host does not count yet.
- Resolve a valid key to a **synthetic user and workspace created for that license on first call** (email = the licensee email from Keygen metadata). Authz, run storage and rate limits then run unchanged against that workspace. Credit metering is off for license callers.
- **No account linking.** The synthetic user is keyed on the license, never matched to a hosted account that happens to share the email. Hosted user data is purged at T+30; these rows are not user data and survive it.

## Consumer rules

- The app sends the imported license's key, a trial's included, on every request to a plugin on SurfSense's plugin host, and to no other host. It does not check the license's expiry: the producer decides. With no license imported it sends no header, and the host answers `401 missing_license`.
- The app makes no request until the user has allowed `plugins.surfsense.com`.
- The app records each `reason` as the plugin's check failure and shows it, with a link to Settings › License. A paid plugin with a refused license is held out of `@` and the agent until a verdict says the license works.
- The app learns the verdict for every paid plugin at once from the plugin host's `GET /license`, below, rather than by listing each one; it falls back to one listing when the route answers `404`.
- Treat `503 license_service_unavailable` as transient: retry later, and do not treat the license as bad.
- MCP sends the same `Authorization: License <key>` header, from `SURFSENSE_LICENSE_KEY`. It does not register the knowledge-base tools in license mode. PATs keep working until the T+30 purge, after which license mode is the only auth.

## Tests each side owns

- Plugin host: each Keygen status maps to the documented status and `reason`, the five-minute cache, the 24-hour grace and its end once a key is refused, and `GET /license` answering once for every paid plugin ([`license_check/tests/`](../../plugins/remote/proprietary/license_check/tests/)).
- App: the key on every request to the plugin host and on none elsewhere, a missing or expired license recorded with its reason, and the verdict asked once of `GET /license`, with a listing when the route is missing ([`test_first_party_plugins.py`](../../surfsense_local/backend/tests/integration/plugins/routes/test_first_party_plugins.py)).
- Backend, once built: each Keygen status maps to the documented status and `reason`; the 24-hour fallback serves a cached key when the Keygen client raises; a first call for an unseen key creates exactly one synthetic user and workspace, and a second call reuses them.
- MCP, once built: a `401` or `403` shows `reason`; a `503` is treated as transient.
