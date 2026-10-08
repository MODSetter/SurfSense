# Paid plugins

> Owns: the `access` rules, the license header, `plugins/proprietary/`, license state on Settings → Plugins.
> Decision: [ADR 0047](../../adr/0047-premium-plugins-are-source-available.md). License: [ADR 0019](../../adr/0019-offline-licenses.md), [license in the app](../../architecture/license/app.md). Scraper API auth: [contract 2](../../contracts/02-scraper-api-auth.md).

Who publishes a plugin and whether it costs money are separate questions.

| | Free | Paid |
|---|---|---|
| **SurfSense** | `access: free`. Server in `plugins/<id>/`, Apache-2.0 | `access: license`, unlocked by the SurfSense license key. Server in `plugins/proprietary/<id>/`, Business Source License 1.1 |
| **Partner or community** | `access: free` | `access: external`: the publisher prices, sells and checks access on its own service. SurfSense takes no payment and never sees what the user bought |

## SurfSense's paid plugins

- The registry entry has `publisher: surfsense`, `access: license` and `auth: { "type": "license" }`. The check refuses `license` on any other publisher.
- Settings → Plugins shows the license state from `status()` in [`modules/license/service.py`](../../../surfsense_local/backend/modules/license/service.py) on the plugin's row: active or trial with its expiry, or why Connect is disabled (no license, expired, clock untrusted), with a link to Settings → License.
- The gateway sends `Authorization: License <key>`, the key from the license file as contract 2 defines it, on every request to the plugin's server.
- The key goes only to a URL whose host is on a list compiled into the app (SurfSense's own plugin hosts). An entry pointing anywhere else is refused before any request, so a mistaken or tampered registry entry cannot send the key away.
- The license is checked again on each call: a license that expires during a session makes the next call a refusal that names the reason. The server checks it too, and its answer is the one that counts: contract 2's `401` and `403` reasons reach the user as written, and a `503 license_service_unavailable` is shown as temporary.
- A trial unlocks paid plugins for its term ([ADR 0025](../../adr/0025-scraper-client-as-paid-plugin.md), still in force on this point).

## Where their code lives

```
plugins/proprietary/
  LICENSE                     Business Source License 1.1, as surfsense_backend/app/proprietary/LICENSE
  surfsense-scrapers/         the scraper plugin's server
```

- The root [`LICENSE`](../../../LICENSE) names only `surfsense_backend/app/proprietary/` as BSL today. It needs a second line naming `plugins/proprietary/`, and a maintainer has to approve that change before any code lands there.
- `CODEOWNERS` gives `plugins/proprietary/` to the maintainers, as AGENTS.md treats `surfsense_backend/app/proprietary/`.
- What makes a paid plugin worth paying for runs on SurfSense's servers: the scrapers behind the scraper API. The plugin's server is the door to it, and it checks the license.

## Third parties' paid plugins

- `access: external` with an `access_note` the user reads before connecting, such as "Requires a Notion Plus plan".
- The user signs in with the publisher (`oauth`) or pastes the publisher's key (`token`). The publisher's server decides what the user may do, and its refusal reaches the user as the tool's error.
- The SurfSense license key never reaches a third-party server.

## Acceptance

- With no license, SurfSense Scrapers' row says a license is needed, links to Settings → License, and Connect is disabled.
- With a trial license, it connects and its tools run; after the trial's expiry the next call is refused, naming the expiry.
- A registry entry with `auth: license` on a host outside the compiled list is refused, and no request carries the key.
- A community entry with `access: license` fails the registry check.
- A partner plugin with `access: external` shows its note before Connect, and its requests carry the user's partner credentials and never the license key.
