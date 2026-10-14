import os
import tempfile
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

# Before the first import that reads settings: shared.queue opens its file at
# import time, and no test may write to the developer's own ~/.surfsense.
os.environ.setdefault(
    "SURFSENSE_LOCAL_DATA_DIR", tempfile.mkdtemp(prefix="surfsense-tests-")
)
os.environ.setdefault("SURFSENSE_LOCAL_SECRET", "test-secret")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from modules.embedding.bundled import BGE
from modules.embedding.lock import lock_index
from shared.config import get_storage_settings
from shared.db import (
    create_db_engine,
    create_session_factory,
    import_models,
)
from shared.migrations import upgrade_to_head
from shared.queue import ingest_queue, plugins_queue, studio_queue
from tests.office_stand_in import office_off

# A feature missing from Base.metadata is one the drift test cannot check.
import_models()

# Where the real embedding model might be: the staged pack `pnpm dev` points the
# app at, then the default data dir scripts/fetch_embedding_model.py writes to.
# Checking both means a checkout that has run either one exercises the real
# encoder instead of silently skipping.
_STAGED_MODELS = Path(__file__).resolve().parents[1] / "models"
_DEFAULT_MODELS = Path.home() / ".surfsense" / "models"
REAL_MODELS = next(
    (
        candidate
        for candidate in (_STAGED_MODELS, _DEFAULT_MODELS)
        if (candidate / "bge-small-en-v1.5" / "model_optimized.onnx").is_file()
    ),
    _DEFAULT_MODELS,
)


@pytest.fixture
async def client(engine: Engine) -> AsyncGenerator[AsyncClient, None]:
    """Drive a fresh app in-process, so tests never bind a port."""
    async with _client_over(engine) as async_client:
        yield async_client


@pytest.fixture
async def unlocked_client(
    unlocked_engine: Engine,
) -> AsyncGenerator[AsyncClient, None]:
    """The app before onboarding has chosen an embedder."""
    async with _client_over(unlocked_engine) as async_client:
        yield async_client


def _client_over(engine: Engine) -> AsyncClient:
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def unlocked_engine(tmp_path: Path) -> Engine:
    """A database built the way a user's is, by migrations, before onboarding
    has chosen an embedder."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    upgrade_to_head(engine)
    return engine


@pytest.fixture
def engine(unlocked_engine: Engine) -> Engine:
    """A user's database once onboarding has fixed the bundled embedder."""
    with create_session_factory(unlocked_engine)() as session:
        lock_index(session, BGE)
        session.commit()
    return unlocked_engine


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point uploads at this test's own tree, and empty the queue it enqueues to.

    Both are process-wide: the settings object is cached, and Huey binds one
    file for the whole session, so leaving either shared would let one test see
    another's files and jobs.
    """
    monkeypatch.setattr(get_storage_settings(), "data_dir", tmp_path)
    ingest_queue.flush()
    studio_queue.flush()
    plugins_queue.flush()
    yield tmp_path
    ingest_queue.flush()
    studio_queue.flush()
    plugins_queue.flush()


@pytest.fixture(autouse=True)
def no_office_support(monkeypatch: pytest.MonkeyPatch) -> None:
    """Office support starts off in every test, whatever LibreOffice this machine has;
    a test of the Office path turns it on (tests/office_stand_in.py)."""
    office_off(monkeypatch)


@pytest.fixture
def real_model(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the encoder at the model fetch_embedding_model.py downloaded, or skip."""
    onnx = REAL_MODELS / "bge-small-en-v1.5" / "model_optimized.onnx"
    if not onnx.is_file():
        pytest.skip("run scripts/fetch_embedding_model.py to exercise the real encoder")

    monkeypatch.setenv("SURFSENSE_LOCAL_MODELS_DIR", str(REAL_MODELS))
    yield REAL_MODELS
