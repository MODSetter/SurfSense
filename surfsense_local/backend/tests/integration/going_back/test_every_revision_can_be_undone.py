"""Going back to a release runs the undo step of every revision written since it."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text

from alembic import command
from shared.db import create_db_engine
from shared.migrations import is_migrated
from tests.integration.going_back.newer_app import ALEMBIC

pytestmark = pytest.mark.integration

# 2.0.0's head. Older revisions belong to releases nobody can go back to.
OLDEST_RELEASED = "0011"


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC))
    config.attributes["engine"] = engine
    return config


def _library(path: Path) -> Engine:
    engine = create_db_engine(path)
    command.upgrade(_config(engine), "head")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workspaces(id, name) VALUES (1, 'Notes')"))
        connection.execute(
            text(
                "INSERT INTO documents(id, workspace_id, title, document_type, status) "
                "VALUES (1, 1, 'note', 'NOTE', 'ready')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chat_threads(id, workspace_id, title) VALUES (1, 1, 'Plans')"
            )
        )
    return engine


def test_every_revision_since_the_first_release_undoes_and_redoes(
    tmp_path: Path,
) -> None:
    """Each undo step written since 2.0.0 runs, keeps the rows, and redoes cleanly."""
    engine = _library(tmp_path / "surfsense.db")

    command.downgrade(_config(engine), OLDEST_RELEASED)
    with engine.connect() as connection:
        kept = connection.execute(text("SELECT title FROM documents")).scalars().all()
    command.upgrade(_config(engine), "head")

    assert kept == ["note"]
    assert is_migrated(engine)
