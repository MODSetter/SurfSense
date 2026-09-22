# Plugins

> A plugin is a folder in this repo. A third party adds one by pull request. The desktop app installs it on demand and runs it as its own process for one job.

Shared contract: [`01-protocol.md`](01-protocol.md). Every stream below implements against that file. Do not invent a second wire format.

Adding a capability later: [`02-extending.md`](02-extending.md). A capability is a verb or it is context, and that file says which, what it costs, and how to keep the facade from leaking.

## Workstreams

Same letter can be picked up at the same time. A stream's own files are in order.

| Stream | Files | Owns | Starts from |
|---|---|---|---|
| **SDK** | [`sdk/01-library-and-harness.md`](sdk/01-library-and-harness.md) | `plugins/sdk/`, `plugins/example/`, `plugins/README.md` | the protocol |
| **Runtime** | [`runtime/01-process.md`](runtime/01-process.md) | `surfsense_local/backend/modules/plugins/` runner | the protocol. There is no result import: the plugin wrote through the API while it ran |
| **Catalog** | [`catalog/01-manifest-and-ci.md`](catalog/01-manifest-and-ci.md) then [`catalog/02-install-and-publish.md`](catalog/02-install-and-publish.md) | manifest checker, PR workflow, install, publish workflow | the protocol. `02` needs the manifest rules in `01` |
| **App** | [`app/01-api.md`](app/01-api.md) and [`app/02-screen.md`](app/02-screen.md) | plugin routes, the plugin screen | the route list in `01`. The screen can be built against that list before the routes exist |
| **Python** | [`python/01-interpreter.md`](python/01-interpreter.md) | the interpreter the packaged app spawns | nothing. Other streams use `uv`'s Python until this lands |

**Demo:** SDK harness runs `plugins/example` against a running app, and the API runs the same plugin as a subprocess and its `document.add()` shows up as a note. No GitHub release required for that demo.

**Ship:** catalog publish workflow uploads a real tarball, the app installs it from the bundled catalog, a paid plugin stays locked without a license.

## Locked decisions

| Decision | Choice |
|---|---|
| Where source lives | `plugins/<id>/` in this repo. A third party contributes by pull request. |
| Id | Folder name. `^[a-z][a-z0-9-]{0,63}$`. Unique. Immutable once a version is published. `plugins/RESERVED` plus the prefix `surfsense-` are ours. `author` is a field, not part of the id. |
| Process | One subprocess per run. Not loaded into the API or the worker. |
| Talks to the app | Arguments and environment variables in, the app's own API over loopback while it runs, an exit code out. No socket of ours, no message protocol, no results file. Stdout is logs. |
| Network | The plugin makes its own HTTP calls. `hosts` in `plugin.json` is copied into the catalog and shown. The app does not intercept those calls and Settings → Network does not apply to them. Loopback is not egress and does not belong in `hosts`. |
| Dependencies | `requirements.txt` with `==` pins. CI runs `pip install` into the tarball. The user's machine never runs `pip`. |
| SDK | `plugins/sdk/` in this repo. Not published to PyPI. The app ships that folder next to the plugin interpreter. A plugin tarball does not contain it. |
| License | `free` or `paid`. Community plugins are `free`. `paid` means one of ours, and it installs and runs only with an unexpired `individual` or `team` license. A trial does not unlock it. No price field. |
| Catalog | `catalog.json` is bundled in the installer, so the list is visible with no network. Refreshing it is a separate egress destination, off by default. The plugins themselves are not bundled. |
| What a plugin can do | A facade in the SDK wraps the app's API, so a plugin calls `document.add()` and never a route. The SDK is the public contract; routes stay ours to rename. Complete within `workspace`, `document`, `artifact`, `model`. Never `license`, `egress`, `migration`. |
| Secrets | Names in the manifest. Values go through `shared/secrets.py`. The app puts each one in an environment variable before spawn. |
| What we do not build | A sandbox, a process-count cap, WASM, a socket or message protocol of our own, hot reload, pip or npm on the user's machine, inferring hosts from imports, plugin-authored HTML, payments. The host places an entry in the existing sidebar and draws its form. |

## Caught while specifying

These were not in the design conversation. They are decided here so a developer is not blocked on them.

| Gap | Decision |
|---|---|
| The packaged app has no general Python. API and worker are PyInstaller binaries. | [`python/01-interpreter.md`](python/01-interpreter.md) ships a real interpreter. Plugins run on that, never inside the frozen binaries. |
| A document has to belong to a workspace. | A run is started in a workspace, and its id is in the plugin's environment. Verbs default to it. |
| A note has no way to say which plugin wrote it. `POST /workspaces/{id}/documents` takes `{title, content}` and nothing else, so `document.add()` cannot stamp `pluginId`, `entry`, or `runId`. | `NoteCreate` gains an optional metadata object, set into the `document_metadata` column that already exists, and the SDK fills it from the run's environment. A plugin could lie about it — loopback has no auth — so it is provenance for the user's benefit, not an audit trail. Without it, nothing in the library says where it came from. |
| The API port is chosen at boot, so nothing outside the app knows it. | Electron writes the URL to `~/.surfsense/api-url` when it picks the port. The runner passes it to plugins as `SURFSENSE_PLUGIN_API_URL`; the harness reads the file so an author does not have to find it. |
| A plugin can ignore the facade and call any route, because loopback has no auth. | Accepted. The facade is what we sanction, not what we prevent, and review is the mechanism — the same position we took on not sandboxing. |
| The installer still downloads from GitHub. | That path may follow only `github.com` → `objects.githubusercontent.com`. The plugin's own HTTP is not this path. |
| A fetched `catalog.json` is the trust anchor for every sha256 in it. | The refresh URL is compiled into the app. A catalog entry whose tarball host is not `github.com` or `objects.githubusercontent.com` is rejected. |
| `documents.dedup_key` already exists. | Plugins do not set it. A plugin that wants to skip work it already did calls `document.list()`, or keeps its own record in its data directory. The platform does not define resume or dedup. |

## Out of scope

Sandboxes, memory and process caps, charging by a community author, bundling plugin code in the installer, running a plugin inside the API process, Amazon or Reddit themselves. Those are plugins someone writes after this lands. The example plugin in the SDK stream is the one this work has to ship.
