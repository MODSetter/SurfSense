from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Drive a fresh app in-process, so tests never bind a port."""
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
