"""The one place that says which LibreOffice the Office pack downloads, and from where.

TDF's own builds, until SurfSense re-hosts the pack on its release repository
(docs/proposals/file-agent/04-runtime-and-packs.md decision 8); moving means
changing HOST and the files below, nothing else.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

# TDF's permanent archive: the stable folder drops a version two point releases on.
# It answers with a redirect to one of TDF's mirrors (download.py).
HOST = "downloadarchive.documentfoundation.org"
_ARCHIVE = f"https://{HOST}/libreoffice/old"


class Packaging(StrEnum):
    WINDOWS_MSI = "windows-msi"
    MACOS_DMG = "macos-dmg"
    LINUX_DEBS = "linux-debs"


@dataclass(frozen=True)
class PackFile:
    """One platform's upstream file, and the program inside it once unpacked."""

    version: str
    url: str
    sha256: str
    size: int
    packaging: Packaging

    @property
    def branch(self) -> str:
        return ".".join(self.version.split(".")[:2])


# Decision 11: the newest point release, at .1 or later, of the oldest branch with
# six months of fixes left. 26.8.1 has no Windows build (TDF's stable folder lists
# one that answers 404), so Windows stays on 26.8.0 until 26.8.2.
FILES: dict[str, PackFile] = {
    "windows-x64": PackFile(
        version="26.8.0.3",
        url=f"{_ARCHIVE}/26.8.0.3/win/x86_64/LibreOffice_26.8.0.3_Win_x86-64.msi",
        # Measured: downloaded and hashed once; matches TDF's published sha256.
        sha256="4aa6c6e1895f4055104effcb556bd3362d20c6ad707c149543304f395ef9db95",
        size=374_906_880,
        packaging=Packaging.WINDOWS_MSI,
    ),
    "macos-x64": PackFile(
        version="26.8.1.1",
        url=f"{_ARCHIVE}/26.8.1.1/mac/x86_64/LibreOffice_26.8.1.1_MacOS_x86-64.dmg",
        # TDF's published sha256 (the .mirrorlist); not downloaded here.
        sha256="4c7464313a529e9074400cbcdc894fc40ac4ef9421ded03b16b5a78d12cb155e",
        size=309_092_706,
        packaging=Packaging.MACOS_DMG,
    ),
    "macos-arm64": PackFile(
        version="26.8.1.1",
        url=f"{_ARCHIVE}/26.8.1.1/mac/aarch64/LibreOffice_26.8.1.1_MacOS_aarch64.dmg",
        sha256="ca074e0b13571efb30a31fc531c5f95e997030637325e5d5de92d67aefdf0dfc",
        size=298_845_477,
        packaging=Packaging.MACOS_DMG,
    ),
    "linux-x64": PackFile(
        version="26.8.1.1",
        url=f"{_ARCHIVE}/26.8.1.1/deb/x86_64/LibreOffice_26.8.1.1_Linux_x86-64_deb.tar.gz",
        sha256="30903df3b9f61360d9660cd707de48cd2831469114492a5008ed58a0ac77d044",
        size=219_791_834,
        packaging=Packaging.LINUX_DEBS,
    ),
    "linux-arm64": PackFile(
        version="26.8.1.1",
        url=f"{_ARCHIVE}/26.8.1.1/deb/aarch64/LibreOffice_26.8.1.1_Linux_aarch64_deb.tar.gz",
        sha256="1b069c20dd237f6decad3ea02cb02f39fdf458b03d09c2a9facb7b9b71e6a27a",
        size=208_175_884,
        packaging=Packaging.LINUX_DEBS,
    ),
}

# The TDF branches an installed LibreOffice may be on, with the day each stops
# getting fixes (TDF's release plan). Updated when the pin moves.
SUPPORTED_BRANCHES: dict[str, date] = {
    "26.2": date(2026, 11, 30),
    "26.8": date(2027, 6, 13),
}
