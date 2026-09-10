# Contract 4: sunset flag

How the legacy desktop app (`surfsense_desktop` v0.0.40) learns that the hosted service has gone export-only, without shipping any sunset content of its own. The legacy app bundles a frozen copy of `surfsense_web`, so anything baked into it would go stale the day the portal changes; instead it asks one question at startup and, when the answer is yes, shows the live website.

## Endpoint

The existing unauthenticated, rate-limit-exempt `GET /health` on the hosted backend gains two fields:

```json
{"status": "ok", "sunset": false, "sunset_url": "https://surfsense.com/sunset"}
```

| Field | Type | Meaning |
|---|---|---|
| `sunset` | boolean | Mirrors `SUNSET_MODE`. `true` from T-0. |
| `sunset_url` | string, optional | Where to send the user. The app defaults to `https://surfsense.com/sunset` when absent. |

## Producer rules (Dev B)

- Ship the fields returning `false` **before** v0.0.40 is published, so the check has something real to hit.
- `sunset` is read from the `SUNSET_MODE` env flag on every request; no restart needed beyond the flag change.
- `/sunset` must work when loaded inside an Electron `BrowserWindow` with the existing session cookie: no Electron-specific assumptions, no new login step for a signed-in user.

## Consumer rules (Dev A, legacy v0.0.40)

- One `GET /health` on startup against `HOSTED_BACKEND_URL`, 3-second timeout, no retry, no periodic recheck. A flip mid-session takes effect on next launch.
- `sunset === true` → `mainWindow.loadURL(sunset_url)` instead of the bundled localhost frontend.
- Anything else — `false`, missing field, non-2xx, timeout, network error, unparseable body — → start exactly as v0.0.39 did. **Fail open.** A flaky network must never turn the app into a sunset page early.
- The updater is capped below 1.0.0 in the same release (`0.x` releases still install; anything higher is ignored). Nothing else changes.

## Tests each side owns

- Dev B: with `SUNSET_MODE=1` the field is `true`; without it, `false`; the endpoint stays unauthenticated and rate-limit exempt.
- Dev A: a stub backend returning `true` loads the live URL; stubs returning `false`, `{}`, 500, and a connection refusal all start the bundled frontend.
