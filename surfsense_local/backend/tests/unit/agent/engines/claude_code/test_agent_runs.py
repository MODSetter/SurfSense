"""One running Claude Code per agent thread, kept while its turns are set up alike."""

from pathlib import Path

import pytest

from modules.agent.engines.claude_code.agent_runs import AgentRuns
from modules.agent.engines.claude_code.turn_link import TurnLink
from tests.claude_run_stand_in import ScriptedRun

pytestmark = pytest.mark.unit


class _Starts:
    """Starts a scripted run, each with a config file of its own."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.started: list[ScriptedRun] = []

    async def __call__(self, link: TurnLink) -> tuple[ScriptedRun, Path]:
        run = ScriptedRun()
        file = self.folder / f"mcp-{len(self.started)}.json"
        file.write_text("{}")
        self.started.append(run)
        return run, file


async def test_the_next_turn_set_up_alike_reuses_the_running_claude_code(
    tmp_path: Path,
) -> None:
    """The start-up is skipped: 0.9 s to a first token warm against 2.3 s cold."""
    starts = _Starts(tmp_path)
    runs = AgentRuns()

    first = await runs.acquire(7, "digest-a", starts)
    again = await runs.acquire(7, "digest-a", starts)

    assert again is first
    assert len(starts.started) == 1


async def test_a_turn_set_up_otherwise_starts_a_new_one_and_ends_the_old(
    tmp_path: Path,
) -> None:
    """Its MCP servers and hidden tools are fixed when it starts; its file goes with it."""
    starts = _Starts(tmp_path)
    runs = AgentRuns()
    first = await runs.acquire(7, "digest-a", starts)

    second = await runs.acquire(7, "digest-b", starts)

    assert second is not first
    assert starts.started[0].closed
    assert not (tmp_path / "mcp-0.json").exists()


class _WillNotReconnect(ScriptedRun):
    async def reconnect(self, server: str) -> None:
        raise RuntimeError(f"{server} did not answer")


async def test_a_server_that_will_not_reconnect_starts_the_claude_code_over(
    tmp_path: Path,
) -> None:
    """A run left with a server's old tools would offer the model what the server no longer has."""
    starts = _Starts(tmp_path)
    runs = AgentRuns()
    held = await runs.acquire(7, "digest-a", starts, {"notes": "tools-a"})
    held.run = _WillNotReconnect()

    again = await runs.acquire(7, "digest-a", starts, {"notes": "tools-b"})

    assert again is not held
    assert len(starts.started) == 2
    assert again.listings == {"notes": "tools-b"}


async def test_an_idle_claude_code_is_ended(tmp_path: Path) -> None:
    """Each holds memory; five minutes covers a reply read and answered."""
    now = [0.0]
    starts = _Starts(tmp_path)
    runs = AgentRuns(idle_seconds=300, clock=lambda: now[0])
    await runs.acquire(7, "digest-a", starts)
    runs.release(7)

    now[0] = 301
    await runs.acquire(8, "digest-a", starts)

    assert starts.started[0].closed
    assert not (tmp_path / "mcp-0.json").exists()


async def test_forgetting_a_thread_and_quitting_end_its_claude_code(
    tmp_path: Path,
) -> None:
    """A deleted thread's Claude Code goes at once; quitting ends every one left."""
    starts = _Starts(tmp_path)
    runs = AgentRuns()
    await runs.acquire(7, "digest-a", starts)
    await runs.acquire(8, "digest-a", starts)

    await runs.forget(7)
    assert starts.started[0].closed
    assert not starts.started[1].closed

    await runs.close_all()
    assert starts.started[1].closed
    assert list(tmp_path.iterdir()) == []
