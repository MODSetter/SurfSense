# Contract 2: scraper API auth

How the app (and, via PAT, MCP) proves it holds an active license when calling the hosted scraper API. Frozen now; enforced from T+7 (v1.1.0). Until then the capabilities routes keep their existing PAT auth unchanged.

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

The app shows `reason` to the user verbatim (mapped to copy), and disables the scraper toggle on `403` until a new license file is imported.

`revoked` covers Keygen `SUSPENDED` and `BANNED`. `invalid` covers unknown key and policy mismatch. `expired` is Keygen `EXPIRED`.

## Producer rules (Dev B)

- Validate with Keygen `POST /licenses/actions/validate-key`. Cache the result per key for **5 minutes**.
- **Keygen unreachable:** a key validated successfully in the last **24 hours** is still accepted; a key never seen returns `503 {"reason": "license_service_unavailable"}`. Never fail closed for a key that was valid this morning.
- Count requests per license (instrumentation only, no cap in v1.1.0).
- MCP: PAT auth stays, gated on the PAT owner having an active license. Same three `403` reasons.

## Consumer rules (Dev A)

- Send the header only when the scraper egress toggle is on and a license is stored. Otherwise the client is inert and makes no request.
- Treat `503 license_service_unavailable` as transient: retry later, do not disable the toggle.

## Tests each side owns

- Dev B: each Keygen status maps to the documented status and `reason`; the 24-hour fallback serves a cached key when the Keygen client raises.
- Dev A: a `403` disables the toggle and surfaces `reason`; no request is made when the toggle is off.
