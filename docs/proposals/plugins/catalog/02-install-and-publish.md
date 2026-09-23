# Catalog — install and publish

> Owns: `modules/plugins/install.py`, `modules/plugins/catalog.py`, `.github/workflows/plugin-publish.yml`, the bundling of `catalog.json` in the desktop build.
> Contract: [`../01-protocol.md`](../01-protocol.md). Checker: [`01-manifest-and-ci.md`](01-manifest-and-ci.md).

## Goal

Merging a plugin publishes a tarball and a catalog entry. The app installs that tarball without running it, and without running `pip`.

## Work

- `installed_plugins` table: `id` primary key, `version`, `path`, `installed_at`. Hand-written migration.
- Publish workflow, on push to `main` that touches `plugins/<id>/**`, and not on the desktop release workflow. For each changed plugin: create a venv with the interpreter version from [`../python/01-interpreter.md`](../python/01-interpreter.md), `pip install -r requirements.txt --target site-packages` when the file exists, tar `<id>-<version>.tar.gz`, sha256 the gzip, upload it as an asset on the GitHub release `plugin-<id>-<version>`. Rebuild `catalog.json` from every `plugins/*/plugin.json` plus the known asset URLs and digests, and upload it as the only asset of the release `plugin-catalog`, replacing the previous asset.
- Do not attach these assets to the `stable` desktop release. electron-updater reads `stable*.yml` from that release.
- Desktop build downloads `catalog.json` from `plugin-catalog` the way `fetch-llamacpp.mjs` downloads a pinned asset, and electron-builder ships it in `extraResources`. Add the step to `.github/workflows/release-local.yml` as well: the release build stages resources one step at a time rather than through `pnpm dist`, which is how sd-server came to be missing from it. A failed download fails the desktop build. The URL is a constant in that script and the same constant in the app.
- Install, given a catalog entry: require `plugin_install` egress enabled, otherwise raise the existing `EgressDeniedError`. Download the URL. Require the final host, after GitHub's redirect, to be `github.com` or `objects.githubusercontent.com`. Both are covered by the one destination `plugin_install`. Reject any other host before writing. Compare sha256. Compare the manifest inside the tarball to the catalog fields. Extract with the path rules in the protocol. Rename into place. Insert or update `installed_plugins`. Create `<data>/plugins/<id>/data` if it is absent. Leave an older version directory in place.
- A yanked entry installs only when already installed, and a run of a yanked version fails with the reason `yanked`.
- `license: paid` consults the stored license state, `status()` in `modules/license/service.py`. Missing, expired, or `clock_untrusted` refuses the install and the run with `license_required`. A `trial` license unlocks it for its term. `free` does not consult it.
- Refresh: download `catalog.json` from the compiled URL when `plugin_catalog` egress is enabled. Replace the in-memory catalog. The bundled file remains the fallback when the destination is off.
- Add `plugin_catalog` and `plugin_install` in `modules/egress/service.py`, and include them in `list_destinations`, so both appear in Settings → Network, off by default. Destinations are one row per host today, so what these two are called is open ([README](../README.md#open-questions)).
- Uninstall: delete `<data>/plugins/<id>/` including `data` and every version, delete `installed_plugins`, delete secrets named `plugin:<id>:*`. Do not delete documents: they are the user's, whatever put them there.

## Acceptance

- A tarball with a `../` member extracts nothing and leaves no directory behind.
- A sha256 mismatch leaves no directory behind.
- A manifest whose `hosts` differ from the catalog entry is rejected.
- A redirect to a host other than the two GitHub hosts is rejected and the body is not saved.
- Install with `plugin_install` disabled raises `EgressDeniedError` and does not open a connection.
- A `paid` entry with no license does not insert `installed_plugins`. With a trial license, it installs. The same entry with `license: free` does, with no license on disk.
- Uninstall removes the folder and the secret and leaves a note that the plugin created.

## Needs from

The manifest checker. The egress module and the license verifier, which exist. The publish workflow can land before the interpreter packaging does: it pins the same CPython minor version that workflow will ship.
