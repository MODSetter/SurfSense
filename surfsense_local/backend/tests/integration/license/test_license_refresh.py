"""Checking for a renewal from Settings: the key goes out, the license server's file comes back."""

import base64
import json
import re

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient, Response

from modules.license.renewal import renewed_file
from shared.config import get_license_server_settings
from tests.license_samples import BUSINESS_KEY, business_license, trust_sample_licenses
from tests.license_server_stand_in import Asked, StandInLicenseServer

pytestmark = pytest.mark.integration

# The same license, renewed for another year on the same key.
RENEWED = business_license(
    issued="2026-09-11T00:00:00.000Z", expiry="2028-10-10T00:00:00.000Z"
)


@pytest.fixture(autouse=True)
def sample_licenses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files signed with the samples' key verify, on a day the samples are valid."""
    trust_sample_licenses(monkeypatch)


async def add_business_license(client: AsyncClient) -> None:
    """Five people at a firm, imported as Settings does."""
    added = await client.put("/license", json={"certificate": business_license()})
    assert added.status_code == 200, added.text


async def refresh(client: AsyncClient) -> Response:
    """Settings' Check for renewal."""
    return await client.post("/license/refresh")


async def stored_expiry(client: AsyncClient) -> str:
    """When the stored license ends, as Settings shows it."""
    return (await client.get("/license/status")).json()["expiry"]


async def test_a_renewal_replaces_the_stored_file_on_the_same_key(
    client: AsyncClient, license_server: StandInLicenseServer
) -> None:
    """Rule 7: the renewed file takes the old one's place, and only the key was sent,
    under the app's bare name as update checks send it."""
    await add_business_license(client)
    license_server.files[BUSINESS_KEY] = RENEWED

    response = await refresh(client)

    assert response.status_code == 200, response.text
    assert response.json()["expiry"] == "2028-10-10T00:00:00Z"
    assert (await client.get("/license/status")).json() == response.json()
    assert license_server.asked == [
        Asked("/api/v1/license/refresh", "", {"key": BUSINESS_KEY}, "SurfSense")
    ]


async def test_a_lapsed_license_s_file_is_kept_and_marked(
    client: AsyncClient, license_server: StandInLicenseServer
) -> None:
    """The server answers an expired license too; expiry is a state, not a rejection."""
    lapsed = business_license(expiry="2026-09-01T00:00:00.000Z")
    await client.put("/license", json={"certificate": lapsed})
    license_server.files[BUSINESS_KEY] = business_license(
        issued="2026-09-11T00:00:00.000Z", expiry="2026-09-05T00:00:00.000Z"
    )

    response = await refresh(client)

    assert response.status_code == 200
    assert (response.json()["state"], response.json()["expiry"]) == (
        "license_expired",
        "2026-09-05T00:00:00Z",
    )


async def test_with_no_license_there_is_nothing_to_renew(
    client: AsyncClient, license_server: StandInLicenseServer
) -> None:
    """No key, no request."""
    response = await refresh(client)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "license_none"
    assert license_server.asked == []


@pytest.mark.parametrize(
    ("answer", "status", "code"),
    [
        ((404, "No license has that key."), 404, "refresh_not_found"),
        (
            (403, "This license cannot be refreshed (SUSPENDED). Contact support."),
            403,
            "refresh_refused",
        ),
        ((429, "Too many requests. Try again later."), 429, "refresh_rate_limited"),
        (
            (503, "Could not check that license right now. Try again later."),
            503,
            "refresh_unavailable",
        ),
        (
            (422, [{"type": "missing", "loc": ["body", "key"]}]),
            503,
            "refresh_unavailable",
        ),
    ],
)
async def test_every_answer_but_a_file_keeps_the_stored_license(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    answer: tuple[int, object],
    status: int,
    code: str,
) -> None:
    """A suspended license is said so, and never disables the app."""
    await add_business_license(client)
    license_server.refusal = answer

    response = await refresh(client)

    assert (response.status_code, response.json()["detail"]["code"]) == (status, code)
    assert response.json()["detail"]["message"]
    assert await stored_expiry(client) == "2027-10-10T00:00:00Z"


async def test_a_server_out_of_reach_is_unavailable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Offline, or nothing listening, reads as Keygen down: try again later."""
    await add_business_license(client)
    monkeypatch.setattr(
        get_license_server_settings(), "license_server_url", "http://127.0.0.1:9"
    )

    response = await refresh(client)

    assert (response.status_code, response.json()["detail"]["code"]) == (
        503,
        "refresh_unavailable",
    )


async def test_a_slow_server_is_given_up_on(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The button never hangs on a server that does not answer."""
    monkeypatch.setattr(renewed_file, "TIMEOUT_SECONDS", 0.1)
    await add_business_license(client)
    license_server.files[BUSINESS_KEY] = RENEWED
    license_server.delay_seconds = 1.0

    response = await refresh(client)

    assert response.json()["detail"]["code"] == "refresh_unavailable"
    assert await stored_expiry(client) == "2027-10-10T00:00:00Z"


async def test_a_file_that_trickles_in_is_given_up_on_at_the_deadline(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The deadline covers the whole exchange: a byte now and then never resets it."""
    monkeypatch.setattr(renewed_file, "TIMEOUT_SECONDS", 0.5)
    await add_business_license(client)
    license_server.files[BUSINESS_KEY] = RENEWED
    # A dozen pieces 0.1 s apart: no gap reaches a read's timeout, the whole does.
    license_server.drip_seconds = 0.1

    response = await refresh(client)

    assert (response.status_code, response.json()["detail"]["code"]) == (
        503,
        "refresh_unavailable",
    )
    assert await stored_expiry(client) == "2027-10-10T00:00:00Z"


async def test_a_body_too_large_for_a_license_file_is_refused(
    client: AsyncClient, license_server: StandInLicenseServer
) -> None:
    """A license file is a few kilobytes; a body past 64 KiB is refused as unavailable."""
    await add_business_license(client)
    license_server.files[BUSINESS_KEY] = "x" * (64 * 1024 + 1)

    response = await refresh(client)

    assert (response.status_code, response.json()["detail"]["code"]) == (
        503,
        "refresh_unavailable",
    )
    assert await stored_expiry(client) == "2027-10-10T00:00:00Z"


def signed_elsewhere(certificate: str) -> str:
    """The same file, signed by a key no SurfSense build trusts."""
    body = re.sub(
        r"\s+", "", re.sub(r"-----(BEGIN|END) LICENSE FILE-----", "", certificate)
    )
    outer = json.loads(base64.b64decode(body))
    forged = Ed25519PrivateKey.generate().sign(f"license/{outer['enc']}".encode())
    outer["sig"] = base64.b64encode(forged).decode()
    wrapped = base64.b64encode(json.dumps(outer).encode()).decode()
    return f"-----BEGIN LICENSE FILE-----\n{wrapped}\n-----END LICENSE FILE-----\n"


@pytest.mark.parametrize(
    ("file", "code"),
    [
        ("Service unavailable", "not_a_license_file"),
        (signed_elsewhere(RENEWED), "bad_signature"),
        (business_license(issued="2026-09-12T12:00:00.000Z"), "clock_untrusted"),
    ],
)
async def test_a_file_the_import_refuses_keeps_its_reason(
    client: AsyncClient, license_server: StandInLicenseServer, file: str, code: str
) -> None:
    """The fetched file passes the same checks as one the user adds, signature first."""
    await add_business_license(client)
    license_server.files[BUSINESS_KEY] = file

    response = await refresh(client)

    assert (response.status_code, response.json()["detail"]["code"]) == (422, code)
    assert await stored_expiry(client) == "2027-10-10T00:00:00Z"


async def test_another_license_s_file_never_replaces_the_stored_one(
    client: AsyncClient, license_server: StandInLicenseServer
) -> None:
    """Rule 7 matches on the key: a server's mix-up cannot swap the user's license."""
    await add_business_license(client)
    license_server.files[BUSINESS_KEY] = business_license(
        key="TEST-BUSN-2026-0099",
        issued="2026-09-11T00:00:00.000Z",
        expiry="2028-10-10T00:00:00.000Z",
    )

    response = await refresh(client)

    assert response.json()["detail"]["code"] == "refresh_unavailable"
    assert await stored_expiry(client) == "2027-10-10T00:00:00Z"


async def test_the_license_server_is_listed_off_in_settings_network(
    client: AsyncClient,
) -> None:
    """Built in, so it can be allowed or blocked before a license needs it."""
    network = {row["destination"]: row for row in (await client.get("/egress")).json()}

    assert network["host:api.surfsense.com"] == {
        "destination": "host:api.surfsense.com",
        "host": "api.surfsense.com",
        "enabled": False,
        "last_call_at": None,
    }


async def test_nothing_is_sent_until_the_license_server_is_allowed(
    client: AsyncClient, compiled_license_server: None
) -> None:
    """Refused before any request, naming the host for the consent question."""
    await add_business_license(client)

    response = await refresh(client)

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "refresh_egress_blocked"
    assert "api.surfsense.com" in detail["message"]
    assert (detail["destination"], detail["host"], detail["hosts"]) == (
        "host:api.surfsense.com",
        "api.surfsense.com",
        ["api.surfsense.com"],
    )
    assert detail["purpose"] == "license_refresh"
    network = {row["host"]: row for row in (await client.get("/egress")).json()}
    assert network["api.surfsense.com"]["last_call_at"] is None
    assert await stored_expiry(client) == "2027-10-10T00:00:00Z"


async def test_a_firm_s_mirror_is_listed_in_settings_network_once_refused(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mirror a build points at is a host like any other: off until allowed."""
    monkeypatch.setattr(
        get_license_server_settings(),
        "license_server_url",
        "https://licenses.example.test",
    )
    await add_business_license(client)

    response = await refresh(client)

    assert response.json()["detail"]["code"] == "refresh_egress_blocked"
    assert response.json()["detail"]["host"] == "licenses.example.test"
    network = {row["host"]: row for row in (await client.get("/egress")).json()}
    assert network["licenses.example.test"]["enabled"] is False
