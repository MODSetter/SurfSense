# App updates

The desktop app updates itself with electron-updater from the GitHub Releases of `MODSetter/SurfSense`, on its own `stable` channel, and only once the user has allowed it. It reads the release's manifest through `updates.surfsense.com`, which counts the check, and straight from GitHub whenever that host fails; installers always come from GitHub. Updates are free for everyone and carry no license logic. The legacy 0.0.x desktop app reads the same releases, so the two apps are kept apart by the names of the manifests each one reads.

**Code:** [`surfsense_local/electron/src/main/updater.ts`](../../surfsense_local/electron/src/main/updater.ts) and, in Electron main, `update-feed/`, `update-schedule/` and `admin-policy/`; [`surfsense_local/electron/electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml), [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml), [`surfsense_local/frontend/src/features/updates/`](../../surfsense_local/frontend/src/features/updates/), [`surfsense_local/frontend/src/features/privacy-choices/`](../../surfsense_local/frontend/src/features/privacy-choices/)
**Decisions:** [ADR 0020](../adr/0020-two-update-channels.md), [ADR 0068](../adr/0068-opt-in-id-less-update-checks-and-usage-statistics.md)
**Contract:** [contract 5](../contracts/05-desktop-telemetry.md), part A

How to cut a release is in [`surfsense_local/RELEASE.md`](../../surfsense_local/RELEASE.md).

## Consent

Updates are a call the app makes on its own, so they are off until the user turns them on.

- A new install asks in onboarding's Privacy choices step, beside usage statistics, with neither answer chosen for the user ([usage statistics](usage-statistics.md#consent)). An install that finished onboarding earlier keeps the setting it had.
- The preference is `updates.json` in Electron's user data: `automatic`, false by default; `lastCheckedAt`, which Settings › Network shows as the App updates row's last call; and `lastAutomaticDay`, the UTC day of the last automatic check.
- The automatic check runs at most once a UTC day: at launch, and from an hourly tick once the day turns while the app stays open. The day is marked before the check, so a failed check waits for the next day. A day's automatic checks therefore count the installs open that day, with no identifier on the wire.
- Check now in Settings › About, the sidebar's update row and Check for Updates… in the macOS app menu share one check (`useCheckForUpdates`), which asks first while `automatic` is off, naming the host it asks. The menu shows only that prompt; the sidebar and Settings show the progress. Allow turns `automatic` on, which also enables the daily check.
- An admin policy file with `"updates": "off"` turns both off and locks the setting; Check now is disabled and says why. `"updateFeed"` names an `https` mirror instead of `updates.surfsense.com`, with no GitHub fallback ([usage statistics](usage-statistics.md#policy) says where the file lives).
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

This is not an `egress.require()` destination, because electron-updater runs in the Electron main process where the backend's check cannot see it ([egress](egress.md)). Differential downloads are off, because GitHub's CDN rejects the multi-range requests they need. A development build shows the same controls and never checks.

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
- Nothing takes an installed previous version through an update before users get it. The updater reads only published releases, so [`RELEASE.md`](../../surfsense_local/RELEASE.md)'s check from the previous version is by hand: the draft's installer over that version before publishing, the update itself only after.
