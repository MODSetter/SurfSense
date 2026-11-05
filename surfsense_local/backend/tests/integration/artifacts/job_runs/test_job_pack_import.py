"""A pack file imported by hand, for a computer that cannot reach the license server: the same
signed pack or a newer one installs, anything else is refused with a code the Jobs screen words,
and nothing is left behind."""

import io
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient, Response
from sqlalchemy.orm import Session

from modules.jobs.packs.installed import installed_packs, packs_dir
from modules.jobs.packs.integrity import MAX_PACK_BYTES
from modules.workspaces.models import Workspace
from tests.integration.artifacts.job_runs.started_runs import start_run
from tests.job_pack_samples import ENTITLEMENT, PACK_ID, zipped_questionnaire_pack
from tests.license_samples import business_license, trust_sample_licenses
from tests.zip_faults import encrypted

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def sample_licenses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files signed with the samples' key verify, on a day the samples are valid."""
    trust_sample_licenses(monkeypatch)


def pack_file(tmp_path: Path, **options: object) -> bytes:
    """The test pack as the file support sends, made with `options`."""
    return zipped_questionnaire_pack(tmp_path / f"pack-{uuid4().hex}", **options)


async def imported(
    client: AsyncClient, data: bytes, name: str = "test-jobs-1.0.0.zip"
) -> Response:
    """The Jobs screen's Import pack file."""
    return await client.post(
        "/job-packs/import", files={"file": (name, data, "application/zip")}
    )


def installed() -> list[tuple[str, str]]:
    """The packs the Jobs screen lists, by id and version."""
    return [(p.manifest.id, p.manifest.version) for p in installed_packs()]


def scratch() -> list[str]:
    """Upload and install leftovers in the packs folder."""
    folder = packs_dir()
    if not folder.is_dir():
        return []
    return [p.name for p in folder.iterdir() if p.name.startswith(".")]


def refusal(response: Response) -> tuple[int, str]:
    """A refused import's status and code."""
    return response.status_code, response.json()["detail"]["code"]


async def test_a_pack_file_imports_and_is_listed(
    client: AsyncClient, tmp_path: Path
) -> None:
    """On an empty data folder: the answer is the listing, as the Jobs screen shows it."""
    assert not packs_dir().exists()

    response = await imported(client, pack_file(tmp_path))

    assert response.status_code == 200, response.text
    (pack,) = response.json()
    assert (pack["id"], pack["version"], pack["locked_code"]) == (
        PACK_ID,
        "1.0.0",
        "none",
    )
    listed = (await client.get("/job-packs")).json()
    assert [(p["id"], p["version"]) for p in listed] == [(PACK_ID, "1.0.0")]
    assert scratch() == []


async def test_an_older_version_is_refused_and_the_installed_one_stays(
    client: AsyncClient, tmp_path: Path
) -> None:
    """An import never takes a job back a version; the refusal says which is installed."""
    await imported(client, pack_file(tmp_path, version="1.1.0"))

    response = await imported(client, pack_file(tmp_path))

    assert refusal(response) == (409, "PACK_OLDER")
    assert response.json()["detail"]["message"] == (
        "This is Test jobs 1.0.0, older than the installed 1.1.0."
    )
    assert installed() == [(PACK_ID, "1.1.0")]


async def test_the_same_version_imports_again_and_moves_nothing(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Support's file for the version already installed answers as a success."""
    data = pack_file(tmp_path)
    await imported(client, data)
    folder = packs_dir() / PACK_ID / "1.0.0"
    before = folder.stat()

    response = await imported(client, data)

    assert response.status_code == 200, response.text
    assert folder.stat().st_ino == before.st_ino
    assert installed() == [(PACK_ID, "1.0.0")]


async def test_a_different_pack_at_the_installed_version_is_refused(
    client: AsyncClient, tmp_path: Path
) -> None:
    """A version names one set of bytes; other contents under it are no update."""
    await imported(client, pack_file(tmp_path))

    response = await imported(client, pack_file(tmp_path, checks=True))

    assert refusal(response) == (409, "PACK_VERSION_TAKEN")
    assert installed() == [(PACK_ID, "1.0.0")]


async def test_a_file_that_is_not_a_pack_is_refused_naming_it(
    client: AsyncClient,
) -> None:
    """The message names the file the user chose, never the copy it was read from."""
    response = await imported(client, b"Question,Answer\n", "Vendor questionnaire.xlsx")

    assert refusal(response) == (422, "NOT_A_PACK")
    assert response.json()["detail"]["message"] == (
        "Vendor questionnaire.xlsx is not a SurfSense job pack."
    )
    assert scratch() == []


@pytest.mark.parametrize("damage", ["encrypted", "truncated"])
async def test_an_encrypted_or_truncated_zip_is_not_a_pack(
    client: AsyncClient, tmp_path: Path, damage: str
) -> None:
    """A zip the app cannot read refuses the import instead of failing it."""
    data = pack_file(tmp_path)
    data = (
        encrypted(data, "LICENSE.md")
        if damage == "encrypted"
        else data[: len(data) // 2]
    )

    response = await imported(client, data)

    assert refusal(response) == (422, "NOT_A_PACK")
    assert installed() == []
    assert scratch() == []


async def test_a_file_over_the_cap_is_refused_and_nothing_is_left(
    client: AsyncClient,
) -> None:
    """Past 50 MB the upload stops, and its scratch file goes."""
    response = await imported(client, bytes(MAX_PACK_BYTES + 1))

    assert refusal(response) == (413, "PACK_TOO_LARGE")
    assert response.json()["detail"]["message"] == "The pack is larger than 50 MB."
    assert scratch() == []


def with_members(data: bytes, *names: str) -> bytes:
    """`data`, a zip, with a small file at each of `names` besides."""
    buffer = io.BytesIO(data)
    with zipfile.ZipFile(buffer, "a") as archive:
        for name in names:
            archive.writestr(name, "x")
    return buffer.getvalue()


async def test_a_small_archive_of_many_files_is_not_a_pack_nor_too_large(
    client: AsyncClient, tmp_path: Path
) -> None:
    """The wrong zip picked, a few kilobytes of more files than any pack holds: the screen
    says it is no pack, not that it is past 50 MB."""
    data = with_members(pack_file(tmp_path), *(f"photos/{n}.jpg" for n in range(1000)))

    response = await imported(client, data, "Photos.zip")

    assert refusal(response) == (422, "NOT_A_PACK")
    assert (
        response.json()["detail"]["message"]
        == "Photos.zip is not a SurfSense job pack."
    )
    assert installed() == []
    assert scratch() == []


@pytest.mark.parametrize(
    "names",
    [("notes", "notes/draft.md"), ("draft?.md",), ("Notes/a.md", "notes/b.md")],
    ids=[
        "a file and a folder of one name",
        "a question mark",
        "a folder spelled two ways",
    ],
)
async def test_a_zip_whose_names_no_disk_can_hold_is_not_taken_for_a_full_disk(
    client: AsyncClient, tmp_path: Path, names: tuple[str, ...]
) -> None:
    """Names a zip made by hand can hold, which some systems would write and others refuse
    or file under another name: refused for its names on every system, which the screen
    words as no pack, never as a disk without room."""
    data = with_members(pack_file(tmp_path), *names)

    response = await imported(client, data)

    assert refusal(response) == (422, "BAD_PATH")
    assert installed() == []
    assert scratch() == []


def with_backslashes(data: bytes) -> bytes:
    """`data`, a zip, written again with a backslash between folders, as Windows PowerShell
    5.1's Compress-Archive writes one."""
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive,
    ):
        for member in source.infolist():
            # ZipInfo would turn the backslashes back into slashes on Windows.
            entry = zipfile.ZipInfo("member", date_time=member.date_time)
            entry.filename = member.filename.replace("/", "\\")
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, source.read(member))
    return buffer.getvalue()


async def test_a_pack_zipped_with_backslashes_is_a_bad_path_on_every_system(
    client: AsyncClient, tmp_path: Path
) -> None:
    """A name is read as the zip stores it, so the signed pack zipped again by hand with
    backslashes, which zipfile reads as slashes on Windows only, is refused there too."""
    response = await imported(client, with_backslashes(pack_file(tmp_path)))

    assert response.status_code == 422, response.text
    assert refusal(response) == (422, "BAD_PATH")
    assert installed() == []
    assert scratch() == []


async def test_a_pack_is_not_imported_while_a_run_of_it_is_pending(
    client: AsyncClient, session: Session, workspace: Workspace, tmp_path: Path
) -> None:
    """The runner reads the pack's files while it runs: import the new one once it ends."""
    added = await client.put(
        "/license", json={"certificate": business_license(jobs=ENTITLEMENT)}
    )
    assert added.status_code == 200, added.text
    await imported(client, pack_file(tmp_path))
    await start_run(client, session, workspace.id)

    response = await imported(client, pack_file(tmp_path, version="1.1.0"))

    assert refusal(response) == (409, "PACK_IN_USE")
    assert installed() == [(PACK_ID, "1.0.0")]


async def test_a_pack_signed_by_another_key_is_refused(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Only a pack SurfSense signed installs, by hand as by download."""
    stranger = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))

    response = await imported(client, pack_file(tmp_path, signed_by=(stranger,)))

    assert refusal(response) == (422, "PACK_BAD_SIGNATURE")
    assert installed() == []
