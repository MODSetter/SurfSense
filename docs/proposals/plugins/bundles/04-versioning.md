# Versioning

> How plugin versions are set, how an app knows which plugin versions it can run, and how a version is stopped. Contract: [`01-protocol.md`](01-protocol.md). Publishing: [`release/03-publishing.md`](release/03-publishing.md).

## One number

People manage one version number: the app's, in `surfsense_local/VERSION`, as [`RELEASE.md`](../../../../surfsense_local/RELEASE.md) already does. Everything else is the app's version or is computed from it.

| Thing | Its version |
|---|---|
| The app | `surfsense_local/VERSION`, bumped by a maintainer for each release |
| The SDK | None of its own. It ships inside the app, so the SDK in SurfSense 2.4.0 is the 2.4.0 SDK |
| A plugin | None in its `manifest.json`. A release stamps a plugin with that release's app version when the plugin changed since the last published release |
| A plugin's compatibility | Computed: plugin version X runs on SurfSense X or newer |
| The protocol | None of its own. It changes only with an app release, so a plugin stamped X speaks app X's protocol |
| The catalog's format | `schema_version`, raised by maintainers only when the file's structure breaks, which is rare |

## A plugin's version

A plugin changes when anything in its folder changes, its locked dependencies included, or when `plugins/bundles/core/build-targets.json` changes in a way that alters its packaged files: a new Python version changes every plugin that has no `any` file, and a new platform every plugin that needs a file of its own there. At release, each plugin that changed since the last published release is stamped with that release's app version. A plugin that did not change keeps the version it had.

| App release | `example` | `hn-search` | `pdf-tools` |
|---|---|---|---|
| 2.3.0 | 2.3.0 (new) | 2.3.0 (new) | — |
| 2.4.0 | 2.3.0 (unchanged) | 2.4.0 (changed) | 2.4.0 (new) |
| 2.5.0 | 2.3.0 | 2.4.0 | 2.5.0 (changed) |

A version is an identity, used in bug reports, in the directory site and to block a version. It carries no meaning of its own beyond "shipped with SurfSense X"; what changed is in the pull request that changed it.

The stamp goes into the packaged copy of `manifest.json` only. The repository's `manifest.json` has no `version`; packaging replaces one if an author writes it.

## Which version an app runs

The catalog keeps every published version of every plugin. For each plugin, an app takes the newest version that:

- is not newer than the app itself;
- is not blocked for this app;
- supports this system's platform, when its manifest names `platforms`;
- has a download for this app's key or `any`.

On SurfSense 2.4.0, after the table above, that is `example 2.3.0`, `hn-search 2.4.0` and `pdf-tools 2.4.0`. An app never installs a plugin version newer than itself, and an older app keeps getting the last version that was released with, or before, it.

The cost: a plugin fix reaches only apps at least as new as the release that carried it. That is the price of never letting a plugin ahead of the app that runs it.

## Stopping a version: `blocked`

A published version never changes, but it can be stopped. A catalog version may carry a `blocked` list; each entry says: do not run this version on these apps, and why.

```json
"blocked": [{ "from_app": "2.6.0", "reason": "Uses document.update, changed in SurfSense 2.6.0", "source": "checks" }]
```

`from_app` absent means every app. An app does not run a version when any entry applies to it; when several do, it shows a maintainer's reason before a check's. `source` says who wrote the entry:

| Source | Written by | When | Example |
|---|---|---|---|
| `maintainer` | A maintainer, as a line in `plugins/bundles/core/policy/withdrawn-versions.txt` | A person finds a problem no check can see | `hn-search 2.4.0 Deletes notes by mistake.` blocks 2.4.0 everywhere |
| `checks` | The release's checks | At each release, every published version not already blocked for the new app is checked against the new SDK, and fails | `hn-search 2.4.0` blocked from 2.6.0, because 2.6.0 changed something it uses |

A maintainer line may also name `from <app-version>` to block only newer apps. The file is the source of every `maintainer` entry: each catalog rewrites them from it, so editing a line changes the block and deleting a line lifts it. `checks` entries are never lifted; they stay in every later catalog.

What each person sees:

- **Withdrawn by a maintainer.** Maya, on 2.4.0 with `hn-search 2.4.0`, refreshes: the plugin's actions are blocked with "hn-search 2.4.0 was withdrawn: Deletes notes by mistake", and the app offers the newest version she can run that is not blocked, `hn-search 2.3.0`.
- **Blocked by the checks.** Tom, on 2.4 with `hn-search 2.4.0`, updates the app to 2.6. Instead of a crash he reads "hn-search 2.4.0 doesn't work with SurfSense 2.6. Update to 2.6.0." Maya, still on 2.4, is not affected.

The frame of each message is interface text and is translated; a maintainer's reason is shown as written. A block written by the checks shows users the frame only: the technical reason is for maintainers and the directory site.

## Why an unchanged plugin cannot break silently

Every plugin lives in this repository, so every SDK change is checked against every plugin before it merges ([`release/02-pull-request-checks.md`](release/02-pull-request-checks.md)). A pull request that removes or changes something a plugin uses fails, naming the plugin, file and line, until that plugin is updated in the same pull request. The updated plugin then changed, so the release stamps it, and apps from that release on take the new version. The release's own check of every published version (the `checks` blocks above) covers copies already installed, whatever version they are, and the older versions an app falls back to when a newer one is blocked.

What no check sees is a function that still exists but behaves differently. That is what a maintainer's review of SDK changes and a `maintainer` block are for.

## Scenarios

| Scenario | What happens |
|---|---|
| A contributor changes a plugin | The checks pass, and it ships stamped with the next release. Older apps keep the version they can run |
| The SDK gains something and a plugin uses it | Both ship in the same release. Older apps keep the plugin's previous version |
| The SDK loses something an unchanged plugin uses | The pull request fails until the plugin is fixed in it. The fix ships stamped with the release, and the old version is blocked from that release by the checks |
| Something breaks at run time that no check saw | A maintainer blocks the version, everywhere or from an app version, and the fix ships with the next release or a hotfix release |
| An emergency between releases | `withdraw` blocks the version at once. Nothing is added |
| A hotfix release 2.4.1 | Changed plugins are stamped 2.4.1, the same flow |
| A user who never updates the app | Keeps getting the newest versions their app can run, never one it cannot |
| A user who downgrades the app | An installed version newer than the app is refused, and the app offers the newest one it can run |
| Python 3.13 | Every plugin with no `any` file is rebuilt and stamped with that release; its Python 3.12 versions stay for older apps |
| A new platform | Its downloads arrive stamped with the release that added it, for the plugins whose files differ there |
| A plugin removed from the repository | The catalog records the release it was removed in; apps from that release on no longer list it |
| A draft app release never published | Its plugin files were uploaded but never went live, so users see nothing. The next release stamps against the last published one |
| A prerelease app release | Bundles the live catalog unchanged. Plugins that changed wait for the next full release, so a prerelease never points at files that are not live |
| A release run that fails halfway | Rerunning is safe: a file already uploaded with the same sha256 counts as done, a different one fails, and the catalog is written last |

## What people do

- **A contributor** changes a plugin, runs `check`, opens a pull request. Never a version.
- **An SDK contributor** fixes, in the same pull request, any plugin the checks say their change breaks.
- **A maintainer** releases from `main` as [`RELEASE.md`](../../../../surfsense_local/RELEASE.md) says: bump `surfsense_local/VERSION`, merge `dev` into `main`, tag `main`, publish the draft, and check that `plugins-go-live.yml` went green. The release pull request carries a comment listing what the release will publish and block. When a version is bad, they add a line to `withdrawn-versions.txt` and run `withdraw`.
- **Automation** does the rest: stamping, packaging, uploading, blocking by checks, going live, the catalog and the directory site ([`release/03-publishing.md`](release/03-publishing.md)).
