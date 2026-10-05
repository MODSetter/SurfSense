"""The cap on live thread instances, as turns and deletions use it."""

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
