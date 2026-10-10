# Release — publishing

> Owns: the `release/` job in `plugins/bundles/core/cli/surfsense_plugin_cli/`, `plugins/bundles/core/policy/withdrawn-versions.txt`, the plugin jobs in `.github/workflows/release-local.yml`, the plugin steps in `surfsense_local/RELEASE.md`, `.github/workflows/plugins-release-plan.yml`, `.github/workflows/plugins-go-live.yml`, `.github/workflows/plugins-withdraw-version.yml`, `surfsense_local/electron/scripts/fetch-plugin-catalog.mjs`, the repository `SurfSense-Inc/surfsense-plugin-releases`, and the GitHub App that writes to it.
> Contract: [`../01-protocol.md`](../01-protocol.md). Versioning: [`../04-versioning.md`](../04-versioning.md). Packaging: [`01-packaging.md`](01-packaging.md). Checks: [`02-pull-request-checks.md`](02-pull-request-checks.md).

## Goal

Plugins reach users only with the app release whose code they were checked against. Nobody writes a version, nobody clicks per plugin, and a bad version can be stopped at any time.

## Work

### Where plugins are published, and the one-time setup

Published files and catalogs live in a second public repository, `SurfSense-Inc/surfsense-plugin-releases`, in the project's GitHub organization, as GitHub Releases, laid out as the protocol shows. This repository's own releases are the app's update channel: installed apps from 2.0.1 on take the newest release here as an update, so nothing but an app release may appear in it. A second repository's releases are its own, public once published with no setting to change, counted per file by GitHub, and downloaded over plain HTTPS.

A workflow's built-in token can write only to its own repository, and this one belongs to a personal account while the second belongs to the organization. Writing across takes a GitHub App, the way GitHub recommends one repository publishing into another. Once:

1. **An owner of SurfSense-Inc** creates the public repository `SurfSense-Inc/surfsense-plugin-releases`. Its README says the repository is generated, that the source lives in `plugins/` of MODSetter/SurfSense, and that nothing in it is edited by hand. GitHub Pages serves its `gh-pages` branch.
2. **An owner of SurfSense-Inc** creates a GitHub App owned by the organization, "SurfSense plugin publisher", with one repository permission, Contents: read and write, and installs it on `surfsense-plugin-releases` alone. Owned by the organization, it does not depend on any one person's account.
3. **MODSetter**, the only one who can manage this repository's secrets, stores the App's ID and private key as `PLUGIN_PUBLISHER_APP_ID` and `PLUGIN_PUBLISHER_PRIVATE_KEY` in an environment of this repository, `plugin-publishing`, limited to `main`, `dev` and `v*` tags.

Every job that writes to the second repository runs in that environment and turns the two into a token with `actions/create-github-app-token`, with `owner: SurfSense-Inc` and `repositories: surfsense-plugin-releases`. The token expires after an hour.

What that credential can and cannot do. Workflows on pull requests from forks never receive secrets, so a contributor cannot reach it. The token cannot write to this repository, so it can never touch the app's releases or update channel. If the private key leaked, someone could publish a false catalog until an owner of SurfSense-Inc deletes the key, which takes one click; that is the same kind of risk as the app's own release pipeline, and the key gets the same care.

`plugins/bundles/core/cli/surfsense_plugin_cli/release/README.md` is the maintainers' guide: this setup, the release flow below, reading the plan comment, withdrawing a version, and replacing the App's key.

### What a release publishes

A plugin is published when it changed since the last published release, as [`../04-versioning.md`](../04-versioning.md#a-plugins-version) defines it. The last published release is the `released_with` of the live catalog; the comparison is between that release's tag and this one, folder by folder, plus whatever `plugins/bundles/core/build-targets.json` changed for each plugin's packaged files. A new folder is published; a folder that is gone gets `removed_from_app` set to this release. The first release ever publishes every plugin.

### The release, step by step

It follows [`RELEASE.md`](../../../../../surfsense_local/RELEASE.md), which this work edits in two places. It makes releasing from `main` the rule: bump on `dev`, merge `dev` into `main` by pull request, tag `main`. Today it also allows tagging `dev`, which would skip the plan comment. And after publishing the draft, the maintainer checks that `plugins-go-live.yml` went green, and reruns it if not, the way `legacy-update-bridge` must be green before undrafting.

`upload`, `go-live` and `withdraw` share one `concurrency` group, `plugins-publishing`, and never cancel one another, so the live catalog is only ever written by one of them at a time. Without it, a `withdraw` finishing after a `go-live` would put an older release's catalog back on top.

1. **`plan`, on the release pull request.** `plugins-release-plan.yml` runs `surfsense-plugins plan` on every pull request into `main` and keeps one comment up to date: the plugins this release will publish and the version each gets, new and removed plugins, the published versions the checks will block from this release, and anything that would fail. The maintainer reads what the release will do before tagging.
2. **`upload`, when the tag is pushed.** A job in `release-local.yml` runs `surfsense-plugins upload` before the desktop build jobs:
   - Package every changed plugin with its stamped version ([`01-packaging.md`](01-packaging.md)).
   - Run the final gate: every plugin type-checks against this release's SDK, and every changed plugin passes every check. A failure fails the release.
   - Check every published version not already blocked for this release against this release's SDK, each from its own release's tag. That covers every copy users may have installed, and every older version an app may fall back to. A version that fails is blocked from this release, with `source: checks`.
   - Write the catalog: the live catalog, plus this release's versions, `checks` blocks and removals, with every `maintainer` entry rewritten from `withdrawn-versions.txt`, and `released_with` and `generated_at` set.
   - Create a **draft** release `surfsense-<version>` in the second repository, or reuse the one a failed run left, and upload the files and the catalog to it.

   The desktop build jobs take that catalog file straight from this job and bundle it, so an app always ships its own release's catalog. A draft is invisible, so a tag whose release is never published changes nothing for users.
3. **`go-live`, when the maintainer publishes the app release.** `plugins-go-live.yml` runs `surfsense-plugins go-live` on the `release: published` event of an app release that is not a prerelease. It rewrites the draft catalog's `maintainer` entries from the current `withdrawn-versions.txt` on `dev`, so a withdrawal made after the tag survives, sets a new `generated_at`, then publishes the draft and marks it latest. Installed apps see it on their next refresh. It then rebuilds the directory site ([`04-plugin-directory-site.md`](04-plugin-directory-site.md)).

A prerelease app tag, such as `v2.5.0-rc.1`, uploads nothing and never goes live: its build bundles the live catalog unchanged. Installed apps accept prereleases as updates, so a prerelease must not point at plugin files that are not published; plugins that changed wait for the full release. A dry run of `release-local.yml`, started by hand without a tag, does the same, because the `plugin-publishing` environment does not admit it.

### Withdrawing a version

`plugins/bundles/core/policy/withdrawn-versions.txt` holds one line per withdrawn version, `<id> <version> [from <app-version>] <reason>`, and `#` comments. The reason is what users read. A maintainer adds the line by pull request into `dev`, then runs `plugins-withdraw-version.yml`, which runs `surfsense-plugins withdraw`: it rewrites the live catalog's `maintainer` entries from the file and publishes the result as a release `withdrawal-<UTC timestamp>`, holding only the catalog, marked latest. It reads the list from `dev` without waiting for a release, because a withdrawal can only stop a version, never add one, so it cannot bring unreleased code to users. It then rebuilds the directory site.

The file is the source of every `maintainer` entry, so editing a line changes its block and deleting one lifts it. `checks` entries are never lifted.

### Safe to rerun

Every step can be rerun. An upload of a file the draft already holds with the same sha256 counts as done; with a different sha256 it fails, because a published version never changes. The catalog is always written last.

### Builds outside a release

`fetch-plugin-catalog.mjs` downloads the live catalog for builds made outside the release workflow, such as `pnpm dist`, and electron-builder ships it in `extraResources`. A failed download fails that build. The URL is one constant, shared with the app's refresh.

## Acceptance

- A release pull request carries one plan comment, updated on each push, listing what the release will publish and block.
- Tagging publishes nothing to users: the second repository gains a draft release holding each changed plugin's files and a catalog whose `sha256` values match them, and the desktop build bundles that catalog.
- Publishing the app release publishes the draft, marked latest; its catalog carries a withdrawal made between the tag and the publishing.
- A plugin unchanged since the last published release is not uploaded again and keeps its version.
- A plugin whose newest published version fails against the new SDK is blocked from the new release, with `source: checks`.
- `withdraw` publishes a catalog-only release marked latest, and the block is still there after the next app release.
- Rerunning an upload that failed halfway completes it without duplicating files; a different file under an existing name fails.
- A prerelease app tag creates no plugins release, and its build bundles the live catalog unchanged.
- A `withdraw` started while a `go-live` runs waits for it, and the live catalog afterwards is the new release's, with the withdrawal applied.
- A version blocked from release N by a maintainer, whose older fallback fails against N's SDK, has that older version blocked from N by the checks.
- Nothing in these workflows creates a release in this repository.
- The second repository receives writes only through the App's token, in the `plugin-publishing` environment.

## Needs from

[`01-packaging.md`](01-packaging.md), [`02-pull-request-checks.md`](02-pull-request-checks.md), `release-local.yml`, and the one-time setup above. Nothing from the app itself.
