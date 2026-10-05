"""The cap on live thread instances, as turns and deletions use it."""

import asyncio
from collections import Counter, OrderedDict
from pathlib import Path

import pytest

from modules.agent.agent_threads import live_instances

pytestmark = pytest.mark.unit

DELETED = Path("threads/1")
OTHER = Path("threads/2")


class _Opencode:
    """Records the instances it was told to dispose."""

    def __init__(self) -> None:
        self.disposed: list[Path] = []

    async def dispose_instance(self, directory: Path) -> None:
        self.disposed.append(directory)


@pytest.fixture(autouse=True)
def one_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """No instances listed, and room for one."""
    monkeypatch.setattr(live_instances, "_used", OrderedDict())
    monkeypatch.setattr(live_instances, "_turns", Counter())
    monkeypatch.setattr(live_instances, "LIVE_INSTANCES", 1)


async def test_a_thread_deleted_during_its_turn_is_not_listed_again() -> None:
    """Its instance went with it; listing it again would dispose a live thread's early."""
    opencode = _Opencode()
    live_instances.turn_began(DELETED)
    live_instances.forget_instance(DELETED)
    await live_instances.turn_ended(opencode, DELETED)  # type: ignore[arg-type]

    live_instances.turn_began(OTHER)
    await live_instances.turn_ended(opencode, OTHER)  # type: ignore[arg-type]

    assert opencode.disposed == []


class _SlowOpencode(_Opencode):
    """Answers a disposal only when told to, as opencode does once the instance is down."""

    def __init__(self) -> None:
        super().__init__()
        self.sent = asyncio.Event()
        self.answer = asyncio.Event()

    async def dispose_instance(self, directory: Path) -> None:
        self.sent.set()
        await self.answer.wait()
        self.disposed.append(directory)


async def test_a_turn_beginning_while_its_instance_is_disposed_waits_for_it() -> None:
    """Calls sent before opencode finishes disposing reach the dying instance and are lost with it."""
    opencode = _SlowOpencode()
    stale, ending = Path("threads/stale"), Path("threads/ending")
    live_instances.instance_used(stale)
    live_instances.turn_began(ending)
    ended = asyncio.create_task(live_instances.turn_ended(opencode, ending))  # type: ignore[arg-type]
    await opencode.sent.wait()

    live_instances.turn_began(stale)
    waiting = asyncio.create_task(live_instances.wait_for_disposal(stale))
    await asyncio.sleep(0.05)
    assert not waiting.done()

    opencode.answer.set()
    await ended
    await asyncio.wait_for(waiting, 1)
    assert opencode.disposed[0] == stale


async def test_an_instance_two_ending_turns_both_pick_is_disposed_once() -> None:
    """A second disposal would start the instance again only to drop it, or drop one in use."""
    opencode = _SlowOpencode()
    first, second = Path("threads/first"), Path("threads/second")
    live_instances.instance_used(Path("threads/idle-1"))
    live_instances.instance_used(Path("threads/idle-2"))
    live_instances.turn_began(first)
    live_instances.turn_began(second)
    first_ended = asyncio.create_task(live_instances.turn_ended(opencode, first))  # type: ignore[arg-type]
    await opencode.sent.wait()
    second_ended = asyncio.create_task(live_instances.turn_ended(opencode, second))  # type: ignore[arg-type]
    await asyncio.sleep(0.05)

    opencode.answer.set()
    await asyncio.gather(first_ended, second_ended)
    assert sorted(opencode.disposed) == sorted(
        [Path("threads/idle-1"), Path("threads/idle-2"), first]
    )
