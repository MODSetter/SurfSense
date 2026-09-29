# Lifecycle

> One plugin from pull request to uninstall, and the doc that owns each step. Contract: [`01-protocol.md`](01-protocol.md). Versions: [`04-versioning.md`](04-versioning.md).

## Stages

| Stage | What happens | Owned by |
|---|---|---|
| Write | The author adds `plugins/<id>/`: `plugin.json`, `main.py`, `requirements.in` and the `requirements.txt` generated from it. No version. The harness runs it against a running app, and `surfsense-plugins check` runs what CI will. | [SDK](sdk/01-library-and-harness.md), [checks](release/02-pull-request-checks.md) |
| Check | A pull request into `dev` runs the checks: manifest, reserved ids, module names that clash, pinned and hashed dependencies, a wheel for each platform the plugin supports, size, licenses, known vulnerabilities, and the type check against the SDK. A change to the SDK type-checks every plugin and runs the contract tests. A maintainer reviews and merges. Nothing is published from `dev`. | [checks](release/02-pull-request-checks.md) |
| Plan | The release pull request from `dev` into `main` carries a comment listing what the release will publish and block. | [publishing](release/03-publishing.md) |
| Upload | Tagging the release packages each changed plugin, stamped with the app version, runs the final checks, and uploads it with the new catalog to a draft in `surfsense-plugin-releases`. The app build bundles that catalog. Users see nothing yet. | [packaging](release/01-packaging.md), [publishing](release/03-publishing.md) |
| Go live | Publishing the app release publishes the draft. Installed apps see the new catalog on their next refresh, and the directory site updates. | [publishing](release/03-publishing.md), [directory site](release/04-plugin-directory-site.md) |
| List | Settings shows, for each plugin, the newest version this app can run. A plugin that needs a license is shown with the reason. | [install](install/01-install-update-uninstall.md), [API](app/01-api.md), [screen](app/02-screen.md) |
| Install | After consent for the two GitHub download hosts: download, verify the sha256, extract, compare the manifest with the catalog, rename. No plugin code and no `pip` run. | [install](install/01-install-update-uninstall.md) |
| Set up | Settings shows a field for each secret the plugin declares. Until every one has a value, its sidebar actions read "Set up". | [screen](app/02-screen.md), [API](app/01-api.md) |
| Run | A sidebar action opens a dialog drawn from the entry's declared inputs. The first run asks consent for every declared host at once. The plugin runs as its own process, writes through the app's API, and is stopped by cancel, by its timeout, or by the app quitting. | [runtime](runtime/01-process.md), [screen](app/02-screen.md) |
| Update | When a newer version this app can run exists, the user clicks Update. The new version replaces the old one, which is deleted; the plugin's data stays. | [install](install/01-install-update-uninstall.md) |
| Block | A version is stopped, everywhere or from an app version: by a maintainer's `withdraw`, at any time, or by the release's checks. Once an app has a catalog that says so, after a refresh or with its next update, the installed copy shows why and offers the version to use instead. | [versioning](04-versioning.md), [publishing](release/03-publishing.md), [install](install/01-install-update-uninstall.md) |
| Uninstall | Runs stop; the plugin's files, data and secrets are deleted. The notes it created stay. | [install](install/01-install-update-uninstall.md) |

## What holds at every stage

- A plugin reaches users only with the app release whose code it was checked against, never ahead of it.
- Nobody writes a version except the app's.
- A published version never changes. A fix is a new version, and a bad one is blocked.
- The user's machine never runs `pip` and never compiles anything.
- Nothing is downloaded without the user's consent for its host, and a plugin does not start until every host it declares is allowed. What it calls outside `http` is not checked ([network](01-protocol.md#network)).
- One version of a plugin is on disk at a time.
- A plugin never outlives the app.
- Uninstalling never deletes the user's documents.
