# Lifecycle

> One plugin from pull request to uninstall, and the doc that owns each step. Contract: [`01-protocol.md`](01-protocol.md).

## Stages

| Stage | What happens | Owned by |
|---|---|---|
| Write | The author adds `plugins/<id>/`: `plugin.json`, `main.py`, `requirements.in` and the `requirements.txt` generated from it. The harness runs it against a running app, and `check` runs what CI will. | [SDK](sdk/01-library-and-harness.md), [checks](catalog/01-manifest-and-ci.md) |
| Check | A pull request into `dev` runs the tree rules and the build rules: manifest, reserved ids, version bump, module names that clash, pinned and hashed dependencies, a wheel for each platform the plugin supports, size, licenses, known vulnerabilities. A maintainer reviews and merges. | [checks](catalog/01-manifest-and-ci.md) |
| Publish | The merge publishes the new version to GitHub Packages, one `any` tarball or one per platform, and updates the catalog there. | [publish](catalog/02-publish.md) |
| Ship the list | Every desktop build bundles the latest catalog, so the list shows with no network. Refresh fetches a newer one. | [publish](catalog/02-publish.md), [install](catalog/03-install.md) |
| List | Settings shows only what this computer can install. A plugin that needs a newer SurfSense, or a license, is shown with the reason. | [install](catalog/03-install.md), [API](app/01-api.md), [screen](app/02-screen.md) |
| Install | After consent for the two GitHub Packages hosts: download, verify the sha256, extract, compare the manifest with the catalog, rename. No plugin code and no `pip` run. | [install](catalog/03-install.md) |
| Set up | Settings shows a field for each secret the plugin declares. Until every one has a value, its sidebar actions read "Set up". | [screen](app/02-screen.md), [API](app/01-api.md) |
| Run | A sidebar action opens a dialog drawn from the entry's declared inputs. The first run asks consent for every declared host at once. The plugin runs as its own process, writes through the app's API, and is stopped by cancel, by its timeout, or by the app quitting. | [runtime](runtime/01-process.md), [screen](app/02-screen.md) |
| Update | The user clicks Update. The new version replaces the old one, which is deleted; the plugin's data stays. | [install](catalog/03-install.md) |
| Yank | A maintainer withdraws a bad version in `plugins/core/YANKED`. Once an app has a catalog that says so, after a refresh or with its next update, its installed copy stops running and shows the reason. The author publishes a fix. | [publish](catalog/02-publish.md), [install](catalog/03-install.md) |
| Uninstall | Runs stop; the plugin's files, data and secrets are deleted. The notes it created stay. | [install](catalog/03-install.md) |

## What holds at every stage

- A published version never changes. A fix is a new version.
- The user's machine never runs `pip` and never compiles anything.
- Nothing is downloaded without the user's consent for its host, and a plugin does not start until every host it declares is allowed. What it calls outside `http` is not checked ([network](01-protocol.md#network)).
- One version of a plugin is on disk at a time.
- A plugin never outlives the app.
- Uninstalling never deletes the user's documents.
