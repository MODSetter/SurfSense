---
status: accepted
code:
  - plugins/
  - surfsense_local/backend/modules/plugins/
  - surfsense_local/frontend/src/features/plugins/
  - surfsense_local/electron/scripts/fetch-plugin-python.mjs
---

# Plugins

> A plugin is a folder in this repo. A third party adds one by pull request. The desktop app installs it on demand and runs it as its own process for one job.

Shared contract: [`01-protocol.md`](01-protocol.md). Every stream below implements against that file. Do not invent a second wire format.

## Workstreams

Same letter can be picked up at the same time. A stream's own files are in order.

| Stream | Files | Owns | Starts from |
|---|---|---|---|
| **SDK** | [`sdk/01-library-and-harness.md`](sdk/01-library-and-harness.md) | `plugins/sdk/`, `plugins/example/`, `plugins/README.md` | the protocol |
| **Runtime** | [`runtime/01-process.md`](runtime/01-process.md) then [`runtime/02-calls-and-results.md`](runtime/02-calls-and-results.md) | `surfsense_local/backend/modules/plugins/` runner and result import | the protocol. `02` reads the file `01`'s process leaves behind |
| **Catalog** | [`catalog/01-manifest-and-ci.md`](catalog/01-manifest-and-ci.md) then [`catalog/02-install-and-publish.md`](catalog/02-install-and-publish.md) | manifest checker, PR workflow, install, publish workflow | the protocol. `02` needs the manifest rules in `01` |
| **App** | [`app/01-api.md`](app/01-api.md) and [`app/02-screen.md`](app/02-screen.md) | plugin routes, the plugin screen | the route list in `01`. The screen can be built against that list before the routes exist |
| **Python** | [`python/01-interpreter.md`](python/01-interpreter.md) | the interpreter the packaged app spawns | nothing. Other streams use `uv`'s Python until this lands |

**Demo:** SDK harness runs `plugins/example` on a laptop, and the API runs the same plugin as a subprocess and a `document` result shows up as a note. No GitHub release required for that demo.

**Ship:** catalog publish workflow uploads a real tarball, the app installs it from the bundled catalog, a paid plugin stays locked without a license.

## Locked decisions

| Decision | Choice |
|---|---|
| Where source lives | `plugins/<id>/` in this repo. A third party contributes by pull request. |
| Id | Folder name. `^[a-z][a-z0-9-]{0,63}$`. Unique. Immutable once a version is published. `plugins/RESERVED` plus the prefix `surfsense-` are ours. `author` is a field, not part of the id. |
| Process | One subprocess per run. Not loaded into the API or the worker. |
| Talks to the app | Arguments, environment variables, and a results file. No socket and no request protocol. Stdout is logs. |
| Network | The plugin makes its own HTTP calls. `hosts` in `plugin.json` is copied into the catalog and shown. Before a plugin's first run, the app asks consent for each host in `hosts` with the egress consent prompt, the same way it asks for a remote model endpoint, and the grants are listed and revocable in Settings → Network. The app does not intercept the plugin's connections, so consent covers the hosts a plugin declares, not every call it makes. |
| Dependencies | `requirements.txt` with `==` pins. CI runs `pip install` into the tarball. The user's machine never runs `pip`. |
| SDK | `plugins/sdk/` in this repo. Not published to PyPI. The app ships that folder next to the plugin interpreter. A plugin tarball does not contain it. |
| License | `free` or `paid`. Community plugins are `free`. `paid` means one of ours, and it installs and runs only with an unexpired license: `individual`, `team`, or a `trial` for its term. No price field. |
| Catalog | `catalog.json` is bundled in the installer, so the list is visible with no network. Refreshing it is a separate egress destination, off by default. The plugins themselves are not bundled. |
| Results | The plugin appends them to a file. After the process exits, `kind: "document"` becomes a note in the run's workspace. Any other kind is stored on the run and shown there. The platform does not require documents, and it does not define resume or dedup. |
| Secrets | Names in the manifest. Values go through `shared/secrets.py`. The app puts each one in an environment variable before spawn. |
| What we do not build | A sandbox, a process-count cap, WASM, `host/generate`, hot reload, pip or npm on the user's machine, inferring hosts from imports, plugin-authored HTML, payments. The host places an entry in the existing sidebar and draws its form. |

## Caught while specifying

These were not in the design conversation. They are decided here so a developer is not blocked on them.

| Gap | Decision |
|---|---|
| The packaged app has no general Python. API and worker are PyInstaller binaries. | [`python/01-interpreter.md`](python/01-interpreter.md) ships a real interpreter. Plugins run on that, never inside the frozen binaries. |
| A result needs a shape the app can import. | One JSON object per line in the results file. `document` becomes a note. Anything else is kept on the run. |
| A document has to belong to a workspace. | A run is started in a workspace. Document results are notes in that workspace, then `ingest_document`. |
| The installer still downloads from GitHub. | That path may follow only `github.com` → `objects.githubusercontent.com`. The plugin's own HTTP is not this path. |
| A fetched `catalog.json` is the trust anchor for every sha256 in it. | The refresh URL is compiled into the app. A catalog entry whose tarball host is not `github.com` or `objects.githubusercontent.com` is rejected. |
| `documents.dedup_key` already exists. | Plugin results do not set it. A plugin that wants to skip work it already did uses its data directory. |

## Out of scope

Sandboxes, memory and process caps, charging by a community author, bundling plugin code in the installer, running a plugin inside the API process, Amazon or Reddit themselves. Those are plugins someone writes after this lands. The example plugin in the SDK stream is the one this work has to ship.

## First paid plugin: the hosted scraper API

The client for the hosted scraper API ships as a `paid` plugin on this system, not as code inside the app ([ADR 0025](../../adr/0025-scraper-client-as-paid-plugin.md)). It is follow-on work: it needs everything above, plus license mode on the scraper API ([contract 2](../../contracts/02-scraper-api-auth.md)), which is not built.

- Its source lives in `plugins/` under a reserved id and is Apache-2.0. The scraper API enforces the license, so there is nothing to hide in the client.
- It declares the scraper API's host in `hosts`, so the user consents before its first run.
- A trial license unlocks it, like any other `paid` plugin.

## Open questions

- How a `paid` plugin gets the license key it sends as `Authorization: License <key>`. The protocol only passes secrets the user sets.
- How a pull request that adds one of our own plugins passes the checker. As written in [`catalog/01-manifest-and-ci.md`](catalog/01-manifest-and-ci.md), `check_tree` rejects any id listed in `plugins/RESERVED` or starting with `surfsense-`, yet only a reserved id may be `paid`.
- How a first run asks for several hosts. The run route's 403 names only the first host not yet allowed, and `request()` in `surfsense_local/frontend/src/lib/api.ts` retries once after Allow, so a plugin that declares two or more hosts cannot start through the existing prompt.
- What the catalog refresh and install downloads are called in egress. [`catalog/02-install-and-publish.md`](catalog/02-install-and-publish.md) names two destinations, `plugin_catalog` and `plugin_install`, but a destination is one `host:` row per host since [ADR 0027](../../adr/0027-egress-consent-per-host.md), and `is_destination()` accepts nothing else. Either that rule gains named destinations back, or these become `host:github.com` and `host:objects.githubusercontent.com`, shared with anything else that calls those hosts.
