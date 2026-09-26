"""How long a stream may stay quiet, and when that stops being acceptable.

One clock cannot answer two questions. Waiting for the first item is waiting
for work that has not started producing yet: for a generation that is the model
loading, and a cold 2.5 GB file on an 8 GB Mac measured 39 seconds. A gap
*between* items is not the same thing, and a stream that dies half way through
should be given up on in seconds.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator


class StreamTimeoutError(TimeoutError):
    """A stream stayed quiet past its budget.

    A `TimeoutError` so that callers written against `asyncio.timeout` keep
    working, and carrying `first_item` because the two cases mean different
    things: one is work that never started, the other is work that died.
    """

    def __init__(self, seconds: float, *, first_item: bool, subject: str) -> None:
        self.first_item = first_item
        self.seconds = seconds
        super().__init__(
            f"{subject} did not start within {seconds:g}s"
            if first_item
            else f"{subject} stopped for more than {seconds:g}s"
        )


async def with_deadlines[T](
    stream: AsyncIterator[T],
    *,
    first_item_seconds: float,
    between_items_seconds: float,
    subject: str = "the stream",
) -> AsyncIterator[T]:
    """Yield from `stream`, applying the start budget then the stall budget.

    The deadline restarts on every item, so a long stream is never cut off for
    being long, only for going quiet. `subject` names what was being waited on,
    so the failure reads as a sentence wherever it is logged.
    """
    items = stream.__aiter__()
    seconds = first_item_seconds
    first_item = True
    try:
        while True:
            try:
                async with asyncio.timeout(seconds):
                    item = await anext(items)
            except StopAsyncIteration:
                return
            except TimeoutError as expired:
                raise StreamTimeoutError(
                    seconds, first_item=first_item, subject=subject
                ) from expired
            yield item
            seconds = between_items_seconds
            first_item = False
    finally:
        # The timeout cancelled a read on whatever the stream was holding: for
        # HTTP, an open response. Leaving it to the garbage collector holds the
        # connection, and with it the worker slot the next request needs.
        aclose = getattr(items, "aclose", None)
        if aclose is not None:
            with contextlib.suppress(Exception):
                await aclose()
