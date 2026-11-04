"""The app's own job-pack check: at startup, then daily, for an active license with jobs, and
once more when a run that held a check back ends, never asking to reach the license server,
and stopping within its bound whatever it was doing."""

import asyncio
import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from api.main import create_app, lifespan
from modules.artifacts.models import Artifact
from modules.jobs.packs.delivery import delivery_schedule
from modules.jobs.packs.delivery.automatic_delivery import (
    deliver_held_back,
    deliver_if_due,
)
from modules.jobs.packs.delivery.delivery_schedule import delivering_daily
from modules.jobs.packs.delivery.held_back import HELD_BACK
from modules.jobs.packs.installed import installed_packs, packs_dir
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from tests.integration.artifacts.job_runs.started_runs import start_run
from tests.job_pack_samples import ENTITLEMENT, PACK_ID, zipped_questionnaire_pack
from tests.license_samples import business_license, trust_sample_licenses
from tests.license_server_stand_in import StandInLicenseServer
from worker.jobs import begin_job

pytestmark = pytest.mark.integration

LICENSE = business_license(jobs=ENTITLEMENT)
# A second job of the license, which a newer version of the test pack adds.
OTHER = "JOB_OTHER"
ANOTHER_JOB_RAN = (
    "A run of another job in the same pack was under way, so this job waits until the "
    "run ends."
)
THIS_JOB_RAN = (
    "A run of this job was under way, so any newer version waits until the run ends."
)
UNAVAILABLE = (503, {"code": "job_packs_unavailable", "message": "Try again later."})
# How often a code a run held back is looked at, in these tests.
FOLLOW_UP = timedelta(seconds=0.1)
DELIVERY_LOG = "modules.jobs.packs.delivery"
DEFERRED = f"job pack for {ENTITLEMENT}: deferred"
INSTALLED = f"job pack for {ENTITLEMENT}: installed"
BLOCKED = "job packs not checked: egress_blocked for api.surfsense.com"
NO_LICENSE = "job packs not checked: license_none"


@pytest.fixture(autouse=True)
def sample_licenses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files signed with the samples' key verify, on a day the samples are valid."""
    trust_sample_licenses(monkeypatch)


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    """The API's own sessions, as its lifespan hands them to the schedule."""
    return create_session_factory(engine)


class WatchedSessions:
    """The API's sessions, noting for each the thread it was opened on and the one that
    closed it."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = create_session_factory(engine)
        self.closes: list[tuple[int, int]] = []
        self.closed = threading.Event()

    def __call__(self) -> Session:
        session = self._sessions()
        opened_on = threading.get_ident()
        close = session.close

        def closing() -> None:
            self.closes.append((opened_on, threading.get_ident()))
            close()
            self.closed.set()

        session.close = closing  # type: ignore[method-assign]
        return session


@contextmanager
def write_lock_held(engine: Engine, seconds: float) -> Iterator[None]:
    """Another connection holds SQLite's write lock for `seconds`, as Studio does while it
    embeds a long document; the block ends once it is let go."""
    taken = threading.Event()

    def hold() -> None:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")  # BEGIN IMMEDIATE takes the lock
            taken.set()
            time.sleep(seconds)
            connection.rollback()

    holder = threading.Thread(target=hold)
    holder.start()
    assert taken.wait(5)
    try:
        yield
    finally:
        holder.join()


async def add_license(client: AsyncClient, certificate: str = LICENSE) -> None:
    """Import a license file, as Settings does."""
    added = await client.put("/license", json={"certificate": certificate})
    assert added.status_code == 200, added.text


def offer(server: StandInLicenseServer, tmp_path: Path, version: str = "1.0.0") -> None:
    """Publish the test pack as the newest for the license's job."""
    server.offer(
        ENTITLEMENT,
        zipped_questionnaire_pack(tmp_path / f"published-{version}", version=version),
    )


async def asked_at_least(server: StandInLicenseServer, count: int) -> None:
    """Wait up to five seconds for the schedule's requests to arrive."""
    for _ in range(500):
        if len(server.pack_asked) >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"asked {len(server.pack_asked)} times, not {count}")


async def until(condition: Callable[[], bool], what: str) -> None:
    """Wait up to five seconds for `condition`."""
    for _ in range(500):
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"not {what} within five seconds")


async def a_few_looks() -> None:
    """Long enough for the schedule to look at what a run holds back five times."""
    await asyncio.sleep(5 * FOLLOW_UP.total_seconds())


async def end_run(client: AsyncClient, artifact_id: int) -> None:
    """Stop a run as Studio's Cancel does, so it is no longer pending or processing."""
    cancelled = await client.post(f"/artifacts/{artifact_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text


def versions() -> list[str]:
    """The installed versions of the test pack. Each read checks every file again, so the
    tests wait on the check's own log instead: on Windows, a file open meanwhile keeps an
    install from moving the old version aside, which it leaves for the next one."""
    return [p.manifest.version for p in installed_packs()]


def logged(caplog: pytest.LogCaptureFixture, line: str, times: int = 1) -> bool:
    """Whether `line` is in the log at least `times` times."""
    return caplog.text.count(line) >= times


def warned(caplog: pytest.LogCaptureFixture) -> list[str]:
    """What delivery logged as a warning or worse."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(DELIVERY_LOG) and record.levelno >= logging.WARNING
    ]


async def test_the_api_downloads_the_license_s_jobs_once_it_starts(
    client: AsyncClient,
    license_server: StandInLicenseServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The schedule rides the API's lifespan, and asks nothing of the renewal's route."""
    monkeypatch.setattr("api.main._warm_catalog", lambda _factory: None)
    await add_license(client)
    offer(license_server, tmp_path)

    async with lifespan(create_app()):
        for _ in range(500):
            if (await client.get("/job-packs")).json():
                break
            await asyncio.sleep(0.01)

    assert [p["id"] for p in (await client.get("/job-packs")).json()] == [PACK_ID]
    assert len(license_server.pack_asked) == 1
    assert license_server.asked == []


async def test_the_api_stops_promptly_while_a_delivery_is_under_way(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
) -> None:
    """A download the server is slow to answer is cancelled once stopping has waited its
    bound."""
    await add_license(client)
    offer(license_server, tmp_path)
    license_server.pack_delay_seconds = 30

    async with delivering_daily(sessions):
        await asked_at_least(license_server, 1)
        stopping = time.monotonic()

    assert (
        time.monotonic() - stopping < delivery_schedule.STOP_WITHIN.total_seconds() + 1
    )
    assert installed_packs() == []


async def test_session_work_under_way_finishes_before_the_api_stops(
    engine: Engine,
) -> None:
    """Stopping waits for the check's worker thread, which commits and closes its own
    session, instead of cancelling under it."""
    watched = WatchedSessions(engine)

    with write_lock_held(engine, 0.3):
        async with delivering_daily(watched):
            await asyncio.sleep(0.05)
        finished_on_time = watched.closed.is_set()

    assert finished_on_time
    loop = threading.get_ident()
    assert watched.closes
    assert all(opened == closed != loop for opened, closed in watched.closes)


async def test_a_cancel_mid_transaction_closes_no_session_under_a_thread(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The cancel lands while the check's transaction waits for the write lock: the API stops
    at once, and the thread, which owns its session, finishes and closes it afterwards."""
    monkeypatch.setattr(delivery_schedule, "STOP_WITHIN", timedelta(seconds=0.1))
    watched = WatchedSessions(engine)

    with write_lock_held(engine, 1.0):
        stopping = time.monotonic()
        async with delivering_daily(watched):
            await asyncio.sleep(0.05)
        stopped_in = time.monotonic() - stopping
        assert not watched.closed.is_set()
    assert watched.closed.wait(5)

    assert stopped_in < 0.8
    loop = threading.get_ident()
    assert watched.closes
    assert all(opened == closed != loop for opened, closed in watched.closes)
    assert "IllegalStateChangeError" not in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_the_api_stops_even_when_a_cancelled_delivery_raises_something_else(
    sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A check cancelled mid-transaction once raised SQLAlchemy's IllegalStateChangeError in
    place of the cancel; caught as any failure, it sent the renewal's loop back to sleep out
    the day. This loop ends on its flag."""
    started = asyncio.Event()

    async def check(_sessions: sessionmaker[Session]) -> None:
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            raise RuntimeError("closed while a worker thread used it") from None

    monkeypatch.setattr(delivery_schedule, "deliver_if_due", check)
    monkeypatch.setattr(delivery_schedule, "STOP_WITHIN", timedelta(seconds=0.1))

    async def stop_during_the_check() -> None:
        async with delivering_daily(sessions):
            await started.wait()

    await asyncio.wait_for(stop_during_the_check(), timeout=3)


async def test_it_checks_at_startup_and_not_again_the_same_day(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
) -> None:
    """A failed check waits a day: never a tight loop against a server that is down."""
    await add_license(client)
    license_server.pack_refusal = UNAVAILABLE

    async with delivering_daily(sessions):
        await asked_at_least(license_server, 1)
        await asyncio.sleep(0.3)

    assert len(license_server.pack_asked) == 1


async def test_it_checks_again_each_day_until_the_api_stops(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Days shortened to a tenth of a second; stopping the API stops the checks."""
    monkeypatch.setattr(delivery_schedule, "CHECK_EVERY", timedelta(seconds=0.1))
    await add_license(client)
    license_server.pack_refusal = UNAVAILABLE

    async with delivering_daily(sessions):
        await asked_at_least(license_server, 2)
    await asyncio.sleep(0.1)
    stopped_at = len(license_server.pack_asked)
    await asyncio.sleep(0.3)

    assert len(license_server.pack_asked) == stopped_at


@pytest.mark.parametrize(
    "certificate",
    [
        None,
        business_license(plan="individual", firm=None, jobs=None, max_users=None),
        business_license(jobs=ENTITLEMENT, expiry="2026-09-01T00:00:00.000Z"),
    ],
    ids=["no license", "no jobs", "expired"],
)
async def test_nothing_is_asked_without_an_active_license_with_jobs(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    certificate: str | None,
) -> None:
    """The free app, and a license with no job to run, never contact the server for one."""
    if certificate is not None:
        await add_license(client, certificate)

    await deliver_if_due(sessions)

    assert license_server.pack_asked == []


async def test_the_business_trial_gets_its_pack(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
) -> None:
    """The plan decides nothing: a trial with the job's code is checked as Business is."""
    await add_license(
        client,
        business_license(plan="trial", firm=None, max_users=None, jobs=ENTITLEMENT),
    )
    offer(license_server, tmp_path)

    await deliver_if_due(sessions)

    assert [p.manifest.id for p in installed_packs()] == [PACK_ID]


async def test_a_refused_host_is_logged_and_never_asked(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    compiled_license_server: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Background work never asks: an install that never allowed the server is told so in
    the log, and nothing is sent."""
    caplog.set_level(
        logging.INFO, logger="modules.jobs.packs.delivery.automatic_delivery"
    )
    await add_license(client)

    await deliver_if_due(sessions)

    assert "job packs not checked: egress_blocked for api.surfsense.com" in caplog.text
    network = {row["host"]: row for row in (await client.get("/egress")).json()}
    assert network["api.surfsense.com"]["last_call_at"] is None


async def test_a_pack_in_use_is_not_asked_for_while_its_run_lasts(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """While a run of the pack is pending, the check sends nothing and logs why."""
    caplog.set_level(
        logging.INFO, logger="modules.jobs.packs.delivery.automatic_delivery"
    )
    await add_license(client)
    offer(license_server, tmp_path)
    await deliver_if_due(sessions)
    await start_run(client, session, workspace.id)
    offer(license_server, tmp_path, version="1.1.0")

    await deliver_if_due(sessions)

    assert len(license_server.pack_asked) == 1
    assert f"job pack for {ENTITLEMENT}: deferred" in caplog.text
    assert [p.manifest.version for p in installed_packs()] == ["1.0.0"]


async def test_a_pack_holding_a_job_the_license_file_lacks_is_no_warning(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The license changed on the server's side, which a renewal brings to this computer:
    the check logs it, at info, and installs nothing."""
    caplog.set_level(logging.INFO, logger=DELIVERY_LOG)
    await add_license(client)
    license_server.license_jobs = frozenset({ENTITLEMENT, "JOB_UNSOLD"})
    license_server.offer(
        ENTITLEMENT,
        zipped_questionnaire_pack(tmp_path / "two-jobs", other_jobs=("JOB_UNSOLD",)),
    )

    await deliver_if_due(sessions)

    assert (
        f"job pack for {ENTITLEMENT}: license_outdated (PACK_NOT_INCLUDED)"
        in caplog.text
    )
    assert warned(caplog) == []
    assert installed_packs() == []


async def test_a_code_no_request_could_carry_is_logged_and_never_asked_for(
    client: AsyncClient,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A hand-issued license's code that contract 6's request does not allow is an unknown
    job, logged at info: never sent, so never the 422 of the app's own bug."""
    caplog.set_level(logging.INFO, logger=DELIVERY_LOG)
    await add_license(client, business_license(jobs="job_lower"))

    await deliver_if_due(sessions)

    assert "job pack for job_lower: unknown_job" in caplog.text
    assert license_server.pack_asked == []
    assert warned(caplog) == []


async def test_a_check_a_run_held_back_is_made_again_once_the_run_ends(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The startup check meets a run of the installed pack, as one the last session left
    processing: it sends nothing, looks again every FOLLOW_UP_EVERY with nothing sent while
    the run lasts, and once the run ends asks again and installs the newer version, without
    waiting a day for the next check."""
    caplog.set_level(logging.INFO, logger=DELIVERY_LOG)
    monkeypatch.setattr(delivery_schedule, "FOLLOW_UP_EVERY", FOLLOW_UP)
    await add_license(client)
    offer(license_server, tmp_path)
    await deliver_if_due(sessions)
    run = await start_run(client, session, workspace.id)
    offer(license_server, tmp_path, version="1.1.0")

    async with delivering_daily(sessions):
        await until(lambda: logged(caplog, DEFERRED), "deferred")
        await a_few_looks()
        asked_while_it_ran = len(license_server.pack_asked)
        await end_run(client, run)
        await until(lambda: logged(caplog, INSTALLED, 2), "installed")

    assert asked_while_it_ran == 1
    assert len(license_server.pack_asked) == 2
    assert license_server.pack_asked[-1].body["installed_version"] == "1.0.0"
    assert versions() == ["1.1.0"]
    assert warned(caplog) == []


async def test_a_download_a_run_held_back_is_made_again_once_the_run_ends(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The user's Download meets a run of the installed pack: the answer says a run held it
    back and nothing is sent, and the schedule, asleep until the next day's check, asks
    again once the run ends."""
    caplog.set_level(logging.INFO, logger=DELIVERY_LOG)
    monkeypatch.setattr(delivery_schedule, "FOLLOW_UP_EVERY", FOLLOW_UP)
    await add_license(client)
    offer(license_server, tmp_path)

    async with delivering_daily(sessions):
        await until(lambda: logged(caplog, INSTALLED), "installed at startup")
        run = await start_run(client, session, workspace.id)
        offer(license_server, tmp_path, version="1.1.0")
        downloaded = await client.post("/job-packs/download")
        await a_few_looks()
        asked_while_it_ran = len(license_server.pack_asked)
        await end_run(client, run)
        await until(lambda: logged(caplog, INSTALLED, 2), "installed")

    assert [o["outcome"] for o in downloaded.json()["outcomes"]] == ["deferred"]
    assert asked_while_it_ran == 1
    assert len(license_server.pack_asked) == 2
    assert versions() == ["1.1.0"]


async def test_a_job_no_installed_pack_has_waits_for_a_run_of_another_job_of_its_pack(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
) -> None:
    """The license holds two jobs, and the installed pack only the first, a run of which is
    under way when the user downloads the second: the newer version that adds it waits for
    that run. The answer says so, with no version, as none of the second job is installed,
    and the check made once the run ends installs it."""
    await add_license(client, business_license(jobs=f"{ENTITLEMENT},{OTHER}"))
    offer(license_server, tmp_path)
    first = await client.post(
        "/job-packs/download", json={"entitlements": [ENTITLEMENT]}
    )
    assert [o["outcome"] for o in first.json()["outcomes"]] == ["installed"]
    run = await start_run(client, session, workspace.id)
    # The Studio worker takes the run up.
    assert begin_job(session, session.get(Artifact, run).document)
    adds_it = zipped_questionnaire_pack(
        tmp_path / "published-1.1.0", version="1.1.0", other_jobs=(OTHER,)
    )
    license_server.offer(ENTITLEMENT, adds_it)
    license_server.offer(OTHER, adds_it)

    held = await client.post("/job-packs/download", json={"entitlements": [OTHER]})

    assert held.status_code == 200, held.text
    assert held.json()["outcomes"] == [
        {
            "entitlement": OTHER,
            "outcome": "deferred",
            "message": ANOTHER_JOB_RAN,
            "version": None,
            "detail": None,
        }
    ]
    assert versions() == ["1.0.0"]
    assert HELD_BACK.held() == {OTHER: PACK_ID}

    await end_run(client, run)
    await deliver_held_back(sessions)

    assert versions() == ["1.1.0"]
    assert license_server.pack_asked[-1].body["entitlement"] == OTHER
    assert HELD_BACK.held() == {}


async def test_a_run_of_the_job_holds_back_its_pack_failing_its_checks_by_its_own_name(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
) -> None:
    """A listed file of the installed pack changes on disk while a run of its one job is
    under way, so no installed pack has the job and the newer version is asked for: it waits
    for that run, and the answer says a run of this job held it, naming the version the run
    reads, never another job's run. The check made once the run ends installs it."""
    await add_license(client)
    offer(license_server, tmp_path)
    first = await client.post("/job-packs/download")
    assert [o["outcome"] for o in first.json()["outcomes"]] == ["installed"]
    run = await start_run(client, session, workspace.id)
    assert begin_job(session, session.get(Artifact, run).document)
    changed = packs_dir() / PACK_ID / "1.0.0" / "LICENSE.md"
    changed.write_bytes(changed.read_bytes() + b"\n")
    assert versions() == []
    offer(license_server, tmp_path, version="1.1.0")

    held = await client.post(
        "/job-packs/download", json={"entitlements": [ENTITLEMENT]}
    )

    assert held.status_code == 200, held.text
    assert held.json()["outcomes"] == [
        {
            "entitlement": ENTITLEMENT,
            "outcome": "deferred",
            "message": THIS_JOB_RAN,
            "version": "1.0.0",
            "detail": None,
        }
    ]
    assert license_server.pack_asked[-1].body.get("installed_version") is None
    assert (await client.get("/job-packs")).json() == []
    assert HELD_BACK.held() == {ENTITLEMENT: PACK_ID}

    await end_run(client, run)
    await deliver_held_back(sessions)

    assert versions() == ["1.1.0"]
    assert HELD_BACK.held() == {}


async def test_a_check_made_again_and_held_back_again_waits_for_that_run_too(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Another run starts while the check made again downloads the newer version: its
    install waits for that run, and the check is made once more when that run ends."""
    caplog.set_level(logging.INFO, logger=DELIVERY_LOG)
    monkeypatch.setattr(delivery_schedule, "FOLLOW_UP_EVERY", FOLLOW_UP)
    await add_license(client)
    offer(license_server, tmp_path)
    await deliver_if_due(sessions)
    first = await start_run(client, session, workspace.id)
    offer(license_server, tmp_path, version="1.1.0")
    loop = asyncio.get_running_loop()
    second: list[int] = []

    def another_run_starts() -> None:
        license_server.before_pack = None
        started = asyncio.run_coroutine_threadsafe(
            start_run(client, session, workspace.id), loop
        )
        second.append(started.result(timeout=30))

    async with delivering_daily(sessions):
        await until(lambda: logged(caplog, DEFERRED), "deferred")
        license_server.before_pack = another_run_starts
        await end_run(client, first)
        await until(lambda: logged(caplog, DEFERRED, 2), "deferred again")
        await a_few_looks()
        held_again = (len(second), versions(), len(license_server.pack_asked))
        await end_run(client, second[0])
        await until(lambda: logged(caplog, INSTALLED, 2), "installed")

    assert held_again == (1, ["1.0.0"], 2)
    assert len(license_server.pack_asked) == 3
    assert versions() == ["1.1.0"]


async def test_a_check_made_again_never_asks_to_reach_the_license_server(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    sessions: sessionmaker[Session],
    compiled_license_server: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The license server's host is off, and the check made once the run ends is background
    work: it is logged once and ends there, with nothing sent and no question asked."""
    caplog.set_level(logging.INFO, logger=DELIVERY_LOG)
    monkeypatch.setattr(delivery_schedule, "FOLLOW_UP_EVERY", FOLLOW_UP)
    await add_license(client)
    imported = await client.post(
        "/job-packs/import",
        files={
            "file": (
                "test-jobs-1.0.0.zip",
                zipped_questionnaire_pack(tmp_path / "pack"),
                "application/zip",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    run = await start_run(client, session, workspace.id)

    async with delivering_daily(sessions):
        await until(lambda: logged(caplog, DEFERRED), "deferred")
        await end_run(client, run)
        await until(lambda: logged(caplog, BLOCKED), "logged")
        await a_few_looks()

    assert caplog.text.count(BLOCKED) == 1
    network = {row["host"]: row for row in (await client.get("/egress")).json()}
    assert network["api.surfsense.com"]["enabled"] is False
    assert network["api.surfsense.com"]["last_call_at"] is None


async def test_a_license_removed_meanwhile_ends_the_check_quietly(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The license goes while the run lasts: once the run ends, the check made again finds
    no license, says so at info, sends nothing and is not made again."""
    caplog.set_level(logging.INFO, logger=DELIVERY_LOG)
    monkeypatch.setattr(delivery_schedule, "FOLLOW_UP_EVERY", FOLLOW_UP)
    await add_license(client)
    offer(license_server, tmp_path)
    await deliver_if_due(sessions)
    run = await start_run(client, session, workspace.id)
    offer(license_server, tmp_path, version="1.1.0")

    async with delivering_daily(sessions):
        await until(lambda: logged(caplog, DEFERRED), "deferred")
        removed = await client.delete("/license")
        assert removed.status_code == 204, removed.text
        await end_run(client, run)
        await until(lambda: logged(caplog, NO_LICENSE), "logged")
        await a_few_looks()

    assert caplog.text.count(NO_LICENSE) == 1
    assert len(license_server.pack_asked) == 1
    assert warned(caplog) == []


@pytest.mark.parametrize("asking", [False, True], ids=["run under way", "asking again"])
async def test_the_api_stops_promptly_while_a_check_is_held_back(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    sessions: sessionmaker[Session],
    license_server: StandInLicenseServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    asking: bool,
) -> None:
    """Stopping waits for nothing a run holds back: not the next look a minute away, and
    not a slow answer to the check made again, which is cancelled within the bound."""
    caplog.set_level(logging.INFO, logger=DELIVERY_LOG)
    await add_license(client)
    offer(license_server, tmp_path)
    await deliver_if_due(sessions)
    run = await start_run(client, session, workspace.id)
    offer(license_server, tmp_path, version="1.1.0")
    if asking:
        monkeypatch.setattr(delivery_schedule, "FOLLOW_UP_EVERY", FOLLOW_UP)
        license_server.pack_delay_seconds = 30

    async with delivering_daily(sessions):
        await until(lambda: logged(caplog, DEFERRED), "deferred")
        if asking:
            await end_run(client, run)
            await asked_at_least(license_server, 2)
        stopping = time.monotonic()

    bound = delivery_schedule.STOP_WITHIN.total_seconds() + (1 if asking else 0)
    assert time.monotonic() - stopping < bound
    assert versions() == ["1.0.0"]
