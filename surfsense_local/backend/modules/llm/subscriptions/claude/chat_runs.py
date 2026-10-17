"""Warm Claude Code runs, one per conversation, so the next message skips the
start-up: measured 0.9 s to the first token warm against 2.3 s cold."""

import asyncio
import contextlib
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable, Hashable, Sequence
from dataclasses import dataclass, field

from claude_agent_sdk import ClaudeAgentOptions

from modules.llm.providers.types import Message
from modules.llm.subscriptions.claude.chat_prompt import (
    continues,
    newest_message,
    whole_conversation,
)
from modules.llm.subscriptions.claude.run import ClaudeRun, Prompt

Opener = Callable[[ClaudeAgentOptions], Awaitable[ClaudeRun]]

# Each warm run is a Claude Code process holding memory; five minutes covers a
# reply being read and answered.
CAPACITY = 4
IDLE_SECONDS = 300.0


@dataclass
class _Warm:
    run: ClaudeRun
    settings: Hashable
    held: tuple[Message, ...] = ()
    used_at: float = 0.0
    busy: asyncio.Lock = field(default_factory=asyncio.Lock)


class ChatRuns:
    def __init__(
        self,
        opener: Opener,
        *,
        capacity: int = CAPACITY,
        idle_seconds: float = IDLE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._open = opener
        self._capacity = capacity
        self._idle = idle_seconds
        self._clock = clock
        self._warm: OrderedDict[str, _Warm] = OrderedDict()

    async def _close(self, run: ClaudeRun) -> None:
        # A run that will not close cleanly is gone either way.
        with contextlib.suppress(Exception):
            await run.close()

    async def _close_idle(self) -> None:
        now = self._clock()
        for key, warm in list(self._warm.items()):
            if now - warm.used_at > self._idle and not warm.busy.locked():
                del self._warm[key]
                await self._close(warm.run)

    @contextlib.asynccontextmanager
    async def turn(
        self,
        conversation: str | None,
        settings: Hashable,
        options: ClaudeAgentOptions,
        messages: Sequence[Message],
    ) -> AsyncIterator[tuple[ClaudeRun, Prompt]]:
        """A run to answer `messages` and what to send it.

        `settings` names what the run was opened with (model, reasoning, schema):
        a run opened otherwise is not reused.
        """
        await self._close_idle()
        warm = self._warm.get(conversation) if conversation else None
        if (
            warm is not None
            and not warm.busy.locked()
            and warm.settings == settings
            and continues(warm.held, messages)
        ):
            async with warm.busy:
                self._warm.move_to_end(conversation)
                try:
                    yield warm.run, newest_message(messages)
                except BaseException:
                    del self._warm[conversation]
                    await self._close(warm.run)
                    raise
                warm.held, warm.used_at = tuple(messages), self._clock()
            return

        if warm is not None and not warm.busy.locked():
            del self._warm[conversation]
            await self._close(warm.run)
        run = await self._open(options)
        if conversation is None or (warm is not None and warm.busy.locked()):
            try:
                yield run, whole_conversation(messages)
            finally:
                await self._close(run)
            return

        fresh = _Warm(run, settings, used_at=self._clock())
        async with fresh.busy:
            # Pooled before it answers, so a message sent meanwhile sees it busy.
            self._warm[conversation] = fresh
            await self._close_over_capacity()
            try:
                yield run, whole_conversation(messages)
            except BaseException:
                if self._warm.get(conversation) is fresh:
                    del self._warm[conversation]
                await self._close(fresh.run)
                raise
            fresh.held, fresh.used_at = tuple(messages), self._clock()

    async def _close_over_capacity(self) -> None:
        idle = [key for key, warm in self._warm.items() if not warm.busy.locked()]
        while len(self._warm) > self._capacity and idle:
            await self._close(self._warm.pop(idle.pop(0)).run)

    async def close_all(self) -> None:
        """Every warm run, when the API stops."""
        while self._warm:
            _, warm = self._warm.popitem()
            await self._close(warm.run)
