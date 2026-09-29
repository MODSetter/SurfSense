# Catalog — publish

> Owns: `.github/workflows/plugin-publish.yml`, `.github/workflows/plugin-audit.yml`, `plugins/core/YANKED`, `surfsense_local/electron/scripts/fetch-plugin-catalog.mjs`.
> Contract: [`../01-protocol.md`](../01-protocol.md). Build tool: [`01-manifest-and-ci.md`](01-manifest-and-ci.md).

## Goal

Merging a version bump into `dev` publishes that plugin within minutes, without a desktop release and without touching the releases feed the app updates from.

## Work

- Where: GitHub Packages on this repository, under `ghcr.io/modsetter/surfsense/plugins/`. Never GitHub Releases: installed apps take the newest release on MODSetter/SurfSense as an app update, and a release without `stable*.yml` breaks every update check until the next app release. Homebrew serves its bottles from ghcr.io, and Dev Container Features serves its feature tarballs and their catalog there. Public packages cost nothing. A public version cannot be deleted once it passes 5,000 downloads, which is one more reason withdrawal is a yank and never a deletion.
- Trigger: a push to `dev` that touches `plugins/**`. A plugin folder, as [`01-manifest-and-ci.md`](01-manifest-and-ci.md) defines one, publishes when its `version` is greater than in the push's previous commit, or when the folder is new. A change to `plugins/core/YANKED`, or a deleted plugin folder, republishes the catalog alone. One publish runs at a time (`concurrency`), so two merges cannot race on the catalog. There is no release branch: the checked version bump is the release decision, as with release-please and Changesets in other monorepos.
- For each plugin to publish: build it with `plugins/core/build/`, then push it to `ghcr.io/modsetter/surfsense/plugins/<id>` under the tag `<version>`, with ORAS 1.3 or later, `permissions: packages: write` and `GITHUB_TOKEN`. An `any` download is one manifest with one file. Per-platform downloads are one manifest per key, joined under the tag by an index (`oras manifest index create`) whose entries name their key. Files carry the types in [`../01-protocol.md`](../01-protocol.md#in-the-registry), and every manifest carries `org.opencontainers.image.source`, set before the first push so the package is linked to this repository and takes its access permissions. A tag that already exists fails the job, because a published version never changes.
- Visibility: GitHub makes a new package private when its owner is a personal account, which MODSetter is, and has no API to change that. So after pushing, the workflow downloads what it pushed without credentials. When that fails, the plugin stays out of the catalog and the job fails with "make `surfsense/plugins/<id>` public in its package settings, then rerun". A maintainer does that once per new plugin; a public package stays public, and later versions need nothing.
- The catalog: start from the published `ghcr.io/modsetter/surfsense/plugins:latest`, or from nothing the first time. Set each published plugin's entry from its `plugin.json` and the new digests. For a folder that is gone, keep the entry but empty its `downloads`, so nobody new can install it while its `yanked` map still reaches installed copies. Apply `plugins/core/YANKED`. Stamp `generated_at`. Push it to the same package with two tags: `latest`, and `generated_at` written as `20261001T120000Z`, so every earlier catalog stays readable. Copies already installed of a removed plugin keep running unless their version is yanked.
- `plugins/core/YANKED` is one line per withdrawn version, `<id> <version> <reason>`. The reason is what the user reads. A maintainer adds the line; the author then publishes a fix as a new version.
- When `python` in `plugins/core/targets.json` changes on `dev`, the workflow rebuilds the latest version of every plugin that has compiled downloads, for the new key, adds those files to that version's index, and adds them to its catalog entry. It is the one change a published version takes: files are only added, and none already there changes. Old keys stay for apps not yet updated. `any` downloads are untouched.
- `plugin-audit.yml`, weekly: `pip-audit` over every plugin's `requirements.txt`, opening or updating one issue per affected plugin, labelled with its id. The fix is a patch release from the author. When none comes, a maintainer yanks the version.
- Desktop build: `fetch-plugin-catalog.mjs` pulls `ghcr.io/modsetter/surfsense/plugins:latest` the way `fetch-llamacpp.mjs` pulls a pinned asset, and electron-builder ships it in `extraResources`. Run it from `dist`, and add its own step to `.github/workflows/release-local.yml`: the release build stages resources one step at a time rather than through `pnpm dist`, which is how sd-server came to be missing from it. A failed fetch fails the desktop build. The repository and tag are one constant, shared with the app's refresh.

## Acceptance

- Merging a version bump pushes the plugin under one tag, its version, and a catalog entry whose `sha256` equals each pushed file's digest. A plugin with compiled dependencies gets one index under that tag, with one entry per platform.
- The first publish of a new plugin whose package is still private fails with the message naming the package, and the catalog does not list the plugin. After the package is made public, rerunning publishes it.
- Each catalog publish is readable afterwards under its own `generated_at` tag.
- Publishing a version that already exists fails and leaves the catalog as it was.
- A line in `plugins/core/YANKED` appears in the entry's `yanked` map, and is still there after the plugin's next version publishes.
- Two merges in a row leave one catalog holding both.
- Deleting a plugin's folder leaves its entry with no downloads and its `yanked` map intact.
- Nothing in these workflows creates a GitHub release.
- A desktop build with the catalog unreachable fails.

## Needs from

The build tool and `plugins/core/targets.json` from [`01-manifest-and-ci.md`](01-manifest-and-ci.md). Nothing from the app.
