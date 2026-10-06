"""Admission: who generates on the shared cache next, and who waits."""

import asyncio

import pytest

from modules.llm.admission.pool import AdmissionPool, LineFullError, Priority

pytestmark = pytest.mark.unit

INTERACTIVE = Priority.INTERACTIVE
BACKGROUND = Priority.BACKGROUND


async def _holding(pool: AdmissionPool, cost: int, priority: Priority, *, log, name):
    """Hold admission until cancelled, recording when it is granted."""
    async with pool.admitted(cost, priority):
        log.append(name)
        await asyncio.Event().wait()


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


async def test_a_request_waits_for_the_only_slot_and_knows_its_place() -> None:
    """One slot: the second request waits, told it is first in line."""
    pool = AdmissionPool(slots=1, budget=1000)
    log: list[str] = []
    positions: list[int] = []
    first = asyncio.create_task(_holding(pool, 10, INTERACTIVE, log=log, name="first"))
    await _settle()

    async def second() -> None:
        async with pool.admitted(10, INTERACTIVE, on_position=positions.append):
            log.append("second")

    waiting = asyncio.create_task(second())
    await _settle()
    assert log == ["first"] and positions == [1]

    first.cancel()
    await waiting
    assert log == ["first", "second"]


async def test_a_free_slot_is_not_enough_when_the_cache_is_full() -> None:
    """Two slots, but the shared cache holds only one of these requests."""
    pool = AdmissionPool(slots=2, budget=1000)
    log: list[str] = []
    big = asyncio.create_task(_holding(pool, 700, INTERACTIVE, log=log, name="big"))
    await _settle()
    other = asyncio.create_task(_holding(pool, 400, INTERACTIVE, log=log, name="other"))
    await _settle()
    assert log == ["big"]

    big.cancel()
    await _settle()
    assert log == ["big", "other"]
    other.cancel()


async def test_requests_that_fit_together_run_together() -> None:
    """Room for both in slots and cache: neither waits."""
    pool = AdmissionPool(slots=2, budget=1000)
    log: list[str] = []
    tasks = [
        asyncio.create_task(_holding(pool, 400, INTERACTIVE, log=log, name=name))
        for name in ("a", "b")
    ]
    await _settle()
    assert sorted(log) == ["a", "b"]
    for task in tasks:
        task.cancel()


async def test_a_request_larger_than_the_cache_runs_when_nothing_else_does() -> None:
    """Admission never refuses a request for being long; the window does that."""
    pool = AdmissionPool(slots=1, budget=1000)
    async with pool.admitted(5000, INTERACTIVE):
        pass


async def test_a_chat_goes_ahead_of_studio_that_queued_first() -> None:
    """What someone is watching goes before background work, whoever came first."""
    pool = AdmissionPool(slots=1, budget=1000)
    log: list[str] = []
    holder = asyncio.create_task(
        _holding(pool, 10, INTERACTIVE, log=log, name="holder")
    )
    await _settle()
    studio = asyncio.create_task(_holding(pool, 10, BACKGROUND, log=log, name="studio"))
    await _settle()
    chat = asyncio.create_task(_holding(pool, 10, INTERACTIVE, log=log, name="chat"))
    await _settle()

    holder.cancel()
    await _settle()
    assert log == ["holder", "chat"]
    chat.cancel()
    await _settle()
    assert log == ["holder", "chat", "studio"]
    studio.cancel()


async def test_the_head_of_the_line_is_not_overtaken_by_a_smaller_request() -> None:
    """First come, first served: a large request is never starved by small ones."""
    pool = AdmissionPool(slots=3, budget=1000)
    log: list[str] = []
    running = asyncio.create_task(_holding(pool, 600, INTERACTIVE, log=log, name="run"))
    await _settle()
    large = asyncio.create_task(_holding(pool, 600, INTERACTIVE, log=log, name="large"))
    await _settle()
    small = asyncio.create_task(_holding(pool, 100, INTERACTIVE, log=log, name="small"))
    await _settle()
    assert log == ["run"]

    running.cancel()
    await _settle()
    assert log == ["run", "large", "small"]
    large.cancel()
    small.cancel()


async def test_leaving_the_line_lets_the_next_request_in() -> None:
    """A request that leaves while waiting holds nothing up."""
    pool = AdmissionPool(slots=1, budget=1000)
    log: list[str] = []
    holder = asyncio.create_task(
        _holding(pool, 10, INTERACTIVE, log=log, name="holder")
    )
    await _settle()
    leaver = asyncio.create_task(
        _holding(pool, 10, INTERACTIVE, log=log, name="leaver")
    )
    stayer = asyncio.create_task(
        _holding(pool, 10, INTERACTIVE, log=log, name="stayer")
    )
    await _settle()

    leaver.cancel()
    await _settle()
    holder.cancel()
    await _settle()
    assert log == ["holder", "stayer"]
    stayer.cancel()


async def test_a_request_that_fails_gives_its_room_back() -> None:
    """A failed generation releases its slot and tokens like a finished one."""
    pool = AdmissionPool(slots=1, budget=1000)
    with pytest.raises(RuntimeError):
        async with pool.admitted(10, INTERACTIVE):
            raise RuntimeError("the model failed")
    async with asyncio.timeout(1):
        async with pool.admitted(10, INTERACTIVE):
            pass


async def test_the_line_has_a_length_past_which_it_refuses() -> None:
    """A guard on a runaway caller; one person never reaches it."""
    pool = AdmissionPool(slots=1, budget=1000, max_waiting=2)
    log: list[str] = []
    tasks = [
        asyncio.create_task(_holding(pool, 10, INTERACTIVE, log=log, name=str(n)))
        for n in range(3)
    ]
    await _settle()
    with pytest.raises(LineFullError):
        async with pool.admitted(10, INTERACTIVE):
            pass
    for task in tasks:
        task.cancel()


async def test_a_waiting_request_hears_its_place_move_up() -> None:
    """A waiting request is told each time its place changes."""
    pool = AdmissionPool(slots=1, budget=1000)
    log: list[str] = []
    positions: list[int] = []
    holder = asyncio.create_task(
        _holding(pool, 10, INTERACTIVE, log=log, name="holder")
    )
    ahead = None
    await _settle()
    ahead = asyncio.create_task(_holding(pool, 10, INTERACTIVE, log=log, name="ahead"))
    await _settle()

    async def behind() -> None:
        async with pool.admitted(10, INTERACTIVE, on_position=positions.append):
            log.append("behind")
            await asyncio.Event().wait()

    waiting = asyncio.create_task(behind())
    await _settle()
    holder.cancel()
    await _settle()
    assert positions == [2, 1]
    for task in (ahead, waiting):
        task.cancel()


async def test_a_request_cancelled_as_the_slot_frees_does_not_jam_the_line() -> None:
    """The slot goes to the next one waiting, not to a request already gone."""
    pool = AdmissionPool(slots=1, budget=1000)
    log: list[str] = []
    holder = asyncio.create_task(
        _holding(pool, 10, INTERACTIVE, log=log, name="holder")
    )
    await _settle()
    gone = asyncio.create_task(_holding(pool, 10, INTERACTIVE, log=log, name="gone"))
    after = asyncio.create_task(_holding(pool, 10, INTERACTIVE, log=log, name="after"))
    await _settle()

    gone.cancel()
    holder.cancel()
    await _settle()
    assert log == ["holder", "after"]
    after.cancel()
