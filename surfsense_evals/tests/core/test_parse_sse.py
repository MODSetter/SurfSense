"""Tests for the SSE consumer."""

from __future__ import annotations

import pytest

from surfsense_evals.core.parse import iter_sse_events


async def _alist(it):
    out = []
    async for x in it:
        out.append(x)
    return out


async def _astream(lines):
    for line in lines:
        yield line


@pytest.mark.asyncio
async def test_basic_data_frame():
    events = await _alist(
        iter_sse_events(
            _astream(
                [
                    'data: {"type": "text-delta", "delta": "hi"}',
                    "",
                    'data: {"type": "finish"}',
                    "",
                ]
            )
        )
    )
    assert [e.data for e in events] == [
        '{"type": "text-delta", "delta": "hi"}',
        '{"type": "finish"}',
    ]


@pytest.mark.asyncio
async def test_done_sentinel_passes_through():
    events = await _alist(
        iter_sse_events(
            _astream(
                [
                    "data: [DONE]",
                    "",
                ]
            )
        )
    )
    assert [e.data for e in events] == ["[DONE]"]


@pytest.mark.asyncio
async def test_multiline_data_joins_with_newline():
    events = await _alist(
        iter_sse_events(
            _astream(
                [
                    "data: line1",
                    "data: line2",
                    "",
                ]
            )
        )
    )
    assert events[0].data == "line1\nline2"


@pytest.mark.asyncio
async def test_comments_and_other_fields_ignored():
    events = await _alist(
        iter_sse_events(
            _astream(
                [
                    ": heartbeat",
                    "event: foo",
                    "id: 123",
                    "data: payload",
                    "",
                ]
            )
        )
    )
    assert [e.data for e in events] == ["payload"]


@pytest.mark.asyncio
async def test_handles_missing_trailing_blank():
    """Some servers omit the final blank line; the consumer should still emit."""

    events = await _alist(
        iter_sse_events(
            _astream(
                [
                    "data: only-one",
                ]
            )
        )
    )
    assert [e.data for e in events] == ["only-one"]
