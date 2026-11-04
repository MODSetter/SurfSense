"""A licence's jobs downloaded from SurfSense's licence server: what the app sends, what it
installs, and what it keeps when anything is refused or fails (contract 6, consumer rules)."""

import asyncio
import errno
import logging
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient, Response
from sqlalchemy.orm import Session

from modules.jobs.packs.delivery import pack_request
from modules.jobs.packs.delivery.held_back import HELD_BACK
from modules.jobs.packs.installed import installed_packs, packs_dir
from modules.jobs.packs.integrity import MAX_PACK_BYTES
from modules.workspaces.models import Workspace
from shared.config import get_license_server_settings
from tests.integration.artifacts.job_runs.started_runs import start_run
from tests.job_pack_samples import ENTITLEMENT, PACK_ID, zipped_questionnaire_pack
from tests.license_samples import BUSINESS_KEY, business_license, trust_sample_licenses
from tests.license_server_stand_in import (
    JOB_NOT_INCLUDED,
    PACK_NOT_COVERED,
    Asked,
    StandInLicenseServer,
)
from tests.mcp_test_server import serving

pytestmark = pytest.mark.integration

# The Business sample, holding the test pack's job.
LICENSE = business_license(jobs=ENTITLEMENT)
RUNNERS = ["workbook-rows/1"]
CURRENT = "The newest version of this job is installed."
UNAVAILABLE = "SurfSense's license server could not send the job; try again later."
NOT_WRITTEN = "The pack could not be written to this computer's disk."
DEFERRED = (
    "A run of this job was under way, so any newer version waits until the run ends."
)
NOT_COVERED = (
    "This job comes only in a pack with a job your license does not include. "
    "Contact support."
)
LICENSE_OUTDATED = (
    "Your license has changed on SurfSense's license server. Check for renewal, then "
    "download the job again."
)
UNKNOWN_JOB = "SurfSense's license server does not offer this job."
# A firm's mirror of the license server, which the `mirror` fixture serves locally.
MIRROR = "licenses.example.test"


@pytest.fixture(autouse=True)
def sample_licenses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files signed with the samples' key verify, on a day the samples are valid."""
    trust_sample_licenses(monkeypatch)


async def add_license(client: AsyncClient, certificate: str = LICENSE) -> None:
    """Import a license file, as Settings does."""
    added = await client.put("/license", json={"certificate": certificate})
    assert added.status_code == 200, added.text


async def download(client: AsyncClient, body: dict | None = None) -> Response:
    """The Jobs screen's Download: every job of the license, or the codes named."""
    if body is None:
        return await client.post("/job-packs/download")
    return await client.post("/job-packs/download", json=body)


def offer(server: StandInLicenseServer, tmp_path: Path, **options: object) -> bytes:
    """Publish the test pack, made with `options`, as the newest for the license's job."""
    archive = zipped_questionnaire_pack(
        tmp_path / f"published-{uuid4().hex}", **options
    )
    server.offer(ENTITLEMENT, archive)
    return archive


def outcome(
    kind: str,
    message: str,
    version: str | None = None,
    detail: str | None = None,
    entitlement: str = ENTITLEMENT,
) -> dict:
    """One code's outcome, as the route answers it."""
    return {
        "entitlement": entitlement,
        "outcome": kind,
        "message": message,
        "version": version,
        "detail": detail,
    }


def installed() -> list[tuple[str, str]]:
    """The packs the Jobs screen lists, by id and version."""
    return [(p.manifest.id, p.manifest.version) for p in installed_packs()]


def scratch() -> list[str]:
    """Download and install leftovers in the packs folder."""
    folder = packs_dir()
    return (
        [p.name for p in folder.iterdir() if p.name.startswith(".")]
        if folder.is_dir()
        else []
    )


async def test_a_license_s_job_is_downloaded_installed_and_listed_unlocked(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """On an empty data folder: the key, the job's code and the app's runners go in the body
    under the app's bare name, nothing in the URL, and the pack is installed and unlocked."""
    await add_license(client)
    offer(license_server, tmp_path)
    assert not packs_dir().exists()

    response = await download(client)

    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["outcomes"] == [
        outcome("installed", "Test jobs 1.0.0 is installed.", "1.0.0")
    ]
    (pack,) = answer["packs"]
    assert (pack["id"], pack["version"], pack["unlocked"], pack["locked_code"]) == (
        PACK_ID,
        "1.0.0",
        True,
        None,
    )
    assert license_server.pack_asked == [
        Asked(
            "/api/v1/license/job-pack",
            "",
            {"key": BUSINESS_KEY, "entitlement": ENTITLEMENT, "runners": RUNNERS},
            "SurfSense",
        )
    ]
    assert license_server.asked == []
    assert scratch() == []


async def test_the_installed_version_is_sent_and_a_204_keeps_it(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """The server answers 204 when the app's version is current, and nothing moves."""
    await add_license(client)
    offer(license_server, tmp_path)
    await download(client)
    folder = packs_dir() / PACK_ID / "1.0.0"
    before = folder.stat()

    response = await download(client)

    assert response.json()["outcomes"] == [outcome("current", CURRENT, "1.0.0")]
    assert license_server.pack_asked[-1].body == {
        "key": BUSINESS_KEY,
        "entitlement": ENTITLEMENT,
        "runners": RUNNERS,
        "installed_version": "1.0.0",
    }
    assert folder.stat().st_ino == before.st_ino


async def test_a_newer_version_replaces_the_installed_one(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """One version of a pack stays on disk: the newer one."""
    await add_license(client)
    offer(license_server, tmp_path)
    await download(client)
    offer(license_server, tmp_path, version="1.1.0")

    response = await download(client)

    assert response.json()["outcomes"] == [
        outcome("installed", "Test jobs 1.1.0 is installed.", "1.1.0")
    ]
    assert installed() == [(PACK_ID, "1.1.0")]
    assert sorted(p.name for p in (packs_dir() / PACK_ID).iterdir()) == ["1.1.0"]


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0"], ids=["older", "same"])
async def test_an_older_or_same_pack_sent_anyway_never_replaces_the_installed_one(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    tmp_path: Path,
    version: str,
) -> None:
    """The app's own check holds whatever the server sends: the installed pack is current."""
    await add_license(client)
    offer(license_server, tmp_path, version="1.1.0")
    await download(client)
    license_server.ignores_installed_version = True
    offer(license_server, tmp_path, version=version)

    response = await download(client)

    assert response.json()["outcomes"] == [outcome("current", CURRENT, "1.1.0")]
    assert installed() == [(PACK_ID, "1.1.0")]


async def test_a_pack_without_the_job_asked_for_is_refused(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """A pack for another code is not this job's, whatever the server says."""
    await add_license(client)
    offer(license_server, tmp_path, entitlement="JOB_OTHER")

    response = await download(client)

    assert response.json()["outcomes"] == [
        outcome(
            "refused",
            f"Test jobs 1.0.0 has no job for {ENTITLEMENT}.",
            detail="PACK_WRONG_JOB",
        )
    ]
    assert installed() == []
    assert scratch() == []


def two_job_pack(folder: Path, version: str = "1.0.0") -> bytes:
    """The test pack with a second job, for a code the license does not hold, zipped."""
    return zipped_questionnaire_pack(
        folder, version=version, other_jobs=("JOB_UNSOLD",)
    )


@pytest.mark.parametrize("before", [None, "1.0.0"], ids=["none installed", "installed"])
async def test_a_pack_holding_a_job_this_computer_s_license_lacks_asks_for_renewal(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    tmp_path: Path,
    before: str | None,
) -> None:
    """The server sends a pack only to a license whose jobs, as its own record lists them,
    hold every job in it, so this computer's license file is the older one: the pack is not
    installed, the outcome says to check for renewal, and the installed pack stays."""
    await add_license(client)
    if before is not None:
        offer(license_server, tmp_path)
        await download(client)
    license_server.license_jobs = frozenset({ENTITLEMENT, "JOB_UNSOLD"})
    license_server.offer(ENTITLEMENT, two_job_pack(tmp_path / "two-jobs", "1.1.0"))

    response = await download(client)

    assert response.json()["outcomes"] == [
        outcome("license_outdated", LICENSE_OUTDATED, before, "PACK_NOT_INCLUDED")
    ]
    assert installed() == ([(PACK_ID, before)] if before else [])
    assert scratch() == []


async def test_a_job_that_comes_only_in_a_pack_the_license_lacks_a_job_of_is_withheld(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """The server's record of the license lacks the pack's other job, so it sends nothing,
    with a code of its own: the license does include the job asked for, and the installed
    pack stays."""
    await add_license(client)
    offer(license_server, tmp_path)
    await download(client)
    license_server.license_jobs = frozenset({ENTITLEMENT})
    license_server.offer(ENTITLEMENT, two_job_pack(tmp_path / "two-jobs", "1.1.0"))

    response = await download(client)

    assert response.json()["outcomes"] == [
        outcome("pack_not_covered", PACK_NOT_COVERED, detail="pack_not_covered")
    ]
    assert installed() == [(PACK_ID, "1.0.0")]


async def test_a_job_the_license_server_s_record_lacks_is_not_included(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """This computer's license file lists the job, the server's record no longer does: it
    sends nothing, in its own words, and the installed pack stays."""
    await add_license(client)
    offer(license_server, tmp_path)
    await download(client)
    license_server.license_jobs = frozenset({"JOB_OTHER"})
    offer(license_server, tmp_path, version="1.1.0")

    response = await download(client)

    assert response.json()["outcomes"] == [
        outcome("job_not_included", JOB_NOT_INCLUDED, detail="job_not_included")
    ]
    assert installed() == [(PACK_ID, "1.0.0")]


async def test_a_pack_signed_by_another_key_is_refused_and_the_installed_one_stays(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """A pack SurfSense did not sign never replaces one it did."""
    await add_license(client)
    offer(license_server, tmp_path)
    await download(client)
    stranger = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
    offer(license_server, tmp_path, version="1.1.0", signed_by=(stranger,))

    response = await download(client)

    (refused,) = response.json()["outcomes"]
    assert (refused["outcome"], refused["detail"]) == ("refused", "PACK_BAD_SIGNATURE")
    assert installed() == [(PACK_ID, "1.0.0")]
    assert scratch() == []


async def test_a_pending_run_defers_the_download_and_nothing_is_sent(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    license_server: StandInLicenseServer,
    tmp_path: Path,
) -> None:
    """The runner reads the pack's files while it runs; the next check brings the new one."""
    await add_license(client)
    offer(license_server, tmp_path)
    await download(client)
    await start_run(client, session, workspace.id)
    offer(license_server, tmp_path, version="1.1.0")

    response = await download(client)

    assert response.json()["outcomes"] == [
        outcome(
            "deferred",
            "A run of this job was under way, so any newer version waits until the run "
            "ends.",
            "1.0.0",
        )
    ]
    assert len(license_server.pack_asked) == 1
    assert installed() == [(PACK_ID, "1.0.0")]


async def test_a_run_started_while_the_pack_downloads_defers_its_install(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    license_server: StandInLicenseServer,
    tmp_path: Path,
) -> None:
    """No run was under way when the download was planned, but one starts before the newer
    version arrives: the install checks again under its lock, so the newer version waits
    and the installed one stays."""
    await add_license(client)
    offer(license_server, tmp_path)
    await download(client)
    offer(license_server, tmp_path, version="1.1.0")
    loop = asyncio.get_running_loop()
    started: list[int] = []

    def a_run_starts() -> None:
        run = asyncio.run_coroutine_threadsafe(
            start_run(client, session, workspace.id), loop
        )
        started.append(run.result(timeout=30))

    license_server.before_pack = a_run_starts

    response = await download(client)

    assert len(started) == 1
    assert response.json()["outcomes"] == [outcome("deferred", DEFERRED, "1.0.0")]
    assert len(license_server.pack_asked) == 2
    assert installed() == [(PACK_ID, "1.0.0")]
    assert scratch() == []


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (
            (
                403,
                {
                    "code": "license_not_valid",
                    "message": "This license cannot download jobs (EXPIRED).",
                },
            ),
            (
                "license_not_valid",
                "This license cannot download jobs (EXPIRED).",
                "license_not_valid",
            ),
        ),
        (
            (
                403,
                {
                    "code": "job_not_included",
                    "message": "This license does not include that job.",
                },
            ),
            (
                "job_not_included",
                "This license does not include that job.",
                "job_not_included",
            ),
        ),
        (
            (403, {"code": "pack_not_covered", "message": PACK_NOT_COVERED}),
            ("pack_not_covered", PACK_NOT_COVERED, "pack_not_covered"),
        ),
        (
            (403, {"code": "pack_not_covered"}),
            ("pack_not_covered", NOT_COVERED, "pack_not_covered"),
        ),
        (
            (403, {"code": "license_on_hold", "message": "This license is on hold."}),
            ("license_not_valid", "This license is on hold.", "license_on_hold"),
        ),
        (
            (403, "Forbidden"),
            (
                "license_not_valid",
                "SurfSense's license server will not send jobs for this license. "
                "Contact support.",
                None,
            ),
        ),
        (
            (
                404,
                {"code": "license_not_found", "message": "No license has that key."},
            ),
            (
                "license_not_found",
                "SurfSense's license server has no license with this key.",
                "license_not_found",
            ),
        ),
        (
            (
                409,
                {
                    "code": "needs_newer_app",
                    "message": "This job needs a newer version of SurfSense.",
                },
            ),
            (
                "needs_newer_app",
                "This job needs a newer version of SurfSense.",
                "needs_newer_app",
            ),
        ),
        (
            (
                422,
                {
                    "code": "unknown_job",
                    "message": "SurfSense has no job with that code.",
                },
            ),
            ("unknown_job", "SurfSense has no job with that code.", "unknown_job"),
        ),
        (
            (429, {"code": "rate_limited", "message": "Too many requests."}),
            (
                "rate_limited",
                "This license asked for jobs too often; try again in an hour.",
                "rate_limited",
            ),
        ),
        (
            (
                503,
                {
                    "code": "job_packs_unavailable",
                    "message": "Jobs cannot be downloaded right now.",
                },
            ),
            ("unavailable", UNAVAILABLE, "job_packs_unavailable"),
        ),
        ((500, "Internal Server Error"), ("unavailable", UNAVAILABLE, None)),
    ],
    ids=[
        "not valid",
        "not included",
        "not covered",
        "not covered, no sentence",
        "another 403 code",
        "forbidden",
        "not found",
        "newer app",
        "unknown job",
        "rate limited",
        "unavailable",
        "server error",
    ],
)
async def test_each_refusal_of_the_server_keeps_the_installed_pack(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    tmp_path: Path,
    answer: tuple[int, object],
    expected: tuple[str, str, str | None],
) -> None:
    """Consumer rule 6: the outcome says why, in the server's own sentence where it is the
    user's to act on, and the pack already installed stays."""
    await add_license(client)
    offer(license_server, tmp_path)
    await download(client)
    license_server.pack_refusal = answer

    response = await download(client)

    kind, message, detail = expected
    assert response.json()["outcomes"] == [outcome(kind, message, detail=detail)]
    assert installed() == [(PACK_ID, "1.0.0")]


async def test_a_server_without_the_route_is_unavailable_not_an_unknown_key(
    client: AsyncClient, license_server: StandInLicenseServer
) -> None:
    """A 404 that names no license refusal is a server that does not deliver packs yet."""
    await add_license(client)
    license_server.pack_route_missing = True

    response = await download(client)

    assert response.json()["outcomes"] == [outcome("unavailable", UNAVAILABLE)]


@pytest.mark.parametrize(
    ("content_type", "archive", "expected"),
    [
        ("text/html; charset=utf-8", None, ("unavailable", None)),
        (
            "application/zip",
            b"<html>Sign in to the portal</html>",
            ("refused", "NOT_A_PACK"),
        ),
    ],
    ids=["another type", "not a zip"],
)
async def test_a_200_that_is_not_a_zip_is_not_installed(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    tmp_path: Path,
    content_type: str,
    archive: bytes | None,
    expected: tuple[str, str | None],
) -> None:
    """A captive portal's page, or bytes that only claim to be a zip, install nothing."""
    await add_license(client)
    offer(license_server, tmp_path)
    if archive is not None:
        license_server.offer(ENTITLEMENT, archive)
    license_server.pack_content_type = content_type

    response = await download(client)

    (answered,) = response.json()["outcomes"]
    assert (answered["outcome"], answered["detail"]) == expected
    assert installed() == []
    assert scratch() == []


async def test_a_redirect_is_never_followed(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """The app reaches no host but the license server, whatever it answers."""
    await add_license(client)
    elsewhere = StandInLicenseServer()
    elsewhere.offer(ENTITLEMENT, zipped_questionnaire_pack(tmp_path / "elsewhere"))
    with serving(elsewhere.app()) as other:
        license_server.pack_redirect = f"{other}/api/v1/license/job-pack"

        response = await download(client)

    assert response.json()["outcomes"] == [outcome("unavailable", UNAVAILABLE)]
    assert elsewhere.pack_asked == []
    assert installed() == []


async def test_a_body_over_the_cap_is_refused_and_no_download_is_left(
    client: AsyncClient, license_server: StandInLicenseServer
) -> None:
    """The download stops past 50 MB, and its scratch file goes."""
    await add_license(client)
    license_server.offer(ENTITLEMENT, bytes(MAX_PACK_BYTES + 1))

    response = await download(client)

    assert response.json()["outcomes"] == [
        outcome("refused", "The pack is larger than 50 MB.", detail="PACK_TOO_LARGE")
    ]
    assert scratch() == []


def disk_without_room(*args: object, **kwargs: object) -> object:
    """The download's scratch file on a disk with no room left: its first write fails, as
    the system fails it."""
    file = tempfile.NamedTemporaryFile(*args, **kwargs)  # noqa: SIM115

    def write(_data: bytes) -> int:
        raise OSError(errno.ENOSPC, "No space left on device")

    file.write = write
    return file


async def test_a_full_disk_keeps_the_installed_pack_and_leaves_no_download(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The newer version arrives on a disk with no room: it is not written, the answer says
    so, and the installed version stays."""
    await add_license(client)
    offer(license_server, tmp_path)
    await download(client)
    offer(license_server, tmp_path, version="1.1.0")
    monkeypatch.setattr(pack_request, "NamedTemporaryFile", disk_without_room)

    response = await download(client)

    assert response.status_code == 200, response.text
    assert response.json()["outcomes"] == [outcome("not_written", NOT_WRITTEN)]
    assert installed() == [(PACK_ID, "1.0.0")]
    assert scratch() == []


async def test_a_packs_folder_that_cannot_be_made_still_answers_every_code(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """A file stands where the packs folder goes, so nothing can be saved: the code sent
    is not written, and the codes after it are still asked for and answered."""
    await add_license(client, business_license(jobs=f"{ENTITLEMENT},JOB_OTHER"))
    offer(license_server, tmp_path)
    packs_dir().write_text("not a folder", encoding="utf-8")

    response = await download(client)

    assert response.status_code == 200, response.text
    assert [(o["entitlement"], o["outcome"]) for o in response.json()["outcomes"]] == [
        (ENTITLEMENT, "not_written"),
        ("JOB_OTHER", "unavailable"),
    ]
    assert [asked.body["entitlement"] for asked in license_server.pack_asked] == [
        ENTITLEMENT,
        "JOB_OTHER",
    ]


async def test_a_server_out_of_reach_is_unavailable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing listens there: the next check or the user's next action tries again."""
    await add_license(client)
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    monkeypatch.setattr(
        get_license_server_settings(), "license_server_url", f"http://127.0.0.1:{port}"
    )

    response = await download(client)

    assert response.json()["outcomes"] == [outcome("unavailable", UNAVAILABLE)]


async def test_a_slow_server_is_given_up_on(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A read that waits past its limit is a failure, not a wait without end."""
    monkeypatch.setattr(pack_request, "READ_SECONDS", 0.3)
    await add_license(client)
    offer(license_server, tmp_path)
    license_server.pack_delay_seconds = 3

    response = await download(client)

    assert response.json()["outcomes"] == [outcome("unavailable", UNAVAILABLE)]
    assert installed() == []


async def test_nothing_is_sent_until_the_license_server_is_allowed(
    client: AsyncClient, compiled_license_server: None
) -> None:
    """Off by default: the route answers the host to ask about, after its plan is committed,
    and the screen asks and tries again."""
    await add_license(client)

    response = await download(client)

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "egress_disabled",
        "message": "sending data to api.surfsense.com is off in Settings > Network",
        "destination": "host:api.surfsense.com",
        "host": "api.surfsense.com",
        "hosts": ["api.surfsense.com"],
        "purpose": "job_packs",
    }
    network = {row["host"]: row for row in (await client.get("/egress")).json()}
    assert network["api.surfsense.com"]["last_call_at"] is None
    assert installed() == []


async def test_a_firm_s_mirror_is_listed_off_once_refused(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mirror no connection names is recorded off, so Settings lists it to allow."""
    monkeypatch.setattr(
        get_license_server_settings(),
        "license_server_url",
        "https://licenses.example.test",
    )
    await add_license(client)

    response = await download(client)

    assert response.status_code == 403
    assert response.json()["detail"]["host"] == "licenses.example.test"
    network = {row["host"]: row for row in (await client.get("/egress")).json()}
    assert network["licenses.example.test"]["enabled"] is False


@pytest.fixture
def mirror(
    license_server: StandInLicenseServer, monkeypatch: pytest.MonkeyPatch
) -> StandInLicenseServer:
    """The stand-in reached by a name that is no loopback address, as a firm's mirror is, so
    Settings > Network can turn its host off: the name resolves to the stand-in, as a hosts
    file would have it."""
    served = urlsplit(get_license_server_settings().license_server_url)
    resolve = socket.getaddrinfo

    def resolved(host: str | bytes | None, *args: object, **kwargs: object):
        named = host.decode() if isinstance(host, bytes) else host
        return resolve(served.hostname if named == MIRROR else host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolved)
    monkeypatch.setattr(
        get_license_server_settings(),
        "license_server_url",
        f"http://{MIRROR}:{served.port}",
    )
    return license_server


async def allow_mirror(client: AsyncClient, enabled: bool) -> None:
    """Turn the mirror's host on or off, as Settings > Network does."""
    answer = await client.put(
        "/egress", json={"destinations": [f"host:{MIRROR}"], "enabled": enabled}
    )
    assert answer.status_code == 200, answer.text


async def test_a_download_a_run_holds_back_still_asks_to_reach_the_license_server(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    mirror: StandInLicenseServer,
    tmp_path: Path,
) -> None:
    """A run of the installed pack holds every code back, so nothing would be sent now; but
    the check made once the run ends is background work, which never asks. So the user's
    Download asks for the host first, and records nothing held back until it is allowed."""
    await add_license(client)
    await allow_mirror(client, True)
    offer(mirror, tmp_path)
    first = await download(client)
    assert first.json()["outcomes"] == [
        outcome("installed", "Test jobs 1.0.0 is installed.", "1.0.0")
    ]
    await allow_mirror(client, False)
    await start_run(client, session, workspace.id)
    offer(mirror, tmp_path, version="1.1.0")

    refused = await download(client)

    assert refused.status_code == 403, refused.text
    assert refused.json()["detail"] == {
        "code": "egress_disabled",
        "message": f"sending data to {MIRROR} is off in Settings > Network",
        "destination": f"host:{MIRROR}",
        "host": MIRROR,
        "hosts": [MIRROR],
        "purpose": "job_packs",
    }
    assert HELD_BACK.held() == {}

    await allow_mirror(client, True)
    deferred = await download(client)

    assert deferred.json()["outcomes"] == [outcome("deferred", DEFERRED, "1.0.0")]
    assert HELD_BACK.held() == {ENTITLEMENT: PACK_ID}
    assert len(mirror.pack_asked) == 1
    assert installed() == [(PACK_ID, "1.0.0")]


async def last_call(client: AsyncClient) -> str | None:
    """The mirror's last call, as Settings > Network shows it."""
    network = {row["host"]: row for row in (await client.get("/egress")).json()}
    return network[MIRROR]["last_call_at"]


async def test_a_download_a_run_holds_back_entirely_shows_no_call_in_settings(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    mirror: StandInLicenseServer,
    tmp_path: Path,
) -> None:
    """Settings > Network shows each host's last call: a Download that a run holds back
    entirely checks that the host is allowed and sends nothing, so the call shown stays the
    one the first download made."""
    await add_license(client)
    await allow_mirror(client, True)
    offer(mirror, tmp_path)
    await download(client)
    called = await last_call(client)
    assert called is not None
    await start_run(client, session, workspace.id)
    offer(mirror, tmp_path, version="1.1.0")

    deferred = await download(client)

    assert deferred.json()["outcomes"] == [outcome("deferred", DEFERRED, "1.0.0")]
    assert len(mirror.pack_asked) == 1
    assert await last_call(client) == called


@pytest.mark.parametrize(
    ("certificate", "code"),
    [
        (None, "license_none"),
        (
            business_license(jobs=ENTITLEMENT, expiry="2026-09-01T00:00:00.000Z"),
            "license_not_active",
        ),
        (
            business_license(plan="individual", firm=None, jobs=None, max_users=None),
            "license_no_jobs",
        ),
    ],
    ids=["no license", "expired", "no jobs"],
)
async def test_without_an_active_license_with_jobs_nothing_is_sent(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    certificate: str | None,
    code: str,
) -> None:
    """There is no job to ask for, so the server is never contacted."""
    if certificate is not None:
        await add_license(client, certificate)

    response = await download(client)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == code
    assert license_server.pack_asked == []


async def test_only_the_named_codes_are_fetched(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """A code the license does not hold is answered at once and never asked for."""
    await add_license(client, business_license(jobs=f"{ENTITLEMENT},JOB_OTHER"))
    offer(license_server, tmp_path)

    response = await download(client, {"entitlements": [ENTITLEMENT, "JOB_UNSOLD"]})

    assert [(o["entitlement"], o["outcome"]) for o in response.json()["outcomes"]] == [
        (ENTITLEMENT, "installed"),
        ("JOB_UNSOLD", "job_not_included"),
    ]
    assert [asked.body["entitlement"] for asked in license_server.pack_asked] == [
        ENTITLEMENT
    ]

    malformed = await download(client, {"entitlements": ["job_questionnaire"]})

    assert malformed.status_code == 422
    assert isinstance(malformed.json()["detail"], list)


async def test_a_code_the_license_server_could_never_take_is_never_sent(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A hand-issued license may list a code contract 6's request does not allow: it is an
    unknown job, answered without a request and logged without alarm, and the license's
    other codes are asked for as before."""
    caplog.set_level(logging.INFO)
    await add_license(
        client, business_license(jobs=f"job_lower,{ENTITLEMENT},JOB-DASH")
    )
    offer(license_server, tmp_path)

    response = await download(client)

    assert response.json()["outcomes"] == [
        outcome("unknown_job", UNKNOWN_JOB, entitlement="job_lower"),
        outcome("installed", "Test jobs 1.0.0 is installed.", "1.0.0"),
        outcome("unknown_job", UNKNOWN_JOB, entitlement="JOB-DASH"),
    ]
    assert [asked.body["entitlement"] for asked in license_server.pack_asked] == [
        ENTITLEMENT
    ]
    assert license_server.pack_rules_broken == []
    assert not [
        record
        for record in caplog.records
        if record.name.startswith("modules.jobs") and record.levelno >= logging.WARNING
    ]


async def test_a_license_whose_codes_could_never_be_sent_asks_to_reach_nothing(
    client: AsyncClient, compiled_license_server: None
) -> None:
    """Nothing would be sent, so the license server's host is not asked about, off as it
    is, and the answer says why there is no job."""
    await add_license(client, business_license(jobs="job_lower"))

    response = await download(client)

    assert response.status_code == 200, response.text
    assert response.json()["outcomes"] == [
        outcome("unknown_job", UNKNOWN_JOB, entitlement="job_lower")
    ]


async def test_a_422_list_is_logged_without_the_key(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A malformed request is the app's own bug: the log says which field, and nothing it
    sent."""
    caplog.set_level(logging.DEBUG)
    await add_license(client)
    license_server.pack_refusal = (
        422,
        [{"type": "missing", "loc": ["body", "runners"], "msg": "Field required"}],
    )

    response = await download(client)

    assert response.json()["outcomes"] == [outcome("unavailable", UNAVAILABLE)]
    assert "missing" in caplog.text and "runners" in caplog.text
    assert "Field required" not in caplog.text
    assert BUSINESS_KEY not in caplog.text


async def test_the_key_is_never_logged(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Not on a download, a refusal or a current pack, at any log level."""
    caplog.set_level(logging.DEBUG)
    await add_license(client)
    offer(license_server, tmp_path)

    await download(client)
    await download(client)
    license_server.pack_refusal = (403, {"code": "license_not_valid", "message": "No."})
    await download(client)

    assert len(license_server.pack_asked) == 3
    assert BUSINESS_KEY not in caplog.text


async def test_every_request_the_app_sends_keeps_the_server_s_rules(
    client: AsyncClient, license_server: StandInLicenseServer, tmp_path: Path
) -> None:
    """The stand-in checks each body as api.surfsense.com does: with nothing installed, with
    an installed version to send, and for the codes named, the app sends none it refuses."""
    await add_license(client, business_license(jobs=f"{ENTITLEMENT},JOB_OTHER"))
    offer(license_server, tmp_path)

    await download(client)
    await download(client)
    await download(client, {"entitlements": ["JOB_OTHER", ENTITLEMENT]})

    assert [
        (asked.body["entitlement"], asked.body.get("installed_version"))
        for asked in license_server.pack_asked
    ] == [
        (ENTITLEMENT, None),
        ("JOB_OTHER", None),
        (ENTITLEMENT, "1.0.0"),
        ("JOB_OTHER", None),
        ("JOB_OTHER", None),
        (ENTITLEMENT, "1.0.0"),
    ]
    assert license_server.pack_rules_broken == []


@pytest.mark.parametrize(
    ("change", "loc"),
    [
        ({"entitlement": "job_questionnaire"}, ["body", "entitlement"]),
        ({"installed_version": "1.0.1234567890"}, ["body", "installed_version"]),
        ({"installed_version": "1.0.\u0661"}, ["body", "installed_version"]),
        ({"runners": [f"runner-{n}/1" for n in range(17)]}, ["body", "runners"]),
        ({"runners": ["Workbook rows"]}, ["body", "runners", 0]),
        ({"key": "   "}, ["body", "key"]),
    ],
    ids=[
        "code",
        "version",
        "a version digit that is not ASCII",
        "17 runners",
        "runner",
        "blank key",
    ],
)
async def test_the_stand_in_refuses_a_body_as_the_server_does(
    license_server: StandInLicenseServer, change: dict, loc: list
) -> None:
    """So the tests above catch any request api.surfsense.com would refuse: its 422 lists
    each rule broken by type and place, and echoes nothing that was sent."""
    body = {"key": BUSINESS_KEY, "entitlement": ENTITLEMENT, "runners": RUNNERS}
    base = get_license_server_settings().license_server_url

    async with AsyncClient(base_url=base) as http:
        answer = await http.post("/api/v1/license/job-pack", json={**body, **change})

    assert answer.status_code == 422
    (error,) = answer.json()["detail"]
    assert (sorted(error), error["loc"]) == (["loc", "msg", "type"], loc)
    assert BUSINESS_KEY not in answer.text
    assert license_server.pack_rules_broken == [[error]]
