from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from shared.db import create_db_engine, import_models
from shared.migrations import upgrade_to_head

# A slice missing from Base.metadata is a slice the drift test cannot check.
import_models()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Drive a fresh app in-process, so tests never bind a port."""
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """A database built the way a user's is: by migrations, never create_all."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    upgrade_to_head(engine)
    return engine
