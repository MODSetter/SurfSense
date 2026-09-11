"""Importing and reading a contract-1 license file, verified offline."""

import base64
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient, Response

from modules.license import service, verify

pytestmark = pytest.mark.integration

SAMPLE = Path(__file__).resolve().parents[5] / (
    "plans/community-local/contracts/license-sample"
)
# The fixtures were issued 2026-09-10 and the shortest one expires two weeks later.
TODAY = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def test_key_and_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify with the fixture key on a fixed day, whatever the shipped key and date."""
    monkeypatch.setattr(
        verify, "KEYGEN_PUBLIC_KEY_HEX", (SAMPLE / "public-key.hex").read_text().strip()
    )
    monkeypatch.setattr(service, "now", lambda: TODAY)


async def put_license(client: AsyncClient, certificate: str) -> Response:
    """Send the file's text, as the renderer does after reading the picked file."""
    return await client.put("/license", json={"certificate": certificate})


async def test_a_valid_file_is_active_and_shows_its_plan(client: AsyncClient) -> None:
    """The buyer drops the file and Settings tells them who it is for and until when."""
    response = await put_license(client, (SAMPLE / "individual.lic").read_text())

    assert response.status_code == 200
    status = (await client.get("/license/status")).json()
    assert status == {
        "state": "active",
        "plan": "individual",
        "email": "ada@example.com",
        "expiry": "2027-09-10T00:00:00Z",
        "max_users": None,
    }


@pytest.mark.parametrize(
    ("file", "plan", "max_users"),
    [("team.lic", "team", 12), ("trial.lic", "trial", None)],
)
async def test_each_plan_reads_as_itself(
    client: AsyncClient, file: str, plan: str, max_users: int | None
) -> None:
    """Team seats are shown, never enforced; a trial is just a short plan."""
    response = await put_license(client, (SAMPLE / file).read_text())

    status = response.json()
    assert (status["state"], status["plan"], status["max_users"]) == (
        "active",
        plan,
        max_users,
    )


async def test_an_expired_license_is_kept_and_marked(client: AsyncClient) -> None:
    """Expiry is a state, not a rejection: the user sees whose license ran out."""
    response = await put_license(client, (SAMPLE / "expired.lic").read_text())

    assert response.status_code == 200
    status = (await client.get("/license/status")).json()
    assert (status["state"], status["email"]) == ("license_expired", "old@example.com")


def certificate_with(certificate: str, **outer_changes: str) -> str:
    """Re-wrap the fixture with fields of the outer JSON replaced."""
    body = re.sub(
        r"\s+", "", re.sub(r"-----(BEGIN|END) LICENSE FILE-----", "", certificate)
    )
    outer = json.loads(base64.b64decode(body))
    outer.update(outer_changes)
    wrapped = base64.b64encode(json.dumps(outer).encode()).decode()
    return f"-----BEGIN LICENSE FILE-----\n{wrapped}\n-----END LICENSE FILE-----\n"


async def test_a_changed_payload_is_refused_and_nothing_is_kept(
    client: AsyncClient,
) -> None:
    """One byte of enc changed: the signature no longer covers it."""
    genuine = (SAMPLE / "individual.lic").read_text()
    body = re.sub(
        r"\s+", "", re.sub(r"-----(BEGIN|END) LICENSE FILE-----", "", genuine)
    )
    enc = json.loads(base64.b64decode(body))["enc"]
    flipped = enc[:-2] + ("A" if enc[-2] != "A" else "B") + enc[-1]

    response = await put_license(client, certificate_with(genuine, enc=flipped))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "bad_signature"
    assert (await client.get("/license/status")).json()["state"] == "none"


# generate.mjs's fixed seed, so a test can sign a payload the fixtures lack.
TEST_SEED = b"surfsense-contract-1-test-seed!!"


def signed(payload: dict, alg: str = "base64+ed25519") -> str:
    """A certificate over `payload`, signed the way Keygen signs."""
    enc = base64.b64encode(json.dumps(payload).encode()).decode()
    sig = Ed25519PrivateKey.from_private_bytes(TEST_SEED).sign(
        f"license/{enc}".encode()
    )
    outer = {"enc": enc, "sig": base64.b64encode(sig).decode(), "alg": alg}
    wrapped = base64.b64encode(json.dumps(outer).encode()).decode()
    return f"-----BEGIN LICENSE FILE-----\n{wrapped}\n-----END LICENSE FILE-----\n"


def payload(issued: str, file_expiry: str | None = None) -> dict:
    """The individual fixture's payload with the file's own timestamps changed."""
    return {
        "meta": {"issued": issued, "expiry": file_expiry, "ttl": None},
        "data": {
            "attributes": {
                "key": "TEST-INDV-2026-0001",
                "expiry": "2027-09-10T00:00:00.000Z",
                "maxUsers": None,
                "metadata": {"plan": "individual", "email": "ada@example.com"},
            }
        },
    }


@pytest.mark.parametrize(
    ("certificate", "code"),
    [
        ("hello", "not_a_license_file"),
        (
            "-----BEGIN LICENSE FILE-----\nbm90IGpzb24=\n-----END LICENSE FILE-----",
            "not_a_license_file",
        ),
        (
            signed(payload("2026-09-10T00:00:00Z"), alg="aes-256-gcm+ed25519"),
            "unsupported_algorithm",
        ),
        (signed(payload("2026-09-11T12:10:00Z")), "clock_untrusted"),
        (
            signed(payload("2026-09-10T00:00:00Z", file_expiry="2026-09-11T00:00:00Z")),
            "file_expired",
        ),
    ],
)
async def test_files_that_cannot_be_trusted_are_refused(
    client: AsyncClient, certificate: str, code: str
) -> None:
    """Each contract reason comes back as a code the UI can explain."""
    response = await put_license(client, certificate)

    assert (response.status_code, response.json()["detail"]["code"]) == (422, code)


async def test_a_few_minutes_of_clock_drift_is_not_tampering(
    client: AsyncClient,
) -> None:
    """A laptop clock four minutes fast must not lock a paying user out."""
    response = await put_license(client, signed(payload("2026-09-11T12:04:00Z")))

    assert response.status_code == 200
    assert response.json()["state"] == "active"


async def test_a_clock_set_back_is_untrusted_until_it_catches_up(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Winding the clock back cannot revive an expiring license; time only moves on."""
    clock = {"now": TODAY}
    monkeypatch.setattr(service, "now", lambda: clock["now"])
    await put_license(client, (SAMPLE / "individual.lic").read_text())

    clock["now"] = TODAY - timedelta(days=1)
    rolled_back = (await client.get("/license/status")).json()["state"]
    clock["now"] = TODAY + timedelta(minutes=1)
    caught_up = (await client.get("/license/status")).json()["state"]

    assert (rolled_back, caught_up) == ("clock_untrusted", "active")


async def test_a_fresh_install_has_no_license(client: AsyncClient) -> None:
    """Nothing imported, nothing to show; the free app does not nag."""
    assert (await client.get("/license/status")).json() == {
        "state": "none",
        "plan": None,
        "email": None,
        "expiry": None,
        "max_users": None,
    }


async def test_removing_the_license_returns_to_none(client: AsyncClient) -> None:
    """Handing a laptop on: the file leaves the machine with the user."""
    await put_license(client, (SAMPLE / "individual.lic").read_text())

    response = await client.delete("/license")

    assert response.status_code == 204
    assert (await client.get("/license/status")).json()["state"] == "none"
