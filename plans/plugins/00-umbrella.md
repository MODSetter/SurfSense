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
| Network | The plugin makes its own HTTP calls. `hosts` in `plugin.json` is copied into the catalog and shown. The app does not intercept those calls and Settings → Network does not apply to them. |
| Dependencies | `requirements.txt` with `==` pins. CI runs `pip install` into the tarball. The user's machine never runs `pip`. |
| SDK | `plugins/sdk/` in this repo. Not published to PyPI. The app ships that folder next to the plugin interpreter. A plugin tarball does not contain it. |
| License | `free` or `paid`. Community plugins are `free`. `paid` means one of ours, and it installs and runs only with an unexpired `individual` or `team` license. A trial does not unlock it. No price field. |
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
