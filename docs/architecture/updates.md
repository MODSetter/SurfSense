# App updates

The desktop app updates itself with electron-updater from the GitHub Releases of `MODSetter/SurfSense`, on its own `stable` channel, and only once the user has allowed it. It reads the release's manifest through `updates.surfsense.com`, which counts the check, and straight from GitHub whenever that host fails; installers always come from GitHub. Updates are free for everyone and carry no license logic. The legacy 0.0.x desktop app reads the same releases, so the two apps are kept apart by the names of the manifests each one reads.

**Code:** [`surfsense_local/electron/src/main/updater.ts`](../../surfsense_local/electron/src/main/updater.ts) and, in Electron main, `update-feed/`, `update-schedule/`, `admin-policy/`, [`install-channel/`](../../surfsense_local/electron/src/main/install-channel/) and [`updater-cache/`](../../surfsense_local/electron/src/main/updater-cache/); [`surfsense_local/electron/patches/electron-updater@6.8.9.patch`](../../surfsense_local/electron/patches/electron-updater@6.8.9.patch), [`surfsense_local/electron/electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml), [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml), [`surfsense_local/frontend/src/features/updates/`](../../surfsense_local/frontend/src/features/updates/), [`surfsense_local/frontend/src/features/privacy-choices/`](../../surfsense_local/frontend/src/features/privacy-choices/)
**Decisions:** [ADR 0020](../adr/0020-two-update-channels.md), [ADR 0070](../adr/0070-opt-in-id-less-update-checks-and-usage-statistics.md)
**Contract:** [contract 5](../contracts/05-desktop-telemetry.md), parts A and C

How to cut a release is in [`surfsense_local/RELEASE.md`](../../surfsense_local/RELEASE.md).

## Consent

Updates are a call the app makes on its own, so they are off until the user turns them on.

- A new install asks in onboarding's Privacy choices step, beside usage statistics, with neither answer chosen for the user ([usage statistics](usage-statistics.md#consent)). An install that finished onboarding earlier keeps the setting it had.
- The preference is `updates.json` in Electron's user data: `automatic`, false by default; `lastCheckedAt`, which Settings › Network shows as the App updates row's last call; and `lastAutomaticDay`, the UTC day of the last automatic check.
- The automatic check runs at most once a UTC day: at launch, and from an hourly tick once the day turns while the app stays open. The day is marked only once a check reads a manifest, from either host. A check that reads none is tried again on the hourly tick, at most three times a UTC day. A day's automatic checks therefore approximate the installs open that day, with no identifier on the wire; a retry after a failed check can add a second event from one install.
- Check now in Settings › About, the sidebar's update row and Check for Updates… in the macOS app menu share one check (`useCheckForUpdates`), which asks first while `automatic` is off, naming the host it asks. The menu shows only that prompt; the sidebar and Settings show the progress. Allow turns `automatic` on, which also enables the daily check.
- An admin policy file with `"updates": "off"` turns both off and locks the setting; Check now is disabled and says why. `"updateFeed"` names an `https` mirror instead of `updates.surfsense.com`, with no GitHub fallback ([usage statistics](usage-statistics.md#policy) says where the file lives).
- An install a package manager owns never checks: Scoop, the AUR and Nix, whose packages write `resources/install-channel`, a snap or a flatpak, known from their environment, and a deb from SurfSense's apt repository, known from `/etc/apt/sources.list.d/surfsense.list` ([contract 5](../contracts/05-desktop-telemetry.md), part C, has the order). The setting is locked as under the policy, which names the lock when both apply. Settings › About then shows only "Updates come from" that package manager, with no daily check described and no "Show exactly what's sent". The app does not construct electron-updater at all for such an install, so a repackaged deb's `package-type` cannot start its deb updater.
- The sidebar's update row is gone while either lock holds, since a check it started would be refused.
- Scoop and the AUR must first be submitted with the first release that carries `install-channel/`, not earlier: an older release has no channel lock, so it would update itself out from under them ([packaging](../../surfsense_local/packaging/README.md)).
- Homebrew and winget run the release's own installer, so nothing marks them and the in-app updater stays available beside `brew upgrade` and `winget upgrade`. The Homebrew cask declares `auto_updates` inside `on_macos` only, so plain `brew upgrade` updates the Mac app while its bundle's version is older than the cask's, as it is whenever the in-app updater is off, and always updates the Linux AppImage, which has no bundle version to compare.
- `autoDownload` is false. The download starts from the `update-available` event, so it only ever follows a check the user enabled or clicked.
- A downloaded update installs when the user restarts from the prompt in Settings, the sidebar or the title bar, which calls `quitAndInstall()` once the download is ready, or else the next time they quit: `autoInstallOnAppQuit`, electron-updater's default, is set to true on purpose. The update prompt says both.

## What a check sends

A custom electron-updater provider asks `https://updates.surfsense.com/api/updates/<channel file>`, where the file is `stable.yml`, `stable-mac.yml`, `stable-linux.yml` or `stable-linux-arm64.yml`. That one request carries the IP address and four headers, and no ID:

| Header | Example |
|---|---|
| `User-Agent` | `SurfSense`, which the outbound session sets on every request, with no version |
| `X-SurfSense-Version` | `2.2.4` |
| `X-SurfSense-Platform` | `win32-x64`, `darwin-arm64`, `linux-x64` |
| `X-SurfSense-OS` | `windows-11`, `macos-15`, `linux` |

It goes through an in-memory session with no cache and no cookies, and refuses a redirect, so the headers never reach another host. The route there serves GitHub's own manifest for the latest release, with each file rewritten to its GitHub release URL, and records one personless event with the country its host derives from the IP address; it never stores the address, though the hosting provider's request logs keep it for a short time ([contract 5](../contracts/05-desktop-telemetry.md), part A).

On any failure of that host within 10 s, a status other than 200, or a manifest whose files do not point at the GitHub release, the provider asks `github.com/MODSetter/SurfSense/releases/latest/download/<channel file>` directly, sending only the IP address and `User-Agent: SurfSense`. Only when GitHub fails too does the check fail, so `updates.surfsense.com` can never hold an update back. With a policy mirror, the mirror is the only host asked.

The installer then downloads from the GitHub release, or from the mirror, with no SurfSense header. GitHub redirects release files, the fallback's manifest included, to its download host on `githubusercontent.com`, which also sees the IP address. electron-updater keeps a random install ID in `userData/.updaterId` for staged rollouts and hands every provider an `x-user-staging-id` header; this provider ignores it, and `requestHeaders` is empty, so the ID leaves on no request. `stagingPercentage` still reads the local file. Versions up to 2.2.3 sent the ID.

Settings › About's "Show exactly what's sent" shows the last request to the feed with its URL and headers, the user agent included, kept in memory since launch, or, before the first check, the only headers a check sends. Without the privacy bridge, an Electron main from before this provider, the update prompt and Settings describe GitHub's releases instead of naming `updates.surfsense.com`.

This is not an `egress.require()` destination, because electron-updater runs in the Electron main process where the backend's check cannot see it ([egress](egress.md)). A development build shows the same controls and never checks.

An inactive electron-updater, such as its AppImage updater in an AppImage run without `$APPIMAGE`, answers a check with null and emits nothing. The check then puts back the state it found, idle unless an update was already downloaded, so Settings and the sidebar never stay on "Checking…". A check that throws keeps the `error` state electron-updater emitted first.

## Update size

Downloads are differential: electron-updater fetches only the blocks that changed, using the `.blockmap` files electron-builder publishes with each release. The app's provider asks for one byte range per request, as electron-updater's `GitHubProvider` does (`update-feed/surfsense-feed-provider.ts`): GitHub's release CDN serves a single range and answers several with 501, which would turn every update into a whole download. Any failure falls back to downloading the whole file, so the result is always the published file.

A proxy or antivirus web shield that drops the `Range` header answers each of those requests with the whole file. electron-updater 6.8.9 writes that body out once per range and checks the sha512 only at the end, so a Windows update would keep downloading until the disk filled. [`patches/electron-updater@6.8.9.patch`](../../surfsense_local/electron/patches/electron-updater@6.8.9.patch), applied by pnpm through `patchedDependencies` in `electron/pnpm-workspace.yaml`, makes any reply other than 206 end the differential attempt at the first request, and the update then downloads whole, as it did before differential downloads were on. It covers the AppImage's blockmap read too. `scripts/electron-updater-ranges.test.mjs` runs electron-updater against a server that ignores `Range`. An electron-updater upgrade has to carry the patch over, because it names 6.8.9.

| Platform | Patches | Typical update |
|---|---|---|
| Windows | `installer.exe` in `%LOCALAPPDATA%\surfsense-local-electron-updater\`, the copy of the installer every install leaves there | about 128 MB instead of 1.16 GB (v2.2.2 → v2.2.3, planned from the real blockmaps; 129 MB measured end to end the other way) |
| macOS | `update.zip` in `~/Library/Caches/surfsense-local-electron-updater/`, the copy of the last downloaded zip | whole (1.28 GB) until a first update leaves `update.zip`, then about 187 MB (planned) |
| AppImage | the running AppImage, through the blockmap embedded in it | about 42 MB |
| deb | nothing; electron-updater always downloads a deb whole | 1.28 GB |
| rpm | nothing; downloaded whole, like the deb | the whole rpm |

An app at 2.2.3 or earlier still downloads its next update whole, because those versions turn differential downloads off.

Fewer bytes do not always mean a shorter wait. A Windows update is about 800 range requests made one after another, with a 1 s pause after every 100; 129 MB took 47–69 s in testing. On a link faster than roughly 150–200 Mbit/s the "Downloading" state can therefore last longer than a whole download would. On macOS electron-updater keeps the last download as `update.zip` (about 1.28 GB), the base of the next update. From a download until the installed version's first launch, which frees `pending/` (below), the cache holds that copy as well as the one in `pending/`, about 2.55 GB in all.

On Windows a differential update needs `installer.exe` and `current.blockmap` to describe the same version. Every install, through the updater or by hand, overwrites `installer.exe` with the installed version, but electron-updater replaces `current.blockmap` with each download's, copying it out of `pending/` right after `update-downloaded`. A download that is not installed yet, or a version installed by hand, breaks that pairing: the patched file fails its sha512, and the update downloads whole after the wasted differential attempt. Without the file, electron-updater fetches the installed version's blockmap (about 1 MB) from that version's release, which fails once the release is pulled, and the update again downloads whole. So on `update-downloaded` `updater-cache/` records the version in `current-blockmap-version.json` beside the blockmap, and before every check it deletes both unless the record names the installed version. An update installed through the updater therefore keeps its own blockmap, and the next update does not depend on its release staying published. A download whose blockmap could not be fetched goes whole and saves no blockmap, so it clears the record instead. A second download in one session reuses `pending/` without emptying it, so on `update-available` `updater-cache/` also deletes any blockmap an earlier download left there, unless `pending/` already holds the offered version. On macOS `update.zip` and `current.blockmap` normally come from the same download and stay together, with no record (see Known gaps); Linux uses neither.

electron-updater downloads into `pending/` beside that base and empties it only when a download fails or a later launch downloads another version, so the installer of the version just installed would sit there until the next update. The app records the downloaded version in `pending/downloaded-version.json`. At launch `updater-cache/` empties `pending/` unless it holds a version newer than the running app. A download with no record was made by an app from before this one, so it is emptied too; a record that cannot be read keeps the download. It is also emptied when a check finds nothing newer than the running app, for instance after a release is pulled, unless this session was offered an update, since quitting installs that download. Every check waits until this tidying is done, so a download never lands in a folder being emptied. `installer.exe` and `update.zip` stay, because they are the base of the next update.

## Two apps, one repo

| | Desktop app 2.x | Legacy desktop 0.0.x |
|---|---|---|
| Finds the release | GitHub's Latest release, through `updates.surfsense.com` or directly | `/releases/latest` |
| Reads | `stable.yml`, `stable-mac.yml`, `stable-linux.yml` | `latest.yml`, `latest-mac.yml`, `latest-linux.yml` |
| Is offered | the newest 2.x release | v0.0.40 |

`publish.channel: stable` in `electron-builder.yml` gives the new app its own manifest names, so it never writes the legacy feed, and its custom provider never reads `latest*.yml`, which `updates.surfsense.com` also refuses with a 404. Since 21 Sep 2026 GitHub's Latest names the newest 2.x release, so a legacy client asking `/releases/latest` lands on a 2.x release. The `legacy-update-bridge` job in `release-local.yml` answers it: on a tag push, once all three builds succeed, it downloads v0.0.40's three `latest*.yml`, prepends `tag: v0.0.40`, checks the tag and version lines, and uploads them onto the new release. electron-updater lets a manifest's `tag` override the release it resolved and builds download URLs from it, so legacy clients are offered v0.0.40 and fetch it from v0.0.40's own assets, with nothing duplicated. That was verified against electron-updater 6.8.3, which every legacy release from v0.0.30 on pins.

Without the bridge every legacy update check 404s on a missing `latest*.yml`. The job must therefore be green on every release, and must stay while 0.0.x clients still check in.

Versions before the custom provider used electron-updater's `GitHubProvider` with `allowPrerelease = true`, which takes the newest entry of the releases feed rather than `/releases/latest`, and retries a failed `stable*.yml` with `latest*.yml` (electron-updater 6.8.9). They are still in the field, and while they are, an app on a stable version takes the newest feed entry even when it is a prerelease, so this app must never publish a prerelease-semver tag. The custom provider reads only `releases/latest/download`, which GitHub serves from the release marked Latest.

## What a release carries

A `v[1-9]*` tag equal to `surfsense_local/VERSION` starts the workflow, which fails when the two differ. electron-builder uploads the installers and the three `stable*.yml` onto a draft, and the bridge job adds the three `latest*.yml`. The draft is published only once all six manifests are on it, because publishing makes it Latest and both updaters read their manifest off it at once ([`RELEASE.md`](../../surfsense_local/RELEASE.md)).

| Platform | Installer | Updates through |
|---|---|---|
| macOS arm64 | `SurfSense-arm64.dmg` | `SurfSense-arm64.zip`; electron-updater needs the zip, so the target is `[dmg, zip]` |
| Windows x64 | `SurfSense-Setup.exe` | the same NSIS installer |
| Linux x64 | `SurfSense.AppImage` | the AppImage |
| Linux x64 | `SurfSense.deb` | the deb, through electron-updater's deb updater, which it picks from `resources/package-type`; apt instead once the apt repository is set up |
| Linux x64 | `SurfSense.rpm` | the rpm, through the rpm updater, picked the same way |
| Linux x64 | the `surfsense-local` snap, uploaded to the Snap Store by its own job and not to the release | snapd, from the Snap Store; the app never checks |
| Linux x64 | `SurfSense.deb` from the flat apt repository on the release (`Packages`, `Packages.gz`, `Release`, `Release.gpg`, `InRelease`, `surfsense-archive-keyring.gpg`) | apt, once `/etc/apt/sources.list.d/surfsense.list` exists; the app never checks |

The apt source is `deb [signed-by=/usr/share/keyrings/surfsense-archive-keyring.gpg] https://github.com/MODSetter/SurfSense/releases/latest/download/ ./`, so apt, like the updater, reads the release marked Latest.

## What GitHub counts

A daily job saves every asset's download count, and says which client each count measures: people, the 2.x updater or legacy clients ([release stats](release-stats.md)).

## Download links

Every installer link outside the app goes through one redirect on the website, `/downloads/<platform>` for `windows`, `mac`, `linux-appimage`, `linux-deb` and `linux-rpm` (`website/app/(home)/downloads/[platform]/route.ts`). It answers a 302 to the GitHub asset, so the bytes still come from GitHub, and counts the download on the way: a personless `installer_download` event with the platform, `src` (where the link was: `site`, `readme`, `email`, `app`, `pricing`, else `other`), the version and the country Vercel derives, sent from the server so a content blocker does not hide it. Obvious bots and mail scanners, matched by User-Agent, are redirected but not counted. The response is `no-store`.

The redirect's `v` pins a tag: the license email (`backend/license/release.py`) sends `src=email&v=<tag>`, so a mail already sent keeps offering the build it was sent for. Without `v`, or with a tag older than 2.0.2, it uses `APP_RELEASE_VERSION` in `website/features/downloads/app-release.ts`; `surfsense_local/scripts/bump-version.sh` writes that pin into both files, and it moves when the web app and the backend are deployed with the bump. The site's `/downloads` grid (`src=site`) and every README's table (`src=readme`) use the pin, so they follow a release on deploy rather than on GitHub's Latest.

A tag counts only once GitHub serves it. The redirect checks it against the newest 30 published releases from the GitHub API, cached for an hour, and otherwise sends the link to `/releases/latest/download/<file>` with the version recorded as `latest`. That covers release day, when the bump is deployed while its release is still a draft whose assets 404 for anyone signed out (about an hour, longer when a release run fails), a tag that was never published or is older than those 30, and a GitHub API that cannot be reached. Artifact names have carried no version since 2.0.2, which is why the redirect builds each URL from a tag and a fixed file name and why Latest has every file but the rpm, which exists only from the first release that builds it. Until that release is Latest, `/downloads/linux-rpm` falls back to a file Latest does not have, and still counts the download. Renaming an installer breaks every link already sent.

## The legacy app

`surfsense_desktop/` left the tree on 17 Sep 2026; its source is at tag `archive/hosted-2026-09`. v0.0.40 caps its updater below 1.0.0, downloading only an offered version that starts with `0.`, and at startup reads `sunset` from the hosted `/health` to load the live `/sunset` page ([contract 4](https://github.com/MODSetter/SurfSense/blob/261edd605ba67f19e47a5e1b6852e2ef045235af/docs/contracts/04-sunset-flag.md), [sunset](https://github.com/MODSetter/SurfSense/blob/261edd605ba67f19e47a5e1b6852e2ef045235af/docs/architecture/sunset.md)). The cap is not a live guard: it hangs off `update-available`, and a release without `latest*.yml` fails the check with a 404 before that event fires. The channel names keep 2.x manifests away from legacy clients, and the bridge keeps their checks from failing.

## Known gaps

- The deb updates itself through electron-updater's deb updater unless SurfSense's apt source is configured, and the rpm through its rpm updater. Neither has been run on an installed package: each downloads the whole package and installs it as root through `pkexec` or `sudo`.
- The macOS differential path has only been planned from the real blockmaps, not run end to end. A failure there falls back to a whole download.
- On macOS a download whose blockmap could not be fetched replaces `update.zip` but not `current.blockmap`, so the next update downloads whole after a wasted differential attempt.
- Uninstalling leaves `%LOCALAPPDATA%\surfsense-local-electron-updater\` behind, with the 1.16 GB `installer.exe` in it.
- Removing the app on macOS leaves `~/Library/Caches/surfsense-local-electron-updater/` behind, with the 1.28 GB `update.zip` in it.
- Nothing takes an installed previous version through an update before users get it. The updater reads only published releases, so [`RELEASE.md`](../../surfsense_local/RELEASE.md)'s check from the previous version is by hand: the draft's installer over that version before publishing, the update itself only after.
