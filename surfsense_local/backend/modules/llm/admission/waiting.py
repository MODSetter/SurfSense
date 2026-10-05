import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack


async def wait_in_line(
    stack: AsyncExitStack,
    admission: Callable[[Callable[[int], None]], AbstractAsyncContextManager[None]],
) -> AsyncIterator[int]:
    """Enter `admission` on `stack`, yielding the place in line while it waits.

    For a stream that has to tell its reader where it stands: each change of
    place comes out as it happens, and the iterator ends once admitted. The
    room is held until `stack` closes.
    """
    places: asyncio.Queue[int] = asyncio.Queue()
    entering = asyncio.ensure_future(
        stack.enter_async_context(admission(places.put_nowait))
    )
    try:
        while not entering.done():
            place = asyncio.ensure_future(places.get())
            await asyncio.wait({entering, place}, return_when=asyncio.FIRST_COMPLETED)
            if place.done():
                yield place.result()
            else:
                place.cancel()
        while not places.empty():
            places.get_nowait()
        entering.result()
    finally:
        if not entering.done():
            entering.cancel()
            await asyncio.gather(entering, return_exceptions=True)
