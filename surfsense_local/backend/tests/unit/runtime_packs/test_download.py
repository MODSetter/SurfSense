"""The pack download: resumable, https-only redirects, and only the pinned bytes kept."""

import hashlib
from pathlib import Path

import httpx
import pytest

from modules.runtime_packs.office.download import (
    DownloadRefusedError,
    download_pack_file,
)
from modules.runtime_packs.office.pin import Packaging, PackFile

pytestmark = pytest.mark.unit

BODY = bytes(range(256)) * 40
PINNED = "https://downloadarchive.documentfoundation.org/lo/LibreOffice.msi"
MIRROR = "https://mirror.example.org/tdf/LibreOffice.msi"


def _file(body: bytes = BODY) -> PackFile:
    return PackFile(
        version="26.8.1.1",
        url=PINNED,
        sha256=hashlib.sha256(body).hexdigest(),
        size=len(body),
        packaging=Packaging.WINDOWS_MSI,
    )


def _mirror(body: bytes = BODY, *, seen: list[httpx.Request] | None = None):
    def reply(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if str(request.url) == PINNED:
            return httpx.Response(302, headers={"location": MIRROR})
        start = int(request.headers.get("range", "bytes=0-")[6:-1] or 0)
        if start:
            return httpx.Response(206, content=body[start:])
        return httpx.Response(200, content=body)

    return httpx.MockTransport(reply)


async def _drain(file: PackFile, destination: Path, transport) -> list:
    return [p async for p in download_pack_file(file, destination, transport=transport)]


async def test_follows_the_mirror_redirect_and_keeps_the_verified_file(
    tmp_path: Path,
) -> None:
    """Progress ends at the pinned size and no .part is left behind."""
    destination = tmp_path / "LibreOffice.msi"
    progress = await _drain(_file(), destination, _mirror())
    assert destination.read_bytes() == BODY
    assert progress[-1].completed == progress[-1].total == len(BODY)
    assert not (tmp_path / "LibreOffice.msi.part").exists()


async def test_a_partial_download_resumes_from_where_it_stopped(tmp_path: Path) -> None:
    """Only the missing bytes are asked for."""
    destination = tmp_path / "LibreOffice.msi"
    (tmp_path / "LibreOffice.msi.part").write_bytes(BODY[:1000])
    seen: list[httpx.Request] = []
    await _drain(_file(), destination, _mirror(seen=seen))
    assert destination.read_bytes() == BODY
    assert seen[-1].headers["range"] == "bytes=1000-"


async def test_wrong_bytes_are_deleted_and_refused(tmp_path: Path) -> None:
    """A mirror serving something else never becomes the pack."""
    destination = tmp_path / "LibreOffice.msi"
    with pytest.raises(DownloadRefusedError) as refused:
        await _drain(_file(), destination, _mirror(b"x" * len(BODY)))
    assert refused.value.code == "checksum_mismatch"
    assert not destination.exists()
    assert not (tmp_path / "LibreOffice.msi.part").exists()


async def test_a_redirect_off_https_is_refused_before_it_is_followed(
    tmp_path: Path,
) -> None:
    """Nothing is fetched from a plain-http mirror."""
    seen: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://mirror.example.org/x"})

    with pytest.raises(DownloadRefusedError) as refused:
        await _drain(_file(), tmp_path / "f.msi", httpx.MockTransport(reply))
    assert refused.value.code == "insecure_redirect"
    assert [str(r.url) for r in seen] == [PINNED]


async def test_more_bytes_than_pinned_stop_the_download(tmp_path: Path) -> None:
    """A mirror cannot fill the disk past the pinned size."""
    pinned = _file()
    with pytest.raises(DownloadRefusedError) as refused:
        await _drain(pinned, tmp_path / "f.msi", _mirror(BODY + b"more"))
    assert refused.value.code == "too_large"
    assert not (tmp_path / "f.msi.part").exists()
