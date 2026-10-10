# Paid plugins

> Owns: the `access` rules, the license header, `plugins/remote/proprietary/`, which license SurfSense's plugin code is under, how Settings → Plugins shows a paid plugin.
> Decision: [ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md). License: [ADR 0019](../../../adr/0019-offline-licenses.md), [license in the app](../../../architecture/license/app.md). License checks on the server: [contract 2](../../../contracts/02-scraper-api-auth.md).

Who publishes a plugin and whether it costs money are separate questions.

| | Free | Paid |
|---|---|---|
| **SurfSense** | `access: free`. Code in `plugins/remote/<id>/`, Apache-2.0 | `access: license`, unlocked by the SurfSense license key, checked by SurfSense's server. Code in `plugins/remote/proprietary/<id>/`, Business Source License 1.1 |
| **Partner or community** | `access: free` | `access: external`: the publisher prices, sells and checks access on its own service. SurfSense takes no payment and never sees what the user bought |

## The license is checked on the server, never in the app

Whether a user may use a paid plugin is decided by the plugin's server on every call. The app holds no rule about plans, trials or expiry; it carries the key and shows the server's answer. A check in the open-source app could be removed by anyone, so it would add nothing.

- The plugin's entry in the built-in list has `publisher: surfsense`, `access: license` and `auth: { "type": "license" }`. Only the built-in list can carry them: the registry check refuses them, and the app drops them from a fetched registry ([`02-registry.md`](02-registry.md#two-lists)).
- When the user has imported a license file, the gateway sends `Authorization: License <key>`, the key from the file as contract 2 defines it, on every request to the plugin's server. It is an ordinary HTTP header, which MCP's HTTP transport carries like any other, not a change to MCP. With no license file, it sends the request without the header.
- The server validates the key with Keygen on every call, as contract 2's producer rules say: a result cached for five minutes, a key validated in the last 24 hours still accepted while Keygen is unreachable, and a key never seen refused with `503 license_service_unavailable` then.
- A refusal comes back as contract 2 defines it: `401 missing_license`, or `403` with `expired`, `invalid` or `revoked`. The gateway turns it into the tool's refusal, the sentence the user reads, with a link to Settings → License; `503` is shown as temporary and retried on the next call.
- Connect is never disabled for a missing license. Connecting works; the first call, or `tools/list` when the server refuses it, says what is missing.
- Settings → Plugins labels the entry "License required", from its `access`, as information for the user, not as a check.
- The key goes only to plugins from the built-in list, and only to a SurfSense host compiled into the app: the plugin host for a remote plugin ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md#the-plugin-host)), and, when bundles come, the license server that delivers a paid bundle ([ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md)). A built-in entry pointing anywhere else fails the check, and the gateway refuses it before any request, so a mistaken entry cannot send the key away. This guards the key; it does not decide access.
- A trial unlocks paid plugins for its term, because the server accepts a trial key ([ADR 0025](../../../adr/0025-scraper-client-as-paid-plugin.md), still in force on this point).

## Which license a SurfSense plugin is under

Price and license are separate questions. A plugin's `access` decides the price; the folder decides the license.

| Folder | License |
|---|---|
| `plugins/remote/proprietary/` | Business Source License 1.1 |
| Everything else in `plugins/`: the host, `mcp_server/`, the registry, free plugins | Apache-2.0 |

- Code goes under `proprietary/` when it is what someone could compete with SurfSense on: the scrapers and the license check today. Everything a free plugin might need stays Apache-2.0.
- So a free plugin is usually Apache-2.0, and a paid one Business Source License. The exception is a free plugin built on paid code, or one meant to become paid: it starts under `proprietary/` with `access: free`, because Apache-2.0 code once published cannot be closed again.
- Apache-2.0 code never imports from `proprietary/`. A check in the plugin pull-request workflow fails any import that does.
- Code SurfSense owns can move out of `proprietary/` to Apache-2.0 at any time, by moving its folder. Each released version also turns Apache-2.0 four years after release, as the license's change date says. Moving the other way works only for code never published under Apache-2.0.

## Where their code lives

```
plugins/remote/proprietary/
  LICENSE      Business Source License 1.1, as surfsense_backend/app/proprietary/LICENSE
  license/     the Keygen check every SurfSense paid plugin uses
  scrapers/    the scrapers plugin and the scraping code it runs
```

- The root [`LICENSE`](../../../../LICENSE) names only `surfsense_backend/app/proprietary/` as BSL today. It needs a second line naming `plugins/remote/proprietary/`, and a maintainer has to approve that change before any code lands there.
- `CODEOWNERS` gives `plugins/remote/proprietary/` to the maintainers, as AGENTS.md treats `surfsense_backend/app/proprietary/`.
- Paid plugins run on the plugin host beside the free ones ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md#the-plugin-host)).
- A SurfSense paid bundle, when bundles come, would live in `plugins/bundles/proprietary/`, with a third line in the root `LICENSE`.

## Third parties' paid plugins

- `access: external` with an `access_note` the user reads before connecting, such as "Requires a Notion Plus plan".
- The user signs in with the publisher (`oauth`) or pastes the publisher's key (`token`). The publisher's server decides what the user may do, and its refusal reaches the user as the tool's error.
- The SurfSense license key never reaches a third-party server.

## Acceptance

- With no license file, SurfSense Scrapers connects; its first call is refused by the server with `missing_license`, and the step says a license is needed and links to Settings → License.
- With a trial license, its tools run; after the trial's expiry the server refuses the next call with `expired`, and the step says so.
- The app contains no expiry or plan check for plugins: a license file edited to look valid gets the server's refusal.
- A built-in entry with `auth: license` on a host other than the compiled one fails the check, and no request carries the key.
- A registry entry with `access: license` or `auth: license` fails the registry check.
- A partner plugin with `access: external` shows its note before Connect, and its requests carry the user's partner credentials and never the license key.
- A file outside `plugins/remote/proprietary/` that imports from it fails the plugin pull-request check.
