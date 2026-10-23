import asyncio
from pathlib import Path

import httpx2
import pytest
from starlette.datastructures import Headers

from host.app import host_app
from host.tests.mcp_calls import tool_names
from host.tests.serving import serving
from mcp_server.access import Refusal, checked_license
from proprietary.license_check.keygen import (
    CLOUD_ACCOUNTS_URL,
    Keygen,
    KeygenUnreachableError,
    Validation,
)
from proprietary.license_check.license_access import (
    GRACE_SECONDS,
    LicenseAccess,
    shared_access,
)
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
    license_id_of,
)

SAMPLES = Path(__file__).parent / "sample_plugins"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def license_header(key: str) -> Headers:
    return Headers({"authorization": f"License {key}"})


class GatedKeygen:
    """Keygen in memory, answering once the test opens its gate."""

    def __init__(self, codes: dict[str, str]) -> None:
        self.codes = codes
        self.asked: list[str] = []
        self.down = False
        self.gate = asyncio.Event()
        self.gate.set()

    async def validation(self, key: str) -> Validation:
        self.asked.append(key)
        await self.gate.wait()
        if self.down:
            raise KeygenUnreachableError("down")
        return Validation(self.codes.get(key, "NOT_FOUND"))


@pytest.mark.parametrize("authorization", [None, "Bearer k-1", "License ", "License"])
async def test_a_request_without_a_license_key_is_refused(
    authorization: str | None,
) -> None:
    """Nothing is asked of Keygen: there is no key to ask about."""
    keygen = StandInKeygen({})
    headers = Headers({"authorization": authorization} if authorization else {})
    with serving(keygen.app) as url:
        refusal = await LicenseAccess(Keygen(accounts_url(url), ACCOUNT)).refusal(
            headers
        )

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
        access = LicenseAccess(Keygen(accounts_url(url), ACCOUNT))
        assert await access.refusal(license_header("k-1")) == refusal


async def test_the_check_names_the_license_keygen_found_without_asking_again() -> None:
    """For the usage meter: Keygen's `data.id`, allowed or refused, never the key."""
    keygen = StandInKeygen({"k-1": "VALID", "k-2": "EXPIRED"})
    with serving(keygen.app) as url:
        access = LicenseAccess(Keygen(accounts_url(url), ACCOUNT))
        found = []
        for authorization in ["k-1", "k-1", "k-2", "k-3"]:
            await access.refusal(license_header(authorization))
            found.append(checked_license.get())
        await access.refusal(Headers({}))
        found.append(checked_license.get())

    # An unknown key and no key at all name no license.
    assert found == [
        license_id_of("k-1"),
        license_id_of("k-1"),
        license_id_of("k-2"),
        None,
        None,
    ]
    assert keygen.validated == ["k-1", "k-2", "k-3"]


async def test_a_key_is_asked_about_once_in_five_minutes() -> None:
    """After five minutes a valid key is asked about again, in the background."""
    keygen = StandInKeygen({"k-1": "VALID"})
    clock = Clock()
    with serving(keygen.app) as url:
        access = LicenseAccess(Keygen(accounts_url(url), ACCOUNT), clock)
        await access.refusal(license_header("k-1"))
        clock.now += 299
        await access.refusal(license_header("k-1"))
        await access.settled()
        assert keygen.validated == ["k-1"]

        clock.now += 1
        await access.refusal(license_header("k-1"))
        await access.settled()
        assert keygen.validated == ["k-1", "k-1"]


async def test_a_stale_valid_key_passes_at_once_while_keygen_is_asked_again() -> None:
    """The answer comes from the background check, for the next request."""
    keygen = GatedKeygen({"k-1": "VALID"})
    clock = Clock()
    access = LicenseAccess(keygen, clock)
    await access.refusal(license_header("k-1"))
    keygen.gate.clear()
    keygen.codes["k-1"] = "EXPIRED"
    clock.now += 600

    for _ in range(3):
        assert await asyncio.wait_for(access.refusal(license_header("k-1")), 1) is None
    keygen.gate.set()
    await access.settled()

    assert keygen.asked == ["k-1", "k-1"]
    assert await access.refusal(license_header("k-1")) == Refusal(403, "expired")


async def test_requests_for_a_key_never_seen_ask_keygen_once() -> None:
    keygen = GatedKeygen({"k-1": "VALID"})
    keygen.gate.clear()
    access = LicenseAccess(keygen, Clock())
    waiting = [
        asyncio.create_task(access.refusal(license_header("k-1"))) for _ in range(5)
    ]
    await asyncio.sleep(0.01)
    keygen.gate.set()

    assert await asyncio.gather(*waiting) == [None] * 5
    assert keygen.asked == ["k-1"]


async def test_a_request_giving_up_leaves_the_check_to_the_others() -> None:
    keygen = GatedKeygen({"k-1": "VALID"})
    keygen.gate.clear()
    access = LicenseAccess(keygen, Clock())
    leaving = asyncio.create_task(access.refusal(license_header("k-1")))
    staying = asyncio.create_task(access.refusal(license_header("k-1")))
    await asyncio.sleep(0.01)
    leaving.cancel()
    keygen.gate.set()

    assert await staying is None
    assert keygen.asked == ["k-1"]


async def test_a_refused_key_waits_for_keygen_s_new_answer() -> None:
    """A renewed key passes on its first request after five minutes."""
    keygen = GatedKeygen({"k-1": "EXPIRED"})
    clock = Clock()
    access = LicenseAccess(keygen, clock)
    assert await access.refusal(license_header("k-1")) == Refusal(403, "expired")
    keygen.codes["k-1"] = "VALID"
    clock.now += 300

    assert await access.refusal(license_header("k-1")) is None


async def test_a_key_unused_for_a_day_waits_for_keygen() -> None:
    """Past the grace, a key once valid is not let through on its old answer."""
    keygen = GatedKeygen({"k-1": "VALID"})
    clock = Clock()
    access = LicenseAccess(keygen, clock)
    await access.refusal(license_header("k-1"))
    keygen.codes["k-1"] = "EXPIRED"
    clock.now += GRACE_SECONDS

    assert await access.refusal(license_header("k-1")) == Refusal(403, "expired")


async def test_keygen_down_in_the_background_keeps_the_grace() -> None:
    keygen = GatedKeygen({"k-1": "VALID"})
    clock = Clock()
    access = LicenseAccess(keygen, clock)
    await access.refusal(license_header("k-1"))
    keygen.down = True

    clock.now += 23 * 3600
    assert await access.refusal(license_header("k-1")) is None
    await access.settled()
    clock.now += 3600
    assert await access.refusal(license_header("k-1")) == Refusal(
        503, "license_service_unavailable"
    )


def test_paid_plugins_share_one_license_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One per process for Keygen's settings, so a key is asked about once for all."""
    monkeypatch.setenv("KEYGEN_API_URL", "http://keygen-a/v1/accounts")
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
    monkeypatch.delenv("KEYGEN_HOST", raising=False)
    first = shared_access()

    assert shared_access() is first
    monkeypatch.setenv("KEYGEN_API_URL", "http://keygen-b/v1/accounts")
    assert shared_access() is not first


async def test_keygen_down_keeps_a_key_valid_this_morning_working() -> None:
    """Never fail closed for a key that was valid in the last day."""
    keygen = StandInKeygen({"k-1": "VALID"})
    clock = Clock()
    with serving(keygen.app) as url:
        access = LicenseAccess(Keygen(accounts_url(url), ACCOUNT), clock)
        await access.refusal(license_header("k-1"))
        keygen.down = True

        clock.now += 23 * 3600
        assert await access.refusal(license_header("k-1")) is None
        clock.now += 3600
        assert await access.refusal(license_header("k-1")) == Refusal(
            503, "license_service_unavailable"
        )


async def test_a_key_refused_since_it_was_valid_has_no_grace() -> None:
    """An expired key stays refused while Keygen is down, though it was valid this morning."""
    keygen = StandInKeygen({"k-1": "VALID"})
    clock = Clock()
    with serving(keygen.app) as url:
        access = LicenseAccess(Keygen(accounts_url(url), ACCOUNT), clock)
        await access.refusal(license_header("k-1"))
        keygen.codes["k-1"] = "EXPIRED"
        clock.now += 300
        await access.refusal(license_header("k-1"))
        # Its answer, EXPIRED, comes from the check this request started.
        await access.settled()
        keygen.down = True
        clock.now += 300

        assert await access.refusal(license_header("k-1")) == Refusal(
            503, "license_service_unavailable"
        )


async def test_keygen_unreachable_refuses_a_key_never_seen_for_now() -> None:
    """A 503: the app shows it as temporary, not as a bad license."""
    with serving(StandInKeygen({}).app) as url:
        pass
    access = LicenseAccess(Keygen(accounts_url(url), ACCOUNT))

    assert await access.refusal(license_header("k-1")) == Refusal(
        503, "license_service_unavailable"
    )


async def test_a_keygen_refusing_the_request_refuses_the_key_as_invalid() -> None:
    """A 4xx, such as a wrong account's 404, is a 403 invalid, never the plugin's 500."""
    keygen = StandInKeygen({"k-1": "VALID"})
    with serving(keygen.app) as url:
        access = LicenseAccess(Keygen(accounts_url(url), "another-account"))
        assert await access.refusal(license_header("k-1")) == Refusal(403, "invalid")


async def test_an_answer_that_is_not_keygen_s_is_no_answer() -> None:
    """A page with no code, as a proxy in the way would serve, gives the grace, not a verdict."""
    keygen = StandInKeygen({"k-1": "VALID"})
    clock = Clock()
    with serving(keygen.app) as url:
        access = LicenseAccess(Keygen(accounts_url(url), ACCOUNT), clock)
        await access.refusal(license_header("k-1"))
        keygen.garbled = True
        clock.now += 300
        assert await access.refusal(license_header("k-1")) is None
        assert await access.refusal(license_header("k-2")) == Refusal(
            503, "license_service_unavailable"
        )


async def test_a_self_hosted_keygen_is_told_its_host_and_https() -> None:
    """Keygen CE finds the account from Host and redirects plain HTTP unless a proxy vouches."""
    keygen = StandInKeygen({"k-1": "VALID"})
    with serving(keygen.app) as url:
        hosted = Keygen(accounts_url(url), ACCOUNT, "keygen.internal")
        assert (await hosted.validation("k-1")).code == "VALID"
        plain = Keygen(accounts_url(url), ACCOUNT)
        assert (await plain.validation("k-1")).code == "VALID"

    (hosted_host, hosted_proto), (plain_host, plain_proto) = keygen.seen_headers
    assert (hosted_host, hosted_proto) == ("keygen.internal", "https")
    assert plain_host == url.removeprefix("http://")
    assert plain_proto is None


def test_keygen_s_settings_are_the_deployment_s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backend's names and meanings, so a deployment gives both the same values."""
    monkeypatch.setenv("KEYGEN_API_URL", "http://keygen-web:3000/v1/accounts")
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
    monkeypatch.setenv("KEYGEN_HOST", "keygen.internal")

    assert Keygen() == Keygen(
        "http://keygen-web:3000/v1/accounts", ACCOUNT, "keygen.internal"
    )


def test_without_settings_keygen_is_keygen_cloud_and_the_account_is_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("KEYGEN_API_URL", "KEYGEN_ACCOUNT_ID", "KEYGEN_HOST"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="KEYGEN_ACCOUNT_ID"):
        Keygen()
    assert Keygen(account_id=ACCOUNT) == Keygen(CLOUD_ACCOUNTS_URL, ACCOUNT, None)


async def test_a_paid_plugin_on_the_host_answers_only_a_valid_license(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keygen = StandInKeygen({"k-1": "VALID", "k-2": "EXPIRED"})
    with serving(keygen.app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
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


async def test_paid_plugins_on_one_host_ask_keygen_once_for_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keygen = StandInKeygen({"k-1": "VALID"})
    with serving(keygen.app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(SAMPLES)) as base:
            licensed = {"Authorization": "License k-1"}
            assert await tool_names(f"{base}/paid/mcp", licensed) == ["scrape"]
            assert await tool_names(f"{base}/paid-too/mcp", licensed) == ["scrape"]

    assert keygen.validated == ["k-1"]


async def test_the_host_answers_the_license_once_for_every_paid_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The app asks once, not by listing each paid plugin; the answers are contract 2's."""
    keygen = StandInKeygen({"k-1": "VALID", "k-2": "EXPIRED"})
    with serving(keygen.app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(SAMPLES)) as base:
            missing = httpx2.get(f"{base}/license")
            expired = httpx2.get(
                f"{base}/license", headers={"Authorization": "License k-2"}
            )
            valid = httpx2.get(
                f"{base}/license", headers={"Authorization": "License k-1"}
            )

    assert (missing.status_code, missing.json()) == (
        401,
        {"reason": "missing_license"},
    )
    assert (expired.status_code, expired.json()) == (403, {"reason": "expired"})
    assert (valid.status_code, valid.json()) == (200, {"status": "valid"})
