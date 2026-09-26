"""Fetching a GGUF into the models directory.

SurfSense does this itself rather than asking the runtime to. llama-server is a
second process we do not proxy, so an in-process fetch is the only place
`egress.require()` can hold, and it also buys resume, checksums and the header
as the file lands.
"""

import hashlib

import httpx
import pytest

from modules.llm.providers.llamacpp import download_gguf

pytestmark = pytest.mark.unit

BODY = b"GGUF" + b"x" * 4092
DIGEST = hashlib.sha256(BODY).hexdigest()


def serving(body: bytes, *, accept_ranges: bool = True, record: list | None = None):
    """A Hugging Face style file endpoint that honours Range when asked."""

    def handler(request: httpx.Request) -> httpx.Response:
        if record is not None:
            record.append(request.headers.get("Range"))
        span = request.headers.get("Range")
        headers = {"content-type": "application/octet-stream"}
        if accept_ranges:
            headers["accept-ranges"] = "bytes"
        if span and accept_ranges:
            start = int(span.removeprefix("bytes=").split("-")[0])
            return httpx.Response(206, content=body[start:], headers=headers)
        return httpx.Response(200, content=body, headers=headers)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_a_download_lands_under_its_real_filename(tmp_path) -> None:
    """Real names, not llama.cpp's content addressed cache layout, because the
    router discovers the directory and reports what it finds."""
    steps = [
        s
        async for s in download_gguf(
            "https://hf.invalid/repo/resolve/main/m.gguf",
            tmp_path / "m.gguf",
            transport=serving(BODY),
        )
    ]

    assert (tmp_path / "m.gguf").read_bytes() == BODY
    assert steps[-1].completed == len(BODY)


@pytest.mark.asyncio
async def test_progress_is_reported_as_it_arrives(tmp_path) -> None:
    """The install route streams these straight through its NDJSON frames."""
    steps = [
        s
        async for s in download_gguf(
            "https://hf.invalid/repo/resolve/main/m.gguf",
            tmp_path / "m.gguf",
            transport=serving(BODY),
        )
    ]

    assert steps
    assert all(s.total == len(BODY) for s in steps)
    assert steps[-1].completed >= steps[0].completed


@pytest.mark.asyncio
async def test_an_interrupted_download_resumes_instead_of_restarting(tmp_path) -> None:
    """A model is gigabytes. Starting over because a laptop slept is not an option."""
    partial = tmp_path / "m.gguf.part"
    partial.write_bytes(BODY[:2000])
    ranges: list = []

    async for _ in download_gguf(
        "https://hf.invalid/repo/resolve/main/m.gguf",
        tmp_path / "m.gguf",
        transport=serving(BODY, record=ranges),
    ):
        pass

    assert ranges == ["bytes=2000-"]
    assert (tmp_path / "m.gguf").read_bytes() == BODY


@pytest.mark.asyncio
async def test_a_file_that_does_not_match_its_checksum_is_not_installed(tmp_path) -> None:
    """A truncated or tampered file must never be left where the router will
    discover it and try to load it."""
    with pytest.raises(ValueError, match="checksum"):
        async for _ in download_gguf(
            "https://hf.invalid/repo/resolve/main/m.gguf",
            tmp_path / "m.gguf",
            sha256="0" * 64,
            transport=serving(BODY),
        ):
            pass

    assert not (tmp_path / "m.gguf").exists()


@pytest.mark.asyncio
async def test_a_matching_checksum_installs(tmp_path) -> None:
    """The happy path, so the guard above cannot pass by rejecting everything."""
    async for _ in download_gguf(
        "https://hf.invalid/repo/resolve/main/m.gguf",
        tmp_path / "m.gguf",
        sha256=DIGEST,
        transport=serving(BODY),
    ):
        pass

    assert (tmp_path / "m.gguf").exists()


@pytest.mark.asyncio
async def test_a_cancelled_download_leaves_nothing_selectable(tmp_path) -> None:
    """Cancelling mid stream keeps the partial file for a later resume, and never
    puts a half model where the router would list it as installed."""
    stream = download_gguf(
        "https://hf.invalid/repo/resolve/main/m.gguf",
        tmp_path / "m.gguf",
        transport=serving(BODY),
    )
    async for _ in stream:
        break
    await stream.aclose()

    assert not (tmp_path / "m.gguf").exists()
