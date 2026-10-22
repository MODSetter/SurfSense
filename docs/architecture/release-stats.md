# Release stats

A daily job saves what GitHub counts about the desktop app's releases: every asset's download count and the repository's traffic, which GitHub keeps for 14 days only. It counts from outside the app and adds nothing to it ([ADR 0016](../adr/0016-no-telemetry.md)).

**Code:** [`.github/workflows/release-stats.yml`](../../.github/workflows/release-stats.yml), [`scripts/release_stats/`](../../scripts/release_stats/)

## The job

At 06:00 UTC every day, and on demand, the workflow runs `python -m release_stats snapshot`, standard library only, with `contents: read`:

1. It lists every release, page by page, and records each published release's assets: tag, asset name, kind, cumulative `download_count`, publish time. Drafts are left out.
2. It reads views, clones, popular referrers and popular paths. Those endpoints need push access, which `GITHUB_TOKEN` never has, so they read through the `RELEASE_STATS_TOKEN` secret when it is set: a fine-grained token on this repository with Administration read. Without it the snapshot records why traffic is missing and keeps the asset counts.
3. The JSON is kept as a workflow artifact, `release-stats-<date>.json`, for 90 days.
4. When the `POSTHOG_PROJECT_API_KEY` secret is set, `python -m release_stats send` posts it to PostHog (`POSTHOG_HOST` repository variable, `https://us.i.posthog.com` by default) as personless events: one `github_release_asset_snapshot` per asset (`tag`, `asset`, `kind`, `download_count`, `published_at`) one `github_traffic_snapshot` with the 14-day totals and the referrers and paths, and one `github_traffic_day` (`day`, `views`, `view_uniques`, `clones`, `clone_uniques`) for each of the 13 whole days before the run. The 14-day totals overlap from one run to the next, so never sum them; sum the `github_traffic_day` figures instead.

Each `github_traffic_day` is timestamped at its day's midnight UTC with a uuid derived from the repository and the day, so every run resends the same event and PostHog keeps the latest copy: a second run on one day replaces the first rather than doubling it, and a missed run is filled in by the next one. PostHog drops the older copies in background merges, not at once, so an exact figure takes one event per `day` (for example `max(views)` grouped by `day`) before summing. The oldest day in GitHub's window may be cut short, so it is never sent.

GitHub runs a scheduled workflow only from the default branch, so the job starts once it reaches `main`. Counts are cumulative: a day's downloads are the difference between two snapshots.

## What each kind measures

GitHub counts requests, not installs or people, and gives no IP, version or id. The kind says which client makes the requests:

| Kind | Assets | Measures |
|---|---|---|
| `installer_windows` | `*.exe` | site, README and email downloads, plus every 2.x Windows update, which fetches the full installer; the release's `stable.yml` count caps the updater's share |
| `installer_mac` | `*.dmg` | people only; no updater fetches it |
| `installer_appimage` | `*.AppImage` | fresh downloads plus AppImage updates |
| `installer_deb` | `*.deb` | fresh downloads plus, probably, deb updates ([updates](updates.md#known-gaps)) |
| `update_zip_mac` | `*.zip` | macOS updates downloaded; only electron-updater fetches it |
| `manifest_stable_windows`, `_mac`, `_linux` | `stable*.yml` | 2.x update checks: one per launch with automatic updates on, or per Check now |
| `manifest_legacy_windows`, `_mac`, `_linux` | `latest*.yml` | update checks from 0.0.x apps, mostly at login, plus 2.x checks retrying after a failed `stable*.yml` |
| `blockmap` | `*.blockmap` | on 2.x releases, the noise floor of bots and mirrors (about 5 per asset), since differential updates are off; on 0.0.x releases, legacy differential updates |
| `other` | anything else | for example the 0.0.x rpm |

The classification and its reasons live in `release_stats/asset_kinds.py`.

## Tests

`scripts/release_stats/tests/` covers the classification of every asset name the releases have carried, paging through releases, skipping traffic on a refused token, the events' shape and batching, and each day's event keeping one identity across reruns, with GitHub and PostHog faked at `urlopen`. They need only pytest: `python -m pytest` from `scripts/release_stats`.

## Known gaps

- Traffic is skipped until a maintainer adds the `RELEASE_STATS_TOKEN` secret.
- The job has not run on GitHub yet; it was checked against the live releases API without a token.
