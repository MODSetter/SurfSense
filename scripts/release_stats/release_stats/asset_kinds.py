"""What a release asset's download count measures, by which client fetches it.

GitHub counts requests, not installs or people, with no IP, version or id.
Package managers (winget, Scoop, Homebrew, apt, the AUR) fetch the installers
themselves and never read ``stable*.yml``, so a manifest count caps only the
app's own updates.

- installer_windows: ``*.exe``. Site, README, email and install.ps1 downloads,
  winget installs and upgrades, Scoop installs and updates (which unpack the
  exe) and the bots that check each new winget manifest, plus every 2.x Windows
  update the app makes itself: the whole installer up to 2.2.3, byte ranges of
  it from then on (differential updates). The same release's ``stable.yml`` count caps only that
  last share, winget installs included, since winget keeps the in-app updater.
- installer_mac: ``*.dmg``. People, plus ``brew install --cask``,
  ``brew upgrade`` and BrewTestBot's checks of each new cask. electron-updater
  never fetches the dmg.
- installer_appimage: ``*.AppImage``. Fresh downloads, install.sh where no
  package manager is found and Homebrew's cask on Linux, plus AppImage updates.
- installer_deb: ``*.deb``. Fresh downloads and install.sh's fallback, plus,
  probably, the app's own deb updates. Once the apt repository exists, apt
  fetches the deb from the release too, so every ``apt upgrade`` and apt
  install of SurfSense counts here, as does every AUR (surfsense-bin) install,
  upgrade or rebuild, since its PKGBUILD downloads the deb.
- installer_rpm: ``*.rpm``, the 2.x ``SurfSense.rpm`` and the 0.0.x
  ``SurfSense-0.0.N-x86_64.rpm``. Fresh downloads, install.sh on dnf and
  zypper, and the app's own rpm updates. Snapshots taken before this reached
  main carry ``other`` for the 0.0.x rpms.
- update_zip_mac: the macOS ``*.zip``. electron-updater and install.sh fetch
  it, so it counts macOS update downloads plus one-line installs on a Mac.
- manifest_stable_*: ``stable*.yml``. One per 2.x update check that reaches
  GitHub: a launch of 2.2.3 or older with automatic updates on, a Check now
  click in those versions, or a check from 2.2.4 or later falling back after
  updates.surfsense.com failed. That proxy also fetches each file from GitHub
  itself, at most once per 15-minute cache while installs ask it, so it adds
  about 96 a day per file (more if Vercel caches per region). Launches and
  refreshes, not installs.
- manifest_legacy_*: ``latest*.yml``. Update checks from 0.0.x apps, mostly at
  login, plus 2.x checks retrying after a failed ``stable*.yml``.
- blockmap: ``*.blockmap``. Up to 2.2.3 no 2.x client fetched one, so those
  releases' counts (about 5 per asset) are the noise floor of bots and mirrors;
  apps after 2.2.3 fetch them for differential updates, as 0.0.x apps did.
- install_script: ``install.sh`` and ``install.ps1``. One per one-line install
  run, refused or failed runs included. Runs, not installs.
- apt_index: the flat apt repository. ``InRelease`` (or ``Release`` and
  ``Release.gpg``) once per ``apt update`` on every machine with the source,
  ``Packages*`` when a new release changed it, and the keyring once per
  install.sh setup. apt reads it through ``latest/download``, so the count lands
  on whichever release was Latest at the time, not the one a machine runs.
- checksums: ``SHA256SUMS``. One per install-script run, plus packagers and
  people checking a download by hand.
- other: anything else, such as a snap or a manifest for an unknown channel.
"""

from __future__ import annotations

from typing import Literal

AssetKind = Literal[
    "installer_windows",
    "installer_mac",
    "installer_appimage",
    "installer_deb",
    "installer_rpm",
    "update_zip_mac",
    "manifest_stable_windows",
    "manifest_stable_mac",
    "manifest_stable_linux",
    "manifest_legacy_windows",
    "manifest_legacy_mac",
    "manifest_legacy_linux",
    "blockmap",
    "install_script",
    "apt_index",
    "checksums",
    "other",
]

_BY_NAME: dict[str, AssetKind] = {
    "install.sh": "install_script",
    "install.ps1": "install_script",
    "packages": "apt_index",
    "packages.gz": "apt_index",
    "release": "apt_index",
    "release.gpg": "apt_index",
    "inrelease": "apt_index",
    "surfsense-archive-keyring.gpg": "apt_index",
    "sha256sums": "checksums",
}

_BY_SUFFIX: tuple[tuple[str, AssetKind], ...] = (
    (".blockmap", "blockmap"),
    (".exe", "installer_windows"),
    (".dmg", "installer_mac"),
    (".appimage", "installer_appimage"),
    (".deb", "installer_deb"),
    (".rpm", "installer_rpm"),
    (".zip", "update_zip_mac"),
)

# electron-updater names a manifest <channel>[-mac|-linux[-arch]].yml.
_MANIFEST_CHANNELS = {"stable": "stable", "latest": "legacy"}


def asset_kind(name: str) -> AssetKind:
    lowered = name.lower()
    if lowered in _BY_NAME:
        return _BY_NAME[lowered]
    for suffix, kind in _BY_SUFFIX:
        if lowered.endswith(suffix):
            return kind
    if lowered.endswith(".yml"):
        return _manifest_kind(lowered.removesuffix(".yml"))
    return "other"


def _manifest_kind(stem: str) -> AssetKind:
    channel, _, platform = stem.partition("-")
    family = _MANIFEST_CHANNELS.get(channel)
    if family is None:
        return "other"
    if not platform:
        os_name = "windows"
    elif platform == "mac":
        os_name = "mac"
    elif platform == "linux" or platform.startswith("linux-"):
        os_name = "linux"
    else:
        return "other"
    return f"manifest_{family}_{os_name}"  # type: ignore[return-value]
