---
status: in-progress
code:
  - plugins/
  - surfsense_local/backend/modules/plugins/
  - surfsense_local/frontend/src/features/plugins/
  - surfsense_local/electron/scripts/fetch-plugin-python.mjs
  - surfsense_local/electron/scripts/fetch-plugin-catalog.mjs
  - .github/workflows/release-local.yml
  - .github/workflows/plugins-pull-request-checks.yml
  - .github/workflows/plugins-weekly-security-audit.yml
  - .github/workflows/plugins-release-plan.yml
  - .github/workflows/plugins-go-live.yml
  - .github/workflows/plugins-withdraw-version.yml
  - .github/workflows/plugins-directory-site.yml
---

# Plugins

> A plugin is a folder in this repo. A third party adds one by pull request. Plugins ship with the app's releases, the desktop app installs one on demand, and runs it as its own process for one job.

Shared contract: [`01-protocol.md`](01-protocol.md). Every stream below implements against that file. Do not invent a second wire format.

Adding a capability later: [`02-extending.md`](02-extending.md). A capability is a verb or it is context, and that file says which, what it costs, who reviews it, and how to keep the facade from leaking.

One plugin from pull request to uninstall, and who owns each step: [`03-lifecycle.md`](03-lifecycle.md).

How versions work, why only the app's version is written by hand, and how a bad version is stopped: [`04-versioning.md`](04-versioning.md).

## Workstreams

Same letter can be picked up at the same time. A stream's own files are in order.

| Stream | Files | Owns | Starts from |
|---|---|---|---|
| **SDK** | [`sdk/01-library.md`](sdk/01-library.md) | `plugins/core/sdk/` and its contract tests | the protocol |
| **CLI** | [`cli/01-author-commands.md`](cli/01-author-commands.md) | `plugins/core/cli/` and its author commands, `plugins/example/`, `plugins/README.md` | the SDK and the manifest rules |
| **Runtime** | [`runtime/01-process.md`](runtime/01-process.md) | `surfsense_local/backend/modules/plugins/` runner, the `plugins` queue and its worker | the protocol. There is no result import: the plugin wrote through the API while it ran |
| **Release** | [`release/01-packaging.md`](release/01-packaging.md), then [`release/02-pull-request-checks.md`](release/02-pull-request-checks.md), then [`release/03-publishing.md`](release/03-publishing.md), then [`release/04-plugin-directory-site.md`](release/04-plugin-directory-site.md) | the release jobs of `surfsense-plugins` in `plugins/core/cli/`, `build-targets.json`, the policy lists, the plugin workflows, the plugins repository | the protocol. Each file builds on the one before |
| **Install** | [`install/01-install-update-uninstall.md`](install/01-install-update-uninstall.md) | choosing a version, install, update, uninstall, the two download hosts | the protocol and the manifest rules. It can test against a fixture catalog before a release publishes a real one |
| **App** | [`app/01-api.md`](app/01-api.md) and [`app/02-screen.md`](app/02-screen.md) | plugin routes, the plugin screen | the route list in `01`. The screen can be built against that list before the routes exist |
| **Python** | [`python/01-interpreter.md`](python/01-interpreter.md) | the interpreter the packaged app spawns, `system_key()` | `plugins/core/build-targets.json`, which whichever stream lands first adds. Other streams use `uv`'s Python until this lands |

**Demo:** `surfsense-plugins invoke` runs `plugins/example` against a running app, and the API runs the same plugin as a subprocess and its `document.add()` shows up as a note. Nothing published is required for that demo.

**Ship:** an app release publishes real plugin files to `surfsense-plugin-releases`, the app installs from the catalog it bundled on all three platforms, including a plugin with a compiled dependency, a paid plugin stays locked without a license, and the directory site lists them.

## Locked decisions

| Decision | Choice |
|---|---|
| Where source lives | `plugins/<id>/` in this repo. A third party contributes by pull request into `dev`. Everything maintainers own, the SDK, the tooling and the lifecycle files, sits in one folder beside the plugins, `plugins/core/`. |
| Id | Folder name. `^[a-z][a-z0-9-]{0,63}$`. Unique. Immutable once published. `plugins/core/policy/reserved-plugin-ids.txt` plus the prefix `surfsense-` are ours, and a pull request may use one only when its author is the repo's owner or a collaborator. `author` is a field, not part of the id. |
| Versioning | People write one version, the app's. The SDK and the protocol have none of their own. A release stamps each plugin that changed with the app's version; plugin version X runs on SurfSense X or newer ([`04-versioning.md`](04-versioning.md)). |
| Publishing | Plugins are published with the app's releases, never from `dev`: uploaded when the release is tagged, live when it is published. A published version never changes. |
| Hosting | GitHub Releases in a second public repository, `SurfSense-Inc/surfsense-plugin-releases`, written by a GitHub App with write access to that repository alone. Never this repository's releases: installed apps take its newest release as an app update. |
| Process | One subprocess per run, on its own `plugins` queue. Not loaded into the API or the worker. Never detached, so it stops when the app quits. |
| Talks to the app | Arguments and environment variables in, the app's own API over loopback while it runs, an exit code out. No socket of ours, no message protocol, no results file. Stdout is logs. |
| Network | The plugin makes its own HTTP calls through `http` in the SDK, which refuses a host not in `hosts`. `hosts` is shown in the app and on the directory site. Before a plugin's first run, one egress consent prompt asks for every host in `hosts` not yet allowed, and the grants are listed and revocable in Settings → Network. This is a check, not enforcement: the app does not intercept connections, and a plugin that skips `http` is not checked. Loopback is not egress and does not belong in `hosts`. |
| Dependencies | The author adds a library with `surfsense-plugins add`, which writes `requirements.in` and generates `requirements.txt` from it with every version and file hash. Packaging installs it for each platform on one Linux runner, from prebuilt wheels only: one `any` file when every platform gets the same files, one per platform otherwise. The user's machine never runs `pip` and never compiles. |
| Platforms | `plugins/core/build-targets.json` lists the platforms and the Python version. A plugin works on all of them unless its optional `platforms` names fewer. The app lists only plugin versions it can run. |
| SDK | `plugins/core/sdk/` in this repo. Not published to PyPI. The app ships that folder next to the plugin interpreter. A plugin's files do not contain it. Strictly typed. |
| Code license | Every plugin is Apache-2.0 under the repository's `LICENSE`, ours and contributed alike. A plugin folder carries no license of its own, and a dependency must be one the Apache Software Foundation lets an Apache-2.0 work include. |
| Access | `free` or `paid`. Community plugins are `free`. `paid` means one of ours, and it installs and runs only with an unexpired SurfSense license file: `individual`, `team`, or a `trial` for its term. No price field. |
| Catalog | `plugin-catalog.json` keeps every published version of every plugin, and each app runs the newest one it can. The app bundles its own release's catalog, so the list is visible with no network. Refreshing it needs the same two hosts as installing, off by default. The plugins themselves are not bundled. |
| Blocking | A version can be blocked, everywhere or from an app version: by a maintainer in `withdrawn-versions.txt`, or by the release's checks when a new app breaks it. The app says why and offers the version to use instead. |
| Versions on disk | One. An update replaces the installed version and deletes the old one. |
| Limits | 100 MB per plugin file unless a maintainer grants more in `plugins/core/policy/size-limit-exceptions.txt`. A run stops at its action's timeout: 30 minutes unless the action sets its own, up to 6 hours. |
| What a plugin can do | A facade in the SDK wraps the app's API, so a plugin calls `document.add()` and never a route. The SDK is the public contract; routes stay ours to rename. Complete within `workspace`, `document`, `artifact`, `model`, of which v1 ships `document`; the other three wait for their app routes. Never `license`, `egress`, `migration`. |
| Declared or coded | Whatever the app must know before running a plugin, to show it, check it or ask the user for it, is declared in `manifest.json`. Whatever happens during a run is the plugin's code, through the SDK. The app never runs plugin code to find something out. |
| What the user provides | Two kinds: an input, asked every run, of kind `string`, `number` or `boolean`; and a secret, set once in Settings and never shown again. The app draws both forms from the declarations. |
| Secrets | Declared with a title and help text. Values go through `shared/secrets.py`. The app puts each one in an environment variable before spawn and never in a file. |
| Environment | Built from scratch for each run: the plugin's context, its secrets, an operating-system allowlist, and the Python variables. Nothing of the app's own. |
| Checks | Every plugin is type-checked with pyright against the SDK, and every SDK change type-checks all of them. Contract tests run each SDK function against the real app. |
| Growing the SDK | Contributions to the SDK are welcome, starting from a plugin that needs the change. SDK and lifecycle changes get a maintainer's review, enforced by `CODEOWNERS` ([`02-extending.md`](02-extending.md#growing-the-sdk-together)). |
| Directory | A generated site lists every plugin, its versions, the hosts it contacts, its blocks and its downloads ([`release/04-plugin-directory-site.md`](release/04-plugin-directory-site.md)). |
| What we do not build | A sandbox, a network proxy or firewall for plugins, a process-count cap beyond the queue's threads, WASM, a socket or message protocol of our own, hot reload, pip or npm on the user's machine, inferring hosts from imports, plugin-authored HTML, payments. The host places an action in the existing sidebar and draws its form. |

## Caught while specifying

These were not in the design conversation. They are decided here so a developer is not blocked on them.

| Gap | Decision |
|---|---|
| The packaged app has no general Python. API and worker are PyInstaller binaries. | [`python/01-interpreter.md`](python/01-interpreter.md) ships a real interpreter. Plugins run on that, never inside the frozen binaries. |
| A document has to belong to a workspace. | A run is started in a workspace, and its id is in the plugin's environment. Verbs default to it. |
| A note has no way to say which plugin wrote it. `POST /workspaces/{id}/documents` takes `{title, content}` and nothing else, so `document.add()` cannot stamp which plugin, action and run wrote the note. | `NoteCreate` gains an optional metadata object, set into the `document_metadata` column that already exists, and the SDK fills it; the keys are in [`app/01-api.md`](app/01-api.md). A plugin could lie about it — loopback has no auth — so it is provenance for the user's benefit, not an audit trail. Without it, nothing in the library says where it came from. |
| The API port is chosen at boot, so nothing outside the app knows it. | Electron writes the URL to `api-url` in its data folder, `~/.surfsense` or `~/.surfsense-dev`, when it picks the port. The runner passes it to plugins as `SURFSENSE_PLUGIN_API_URL`; `surfsense-plugins invoke` reads the file so an author does not have to find it. |
| A plugin can ignore the facade and call any route, because loopback has no auth. | Accepted. The facade is what we sanction, not what we prevent, and review is the mechanism — the same position we took on not sandboxing. |
| A GitHub release on this repo is read by every installed app as an app update. | Plugins publish to a second repository's releases. The app downloads from `github.com`, which redirects to `release-assets.githubusercontent.com`; those are the two hosts install and refresh need. The plugin's own HTTP is not this path. |
| A fetched catalog is the trust anchor for every sha256 in it. | The refresh URL is compiled into the app, and a version whose `url` is outside `https://github.com/SurfSense-Inc/surfsense-plugin-releases/releases/download/` is dropped. |
| A plugin published from `dev` could reach users before the app code that runs it. | Plugins publish only with an app release, stamped with its version, and no app runs a plugin version newer than itself. |
| An SDK change could break a plugin nobody touched. | Every SDK change type-checks every plugin and fails until the broken ones are updated in the same pull request; at release, the version older apps run is re-checked and blocked from the new app when it fails. |
| Compiled code runs only on the platform and the Python it was built for. | A download key names both, such as `cp312-linux-x64`. A release that changes the Python version republishes the plugins with compiled code, under the new key. |
| A draft app release that is never published must not change what users see. | Plugin files upload to a draft when the tag is pushed; the catalog goes live only when the app release is published. |
| A block recorded on one version would be lost when the next version is published. | The catalog keeps every version with its `blocked` list; `checks` entries stay for good, and `maintainer` entries follow `withdrawn-versions.txt`. |
| A withdrawal published while a release is a draft is written later than that release's bundled catalog, but from the release before. | An app prefers the catalog with the higher `released_with`, then the later `generated_at`, and `upload`, `go-live` and `withdraw` never run at the same time. |
| A removed plugin's id taken by a new folder would update its installed copies to someone else's code. | A published id is never reused. |
| Installed apps accept prereleases as updates, and a prerelease's plugins would never go live. | A prerelease bundles the live catalog unchanged; changed plugins wait for the full release. |
| The frozen backend never reads the version `bump-version.sh` writes. | Electron passes `app.getVersion()` to the backend as `SURFSENSE_LOCAL_APP_VERSION`. |
| A dependency installed into a plain directory skips its `.pth` files, and pywin32 needs one. | The SDK adds `site-packages` with `site.addsitedir()`. |
| A plugin started as its own process group would outlive the app. | The runner never detaches it, so the supervisor's group and tree kill reaches it. Runs left `queued` or `running` become `failed` with `interrupted` at the next start, so nothing starts by itself. |
| A child process inherits its parent's environment, and the worker's holds `SURFSENSE_LOCAL_SECRET`, the key that decrypts every stored API key. | The runner builds each plugin's environment from an allowlist, and a test fails on any `SURFSENSE_LOCAL_` variable reaching a plugin. |
| `python -m` puts the plugin's folder ahead of the standard library. | `PYTHONSAFEPATH=1` in the plugin's environment. |
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
| A description per action | A subtitle in the run dialog |
| An affected-plugin report on SDK pull requests, with griffe's `griffe check` | Seeing which plugins a compatible SDK change touches; the type check already names every plugin a change breaks |
| Schedules that run an action by themselves, settings per workspace, icons and categories, a "Test connection" action | Syncing plugins, and a richer plugin list |
| Signing in with OAuth (Google, Reddit, Notion) | The largest gap: until it is designed, a plugin asks for a token as a secret |

Next after v1: the SDK's `http` asks the operating system to verify certificates, through a vendored `truststore`. Until then `http` checks against the system's certificate file. That covers every public site, but not a root a company or the user added to the macOS Keychain, so behind a proxy that inspects HTTPS, a site the browser opens can fail in a plugin. Adding it changes no manifest or protocol field: plugins only start trusting more.

## First paid plugin: the hosted scraper API

The client for the hosted scraper API ships as a `paid` plugin on this system, not as code inside the app ([ADR 0025](../../adr/0025-scraper-client-as-paid-plugin.md)). It is follow-on work: it needs everything above, plus license mode on the scraper API ([contract 2](../../contracts/02-scraper-api-auth.md)), which is not built.

- Its source lives in `plugins/` under a reserved id and is Apache-2.0. The scraper API enforces the license, so there is nothing to hide in the client.
- It declares the scraper API's host in `hosts`, so the user consents before its first run.
- A trial license unlocks it, like any other `paid` plugin.

## Open questions

- How a `paid` plugin gets the license key it sends as `Authorization: License <key>`. The protocol only passes secrets the user sets. The leading answer is one more context variable, passed only to reserved ids, when the scraper plugin is built.
- Whether CI runs a plugin's own `tests/`, and against what. They would need a stub of the app that plugins can import, which the SDK builds for its own tests but does not publish yet.
