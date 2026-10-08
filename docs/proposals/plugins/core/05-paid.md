# Paid plugins

> Owns: the `access` rules, the license header, `plugins/proprietary/`, how Settings → Plugins shows a paid plugin.
> Decision: [ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md). License: [ADR 0019](../../../adr/0019-offline-licenses.md), [license in the app](../../../architecture/license/app.md). License checks on the server: [contract 2](../../../contracts/02-scraper-api-auth.md).

Who publishes a plugin and whether it costs money are separate questions.

| | Free | Paid |
|---|---|---|
| **SurfSense** | `access: free`. Server in `plugins/<id>/`, Apache-2.0 | `access: license`, unlocked by the SurfSense license key, checked by SurfSense's server. Server in `plugins/proprietary/<id>/`, Business Source License 1.1 |
| **Partner or community** | `access: free` | `access: external`: the publisher prices, sells and checks access on its own service. SurfSense takes no payment and never sees what the user bought |

## The license is checked on the server, never in the app

Whether a user may use a paid plugin is decided by the plugin's server on every call. The app holds no rule about plans, trials or expiry; it carries the key and shows the server's answer. A check in the open-source app could be removed by anyone, so it would add nothing.

- The registry entry has `publisher: surfsense`, `access: license` and `auth: { "type": "license" }`. The check refuses `license` on any other publisher.
- When the user has imported a license file, the gateway sends `Authorization: License <key>`, the key from the file as contract 2 defines it, on every request to the plugin's server. With no license file, it sends the request without the header.
- The server validates the key with Keygen on every call, as contract 2's producer rules say: a result cached for five minutes, a key validated in the last 24 hours still accepted while Keygen is unreachable, and a key never seen refused with `503 license_service_unavailable` then.
- A refusal comes back as contract 2 defines it: `401 missing_license`, or `403` with `expired`, `invalid` or `revoked`. The gateway turns it into the tool's refusal, the sentence the user reads, with a link to Settings → License; `503` is shown as temporary and retried on the next call.
- Connect is never disabled for a missing license. Connecting works; the first call, or `tools/list` when the server refuses it, says what is missing.
- Settings → Plugins labels the entry "License required", from the registry's `access`, as information for the user, not as a check.
- The key goes only to SurfSense's plugin host ([`02-registry.md`](02-registry.md#how-the-app-gets-the-registry)), compiled into the app. An entry pointing anywhere else is refused before any request, so a mistaken or tampered entry cannot send the key away. This guards the key; it does not decide access.
- A trial unlocks paid plugins for its term, because the server accepts a trial key ([ADR 0025](../../../adr/0025-scraper-client-as-paid-plugin.md), still in force on this point).

## Where their code lives

```
plugins/proprietary/
  LICENSE                     Business Source License 1.1, as surfsense_backend/app/proprietary/LICENSE
  surfsense-scrapers/         the scrapers plugin: its server and the scraping code it runs
```

- The root [`LICENSE`](../../../../LICENSE) names only `surfsense_backend/app/proprietary/` as BSL today. It needs a second line naming `plugins/proprietary/`, and a maintainer has to approve that change before any code lands there.
- `CODEOWNERS` gives `plugins/proprietary/` to the maintainers, as AGENTS.md treats `surfsense_backend/app/proprietary/`.
- Everything under it is under the Business Source License. Each paid plugin is its own container ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md)).

## Third parties' paid plugins

- `access: external` with an `access_note` the user reads before connecting, such as "Requires a Notion Plus plan".
- The user signs in with the publisher (`oauth`) or pastes the publisher's key (`token`). The publisher's server decides what the user may do, and its refusal reaches the user as the tool's error.
- The SurfSense license key never reaches a third-party server.

## Acceptance

- With no license file, SurfSense Scrapers connects; its first call is refused by the server with `missing_license`, and the step says a license is needed and links to Settings → License.
- With a trial license, its tools run; after the trial's expiry the server refuses the next call with `expired`, and the step says so.
- The app contains no expiry or plan check for plugins: a license file edited to look valid gets the server's refusal.
- A registry entry with `auth: license` on a host outside the compiled list is refused, and no request carries the key.
- A community entry with `access: license` fails the registry check.
- A partner plugin with `access: external` shows its note before Connect, and its requests carry the user's partner credentials and never the license key.
