"""Per-workspace rate limit: a secondary guard behind the credit meter-gate (05)."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.capabilities.access import rate_limit


def _request(workspace_id: int) -> Request:
    return Request({"type": "http", "path_params": {"workspace_id": workspace_id}})


@pytest.mark.asyncio
async def test_passes_at_the_limit(monkeypatch):
    monkeypatch.setattr(
        rate_limit, "_incr", lambda *a, **k: rate_limit.CAPABILITY_RATE_LIMIT_PER_MINUTE
    )
    await rate_limit.enforce_capability_rate_limit(_request(1))


@pytest.mark.asyncio
async def test_blocks_over_the_limit(monkeypatch):
    monkeypatch.setattr(
        rate_limit,
        "_incr",
        lambda *a, **k: rate_limit.CAPABILITY_RATE_LIMIT_PER_MINUTE + 1,
    )
    with pytest.raises(HTTPException) as exc:
        await rate_limit.enforce_capability_rate_limit(_request(1))
    assert exc.value.status_code == 429


def test_memory_fallback_counts_within_window():
    rate_limit._memory.clear()
    assert rate_limit._incr_memory("k", window_seconds=60) == 1
    assert rate_limit._incr_memory("k", window_seconds=60) == 2
