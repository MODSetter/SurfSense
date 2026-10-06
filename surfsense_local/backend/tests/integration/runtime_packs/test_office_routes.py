"""Office support in Settings: nothing downloads until the user turns it on and allows the host."""

import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient

from modules.runtime_packs.office import layout
from modules.runtime_packs.office import router as office_router
from modules.runtime_packs.office.install import OfficeInstaller
from modules.runtime_packs.office.pin import HOST, Packaging, PackFile
from modules.runtime_packs.office.program import bootstrap_file, program_in
from modules.runtime_packs.office.runtime import OfficeRuntime, office_runtime

pytestmark = pytest.mark.integration

DESTINATION = f"host:{HOST}"
UPSTREAM = b"pretend LibreOffice " * 500
FILE = PackFile(
    version="26.8.1.1",
    url=f"https://{HOST}/libreoffice/old/26.8.1.1/LibreOffice.msi",
    sha256=hashlib.sha256(UPSTREAM).hexdigest(),
    size=len(UPSTREAM),
    packaging=Packaging.WINDOWS_MSI,
)


class Office:
    """What the installer was asked to do, in place of the network and LibreOffice."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        self.smoked: list[OfficeRuntime] = []
        self.smoke_error: Exception | None = None

    def transport(self) -> httpx.MockTransport:
        def reply(request: httpx.Request) -> httpx.Response:
            self.requests.append(str(request.url))
            if request.url.host == HOST:
                return httpx.Response(
                    302, headers={"location": "https://mirror.example/f"}
                )
            return httpx.Response(200, content=UPSTREAM)

        return httpx.MockTransport(reply)

    def unpack(self, packaging: Packaging, upstream: Path, into: Path) -> Path:
        assert upstream.read_bytes() == UPSTREAM
        program_in(into).parent.mkdir(parents=True)
        program_in(into).write_bytes(b"")
        return into

    def smoke(self, runtime: OfficeRuntime) -> None:
        self.smoked.append(runtime)
        if self.smoke_error is not None:
            raise self.smoke_error


@pytest.fixture
def office(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Office:
    """The routes' installer runs against the stand-ins; no install is found on disk."""
    stand_in = Office()
    monkeypatch.setattr(
        office_router,
        "OfficeInstaller",
        lambda file: OfficeInstaller(
            FILE,
            transport=stand_in.transport(),
            unpacker=stand_in.unpack,
            smoke=stand_in.smoke,
            version_of=lambda runtime: "26.8.1.1",
        ),
    )
    monkeypatch.setattr(
        "modules.runtime_packs.office.detect._fixed_locations",
        lambda: [tmp_path / "found"],
    )
    return stand_in


async def _settled(client: AsyncClient) -> dict:
    for _ in range(200):
        status = (await client.get("/runtime-packs/office")).json()
        if status["state"] not in ("downloading", "unpacking", "checking"):
            return status
        await asyncio.sleep(0.02)
    raise AssertionError("the install never finished")


def _found_install(root: Path, branch: str) -> None:
    program_in(root).parent.mkdir(parents=True)
    program_in(root).write_bytes(b"")
    bootstrap_file(root).parent.mkdir(parents=True, exist_ok=True)
    bootstrap_file(root).write_text(f"ProductKey=LibreOffice {branch}\n")


async def test_it_starts_off_and_offers_the_pinned_download(
    client: AsyncClient, office: Office
) -> None:
    """The offer names the version, size and the host the user must allow."""
    status = (await client.get("/runtime-packs/office")).json()
    assert status["state"] == "not_installed"
    assert status["offer"] == {
        "version": "26.8.1.1",
        "size": len(UPSTREAM),
        "host": HOST,
        "destination": DESTINATION,
    }
    assert status["detected"] is None


async def test_turning_it_on_needs_the_host_allowed_first(
    client: AsyncClient, office: Office
) -> None:
    """403 names the host for the consent dialog; nothing was requested."""
    refused = await client.post("/runtime-packs/office/install")
    assert refused.status_code == 403
    assert refused.json()["detail"]["destination"] == DESTINATION
    assert office.requests == []
    assert (await client.get("/runtime-packs/office")).json()[
        "state"
    ] == "not_installed"


async def test_once_allowed_it_downloads_unpacks_checks_and_is_installed(
    client: AsyncClient, office: Office
) -> None:
    """The pinned host first, then its mirror; the smoke runs before it is in place."""
    await client.put(f"/egress/{DESTINATION}", json={"enabled": True})
    started = await client.post("/runtime-packs/office/install")
    assert started.status_code == 202

    status = await _settled(client)
    assert status["state"] == "installed"
    assert status["version"] == "26.8.1.1"
    assert office.requests == [FILE.url, "https://mirror.example/f"]
    # Checked where it was unpacked, then put in place.
    assert ".staging-" in office.smoked[0].program.parent.parent.name
    assert office_runtime() == OfficeRuntime(
        program_in(layout.versions_dir() / "26.8.1.1"), "26.8.1.1", "pack"
    )
    assert not any(layout.downloads_dir().iterdir())


async def test_a_failed_check_leaves_nothing_installed_and_says_why(
    client: AsyncClient, office: Office
) -> None:
    """The unpacked folder is only put in place after the smoke passes, and is
    deleted when it fails: a whole build is over a gigabyte."""
    from modules.runtime_packs.office.soffice.errors import OfficeFailed

    office.smoke_error = OfficeFailed("LibreOffice wrote no pdf")
    await client.put(f"/egress/{DESTINATION}", json={"enabled": True})
    await client.post("/runtime-packs/office/install")

    status = await _settled(client)
    assert status["state"] == "error"
    assert status["error"]["code"] == "smoke_failed"
    assert list(layout.versions_dir().iterdir()) == []


async def test_removing_it_deletes_the_pack(
    client: AsyncClient, office: Office
) -> None:
    """Back to not installed, with the version folder gone."""
    await client.put(f"/egress/{DESTINATION}", json={"enabled": True})
    await client.post("/runtime-packs/office/install")
    await _settled(client)

    removed = await client.delete("/runtime-packs/office")
    assert removed.status_code == 200
    assert removed.json()["state"] == "not_installed"
    assert not any(layout.versions_dir().iterdir())


async def test_an_installed_libreoffice_on_a_supported_branch_is_used_once_confirmed(
    client: AsyncClient, office: Office, tmp_path: Path
) -> None:
    """Shown as found first; after Use it, it runs, and removing only forgets it."""
    _found_install(tmp_path / "found", "26.8")
    before = (await client.get("/runtime-packs/office")).json()
    assert before["state"] == "not_installed"
    assert before["detected"]["usable"] is True

    used = await client.post("/runtime-packs/office/use-installed")
    assert used.status_code == 200
    assert used.json()["state"] == "using_installed"
    assert used.json()["version"] == "26.8.1.1"
    assert used.json()["path"] == str(tmp_path / "found")
    assert office.smoked[0].program == program_in(tmp_path / "found")

    forgotten = (await client.delete("/runtime-packs/office")).json()
    assert forgotten["state"] == "not_installed"
    assert program_in(tmp_path / "found").exists()


async def test_an_installed_libreoffice_on_an_ended_branch_is_refused(
    client: AsyncClient, office: Office, tmp_path: Path
) -> None:
    """25.2 gets no security fixes; customer documents are untrusted input."""
    _found_install(tmp_path / "found", "25.2")
    detected = (await client.get("/runtime-packs/office")).json()["detected"]
    assert detected["refusal"] == "branch_unsupported"

    refused = await client.post("/runtime-packs/office/use-installed")
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "branch_unsupported"
    assert office.smoked == []


async def test_using_an_installed_one_when_none_is_found_is_not_found(
    client: AsyncClient, office: Office
) -> None:
    """404 not_found."""
    reply = await client.post("/runtime-packs/office/use-installed")
    assert reply.status_code == 404
    assert reply.json()["detail"]["code"] == "not_found"


async def test_the_feed_opens_with_the_current_state(base_url: str) -> None:
    """A screen that connects late needs nothing it missed."""
    async with (
        AsyncClient(base_url=base_url, timeout=10) as client,
        client.stream("GET", "/runtime-packs/office/events") as reply,
    ):
        assert reply.headers["content-type"].startswith("application/x-ndjson")
        first = json.loads(await anext(reply.aiter_lines()))
    assert first["state"] in ("not_installed", "using_installed", "installed")
