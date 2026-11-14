"""The app's own renewal check: at startup, then daily, only for a license whose renewal is due."""

import asyncio
import logging
import threading
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from api.main import create_app, lifespan
from modules.license.renewal import renewal_schedule
from modules.license.renewal.automatic_renewal import renew_if_due
from modules.license.renewal.renewal_schedule import renewing_daily
from shared.db import create_session_factory
from tests.license_samples import (
    BUSINESS_KEY,
    business_license,
    import_license,
    trust_sample_licenses,
)
from tests.license_server_stand_in import StandInLicenseServer

pytestmark = pytest.mark.integration

# Under 30 days after the samples' day, 2026-09-11: the year paid for has ended.
ENDING = "2026-10-01T00:00:00.000Z"
# Checked out on the samples' day, as the server does at every refresh.
ISSUED = "2026-09-11T00:00:00.000Z"
RENEWED = business_license(issued=ISSUED, expiry="2027-10-01T00:00:00.000Z")
TRIAL = {"plan": "trial", "firm": None, "max_users": None}


@pytest.fixture(autouse=True)
def sample_licenses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files signed with the samples' key verify, on a day the samples are valid."""
    trust_sample_licenses(monkeypatch)


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    """The API's own sessions, as its lifespan hands them to the schedule."""
    return create_session_factory(engine)


async def add(client: AsyncClient, certificate: str) -> None:
    """Import a file, as Settings does."""
    added = await client.put("/license", json={"certificate": certificate})
    assert added.status_code == 200, added.text


async def stored_expiry(client: AsyncClient) -> str:
    """When the stored license ends, as Settings shows it."""
    return (await client.get("/license/status")).json()["expiry"]


@pytest.mark.parametrize(
    "certificate",
    [
        business_license(expiry=ENDING),
        # Lapsed ten days ago: a renewal paid late still arrives.
        business_license(expiry="2026-09-01T00:00:00.000Z"),
    ],
)
async def test_a_business_license_near_or_just_past_its_end_is_renewed_on_its_own(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    certificate: str,
) -> None:
    """The renewal reaches the app before the user needs it, with only the key sent."""
    await add(client, certificate)
    license_server.files[BUSINESS_KEY] = RENEWED

    await renew_if_due(sessions)

    assert [asked.body for asked in license_server.asked] == [{"key": BUSINESS_KEY}]
    assert await stored_expiry(client) == "2027-10-01T00:00:00Z"


@pytest.mark.parametrize(
    "certificate",
    [
        # More than 30 days from its end: the period paid for has not ended.
        business_license(expiry="2026-10-12T00:00:00.000Z"),
        # Lapsed more than 30 days ago: only support could still extend it.
        business_license(expiry="2026-08-11T00:00:00.000Z"),
        # The Business trial is extended only by hand, so Settings' button asks.
        business_license(**TRIAL, expiry=ENDING),
        # Renewed by a new file, being neither Business nor carrying jobs.
        business_license(
            plan="individual", firm=None, jobs=None, max_users=None, expiry=ENDING
        ),
    ],
)
async def test_nothing_is_asked_for_a_license_not_due(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    certificate: str,
) -> None:
    """The check sends nothing unless a renewal could be waiting."""
    await add(client, certificate)
    license_server.files[BUSINESS_KEY] = RENEWED

    await renew_if_due(sessions)

    assert license_server.asked == []


async def test_nothing_is_asked_without_a_license(
    sessions: sessionmaker[Session], license_server: StandInLicenseServer
) -> None:
    """The free app never contacts the license server."""
    await renew_if_due(sessions)

    assert license_server.asked == []


async def test_a_sample_trial_near_its_end_is_not_asked_about(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
) -> None:
    """The scrapers' trial carries no jobs and is never renewed."""
    await import_license(client, "trial.lic")

    await renew_if_due(sessions)

    assert license_server.asked == []


async def test_nothing_is_sent_while_the_license_server_is_off(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    compiled_license_server: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An air-gapped install, or one that never allowed it, is refused without a request,
    and the refusal is logged rather than asked about."""
    caplog.set_level(logging.INFO, logger="modules.license.renewal.automatic_renewal")
    await add(client, business_license(expiry=ENDING))

    await renew_if_due(sessions)

    assert "refresh_egress_blocked" in caplog.text
    network = {row["host"]: row for row in (await client.get("/egress")).json()}
    assert network["api.surfsense.com"]["last_call_at"] is None
    assert await stored_expiry(client) == "2026-10-01T00:00:00Z"


async def asked_at_least(server: StandInLicenseServer, count: int) -> None:
    """Wait up to five seconds for the schedule's requests to arrive."""
    for _ in range(500):
        if len(server.asked) >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"asked {len(server.asked)} times, not {count}")


async def test_a_license_removed_while_its_renewal_is_fetched_stays_removed(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
) -> None:
    """Handing a laptop on mid-check: the renewal never brings the license back."""
    await add(client, business_license(expiry=ENDING))
    license_server.files[BUSINESS_KEY] = RENEWED
    license_server.delay_seconds = 0.5
    checking = asyncio.create_task(renew_if_due(sessions))
    await asked_at_least(license_server, 1)

    assert (await client.delete("/license")).status_code == 204
    await checking

    assert (await client.get("/license/status")).json()["state"] == "none"


async def test_the_api_checks_once_it_starts(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The schedule rides the API's lifespan, beside nothing that slows /health."""
    monkeypatch.setattr("api.main._warm_catalog", lambda _factory: None)
    await add(client, business_license(expiry=ENDING))
    license_server.files[BUSINESS_KEY] = RENEWED

    async with lifespan(create_app()):
        for _ in range(500):
            if await stored_expiry(client) == "2027-10-01T00:00:00Z":
                break
            await asyncio.sleep(0.01)

    assert await stored_expiry(client) == "2027-10-01T00:00:00Z"
    assert [asked.body for asked in license_server.asked] == [{"key": BUSINESS_KEY}]


async def test_it_asks_at_startup_and_not_again_the_same_day(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
) -> None:
    """A failed check waits a day: never a tight loop against a server that is down."""
    await add(client, business_license(expiry=ENDING))
    license_server.refusal = (503, "Could not check that license right now.")

    async with renewing_daily(sessions):
        await asked_at_least(license_server, 1)
        await asyncio.sleep(0.3)

    assert len(license_server.asked) == 1


async def test_it_asks_again_each_day_until_the_api_stops(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Days shortened to a tenth of a second; stopping the API stops the checks."""
    monkeypatch.setattr(renewal_schedule, "CHECK_EVERY", timedelta(seconds=0.1))
    await add(client, business_license(expiry=ENDING))
    license_server.refusal = (503, "Could not check that license right now.")

    async with renewing_daily(sessions):
        await asked_at_least(license_server, 2)
    await asyncio.sleep(0.1)
    stopped_at = len(license_server.asked)
    await asyncio.sleep(0.3)

    assert len(license_server.asked) == stopped_at


async def test_a_check_under_way_finishes_its_session_work_before_the_api_stops(
    sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stopping waits for the check's worker thread instead of cancelling under it."""
    in_thread = threading.Event()
    finished: list[str] = []

    def session_work() -> None:
        in_thread.set()
        threading.Event().wait(0.3)
        finished.append("session work")

    async def check(_sessions: sessionmaker[Session]) -> None:
        await run_in_threadpool(session_work)
        finished.append("check")

    monkeypatch.setattr(renewal_schedule, "renew_if_due", check)

    async with renewing_daily(sessions):
        await asyncio.to_thread(in_thread.wait, 5)

    assert finished == ["session work", "check"]


async def test_the_api_stops_even_when_a_cancelled_check_raises_something_else(
    sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A check cancelled mid-transaction can raise in place of the cancel.

    SQLAlchemy raises IllegalStateChangeError when the session closes while a worker
    thread still uses it. Caught as any failure, it once sent the schedule back to
    sleep out the day, and the API's shutdown waited on it.
    """
    started = asyncio.Event()

    async def check(_sessions: sessionmaker[Session]) -> None:
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            raise RuntimeError("closed while a worker thread used it") from None

    monkeypatch.setattr(renewal_schedule, "renew_if_due", check)
    monkeypatch.setattr(renewal_schedule, "STOP_WITHIN", timedelta(seconds=0.1))

    async def stop_during_the_check() -> None:
        async with renewing_daily(sessions):
            await started.wait()

    await asyncio.wait_for(stop_during_the_check(), timeout=3)
