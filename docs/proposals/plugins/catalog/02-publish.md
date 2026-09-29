# Catalog — publish

> Owns: `.github/workflows/plugin-publish.yml`, `.github/workflows/plugin-audit.yml`, `plugins/YANKED`, `surfsense_local/electron/scripts/fetch-plugin-catalog.mjs`.
> Contract: [`../01-protocol.md`](../01-protocol.md). Build tool: [`01-manifest-and-ci.md`](01-manifest-and-ci.md).

## Goal

Merging a version bump into `dev` publishes that plugin within minutes, without a desktop release and without touching the releases feed the app updates from.

## Work

- Where: GitHub Packages on this repository, under `ghcr.io/modsetter/surfsense/plugins/`. Never GitHub Releases: installed apps take the newest release on MODSetter/SurfSense as an app update, and a release without `stable*.yml` breaks every update check until the next app release. Homebrew serves its bottles from ghcr.io, and Dev Container Features serves its feature tarballs and their catalog there. Public packages cost nothing. A public version cannot be deleted once it passes 5,000 downloads, which is one more reason withdrawal is a yank and never a deletion.
- Trigger: a push to `dev` that touches `plugins/**`. A plugin folder, as [`01-manifest-and-ci.md`](01-manifest-and-ci.md) defines one, publishes when its `version` is greater than in the push's previous commit, or when the folder is new. A change to `plugins/YANKED`, or a deleted plugin folder, republishes the catalog alone. One publish runs at a time (`concurrency`), so two merges cannot race on the catalog. There is no release branch: the checked version bump is the release decision, as with release-please and Changesets in other monorepos.
- For each plugin to publish: build it with `plugins/build/`, then push each tarball with ORAS as `ghcr.io/modsetter/surfsense/plugins/<id>:<version>-<key>`, with `permissions: packages: write` and `GITHUB_TOKEN`, and the `org.opencontainers.image.source` annotation linking the package to this repository. A tag that already exists fails the job, because a published version never changes.
- The catalog: start from the published `catalog:latest`, or from nothing the first time. Set each published plugin's entry from its `plugin.json` and the new digests. For a folder that is gone, keep the entry but empty its `downloads`, so nobody new can install it while its `yanked` map still reaches installed copies. Apply `plugins/YANKED`. Stamp `generated_at`. Push it as `ghcr.io/modsetter/surfsense/plugins/catalog:latest`. Copies already installed of a removed plugin keep running unless their version is yanked.
- Packages are public. Check that after the first publish: GitHub's docs disagree on the default, and public cannot be undone.
- `plugins/YANKED` is one line per withdrawn version, `<id> <version> <reason>`. The reason is what the user reads. A maintainer adds the line; the author then publishes a fix as a new version.
- When `python` in `plugins/targets.json` changes on `dev`, the workflow rebuilds the latest version of every plugin that has compiled downloads, for the new key, and adds those downloads to its entry. Old keys stay for apps not yet updated. `any` downloads are untouched.
- `plugin-audit.yml`, weekly: `pip-audit` over every plugin's `requirements.txt`, opening or updating one issue per affected plugin, labelled with its id. The fix is a patch release from the author. When none comes, a maintainer yanks the version.
- Desktop build: `fetch-plugin-catalog.mjs` pulls `catalog:latest` the way `fetch-llamacpp.mjs` pulls a pinned asset, and electron-builder ships it in `extraResources`. Run it from `dist`, and add its own step to `.github/workflows/release-local.yml`: the release build stages resources one step at a time rather than through `pnpm dist`, which is how sd-server came to be missing from it. A failed fetch fails the desktop build. The repository and tag are one constant, shared with the app's refresh.

## Acceptance

- Merging a version bump pushes the plugin's tarballs and a catalog entry whose `sha256` equals each pushed blob's digest.
- Publishing a version that already exists fails and leaves the catalog as it was.
- A line in `plugins/YANKED` appears in the entry's `yanked` map, and is still there after the plugin's next version publishes.
- Two merges in a row leave one catalog holding both.
- Deleting a plugin's folder leaves its entry with no downloads and its `yanked` map intact.
- Nothing in these workflows creates a GitHub release.
- A desktop build with the catalog unreachable fails.

## Needs from

The build tool and `plugins/targets.json` from [`01-manifest-and-ci.md`](01-manifest-and-ci.md). Nothing from the app.
