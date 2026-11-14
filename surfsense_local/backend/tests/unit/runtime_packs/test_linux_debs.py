"""TDF's Linux tarball becomes one install tree without dpkg, and nothing lands outside it."""

import io
import tarfile
from pathlib import Path

import pytest

from modules.runtime_packs.office.unpack.linux_debs import unpack_debs

pytestmark = pytest.mark.unit


def _tar(files: dict[str, bytes], mode: str = "w:gz") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _ar_member(name: str, data: bytes) -> bytes:
    header = (
        f"{name + '/':<16}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n"
    ).encode()
    return header + data + (b"\n" if len(data) % 2 else b"")


def _deb(files: dict[str, bytes]) -> bytes:
    return (
        b"!<arch>\n"
        + _ar_member("debian-binary", b"2.0\n")
        + _ar_member("control.tar.xz", _tar({"control": b"x"}, "w:xz"))
        + _ar_member("data.tar.xz", _tar(files, "w:xz"))
    )


def _tarball(path: Path, debs: dict[str, bytes]) -> Path:
    path.write_bytes(
        _tar(
            {
                f"LibreOffice_26.8.1.1_Linux_x86-64_deb/DEBS/{n}": d
                for n, d in debs.items()
            }
        )
    )
    return path


def test_every_deb_lands_in_one_tree_and_the_root_is_found(tmp_path: Path) -> None:
    """The core and Writer packages share opt/libreoffice26.8."""
    tarball = _tarball(
        tmp_path / "lo.tar.gz",
        {
            "core.deb": _deb({"./opt/libreoffice26.8/program/soffice": b"#!"}),
            "writer.deb": _deb({"./opt/libreoffice26.8/program/libswlo.so": b"so"}),
        },
    )
    root = unpack_debs(tarball, tmp_path / "staging")
    assert root == tmp_path / "staging" / "opt" / "libreoffice26.8"
    assert (root / "program" / "soffice").read_bytes() == b"#!"
    assert (root / "program" / "libswlo.so").exists()
    assert not (tmp_path / "staging.debs").exists()


def _deb_with_link(name: str, target: str) -> bytes:
    """A .deb whose data holds one symlink, as TDF's menus package does."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:xz") as archive:
        info = tarfile.TarInfo(name)
        info.type = tarfile.SYMTYPE
        info.linkname = target
        archive.addfile(info)
    return (
        b"!<arch>\n"
        + _ar_member("debian-binary", b"2.0\n")
        + _ar_member("data.tar.xz", buffer.getvalue())
    )


def test_tdfs_menus_package_is_left_out(tmp_path: Path) -> None:
    """Its link into /usr/local/bin sits beside the other .debs in the real tarball."""
    tarball = _tarball(
        tmp_path / "lo.tar.gz",
        {
            "libreoffice26.8-debian-menus_26.8.1-1_all.deb": _deb_with_link(
                "./usr/local/bin/libreoffice26.8",
                "/opt/libreoffice26.8/program/soffice",
            ),
            "core.deb": _deb({"./opt/libreoffice26.8/program/soffice": b"#!"}),
        },
    )
    root = unpack_debs(tarball, tmp_path / "staging")
    assert (root / "program" / "soffice").exists()
    assert not (tmp_path / "staging" / "usr").exists()


def test_a_path_leaving_the_tree_is_refused(tmp_path: Path) -> None:
    """The data filter rejects `..`."""
    tarball = _tarball(
        tmp_path / "lo.tar.gz", {"evil.deb": _deb({"../../escaped": b"x"})}
    )
    with pytest.raises(tarfile.FilterError):
        unpack_debs(tarball, tmp_path / "staging")
    assert not (tmp_path / "escaped").exists()
