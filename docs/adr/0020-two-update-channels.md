# ADR 0020: The new app and the legacy app share one release feed and are kept apart by update channel

- **Status:** Accepted
- **Date:** 2026-09-12
- **Source:** [Pivot plan L81–82](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L81-L82), [Pivot plan L232](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L232), [Pivot plan L303](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L303), [Release guide L3–5](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/surfsense_local/RELEASE.md#L3-L5), [Release guide L83–103](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/surfsense_local/RELEASE.md#L83-L103)

## Context

Both desktop apps publish to the releases of `MODSetter/SurfSense`. The legacy 0.0.x app resolves updates through GitHub's `/releases/latest` and reads `latest*.yml` from whatever release GitHub marks Latest. A legacy client must never parse a 2.x manifest, or it would pull the new app into the old one. Updates as built are in [updates](../architecture/updates.md).

## Decision

- The new app publishes its manifests on its own channel. `publish.channel: stable` in [`electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml) writes `stable.yml`, `stable-mac.yml` and `stable-linux.yml`.
- It sets `autoUpdater.allowPrerelease = true` ([`electron/src/main/updater.ts`](../../surfsense_local/electron/src/main/updater.ts)), which in electron-updater means taking the newest entry of the releases feed instead of `/releases/latest`.
- Since 21 Sep the Latest badge sits on the newest 2.x release. The `legacy-update-bridge` job in [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml) attaches v0.0.40's `latest*.yml` to every release with a `tag: v0.0.40` line prepended. electron-updater honours that key, so legacy clients are offered v0.0.40 and download it from v0.0.40's own assets.
- The app never publishes a prerelease-semver tag, because it would be offered to everyone.
- Download links on the site and in the license email pin a tag through `APP_RELEASE_VERSION`, never `/releases/latest`, so a deployed page or a mail already sent keeps offering the build it was made for; both pick installers from that tag's assets by suffix ([`surfsense_web/lib/app-release.ts`](../../surfsense_web/lib/app-release.ts), [`surfsense_backend/app/license/release.py`](../../surfsense_backend/app/license/release.py)).
- Updates are off by default. A check runs on demand or on the user's opt-in, the download follows the check, and the install waits for the user. macOS ships `[dmg, zip]` because electron-updater needs the zip; the Linux AppImage updates itself and the deb does not.

## Consequences

- A release must not be undrafted before its bridge manifests are attached, or every legacy update check 404s.
- The bridge job stays while 0.0.x clients still check in. It relies on an electron-updater implementation detail, verified against 6.8.3, the version every legacy release from v0.0.30 on pins.
- Every user is offered every release; the updater has no license logic ([ADR 0019](0019-offline-licenses.md)).
- A `v0.*` tag belongs to the legacy line and is never pushed for this app.

## Where the code stands

- 2.0.0 shipped without `allowPrerelease`, and 2.0.1 added it. `updater.ts` notes that Latest names a 2.x release again, so the flag is no longer required, and that dropping it would change behaviour for shipped clients.
- `legacy-update-bridge` failed on the v2.0.2 tag run. The job skips checkout, so `gh release upload` had no repository to infer. The three manifests were uploaded by hand, and commit [a0c5bd3b8](https://github.com/MODSetter/SurfSense/commit/a0c5bd3b81b26b65d1bb79866a6d3e834e6a03b6) added `--repo`.
- The workflow does not reject prerelease tags. The version check in its "Resolve version" step accepts `X.Y.Z-suffix`.
