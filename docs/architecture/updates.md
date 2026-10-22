# App updates

The desktop app updates itself with electron-updater from the GitHub Releases of `MODSetter/SurfSense`, on its own `stable` channel, and only once the user has allowed it. Updates are free for everyone and carry no license logic. The legacy 0.0.x desktop app reads the same releases, so the two apps are kept apart by the names of the manifests each one reads, not by GitHub's Latest pointer.

**Code:** [`surfsense_local/electron/src/main/updater.ts`](../../surfsense_local/electron/src/main/updater.ts), [`surfsense_local/electron/electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml), [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml), [`surfsense_local/frontend/src/features/updates/`](../../surfsense_local/frontend/src/features/updates/)
**Decisions:** [ADR 0020](../adr/0020-two-update-channels.md)

How to cut a release is in [`surfsense_local/RELEASE.md`](../../surfsense_local/RELEASE.md).

## Consent

Updates are the one call the app is designed to make on its own, so they are off until the user turns them on.

- The preference is `updates.json` in Electron's user data: `automatic`, false by default, and `lastCheckedAt`, which Settings › Network shows as the App updates row's last call.
- The check at launch runs only when `automatic` is on.
- Check now in Settings › About, the sidebar's update row and Check for Updates… in the macOS app menu share one check (`useCheckForUpdates`), which asks first while `automatic` is off. The menu shows only that prompt; the sidebar and Settings show the progress. Allow turns `automatic` on, which also enables the launch check.
- `autoDownload` is false. The download starts from the `update-available` event, so it only ever follows a check the user enabled or clicked.
- A downloaded update installs when the user restarts from the prompt in Settings, the sidebar or the title bar, which calls `quitAndInstall()` once the download is ready, or else the next time they quit: `autoInstallOnAppQuit`, electron-updater's default, is set to true on purpose. The update prompt says both.

## What a check sends

Each request a check makes to github.com sends the IP address and the user agent `electron-builder`. It reads the releases feed, `MODSetter/SurfSense/releases.atom`, then asks the newest release for the platform's manifest, `stable.yml`, `stable-mac.yml` or `stable-linux.yml`, and asks again for `latest*.yml` when that fails (Two apps, one repo, below). GitHub redirects release files to its download host on `githubusercontent.com`, which also sees the IP address; the update's own download goes the same way. No request sends the app version or an ID.

electron-updater keeps a random install ID in `userData/.updaterId` for staged rollouts and sends it as `x-user-staging-id` on the feed and manifest requests. `attachUpdater` sets `requestHeaders` to send `0` in that header instead, and electron-updater merges `requestHeaders` over its own, so the constant also goes on downloads. `stagingPercentage` still reads the local file. Versions up to 2.2.3 sent the ID.

This is not an `egress.require()` destination, because electron-updater runs in the Electron main process where the backend's check cannot see it ([egress](egress.md)). Differential downloads are off, because GitHub's CDN rejects the multi-range requests they need. A development build shows the same controls and never checks.

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

## What GitHub counts

A daily job saves every asset's download count, and says which client each count measures: people, the 2.x updater or legacy clients ([release stats](release-stats.md)).

## Download links

Every installer link outside the app goes through one redirect on the website, `/downloads/<platform>` for `windows`, `mac`, `linux-appimage` and `linux-deb` (`surfsense_web/app/(home)/downloads/[platform]/route.ts`). It answers a 302 to the GitHub asset, so the bytes still come from GitHub, and counts the download on the way: a personless `installer_download` event with the platform, `src` (where the link was: `site`, `readme`, `email`, `app`, `pricing`, else `other`), the version and the country Vercel derives, sent from the server so a content blocker does not hide it. Obvious bots and mail scanners, matched by User-Agent, are redirected but not counted. The response is `no-store`.

The redirect's `v` pins a tag: the license email (`surfsense_backend/app/license/release.py`) sends `src=email&v=<tag>`, so a mail already sent keeps offering the build it was sent for. Without `v`, or with a tag older than 2.0.2, it uses `APP_RELEASE_VERSION` in `surfsense_web/lib/app-release.ts`; `surfsense_local/scripts/bump-version.sh` writes that pin into both files, and it moves when the web app and the backend are deployed with the bump. The site's `/downloads` grid (`src=site`) and every README's table (`src=readme`) use the pin, so they follow a release on deploy rather than on GitHub's Latest.

A tag counts only once GitHub serves it. The redirect checks it against the newest 30 published releases from the GitHub API, cached for an hour, and otherwise sends the link to `/releases/latest/download/<file>` with the version recorded as `latest`. That covers release day, when the bump is deployed while its release is still a draft whose assets 404 for anyone signed out (about an hour, longer when a release run fails), a tag that was never published or is older than those 30, and a GitHub API that cannot be reached. Artifact names have carried no version since 2.0.2, which is why the redirect builds each URL from a tag and a fixed file name and why Latest always has the file; renaming an installer breaks every link already sent.

## The legacy app

`surfsense_desktop/` left the tree on 17 Sep 2026; its source is at tag `archive/hosted-2026-09`. v0.0.40 caps its updater below 1.0.0, downloading only an offered version that starts with `0.`, and at startup reads `sunset` from the hosted `/health` to load the live `/sunset` page ([contract 4](../contracts/04-sunset-flag.md), [sunset](sunset.md)). The cap is not a live guard: it hangs off `update-available`, and a release without `latest*.yml` fails the check with a 404 before that event fires. The channel names keep 2.x manifests away from legacy clients, and the bridge keeps their checks from failing.

## Known gaps

- The deb build likely auto-updates, although the launch plan said it would not: electron-builder writes `resources/package-type` for a deb, electron-updater picks its deb updater from that file, and v2.0.2's `stable-linux.yml` on the release lists `SurfSense.deb`. Not checked on an installed deb.
- Nothing takes an installed previous version through an update before users get it. The updater reads only published releases, so [`RELEASE.md`](../../surfsense_local/RELEASE.md)'s check from the previous version is by hand: the draft's installer over that version before publishing, the update itself only after.
