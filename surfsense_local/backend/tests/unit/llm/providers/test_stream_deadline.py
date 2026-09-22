"""Two clocks in front of a generation, not one.

The measured failure: a freshly downloaded 2.5 GB model took 39 seconds to load
on an 8 GB Mac, and a single 30 second budget around the whole stream cancelled
the request 9 seconds before the first token arrived. Waiting for a load is not
evidence of a fault; silence part way through an answer is.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest

from modules.llm.providers.stream_deadline import StreamTimeoutError, with_deadlines

pytestmark = pytest.mark.unit


async def _after(delays: list[float]) -> AsyncIterator[str]:
    """One token per delay, each arriving that many seconds after the last."""
    for index, delay in enumerate(delays):
        await asyncio.sleep(delay)
        yield str(index)


async def _collect(stream: AsyncIterator[str]) -> list[str]:
    return [delta async for delta in stream]


async def test_a_slow_load_is_waited_out_not_cancelled() -> None:
    """The whole point. The first token may take far longer than any later one,
    because that wait is the model loading, and its length is a property of the
    machine rather than of the request."""
    tokens = await _collect(
        with_deadlines(
            _after([0.15, 0.0, 0.0]),
            first_item_seconds=1.0,
            between_items_seconds=0.05,
        )
    )

    assert tokens == ["0", "1", "2"]


async def test_going_quiet_mid_answer_is_cut_off_without_waiting_for_the_load_budget() -> None:
    """The opposite case, and the reason the second clock is tight: once tokens
    are flowing, a long gap really is a fault and should not inherit the
    patience a cold load earns."""
    with pytest.raises(StreamTimeoutError) as raised:
        await _collect(
            with_deadlines(
                _after([0.0, 5.0]),
                first_item_seconds=5.0,
                between_items_seconds=0.05,
            )
        )

    assert not raised.value.first_item


async def test_a_model_that_never_starts_answering_says_so() -> None:
    """Told apart from the case above, because they mean different things to
    whoever reads the log: one is a machine too slow or a load that failed, the
    other is a stream that died."""
    with pytest.raises(StreamTimeoutError) as raised:
        await _collect(
            with_deadlines(
                _after([5.0]),
                first_item_seconds=0.05,
                between_items_seconds=5.0,
            )
        )

    assert raised.value.first_item


async def test_the_underlying_stream_is_closed_when_a_budget_fires() -> None:
    """A timeout abandons an open HTTP response, and leaving it to the garbage
    collector holds the connection and the worker's slot."""
    closed = False

    async def source() -> AsyncIterator[str]:
        nonlocal closed
        try:
            await asyncio.sleep(5.0)
            yield "never"
        finally:
            closed = True

    with pytest.raises(StreamTimeoutError):
        await _collect(
            with_deadlines(
                source(), first_item_seconds=0.05, between_items_seconds=5.0
            )
        )

    assert closed
