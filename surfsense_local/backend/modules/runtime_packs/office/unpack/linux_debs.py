"""Unpack TDF's tarball of .deb files into one tree, with no package manager.

dpkg-deb is not on every distribution, so the ar archives are read here. Every
tar extraction uses the "data" filter: no absolute paths, no `..`, no links out.
"""

import shutil
import tarfile
from pathlib import Path
from typing import BinaryIO

_AR_MAGIC = b"!<arch>\n"
_HEADER = 60


def unpack_debs(tarball: Path, into: Path) -> Path:
    """Unpack every .deb's files into `into`; return the install root (opt/libreoffice*)."""
    debs = into.parent / f"{into.name}.debs"
    with tarfile.open(tarball) as archive:
        archive.extractall(debs, filter="data")
    into.mkdir(parents=True, exist_ok=True)
    # DEBS/desktop-integration/ is left out: it links into /usr, outside the tree.
    for deb in sorted(debs.glob("*/DEBS/*.deb")):
        _extract_deb(deb, into)
    _remove(debs)
    roots = sorted((into / "opt").glob("libreoffice*"))
    if not roots:
        raise FileNotFoundError("no opt/libreoffice* in the unpacked debs")
    return roots[-1]


def _extract_deb(deb: Path, into: Path) -> None:
    """A .deb is an ar archive; its files are in the data.tar.* member."""
    with deb.open("rb") as handle:
        if handle.read(len(_AR_MAGIC)) != _AR_MAGIC:
            raise ValueError(f"{deb.name} is not a .deb")
        while header := handle.read(_HEADER):
            name = header[:16].decode().strip().rstrip("/")
            size = int(header[48:58].decode().strip())
            start = handle.tell()
            if name.startswith("data.tar"):
                # A stream: the member is read once, front to back, never seeked.
                with tarfile.open(fileobj=_Slice(handle, size), mode="r|*") as data:
                    data.extractall(into, filter="data")
                return
            handle.seek(start + size + (size % 2))
    raise ValueError(f"{deb.name} has no data archive")


class _Slice:
    """One ar member, read as a stream of its own."""

    def __init__(self, handle: BinaryIO, size: int) -> None:
        self._handle = handle
        self._left = size

    def read(self, size: int = -1) -> bytes:
        size = self._left if size < 0 else min(size, self._left)
        data = self._handle.read(size)
        self._left -= len(data)
        return data


def _remove(folder: Path) -> None:
    shutil.rmtree(folder, ignore_errors=True)
