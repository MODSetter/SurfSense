# ADR 0071: Package managers ship the GitHub release files, and a package manager that installs SurfSense owns its updates

- **Status:** Accepted
- **Date:** 2026-10-23
- **Source:** [install-channel research, 2026-10-21](../architecture/install-channels.md)

## Context

Until 2.2.3 the desktop app reached users only as five files on GitHub Releases. People also install apps through Homebrew, winget, Scoop, the AUR, the Snap Store, the Microsoft Store and apt or dnf, and none of them listed SurfSense. Each installer is 1.0 to 1.5 GB. Every installer is signed and has a fixed per-tag URL, and the release API gives each asset's SHA-256, so a channel can point at the files without downloading them.

The app also updates itself through electron-updater, but only once the user allows it. A package manager that installs the app expects to update it. Repackaged builds broke the in-app updater: a snap or Nix build left Settings stuck on "checking", and an AUR build of the .deb would download 1.35 GB and then fail to install it with dpkg.

## Decision

- Every channel serves the files a release already publishes, at their per-tag URLs. The new artifacts are an .rpm, a snap built from the same `linux-unpacked` folder, a SHA256SUMS file, and a signed flat apt repository published as release assets.
- Third-party repositories (Homebrew, winget, Scoop, the AUR) get manifests rendered from the release's asset digests. After the first, maintainer-submitted version, updates are automated: Homebrew's and Scoop's bots bump themselves, and `release-channels.yml` updates winget, the AUR and the snap when a release is published.
- When a package manager installed the app, the app never constructs electron-updater, and Settings says "Updates come from <channel>". A repackager declares the channel in `resources/install-channel` (Scoop, AUR, Nix). Snap and Flatpak are recognised from their environment, and an apt install from the presence of `/etc/apt/sources.list.d/surfsense.list`. An admin policy still wins over a channel.
- Homebrew, winget and the Microsoft Store run the signed installer itself, so the in-app updater stays available there, as it does for downloads from the website.
- Channels whose rules SurfSense cannot meet are left out. Flathub requires a from-source build and forbids AI-written manifests. The Mac App Store's sandbox rules out the sidecars. npm and PyPI cannot hold a 1 GB payload.

## Consequences

- A release carries more assets, and one more job (`release-extras`) must be green before the draft is published: a published release without its apt files breaks `apt update` for every apt user, because the repository lives at `releases/latest/download/`.
- The update feed's file-name rule now accepts `.rpm`, since electron-builder lists the rpm in `stable-linux.yml` ([contract 5](../contracts/05-desktop-telemetry.md)).
- A snapped app keeps its data in `$SNAP_USER_COMMON/.surfsense`, not `~/.surfsense`, so tools that look for `~/.surfsense` miss it.
- Under the channel lock nobody gets updates from the app itself. Users on a channel whose bot stalls stay on the old version until the channel catches up.
- Submissions that need an account or a person stay with the maintainer: the Homebrew PR (with its AI disclosure), the winget CLA, the Scoop package request, the AUR and Snap Store accounts, and the Microsoft Store's company account.

## Where the code stands

Nothing has been released with this yet. The snap job and the apt job have not run on GitHub, and each external channel waits for its first submission ([install channels](../architecture/install-channels.md#known-gaps)).
