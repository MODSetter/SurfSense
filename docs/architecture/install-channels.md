# Install channels

Besides the downloads on the website, the desktop app can be installed through one-line scripts and through package managers. Every channel installs the signed files a release already publishes, from their per-tag URLs. The only things built for channels are an rpm, a snap packed from the same `linux-unpacked` folder, a SHA256SUMS file and a signed apt repository, all in the release workflow. When a package manager installed the app, it owns the updates: the app never starts electron-updater, and Settings says where updates come from ([updates](updates.md)).

**Code:** [`surfsense_local/packaging/`](../../surfsense_local/packaging/) (install scripts, the apt repository, SHA256SUMS, the channel manifests), [`surfsense_local/electron/src/main/install-channel/`](../../surfsense_local/electron/src/main/install-channel/), [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml), [`.github/workflows/release-channels.yml`](../../.github/workflows/release-channels.yml), [`www/features/downloads/install-script-redirects.ts`](../../www/features/downloads/install-script-redirects.ts)
**Decisions:** [ADR 0071](../adr/0071-package-managers-ship-the-release-files-and-own-their-updates.md), [ADR 0021](../adr/0021-no-intel-mac-build.md)
**Contract:** [contract 5](../contracts/05-desktop-telemetry.md), part C

How a release is cut is in [`surfsense_local/RELEASE.md`](../../surfsense_local/RELEASE.md); how each channel is first submitted is in [`surfsense_local/packaging/README.md`](../../surfsense_local/packaging/README.md).

## Channels

| Channel | The user runs | It installs | Updates come from | Kept current by |
|---|---|---|---|---|
| Website, GitHub Releases | a download | the installer for their OS | the in-app updater, once allowed | nothing to do |
| Install script, macOS and Linux | `curl -fsSL https://www.surfsense.com/install.sh \| sh` | macOS: the zip into `/Applications`. Linux: the apt repository, else the deb; the rpm with dnf or zypper; else the AppImage | apt for a repository install, else the in-app updater | `release-extras` uploads the script to each release |
| Install script, Windows | `irm https://www.surfsense.com/install.ps1 \| iex` | `SurfSense-Setup.exe /S` | the in-app updater | the same |
| apt repository | the source line below, then `apt install surfsense-local-electron` | `SurfSense.deb` | apt | `release-extras` signs and uploads the index |
| rpm | `dnf install ./SurfSense.rpm` | `SurfSense.rpm` | the in-app updater, as for the deb | electron-builder |
| Homebrew cask | `brew install --cask surfsense` | the dmg on Apple Silicon, the AppImage on Linux | the in-app updater, or `brew upgrade` | BrewTestBot |
| winget | `winget install SurfSense.SurfSense` | `SurfSense-Setup.exe` | `winget upgrade`, or the in-app updater | `release-channels.yml` (winget-releaser) |
| Scoop (Extras) | `scoop install extras/surfsense` | the payload inside `SurfSense-Setup.exe`, extracted | Scoop | Scoop's Excavator bot |
| AUR | `yay -S surfsense-bin` | the deb, repackaged into `/opt/SurfSense` | pacman | `release-channels.yml` |
| Snap Store | `snap install surfsense-local` | the snap, strictly confined | snapd | the `snap` job puts it on `candidate`; `release-channels.yml` promotes it to `stable` |
| Microsoft Store | the Store's Get button | `SurfSense-Setup.exe`, from its per-tag URL | the in-app updater (the Store does not update installer-based apps) | a new submission per release, by hand |
| AppImage catalog, AM | the catalog or `am -i surfsense` | the AppImage | the in-app updater | the catalog and AM read GitHub themselves |

The macOS build is Apple Silicon only ([ADR 0021](../adr/0021-no-intel-mac-build.md)), and Windows and Linux are x64 only. On Windows on Arm, winget and the installer fall back to the x64 build, which runs under emulation and has not been tested there.

## When a package manager owns updates

`install-channel/` decides it once at startup, in packaged builds only, in this order:

1. `resources/install-channel` holds `scoop`, `aur` or `nix`. The Scoop manifest, the AUR package and a Nix wrapper write it, since their copies are otherwise identical to the release.
2. On Linux, SurfSense's own snap (`SNAP_NAME` is `surfsense-local` and the executable is under `$SNAP`; another snap's variables, inherited by a normal install started from that snap's shell, do not count), and `FLATPAK_ID` or `/.flatpak-info` for a flatpak.
3. On Linux, an executable under `/nix/store/` means Nix.
4. On Linux, `resources/package-type` saying `deb` together with `/etc/apt/sources.list.d/surfsense.list` means the apt repository.

A channel locks update checks the way an admin policy does, and the policy wins when both apply. Electron-updater is never constructed, because a deb repackaged for another distribution carries `package-type`, which would otherwise start electron-updater's deb updater. Settings shows "Updates come from" the channel ([updates](updates.md#consent)). Homebrew, winget and the Microsoft Store run the release's own installer, so nothing marks them, and the in-app updater stays available there.

A snap keeps its data in `$SNAP_USER_COMMON/.surfsense`, because `$HOME` inside a strict snap is a per-revision folder that snapd copies on every refresh, and points `TMPDIR` at `$SNAP_USER_COMMON/tmp` rather than the small tmpfs snapcraft sets. The session log also redacts `$SNAP_REAL_HOME`.

## What a release adds

- **rpm.** `linux.target` builds `SurfSense.rpm` after the deb. Both depend on the host's libgomp, which llama.cpp loads; the rpm names it `(libgomp or libgomp1)` so Fedora, EL10 and openSUSE all resolve it, and drops electron-builder's `libXScrnSaver`, which EL10 ships only in EPEL and Electron never loads ([packaging](packaging.md)). electron-builder lists the rpm in `stable-linux.yml`, so the update feed accepts `.rpm` ([contract 5](../contracts/05-desktop-telemetry.md)).
- **Snap.** The Linux build uploads `linux-unpacked`, without `package-type` and `app-update.yml`. The `snap` job, on ubuntu-24.04, packs it with electron-builder's core24 target and uploads it to the Snap Store's `candidate` channel when `SNAPCRAFT_STORE_CREDENTIALS` is set. Nothing waits on it, so a broken snap never holds back the installers.
- **`release-extras`.** It runs on a tag push, after the build and the legacy update bridge, while the release is still a draft. It uploads `install.sh` and `install.ps1`. It builds the flat apt repository from the exact `SurfSense.deb` on the draft (`packaging/apt/build-apt-repo.sh`): `Packages`, `Packages.gz`, `Release`, a signed `InRelease` and `Release.gpg`, and the binary keyring `surfsense-archive-keyring.gpg`, signed with `APT_GPG_PRIVATE_KEY`; without that secret it skips the repository with a notice. Last, it writes `SHA256SUMS` from the draft's asset digests (`packaging/checksums/write-sha256sums.mjs`), so the file covers everything uploaded before it.
- **`release-channels.yml`.** It runs when a desktop release is published, which happens when the maintainer undrafts it with their own credentials, so the event fires. It updates winget with winget-releaser, renders and pushes the AUR's `PKGBUILD`, and promotes the snap from `candidate` to `stable`. Each job skips with a notice when its secret is missing. Homebrew and Scoop need no job: their bots bump the version from GitHub.

The apt source line the install script writes, and the docs give, is:

```text
deb [signed-by=/usr/share/keyrings/surfsense-archive-keyring.gpg] https://github.com/MODSetter/SurfSense/releases/latest/download/ ./
```

apt therefore reads the release GitHub marks Latest. A release published without the apt files breaks `apt update` for every apt user, which is why `release-extras` must be green before the undraft once the key exists.

## Install scripts

Both scripts look up the release tag once and download `SHA256SUMS` and the installer from that tag, so the two always match. Each file is checked against `SHA256SUMS` before it is used. On top of that, `install.sh` requires macOS's `spctl` to accept the app before it moves it into place, and `install.ps1` requires a valid Authenticode signature whose signer is `CN=SurfSense`. `install.sh` sets up the apt repository only when `SHA256SUMS` on that tag lists `InRelease` and the keyring; otherwise it installs the deb. It refuses a Linux below glibc 2.35 before downloading anything ([packaging](packaging.md#the-linux-floor)), and on an image-based system (Fedora Atomic desktops, openSUSE Aeon and MicroOS), where dnf or zypper cannot install, it installs the AppImage instead. On Windows and macOS the script refuses while SurfSense is running; on Linux the package manager replaces the files of a running app. `SURFSENSE_VERSION` pins a release, and installs it even when it is older than the one installed; `SURFSENSE_INSTALL_DRY_RUN=1` prints the plan and changes nothing. The website's `/install.sh` and `/install.ps1` are temporary redirects to GitHub's `releases/latest/download/`; nothing counts them, but GitHub counts the asset downloads ([release stats](release-stats.md)).

## Channels left out

- **Flathub.** An open-source app must be built entirely from source inside Flathub's offline builder, the manifest may not be AI-written or AI-assisted, and AI-written app code must be disclosed. No manifest is drafted here.
- **Mac App Store and Setapp.** The sandbox rules out the sidecars and the in-app downloads, and Setapp needs a universal binary.
- **npm and PyPI.** npm refuses packages of more than about 200 MB, and PyPI caps a file at 1 GiB, while every installer is about 1 GB or more.
- **Chocolatey and nixpkgs.** Left to community packagers; the AUR and Scoop manifests show what they need to write.
- **Docker.** Planned separately ([ADR 0035](../adr/0035-docker-compose-runs-the-desktop-stack.md)).
- **Download portals.** Softpedia refuses apps with LLM-written code, and Softonic, FileHippo and Chip.de wrap downloads in their own installers.

## Known gaps

- No release has carried any of this yet. Until one that does is Latest, `/install.sh` and `/install.ps1` redirect to a missing file, and both scripts refuse because no `SHA256SUMS` exists.
- The `snap` job, `release-extras` and `release-channels.yml` have not run on GitHub. A dry run checks the snap; the apt and checksum steps run only on a tag push.
- The strict snap has not been installed anywhere. Not checked: whether the LXD build with snapcraft's gnome extension gives the app everything it needs at run time, since CI never launches the snap, whether `/etc/surfsense/policy.json` reads as missing or unreadable inside the snap, and whether speech-to-text works, since snapd does not auto-connect `audio-record`. Features that reach the host's own files, such as the user's Claude Code, do not see them inside the snap.
- No install script has been run end to end on a real machine; only their dry-run plans are tested.
- The rpm is unsigned, so its integrity rests on HTTPS and `SHA256SUMS`, and dnf5's handling of an unsigned local rpm is unchecked.
- The Microsoft Store listing goes in without signing the 433 unsigned `.dll` and `.pyd` files. Store policy 10.2.9 says every executable file must be signed, while the certification page calls it highly recommended. If certification refuses it, the fallback is to sign only the unsigned files in one batch, which makes every Windows update download them again.
- A Linux user who installed the deb by hand and later adds the apt source switches from the in-app updater to apt without being told.
