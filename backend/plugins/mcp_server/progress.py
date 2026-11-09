"""Progress a tool reports at each stage of a call, so a slow first item does not look dead.

A client gives up on a call after a silence (opencode: 200 s), and a progress
notification is the only message that resets it. Reporting only when an item
finishes leaves a slow first item silent; reporting each stage, once a second at
most, keeps the call alive without flooding the stream.
"""

import asyncio
import logging
import time
import weakref
from dataclasses import dataclass

from mcp.server.mcpserver import Context

logger = logging.getLogger(__name__)

# At most one notification a second per call.
INTERVAL_SECONDS = 1.0

# Read through the module, so a test can move time.
_clock = time.monotonic


@dataclass
class _Call:
    """What a call has reported: whole items done, and stages since the last one."""

    done: float = 0.0
    stages: int = 0
    total: float | None = None
    sent_at: float | None = None
    # The loop of the call's first stage, the tool's own, which owns its stream.
    loop: asyncio.AbstractEventLoop | None = None

    def value(self) -> float:
        # Stages between two items count as fractions that never reach the next
        # item, so the value rises with every notification, as MCP requires.
        return self.done + self.stages / (self.stages + 1)


# By the context's id, removed when the context is: a Context cannot be hashed.
_calls: dict[int, _Call] = {}


async def stage(
    ctx: Context | None,
    message: str,
    *,
    done: int | None = None,
    total: int | None = None,
) -> None:
    """Report `message`, with `done` of `total` items when given, as a progress notification.

    Sent at most once a second per call, except the stage whose `done` first reaches
    `total`, which is always sent. Never raises: progress is not worth failing a
    call for. A no-op without a context or when the client asked for no progress.
    A stage reported from another loop, such as the browser loop, is sent on the
    loop of the call's first stage.
    """
    if ctx is None:
        return
    try:
        call = _calls.get(id(ctx))
        if call is None:
            call = _calls[id(ctx)] = _Call()
            # Before its id can be reused.
            weakref.finalize(ctx, _calls.pop, id(ctx), None)
        if total is not None:
            call.total = total
        # Only the stage that first reaches the total: a plugin may count past a
        # per-URL total, and the items after it are limited like any other.
        last = (
            done is not None
            and call.total is not None
            and call.done < call.total <= done
        )
        if done is not None and done > call.value():
            call.done, call.stages = done, 0
        else:
            last = False
            call.stages += 1
        now = _clock()
        if (
            not last
            and call.sent_at is not None
            and now - call.sent_at < INTERVAL_SECONDS
        ):
            return
        call.sent_at = now
        loop = asyncio.get_running_loop()
        call.loop = call.loop or loop
        if call.loop is loop:
            await ctx.report_progress(call.value(), call.total, message)
        elif not call.loop.is_closed():
            # Not awaited: the browser loop's work need not wait on the stream.
            asyncio.run_coroutine_threadsafe(
                ctx.report_progress(call.value(), call.total, message), call.loop
            )
    except Exception as error:
        logger.debug("[progress] not reported: %r", error)
