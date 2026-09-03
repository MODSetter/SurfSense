import os
import tempfile
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

# Before the first import that reads settings: shared.queue opens its file at
# import time, and no test may write to the developer's own ~/.surfsense.
os.environ.setdefault(
    "SURFSENSE_LOCAL_DATA_DIR", tempfile.mkdtemp(prefix="surfsense-tests-")
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from shared.config import get_storage_settings
from shared.db import (
    create_db_engine,
    create_session_factory,
    import_models,
)
from shared.migrations import upgrade_to_head
from shared.queue import huey

# A slice missing from Base.metadata is a slice the drift test cannot check.
import_models()


@pytest.fixture
async def client(engine: Engine) -> AsyncGenerator[AsyncClient, None]:
    """Drive a fresh app in-process, so tests never bind a port."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """A database built the way a user's is: by migrations, never create_all."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    upgrade_to_head(engine)
    return engine


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point uploads at this test's own tree, and empty the queue it enqueues to.

    Both are process-wide: the settings object is cached, and Huey binds one
    file for the whole session, so leaving either shared would let one test see
    another's files and jobs.
    """
    monkeypatch.setattr(get_storage_settings(), "data_dir", tmp_path)
    huey.flush()
    yield tmp_path
    huey.flush()
