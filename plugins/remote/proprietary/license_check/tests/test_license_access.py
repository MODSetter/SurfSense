from pathlib import Path

import httpx2
import pytest
from starlette.datastructures import Headers

from host.app import host_app
from host.tests.mcp_calls import tool_names
from host.tests.serving import serving
from mcp_server.access import Refusal
from proprietary.license_check.keygen import Keygen
from proprietary.license_check.license_access import LicenseAccess
from proprietary.license_check.tests.stand_in_keygen import ACCOUNT, StandInKeygen

SAMPLES = Path(__file__).parent / "sample_plugins"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def license_header(key: str) -> Headers:
    return Headers({"authorization": f"License {key}"})


@pytest.mark.parametrize("authorization", [None, "Bearer k-1", "License ", "License"])
async def test_a_request_without_a_license_key_is_refused(
    authorization: str | None,
) -> None:
    """Nothing is asked of Keygen: there is no key to ask about."""
    keygen = StandInKeygen({})
    headers = Headers({"authorization": authorization} if authorization else {})
    with serving(keygen.app) as url:
        refusal = await LicenseAccess(Keygen(url, ACCOUNT)).refusal(headers)

    assert refusal == Refusal(401, "missing_license")
    assert keygen.validated == []


@pytest.mark.parametrize(
    ("code", "refusal"),
    [
        ("VALID", None),
        ("EXPIRED", Refusal(403, "expired")),
        ("SUSPENDED", Refusal(403, "revoked")),
        ("BANNED", Refusal(403, "revoked")),
        ("NOT_FOUND", Refusal(403, "invalid")),
        ("POLICY_SCOPE_MISMATCH", Refusal(403, "invalid")),
    ],
)
async def test_keygen_decides_whether_a_key_may_call(
    code: str, refusal: Refusal | None
) -> None:
    """Contract 2's reasons: a refund suspends a license, which reads as revoked."""
    keygen = StandInKeygen({"k-1": code})
    with serving(keygen.app) as url:
        access = LicenseAccess(Keygen(url, ACCOUNT))
        assert await access.refusal(license_header("k-1")) == refusal


async def test_a_key_is_asked_about_once_in_five_minutes() -> None:
    keygen = StandInKeygen({"k-1": "VALID"})
    clock = Clock()
    with serving(keygen.app) as url:
        access = LicenseAccess(Keygen(url, ACCOUNT), clock)
        await access.refusal(license_header("k-1"))
        clock.now += 299
        await access.refusal(license_header("k-1"))
        assert keygen.validated == ["k-1"]

        clock.now += 1
        await access.refusal(license_header("k-1"))
        assert keygen.validated == ["k-1", "k-1"]


async def test_keygen_down_keeps_a_key_valid_this_morning_working() -> None:
    """Never fail closed for a key that was valid in the last day."""
    keygen = StandInKeygen({"k-1": "VALID"})
    clock = Clock()
    with serving(keygen.app) as url:
        access = LicenseAccess(Keygen(url, ACCOUNT), clock)
        await access.refusal(license_header("k-1"))
        keygen.down = True

        clock.now += 23 * 3600
        assert await access.refusal(license_header("k-1")) is None
        clock.now += 3600
        assert await access.refusal(license_header("k-1")) == Refusal(
            503, "license_service_unavailable"
        )


async def test_keygen_unreachable_refuses_a_key_never_seen_for_now() -> None:
    """A 503: the app shows it as temporary, not as a bad license."""
    with serving(StandInKeygen({}).app) as url:
        pass
    access = LicenseAccess(Keygen(url, ACCOUNT))

    assert await access.refusal(license_header("k-1")) == Refusal(
        503, "license_service_unavailable"
    )


async def test_a_paid_plugin_on_the_host_answers_only_a_valid_license(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keygen = StandInKeygen({"k-1": "VALID", "k-2": "EXPIRED"})
    with serving(keygen.app) as keygen_url:
        monkeypatch.setenv("STAND_IN_KEYGEN_URL", keygen_url)
        with serving(host_app(SAMPLES)) as base:
            plugin = f"{base}/paid/mcp"
            missing = httpx2.post(plugin, json={})
            expired = httpx2.post(
                plugin, json={}, headers={"Authorization": "License k-2"}
            )
            tools = await tool_names(plugin, {"Authorization": "License k-1"})

    assert (missing.status_code, missing.json()) == (
        401,
        {"reason": "missing_license"},
    )
    assert (expired.status_code, expired.json()) == (403, {"reason": "expired"})
    assert tools == ["scrape"]
