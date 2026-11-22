"""With licensing off, as every release ships since 27 Nov 2026 (ADR 0092): the status says
so, the routes that would reach the licence server refuse before sending anything, and a
licence or a pack can still be imported."""

import pytest
from httpx import AsyncClient

from modules.egress.service import BUILT_IN, LICENSE_SERVER
from modules.license.licensing import OVERRIDE
from tests.job_pack_samples import PACK_ID, zipped_questionnaire_pack
from tests.license_samples import business_license, trust_sample_licenses
from tests.license_server_stand_in import StandInLicenseServer

pytestmark = pytest.mark.integration

LICENSING_OFF = {
    "code": "licensing_off",
    "message": "SurfSense is free, so there is no license to renew and no job pack "
    "to download: every job runs as it is.",
}


@pytest.fixture(autouse=True)
def licensing_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """As a release runs: the tests' override unset, the business sample trusted."""
    monkeypatch.delenv(OVERRIDE, raising=False)
    trust_sample_licenses(monkeypatch)


async def test_the_status_says_licensing_is_off(client: AsyncClient) -> None:
    """The one flag the screens hide every licence surface by."""
    status = (await client.get("/license/status")).json()

    assert status["licensing"] is False
    assert status["state"] == "none"


async def test_a_license_is_still_imported_and_says_licensing_is_off(
    client: AsyncClient,
) -> None:
    """Import stays reachable, so a relaunch can read a file a user already holds."""
    imported = await client.put("/license", json={"certificate": business_license()})

    assert imported.status_code == 200, imported.text
    assert imported.json()["state"] == "active"
    assert imported.json()["licensing"] is False


async def test_a_renewal_check_is_refused_and_sends_nothing(
    client: AsyncClient, license_server: StandInLicenseServer
) -> None:
    """Even with a licence that could be renewed: no licence server is there to answer."""
    await client.put("/license", json={"certificate": business_license()})

    refreshed = await client.post("/license/refresh")

    assert refreshed.status_code == 409
    assert refreshed.json()["detail"] == LICENSING_OFF
    assert license_server.asked == []


async def test_a_pack_download_is_refused_and_sends_nothing(
    client: AsyncClient, license_server: StandInLicenseServer
) -> None:
    """The packs come with the app instead."""
    await client.put("/license", json={"certificate": business_license()})

    downloaded = await client.post("/job-packs/download")

    assert downloaded.status_code == 409
    assert downloaded.json()["detail"] == LICENSING_OFF
    assert license_server.pack_asked == []


async def test_a_pack_is_still_imported_and_its_paid_job_is_unlocked(
    client: AsyncClient, tmp_path
) -> None:
    """No licence at all: an imported paid pack's job runs."""
    imported = await client.post(
        "/job-packs/import",
        files={
            "file": (
                "pack.zip",
                zipped_questionnaire_pack(tmp_path / "pack"),
                "application/zip",
            )
        },
    )

    assert imported.status_code == 200, imported.text
    (pack,) = [p for p in imported.json() if p["id"] == PACK_ID]
    assert pack["access"] == "paid"
    assert pack["unlocked"] is True
    assert [job["unlocked"] for job in pack["jobs"]] == [True]


async def test_network_settings_no_longer_list_the_license_server(
    client: AsyncClient,
) -> None:
    """Nothing reaches it, so there is nothing to allow; the other built-in hosts stay."""
    listed = [row["destination"] for row in (await client.get("/egress")).json()]

    assert LICENSE_SERVER not in listed
    assert listed == [host for host in BUILT_IN if host != LICENSE_SERVER]
