"""What a release asset's download count measures, by which client fetches it.

GitHub counts requests, not installs or people, with no IP, version or id.

- installer_windows: ``*.exe``. Site, README and email downloads, plus every
  2.x Windows update, which fetches the full installer (differential downloads
  are off). The same release's ``stable.yml`` count caps the updater's share.
- installer_mac: ``*.dmg``. People only: no updater fetches the dmg.
- installer_appimage: ``*.AppImage``. Fresh downloads plus AppImage updates.
- installer_deb: ``*.deb``. Fresh downloads plus, probably, deb updates.
- update_zip_mac: the macOS ``*.zip``. Only electron-updater fetches it, so it
  counts macOS update downloads.
- manifest_stable_*: ``stable*.yml``. One per 2.x update check, a launch with
  automatic updates on or a Check now click. Launches, not installs.
- manifest_legacy_*: ``latest*.yml``. Update checks from 0.0.x apps, mostly at
  login, plus 2.x checks retrying after a failed ``stable*.yml``.
- blockmap: ``*.blockmap``. No 2.x client fetches one, so on 2.x releases the
  count (about 5 per asset) is the noise floor of bots and mirrors; on 0.0.x
  releases it counts legacy differential updates.
- other: anything else, such as the 0.0.x rpm.
"""

from __future__ import annotations

from typing import Literal

AssetKind = Literal[
    "installer_windows",
    "installer_mac",
    "installer_appimage",
    "installer_deb",
    "update_zip_mac",
    "manifest_stable_windows",
    "manifest_stable_mac",
    "manifest_stable_linux",
    "manifest_legacy_windows",
    "manifest_legacy_mac",
    "manifest_legacy_linux",
    "blockmap",
    "other",
]

_BY_SUFFIX: tuple[tuple[str, AssetKind], ...] = (
    (".blockmap", "blockmap"),
    (".exe", "installer_windows"),
    (".dmg", "installer_mac"),
    (".appimage", "installer_appimage"),
    (".deb", "installer_deb"),
    (".zip", "update_zip_mac"),
)

# electron-updater names a manifest <channel>[-mac|-linux[-arch]].yml.
_MANIFEST_CHANNELS = {"stable": "stable", "latest": "legacy"}


def asset_kind(name: str) -> AssetKind:
    lowered = name.lower()
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
