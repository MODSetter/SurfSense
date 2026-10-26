"""The desktop release licence mail links to, through the site's download redirect.

Kept in lockstep with ``www/features/downloads/app-release.ts``: both name the same
tag, and ``surfsense_local/scripts/bump-version.sh`` writes both. Each link
carries ``v=<tag>``, so a mail already sent keeps naming the build it was sent
for, and ``src=email``, so the redirect counts which downloads mail produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

# Written by bump-version.sh. Do not edit by hand.
APP_RELEASE_VERSION = "2.2.5"
APP_RELEASE_TAG = f"v{APP_RELEASE_VERSION}"

_DOWNLOADS_URL = "https://www.surfsense.com/downloads"


@dataclass(frozen=True, slots=True)
class InstallerLink:
    label: str
    url: str


# The redirect's platforms (``/downloads/[platform]/route.ts``), in the order
# and with the labels of the /downloads grid.
_PLATFORMS: tuple[tuple[str, str], ...] = (
    ("windows", "Windows (exe)"),
    ("mac", "macOS Apple Silicon (dmg)"),
    ("linux-deb", "Linux (deb)"),
    ("linux-appimage", "Linux (AppImage)"),
)


def installer_link(platform: str, *, tag: str = APP_RELEASE_TAG) -> str:
    """The site redirect for one platform's installer of ``tag``."""
    return f"{_DOWNLOADS_URL}/{platform}?{urlencode({'src': 'email', 'v': tag})}"


def installer_links(*, tag: str = APP_RELEASE_TAG) -> tuple[InstallerLink, ...]:
    """Every installer the mail offers, pinned to ``tag``."""
    return tuple(
        InstallerLink(label=label, url=installer_link(platform, tag=tag))
        for platform, label in _PLATFORMS
    )
