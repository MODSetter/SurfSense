"""Install jobs: one runs at a time, the rest wait, and each can be cancelled."""

import asyncio
from collections.abc import AsyncIterator, Callable

import pytest

from modules.llm.catalog.local.install_jobs.jobs import InstallJobs
from modules.llm.model_type import ModelType

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _steps(*events: dict, gate: asyncio.Event | None = None) -> Callable:
    async def run() -> AsyncIterator[dict]:
        for event in events:
            yield event
        if gate is not None:
            await gate.wait()
        yield {"type": "complete", "message": "Model is ready", "selection": None}

    return run


def _start(jobs: InstallJobs, run: Callable, catalog_id: str = "id"):
    return jobs.start(
        catalog_id=catalog_id,
        label="SDXL Turbo Q4_0",
        model_types=(ModelType.IMAGE_GEN,),
        select=False,
        model_type=None,
        steps=run,
    )


async def _settle(jobs: InstallJobs) -> None:
    for _ in range(50):
        if not jobs.running():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("jobs did not settle")


async def test_a_job_ends_on_its_last_step() -> None:
    """The job carries its steps' last event."""
    jobs = InstallJobs(asyncio.Lock())

    job = _start(jobs, _steps({"type": "downloading", "completed": 1, "total": 2}))
    await _settle(jobs)

    assert jobs.get(job.id).event["type"] == "complete"


async def test_a_second_job_waits_for_the_first_rather_than_failing() -> None:
    """A model chosen while another downloads still comes."""
    jobs = InstallJobs(asyncio.Lock())
    gate = asyncio.Event()
    first = _start(jobs, _steps(gate=gate), "first")
    await asyncio.sleep(0.01)

    second = _start(jobs, _steps(), "second")
    await asyncio.sleep(0.01)

    assert jobs.get(second.id).event["type"] == "queued"
    gate.set()
    await _settle(jobs)
    assert jobs.get(first.id).event["type"] == "complete"
    assert jobs.get(second.id).event["type"] == "complete"


async def test_cancelling_a_queued_job_ends_it_without_running_it() -> None:
    """Cancel reaches a job still waiting for the lock."""
    jobs = InstallJobs(asyncio.Lock())
    gate = asyncio.Event()
    _start(jobs, _steps(gate=gate), "first")
    await asyncio.sleep(0.01)
    ran = False

    async def never() -> AsyncIterator[dict]:
        nonlocal ran
        ran = True
        yield {"type": "complete", "message": "", "selection": None}

    second = _start(jobs, never, "second")
    await asyncio.sleep(0.01)

    assert jobs.cancel(second.id)
    gate.set()
    await _settle(jobs)
    assert jobs.get(second.id).event["type"] == "cancelled"
    assert not ran


async def test_cancelling_a_running_job_frees_the_lock_for_the_next() -> None:
    """The next job runs once a cancelled one lets go."""
    lock = asyncio.Lock()
    jobs = InstallJobs(lock)
    first = _start(jobs, _steps(gate=asyncio.Event()), "first")
    second = _start(jobs, _steps(), "second")
    await asyncio.sleep(0.01)

    jobs.cancel(first.id)
    await _settle(jobs)

    assert jobs.get(first.id).event["type"] == "cancelled"
    assert jobs.get(second.id).event["type"] == "complete"
    assert not lock.locked()


async def test_a_step_that_raises_ends_the_job_with_the_retry_message() -> None:
    """An unexpected failure reads as the stream's generic error."""
    jobs = InstallJobs(asyncio.Lock())

    async def broken() -> AsyncIterator[dict]:
        yield {"type": "starting", "message": "Checking the model"}
        raise OSError("disk went away")

    job = _start(jobs, broken)
    await _settle(jobs)

    assert jobs.get(job.id).event == {
        "type": "error",
        "message": "The model could not be installed. Retry the download.",
    }


async def test_a_finished_job_is_listed_only_until_the_keep_window_passes() -> None:
    """Long enough for a screen that reconnects to see how it ended."""
    now = [0.0]
    jobs = InstallJobs(asyncio.Lock(), keep_finished_seconds=60, clock=lambda: now[0])
    job = _start(jobs, _steps())
    await _settle(jobs)

    assert [j.id for j in jobs.list()] == [job.id]
    now[0] = 61.0
    assert jobs.list() == []
    assert jobs.get(job.id) is None


async def test_a_subscriber_is_woken_by_a_change() -> None:
    """The feed learns of a new job without polling."""
    jobs = InstallJobs(asyncio.Lock())
    changed = jobs.subscribe()

    _start(jobs, _steps())

    await asyncio.wait_for(changed.wait(), 1)
    jobs.unsubscribe(changed)


async def test_cancelling_an_unknown_or_finished_job_says_so() -> None:
    """Only a job still going can be cancelled."""
    jobs = InstallJobs(asyncio.Lock())
    job = _start(jobs, _steps())
    await _settle(jobs)

    assert not jobs.cancel("never-started")
    assert not jobs.cancel(job.id)
