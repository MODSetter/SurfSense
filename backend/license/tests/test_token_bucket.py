"""The rate limits' bucket on a real Redis: CI's service, or a throwaway redis-server."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from host.tests.redis_server import redis_url
from license import token_bucket
from license.settings import config

pytestmark = pytest.mark.unit


@pytest.fixture
async def redis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    with redis_url(tmp_path) as url:
        monkeypatch.setattr(config, "REDIS_URL", url)
        await another_copy(monkeypatch)
        yield
        await another_copy(monkeypatch)


async def another_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    """A copy of the backend shares nothing with this one but Redis."""
    if token_bucket._redis_client is not None:
        await token_bucket._redis_client.aclose()
    monkeypatch.setattr(token_bucket, "_redis_client", None)
    monkeypatch.setattr(token_bucket, "_memory_buckets", {})


async def take(scope: str) -> int:
    return await token_bucket.acquire_token(scope, capacity=2, refill_per_sec=2 / 3600)


async def test_every_copy_of_the_backend_draws_on_one_bucket(
    redis: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otherwise each copy behind the proxy would grant its own allowance."""
    scope = f"license:trial:ip:{uuid.uuid4()}"

    first = [await take(scope), await take(scope)]
    await another_copy(monkeypatch)
    third = await take(scope)

    assert first == [0, 0]
    assert third > 0
