# Release stats

A daily job saves what GitHub counts about the desktop app's releases: every asset's download count and the repository's traffic, which GitHub keeps for 14 days only. It counts from outside the app and adds nothing to it ([ADR 0016](../adr/0016-no-telemetry.md)).

**Code:** [`.github/workflows/release-stats.yml`](../../.github/workflows/release-stats.yml), [`scripts/release_stats/`](../../scripts/release_stats/)

## The job

At 06:00 UTC every day, and on demand, the workflow runs `python -m release_stats snapshot`, standard library only, with `contents: read`:

1. It lists every release, page by page, following GitHub's next-page links and redirects only while they stay on `https://api.github.com`, since the token goes with every request and urllib would copy it onto a redirect; a link or redirect elsewhere stops the job with an error before anything is sent there. It records each published release's assets: tag, asset name, kind, cumulative `download_count`, publish time. Drafts are left out.
2. It reads views, clones, popular referrers and popular paths. Those endpoints need push access, which `GITHUB_TOKEN` never has, so they read through the `RELEASE_STATS_TOKEN` secret when it is set: a fine-grained token on this repository with Administration read. Without it the snapshot records why traffic is missing and keeps the asset counts.
3. The JSON is kept as a workflow artifact, `release-stats-<date>.json`, for 90 days.
4. When the `POSTHOG_PROJECT_API_KEY` secret is set, `python -m release_stats send` posts it to PostHog (`POSTHOG_HOST` repository variable, `https://us.i.posthog.com` by default) as personless events: one `github_release_asset_snapshot` per asset (`tag`, `asset`, `kind`, `download_count`, `published_at`) one `github_traffic_snapshot` with the 14-day totals and the referrers and paths, and one `github_traffic_day` (`day`, `views`, `view_uniques`, `clones`, `clone_uniques`) for each of the 13 whole days before the run. The 14-day totals overlap from one run to the next, so never sum them; sum the `github_traffic_day` figures instead.

Each `github_traffic_day` is timestamped at its day's midnight UTC with a uuid derived from the repository and the day, so every run resends the same event and PostHog keeps the latest copy: a second run on one day replaces the first rather than doubling it, and a missed run is filled in by the next one. PostHog drops the older copies in background merges, not at once, so an exact figure takes one event per `day` (for example `max(views)` grouped by `day`) before summing. The oldest day in GitHub's window may be cut short, so it is never sent.

GitHub runs a scheduled workflow only from the default branch, so the job starts once it reaches `main`. Counts are cumulative: a day's downloads are the difference between two snapshots.

## What each kind measures

GitHub counts requests, not installs or people, and gives no IP, version or id. The kind says which client makes the requests:

| Kind | Assets | Measures |
|---|---|---|
| `installer_windows` | `*.exe` | site, README, email and `install.ps1` downloads, winget installs and upgrades, Scoop installs and updates, which unpack the exe, and the bots that check each new winget manifest, plus every 2.x Windows update the app makes itself, the whole installer up to 2.2.3 and byte ranges of it after; the release's `stable.yml` count caps only that last share, winget installs included, since winget leaves the in-app updater in place |
| `installer_mac` | `*.dmg` | people, plus `brew install --cask`, `brew upgrade` and BrewTestBot's checks of each new cask; electron-updater never fetches it |
| `installer_appimage` | `*.AppImage` | fresh downloads, `install.sh` where no package manager is found, and Homebrew's cask on Linux, installs and upgrades, plus AppImage updates |
| `installer_deb` | `*.deb` | fresh downloads and `install.sh`'s fallback, plus, probably, the app's own deb updates ([updates](updates.md#known-gaps)); once the apt repository exists, apt fetches the deb from the release too, so every `apt upgrade` and apt install of SurfSense counts here; so does every AUR (`surfsense-bin`) install, upgrade or rebuild, since its PKGBUILD downloads the deb |
| `installer_rpm` | `*.rpm`: the 2.x `SurfSense.rpm` and the 0.0.x `SurfSense-0.0.N-x86_64.rpm` | fresh downloads, `install.sh` on dnf and zypper, and the app's own rpm updates; snapshots taken before this classification reached `main` carry `other` for the 0.0.x rpms |
| `update_zip_mac` | `*.zip` | macOS updates downloaded plus one-line installs on a Mac; only electron-updater and `install.sh` fetch it |
| `manifest_stable_windows`, `_mac`, `_linux` | `stable*.yml` | 2.x update checks that reach GitHub: one per launch of 2.2.3 or older with automatic updates on, per Check now in those versions, or per 2.2.4-or-later check falling back after `updates.surfsense.com` failed; that proxy also fetches each file from GitHub itself, at most once per 15-minute cache while installs ask it, about 96 a day per file (more if Vercel caches per region) |
| `manifest_legacy_windows`, `_mac`, `_linux` | `latest*.yml` | update checks from 0.0.x apps, mostly at login, plus 2.x checks retrying after a failed `stable*.yml` |
| `blockmap` | `*.blockmap` | up to 2.2.3, the noise floor of bots and mirrors (about 5 per asset), since those apps download updates whole; after it, the app's differential updates ([updates](updates.md#update-size)); on 0.0.x releases, legacy differential updates |
| `install_script` | `install.sh`, `install.ps1` | one per one-line install run, refused and failed runs included; runs, not installs |
| `apt_index` | `InRelease`, `Release`, `Release.gpg`, `Packages`, `Packages.gz`, `surfsense-archive-keyring.gpg` | `InRelease` (or `Release` and `Release.gpg`) once per `apt update` on every machine with the source, `Packages*` when a new release changed it, the keyring once per `install.sh` setup; apt reads them through `latest/download`, so the count lands on whichever release was Latest at the time, not the one a machine runs |
| `checksums` | `SHA256SUMS` | one per install-script run, plus packagers and people checking a download by hand |
| `other` | anything else | for example a snap, or a manifest for an unknown channel |

Package managers fetch the release's own files: winget and Scoop the exe, Homebrew the dmg and the AppImage, apt and the AUR the deb ([install channels](install-channels.md)). They never read `stable*.yml` to do it, so a `stable*.yml` count caps only the app's own updates, and an installer count minus that cap is not all website downloads.

The classification and its reasons live in `release_stats/asset_kinds.py`.

## Tests

`scripts/release_stats/tests/` covers the classification of every asset name the releases have carried or are about to carry (the rpm, install scripts, apt repository and `SHA256SUMS`), paging through releases, refusing a next-page link or a redirect off the API's origin, skipping traffic on a refused token, the events' shape and batching, and each day's event keeping one identity across reruns, with GitHub and PostHog faked at `urlopen`; urllib follows redirects itself, so those tests run against a server on 127.0.0.1. They need only pytest: `python -m pytest` from `scripts/release_stats`.

## Known gaps

- Traffic is skipped until a maintainer adds the `RELEASE_STATS_TOKEN` secret.
- The job has not run on GitHub yet; it was checked against the live releases API without a token.
