import asyncio
from collections.abc import AsyncIterator

# Often enough that a reader with a stall budget never mistakes a request
# waiting for the runtime, or a model reading a long prompt, for a dead stream.
KEEP_ALIVE_SECONDS = 15.0

KEEP_ALIVE = b": keep-alive\n\n"


async def with_keep_alive(frames: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """`frames`, with a comment whenever nothing else has been sent for a while."""
    pending = asyncio.ensure_future(anext(frames))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=KEEP_ALIVE_SECONDS)
            if not done:
                yield KEEP_ALIVE
                continue
            try:
                frame = pending.result()
            except StopAsyncIteration:
                return
            yield frame
            pending = asyncio.ensure_future(anext(frames))
    finally:
        if not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        await frames.aclose()
