# App updates

The desktop app updates itself with electron-updater from the GitHub Releases of `MODSetter/SurfSense`, on its own `stable` channel, and only once the user has allowed it. Updates are free for everyone and carry no license logic. The legacy 0.0.x desktop app reads the same releases, so the two apps are kept apart by the names of the manifests each one reads, not by GitHub's Latest pointer.

**Code:** [`surfsense_local/electron/src/main/updater.ts`](../../surfsense_local/electron/src/main/updater.ts), [`surfsense_local/electron/src/main/updater-cache/`](../../surfsense_local/electron/src/main/updater-cache/), [`surfsense_local/electron/patches/electron-updater@6.8.9.patch`](../../surfsense_local/electron/patches/electron-updater@6.8.9.patch), [`surfsense_local/electron/electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml), [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml), [`surfsense_local/frontend/src/features/updates/`](../../surfsense_local/frontend/src/features/updates/)
**Decisions:** [ADR 0020](../adr/0020-two-update-channels.md)

How to cut a release is in [`surfsense_local/RELEASE.md`](../../surfsense_local/RELEASE.md).

## Consent

Updates are the one call the app is designed to make on its own, so they are off until the user turns them on.

- The preference is `updates.json` in Electron's user data: `automatic`, false by default, and `lastCheckedAt`, which Settings › Network shows as the App updates row's last call.
- The check at launch runs only when `automatic` is on.
- Check now in Settings › About, the sidebar's update row and Check for Updates… in the macOS app menu share one check (`useCheckForUpdates`), which asks first while `automatic` is off. The menu shows only that prompt; the sidebar and Settings show the progress. Allow turns `automatic` on, which also enables the launch check.
- `autoDownload` is false. The download starts from the `update-available` event, so it only ever follows a check the user enabled or clicked.
- Installing waits for the user: the restart action in Settings, the sidebar or the title bar calls `quitAndInstall()`, and only once the download is ready.

This is not an `egress.require()` destination, because electron-updater runs in the Electron main process where the backend's check cannot see it ([egress](egress.md)). A development build shows the same controls and never checks.

## Update size

Downloads are differential: electron-updater fetches only the blocks that changed, using the `.blockmap` files electron-builder publishes with each release. electron-updater 6.8.9's GitHub provider asks for one byte range per request, which GitHub serves, and any failure falls back to downloading the whole file, so the result is always the published file.

A proxy or antivirus web shield that drops the `Range` header answers each of those requests with the whole file. electron-updater 6.8.9 writes that body out once per range and checks the sha512 only at the end, so a Windows update would keep downloading until the disk filled. [`patches/electron-updater@6.8.9.patch`](../../surfsense_local/electron/patches/electron-updater@6.8.9.patch), applied by pnpm through `patchedDependencies` in `electron/pnpm-workspace.yaml`, makes any reply other than 206 end the differential attempt at the first request, and the update then downloads whole, as it did before differential downloads were on. It covers the AppImage's blockmap read too. `scripts/electron-updater-ranges.test.mjs` runs electron-updater against a server that ignores `Range`. An electron-updater upgrade has to carry the patch over, because it names 6.8.9.

| Platform | Patches | Typical update |
|---|---|---|
| Windows | `installer.exe` in `%LOCALAPPDATA%\surfsense-local-electron-updater\`, the copy of the installer every install leaves there | about 128 MB instead of 1.16 GB (v2.2.2 → v2.2.3, planned from the real blockmaps; 129 MB measured end to end the other way) |
| macOS | `update.zip` in `~/Library/Caches/surfsense-local-electron-updater/`, the copy of the last downloaded zip | whole (1.28 GB) until a first update leaves `update.zip`, then about 187 MB (planned) |
| AppImage | the running AppImage, through the blockmap embedded in it | about 42 MB |
| deb | nothing; electron-updater always downloads a deb whole | 1.28 GB |

An app at 2.2.3 or earlier still downloads its next update whole, because those versions turn differential downloads off.

Fewer bytes do not always mean a shorter wait. A Windows update is about 800 range requests made one after another, with a 1 s pause after every 100; 129 MB took 47–69 s in testing. On a link faster than roughly 150–200 Mbit/s the "Downloading" state can therefore last longer than a whole download would. On macOS electron-updater keeps the last download as `update.zip` (about 1.28 GB), the base of the next update. From a download until its install the cache holds that copy as well as the one in `pending/`, about 2.55 GB in all; the install frees `pending/`.

On Windows a differential update needs `installer.exe` and `current.blockmap` to describe the same version. Every install overwrites `installer.exe` with the installed version, but electron-updater saves `current.blockmap` with each download. A download that is not installed yet, or a version installed by hand, breaks that pairing: the patched file fails its sha512, and the update downloads whole after the wasted differential attempt. So on Windows `updater-cache/` deletes `current.blockmap` before every check, and electron-updater fetches the installed version's blockmap (about 1 MB), which always matches. On macOS `update.zip` and `current.blockmap` come from the same download and stay together; Linux uses neither.

electron-updater downloads into `pending/` beside that base and empties it only when the next download starts, so the installer of the version just installed would sit there until the next update. The app records the downloaded version in `pending/downloaded-version.json`. At launch `updater-cache/` empties `pending/` unless it holds a version newer than the running app. A download with no record was made by an app from before this one, so it is emptied too; a record that cannot be read keeps the download. It is also emptied when a check finds nothing newer than the running app, for instance after a release is pulled, unless this session was offered an update, since quitting installs that download. Every check waits until this tidying is done, so a download never lands in a folder being emptied. `installer.exe` and `update.zip` stay, because they are the base of the next update.

## Two apps, one repo

| | Desktop app 2.x | Legacy desktop 0.0.x |
|---|---|---|
| Finds the release | newest entry of the releases feed (`allowPrerelease = true`) | `/releases/latest` |
| Reads | `stable.yml`, `stable-mac.yml`, `stable-linux.yml` | `latest.yml`, `latest-mac.yml`, `latest-linux.yml` |
| Is offered | the newest 2.x release | v0.0.40 |

`publish.channel: stable` in `electron-builder.yml` gives the new app its own manifest names, so it never writes the legacy feed and reads it only as electron-updater's fallback: with `allowPrerelease` set, a failed `stable*.yml` fetch is retried with `latest*.yml` (`GitHubProvider` in electron-updater 6.8.9). Since 21 Sep 2026 GitHub's Latest names the newest 2.x release, so a legacy client asking `/releases/latest` lands on a 2.x release. The `legacy-update-bridge` job in `release-local.yml` answers it: on a tag push, once all three builds succeed, it downloads v0.0.40's three `latest*.yml`, prepends `tag: v0.0.40`, checks the tag and version lines, and uploads them onto the new release. electron-updater lets a manifest's `tag` override the release it resolved and builds download URLs from it, so legacy clients are offered v0.0.40 and fetch it from v0.0.40's own assets, with nothing duplicated. That was verified against electron-updater 6.8.3, which every legacy release from v0.0.30 on pins.

Without the bridge every legacy update check 404s on a missing `latest*.yml`. The job must therefore be green on every release, and must stay while 0.0.x clients still check in.

`allowPrerelease = true` makes the app take the newest entry of the releases feed rather than `/releases/latest`. It was required while Latest stayed pinned to the legacy release; its comment in `updater.ts` notes that it no longer is, and that dropping it changes behaviour for shipped clients, so that change ships on its own. 2.0.0 shipped without it and resolves `/releases/latest`, which has named a 2.x release since 21 Sep. While it is set, an app on a stable version takes the newest feed entry even when that entry is a prerelease, so this app must never publish a prerelease-semver tag.

## What a release carries

A `v*` tag equal to `surfsense_local/VERSION` starts the workflow, which fails when the two differ. electron-builder uploads the installers and the three `stable*.yml` onto a draft, and the bridge job adds the three `latest*.yml`. The draft is published only once all six manifests are on it, because publishing makes it Latest and both updaters read their manifest off it at once ([`RELEASE.md`](../../surfsense_local/RELEASE.md)).

| Platform | Installer | Updates through |
|---|---|---|
| macOS arm64 | `SurfSense-arm64.dmg` | `SurfSense-arm64.zip`; electron-updater needs the zip, so the target is `[dmg, zip]` |
| Windows x64 | `SurfSense-Setup.exe` | the same NSIS installer |
| Linux x64 | `SurfSense.AppImage` | the AppImage |
| Linux x64 | `SurfSense.deb` | likely the deb (Known gaps) |

## Download links

Artifact names carry no version, so the root README's links to `/releases/latest/download/<name>` always reach the release GitHub marks Latest. The site's downloads (`surfsense_web/lib/app-release.ts`) and the license email (`surfsense_backend/app/license/release.py`) pin a tag instead, `APP_RELEASE_VERSION`, which `surfsense_local/scripts/bump-version.sh` writes into both. Each reads that tag's assets from the GitHub API and picks installers by suffix, so a deployed page, or a mail already sent, keeps offering the build it was made for. The pin moves when the web app and the backend are deployed with the bump.

## The legacy app

`surfsense_desktop/` left the tree on 17 Sep 2026; its source is at tag `archive/hosted-2026-09`. v0.0.40 caps its updater below 1.0.0, downloading only an offered version that starts with `0.`, and at startup reads `sunset` from the hosted `/health` to load the live `/sunset` page ([contract 4](../contracts/04-sunset-flag.md), [sunset](sunset.md)). The cap is not a live guard: it hangs off `update-available`, and a release without `latest*.yml` fails the check with a 404 before that event fires. The channel names keep 2.x manifests away from legacy clients, and the bridge keeps their checks from failing.

## Known gaps

- The deb build likely auto-updates, although the launch plan said it would not: electron-builder writes `resources/package-type` for a deb, electron-updater picks its deb updater from that file, and v2.0.2's `stable-linux.yml` on the release lists `SurfSense.deb`. Not checked on an installed deb.
- The macOS differential path has only been planned from the real blockmaps, not run end to end. A failure there falls back to a whole download.
- Uninstalling leaves `%LOCALAPPDATA%\surfsense-local-electron-updater\` behind, with the 1.16 GB `installer.exe` in it.
- Nothing takes an installed previous version through an update before users get it. The updater reads only published releases, so [`RELEASE.md`](../../surfsense_local/RELEASE.md)'s check from the previous version is by hand: the draft's installer over that version before publishing, the update itself only after.
