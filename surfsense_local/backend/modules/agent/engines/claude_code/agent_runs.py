"""One running Claude Code per agent thread, so the next turn skips the start-up.

Its MCP servers, hidden tools and skills are fixed when it starts: a turn set
up otherwise, as its digest says, ends it and starts another, resuming the same
session. A server whose tools changed is only connected again, since Claude Code
lists a server's tools once it connects. Each holds a config file with sign-in
headers, removed with it.
"""

import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from modules.agent.engines.claude_code.approvals import APPROVALS, Approvals
from modules.agent.engines.claude_code.turn_link import TurnLink
from modules.llm.subscriptions.claude.run import ClaudeRun

logger = logging.getLogger(__name__)

Start = Callable[[TurnLink], Awaitable[tuple[ClaudeRun, Path]]]

IDLE_SECONDS = 300.0


@dataclass
class HeldRun:
    run: ClaudeRun
    link: TurnLink
    digest: str
    mcp_file: Path
    used_at: float
    turning: bool = True
    # A digest of each server's tools, as the run last connected it.
    listings: dict[str, str] = field(default_factory=dict)


class AgentRuns:
    def __init__(
        self,
        *,
        approvals: Approvals = APPROVALS,
        idle_seconds: float = IDLE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._approvals = approvals
        self._idle = idle_seconds
        self._clock = clock
        self._held: dict[int, HeldRun] = {}

    async def acquire(
        self,
        thread_id: int,
        digest: str,
        start: Start,
        listings: dict[str, str] | None = None,
    ) -> HeldRun:
        """The thread's Claude Code for a turn set up as `digest` says, its servers' tools as `listings` say."""
        await self._end_idle()
        listings = listings or {}
        held = self._held.get(thread_id)
        if held is not None and held.digest == digest:
            held.turning = True
            held.used_at = self._clock()
            if await _reconnected(held, listings):
                return held
        await self.forget(thread_id)
        link = TurnLink(thread_id, self._approvals)
        run, mcp_file = await start(link)
        held = HeldRun(run, link, digest, mcp_file, self._clock(), listings=listings)
        self._held[thread_id] = held
        return held

    def release(self, thread_id: int) -> None:
        """The turn ended; the run waits for the next one until it idles out."""
        held = self._held.get(thread_id)
        if held is not None:
            held.turning = False
            held.used_at = self._clock()
            held.link.end()

    async def forget(self, thread_id: int) -> None:
        held = self._held.pop(thread_id, None)
        if held is not None:
            await _end(held)

    async def close_all(self) -> None:
        for thread_id in list(self._held):
            await self.forget(thread_id)

    async def _end_idle(self) -> None:
        now = self._clock()
        for thread_id, held in list(self._held.items()):
            if not held.turning and now - held.used_at > self._idle:
                await self.forget(thread_id)


async def _reconnected(held: HeldRun, listings: dict[str, str]) -> bool:
    """Connect again each server whose tools changed; False when one would not, and the run starts over."""
    for server, listing in listings.items():
        if held.listings.get(server) == listing:
            continue
        try:
            await held.run.reconnect(server)
        except Exception:
            logger.warning("Claude Code did not reconnect %s", server, exc_info=True)
            return False
        held.listings[server] = listing
    return True


async def _end(held: HeldRun) -> None:
    held.link.end()
    # A run that will not close cleanly is gone either way.
    with contextlib.suppress(Exception):
        await held.run.close()
    held.mcp_file.unlink(missing_ok=True)
