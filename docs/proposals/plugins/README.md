---
status: accepted
code:
  - plugins/
  - surfsense_local/backend/modules/plugins/
  - surfsense_local/frontend/src/features/plugins/
  - surfsense_local/electron/scripts/fetch-plugin-python.mjs
  - surfsense_local/electron/scripts/fetch-plugin-catalog.mjs
  - .github/workflows/plugin-check.yml
  - .github/workflows/plugin-publish.yml
  - .github/workflows/plugin-audit.yml
---

# Plugins

> A plugin is a folder in this repo. A third party adds one by pull request. The desktop app installs it on demand and runs it as its own process for one job.

Shared contract: [`01-protocol.md`](01-protocol.md). Every stream below implements against that file. Do not invent a second wire format.

Adding a capability later: [`02-extending.md`](02-extending.md). A capability is a verb or it is context, and that file says which, what it costs, and how to keep the facade from leaking.

One plugin from pull request to uninstall, and who owns each step: [`03-lifecycle.md`](03-lifecycle.md).

## Workstreams

Same letter can be picked up at the same time. A stream's own files are in order.

| Stream | Files | Owns | Starts from |
|---|---|---|---|
| **SDK** | [`sdk/01-library-and-harness.md`](sdk/01-library-and-harness.md) | `plugins/sdk/`, `plugins/example/`, `plugins/README.md` | the protocol |
| **Runtime** | [`runtime/01-process.md`](runtime/01-process.md) | `surfsense_local/backend/modules/plugins/` runner, the `plugins` queue and its worker | the protocol. There is no result import: the plugin wrote through the API while it ran |
| **Catalog** | [`catalog/01-manifest-and-ci.md`](catalog/01-manifest-and-ci.md), then [`catalog/02-publish.md`](catalog/02-publish.md), then [`catalog/03-install.md`](catalog/03-install.md) | manifest checker, build tool, `plugins/targets.json`, PR and publish workflows, install and update | the protocol. `02` builds with the tool in `01`. `03` needs the manifest rules in `01` and can test against a fixture catalog before `02` publishes one |
| **App** | [`app/01-api.md`](app/01-api.md) and [`app/02-screen.md`](app/02-screen.md) | plugin routes, the plugin screen | the route list in `01`. The screen can be built against that list before the routes exist |
| **Python** | [`python/01-interpreter.md`](python/01-interpreter.md) | the interpreter the packaged app spawns, `system_key()` | `plugins/targets.json`, which whichever stream lands first adds. Other streams use `uv`'s Python until this lands |

**Demo:** SDK harness runs `plugins/example` against a running app, and the API runs the same plugin as a subprocess and its `document.add()` shows up as a note. Nothing published is required for that demo.

**Ship:** the publish workflow pushes real tarballs to GitHub Packages, the app installs from the bundled catalog on all three platforms, including a plugin with a compiled dependency, and a paid plugin stays locked without a license.

## Locked decisions

| Decision | Choice |
|---|---|
| Where source lives | `plugins/<id>/` in this repo. A third party contributes by pull request into `dev`. |
| Id | Folder name. `^[a-z][a-z0-9-]{0,63}$`. Unique. Immutable once a version is published. `plugins/RESERVED` plus the prefix `surfsense-` are ours, and a pull request may use one only when its author is the repo's owner or a collaborator. `author` is a field, not part of the id. |
| Publishing | A merged pull request that raises a plugin's version publishes that version from `dev`. No release branch, no desktop release. A published version never changes. |
| Hosting | GitHub Packages on this repo (ghcr.io), for tarballs and the catalog. Never GitHub Releases: installed apps take the newest release on this repo as an app update. |
| Process | One subprocess per run, on its own `plugins` queue. Not loaded into the API or the worker. Never detached, so it stops when the app quits. |
| Talks to the app | Arguments and environment variables in, the app's own API over loopback while it runs, an exit code out. No socket of ours, no message protocol, no results file. Stdout is logs. |
| Network | The plugin makes its own HTTP calls through `http` in the SDK, which refuses a host not in `hosts`. `hosts` is copied into the catalog and shown. Before a plugin's first run, one egress consent prompt asks for every host in `hosts` not yet allowed, and the grants are listed and revocable in Settings → Network. This is a check, not enforcement: the app does not intercept connections, and a plugin that skips `http` is not checked. Loopback is not egress and does not belong in `hosts`. |
| Dependencies | The author writes `requirements.in`; `requirements.txt` is generated from it with every version and file hash. CI installs it for each platform on one Linux runner, from prebuilt wheels only, into the tarball: one `any` tarball when every platform gets the same files, one per platform otherwise. The user's machine never runs `pip` and never compiles. |
| Platforms | `plugins/targets.json` lists the platforms and the Python version. A plugin works on all of them unless its optional `platforms` names fewer. The app lists only plugins it can install. |
| SDK | `plugins/sdk/` in this repo. Not published to PyPI. The app ships that folder next to the plugin interpreter. A plugin tarball does not contain it. Its version lives in `plugins/sdk/VERSION`, which both the SDK and the app read. |
| Code license | Every plugin is Apache-2.0 under the repository's `LICENSE`, ours and contributed alike. A plugin folder carries no license of its own, and a dependency must be one the Apache Software Foundation lets an Apache-2.0 work include. |
| Access | `free` or `paid`. Community plugins are `free`. `paid` means one of ours, and it installs and runs only with an unexpired SurfSense license file: `individual`, `team`, or a `trial` for its term. No price field. |
| Catalog | `catalog.json` is bundled in the installer, so the list is visible with no network. Refreshing it needs the same two hosts as installing, off by default. The plugins themselves are not bundled. |
| Versions on disk | One. An update replaces the installed version and deletes the old one. No rollback. A bad version is yanked, and its author publishes a fix. |
| Limits | 100 MB per tarball unless a maintainer grants more in `plugins/SIZE-EXCEPTIONS`. A run stops at its entry's timeout: 30 minutes unless the entry sets its own, up to 6 hours. |
| What a plugin can do | A facade in the SDK wraps the app's API, so a plugin calls `document.add()` and never a route. The SDK is the public contract; routes stay ours to rename. Complete within `workspace`, `document`, `artifact`, `model`, of which v1 ships `document`; the other three wait for their app routes. Never `license`, `egress`, `migration`. |
| Declared or coded | Whatever the app must know before running a plugin, to show it, check it or ask the user for it, is declared in `plugin.json`. Whatever happens during a run is the plugin's code, through the SDK. The app never runs plugin code to find something out. |
| What the user provides | Two kinds: an input, asked every run, of kind `string`, `number` or `boolean`; and a secret, set once in Settings and never shown again. The app draws both forms from the declarations. Raycast splits arguments and preferences the same way. |
| Secrets | Declared with a title and help text. Values go through `shared/secrets.py`. The app puts each one in an environment variable before spawn and never in a file. |
| Environment | Built from scratch for each run: the plugin's context, its secrets, an operating-system allowlist, and the Python variables. Nothing of the app's own. |
| Growing the SDK | Contributions to the SDK are welcome, starting from a plugin that needs the change. SDK and lifecycle changes get a maintainer's review, enforced by `CODEOWNERS` ([`02-extending.md`](02-extending.md#growing-the-sdk-together)). |
| What we do not build | A sandbox, a network proxy or firewall for plugins, a process-count cap beyond the queue's threads, WASM, a socket or message protocol of our own, hot reload, pip or npm on the user's machine, inferring hosts from imports, plugin-authored HTML, rollback, payments. The host places an entry in the existing sidebar and draws its form. |

## Caught while specifying

These were not in the design conversation. They are decided here so a developer is not blocked on them.

| Gap | Decision |
|---|---|
| The packaged app has no general Python. API and worker are PyInstaller binaries. | [`python/01-interpreter.md`](python/01-interpreter.md) ships a real interpreter. Plugins run on that, never inside the frozen binaries. |
| A document has to belong to a workspace. | A run is started in a workspace, and its id is in the plugin's environment. Verbs default to it. |
| A note has no way to say which plugin wrote it. `POST /workspaces/{id}/documents` takes `{title, content}` and nothing else, so `document.add()` cannot stamp which plugin, entry and run wrote the note. | `NoteCreate` gains an optional metadata object, set into the `document_metadata` column that already exists, and the SDK fills it; the keys are in [`app/01-api.md`](app/01-api.md). A plugin could lie about it — loopback has no auth — so it is provenance for the user's benefit, not an audit trail. Without it, nothing in the library says where it came from. |
| The API port is chosen at boot, so nothing outside the app knows it. | Electron writes the URL to `~/.surfsense/api-url` when it picks the port. The runner passes it to plugins as `SURFSENSE_PLUGIN_API_URL`; the harness reads the file so an author does not have to find it. |
| A plugin can ignore the facade and call any route, because loopback has no auth. | Accepted. The facade is what we sanction, not what we prevent, and review is the mechanism — the same position we took on not sandboxing. |
| A GitHub release on this repo is read by every installed app as an app update. | Plugins publish to GitHub Packages. The app downloads from `ghcr.io` and follows a redirect only to `pkg-containers.githubusercontent.com`, the two hosts install and refresh need. The plugin's own HTTP is not this path. |
| A fetched `catalog.json` is the trust anchor for every sha256 in it. | The refresh reference is compiled into the app. A catalog entry whose `url` is outside `https://ghcr.io/v2/modsetter/surfsense/plugins/` is dropped. |
| Compiled code runs only on the platform and the Python it was built for. | A download key names both, such as `cp312-linux-x64`. Upgrading the app's Python rebuilds the plugins that have compiled code, under the new key. |
| A yank recorded on one catalog entry would be lost when the next version is published. | `yanked` maps each withdrawn version to its reason and survives later versions. |
| A dependency installed into a plain directory skips its `.pth` files, and pywin32 needs one. | The SDK adds `site-packages` with `site.addsitedir()`. |
| A plugin started as its own process group would outlive the app. | The runner never detaches it, so the supervisor's group and tree kill reaches it. Runs left `queued` or `running` become `failed` with `interrupted` at the next start, so nothing starts by itself. |
| A child process inherits its parent's environment, and the worker's holds `SURFSENSE_LOCAL_SECRET`, the key that decrypts every stored API key. | The runner builds each plugin's environment from an allowlist, and a test fails on any `SURFSENSE_LOCAL_` variable reaching a plugin. |
| A secret listed only by name gave the user no idea what to paste or where to get it. | A secret is declared with a title and help text. |
| `documents.dedup_key` already exists. | Plugins do not set it. A plugin that wants to skip work it already did calls `document.list()`, or keeps its own record in its data directory. The platform does not define resume or dedup. |

## Out of scope

Sandboxes, network proxies, memory and process caps, charging by a community author, bundling plugin code in the installer, running a plugin inside the API process, code that runs at install, update or uninstall, Amazon or Reddit themselves. Those are plugins someone writes after this lands. The example plugin in the SDK stream is the one this work has to ship.

## Later, on demand

Ideas that came up while designing, kept here so they are not lost. None is built until a plugin needs it, and each then arrives as [`02-extending.md`](02-extending.md#growing-the-sdk-together) describes, with a maintainer's review.

| Idea | The need it would meet |
|---|---|
| Settings that are not secret, kept and editable in Settings | A plugin configured once, such as the subreddits to follow |
| More input kinds: several lines of text, a choice from a list, a number range, defaults | A run dialog richer than text, number and checkbox |
| Files and folders as inputs, which needs an Electron bridge to the system dialog since Electron 32 removed `File.path` | A plugin that imports a file or a folder |
| `progress()` | A long run showing "120 of 800" rather than a spinner |
| `fail(message)` | A failure shown as a sentence rather than an exit code and a log |
| The interface language, as context | A plugin that writes in the user's language |
| The plugin's own version, as context | A plugin identifying itself to the sites it calls |
| A description per entry | A subtitle in the run dialog |
| Schedules that run an entry by themselves, settings per workspace, icons and categories, a "Test connection" action | Syncing plugins, and a richer plugin list |
| Signing in with OAuth (Google, Reddit, Notion) | The largest gap: until it is designed, a plugin asks for a token as a secret |

Next after v1: the SDK's `http` asks the operating system to verify certificates, through a vendored `truststore`, as pip does by default since 24.2. Until then `http` checks against the system's certificate file. That covers every public site, but not a root a company or the user added to the macOS Keychain, so behind a proxy that inspects HTTPS, a site the browser opens can fail in a plugin. Adding it changes no manifest or protocol field: plugins only start trusting more.

## First paid plugin: the hosted scraper API

The client for the hosted scraper API ships as a `paid` plugin on this system, not as code inside the app ([ADR 0025](../../adr/0025-scraper-client-as-paid-plugin.md)). It is follow-on work: it needs everything above, plus license mode on the scraper API ([contract 2](../../contracts/02-scraper-api-auth.md)), which is not built.

- Its source lives in `plugins/` under a reserved id and is Apache-2.0. The scraper API enforces the license, so there is nothing to hide in the client.
- It declares the scraper API's host in `hosts`, so the user consents before its first run.
- A trial license unlocks it, like any other `paid` plugin.

## Open questions

- How a `paid` plugin gets the license key it sends as `Authorization: License <key>`. The protocol only passes secrets the user sets. The leading answer is one more context variable, passed only to reserved ids, when the scraper plugin is built.
- Whether CI runs a plugin's own `tests/`, and against what. They would need a stub of the app that plugins can import, which the SDK builds for its own tests but does not publish yet.
