"""Revision 0035: a connection can be ElevenLabs' own."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from shared.db import create_db_engine

pytestmark = pytest.mark.integration


def _config(engine: Engine) -> Config:
    """Alembic pointed at this engine."""
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    return config


def _insert(engine: Engine, label: str, auth_kind: str) -> None:
    """One connection row, straight into the table."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections"
                "(label, provider, base_url, auth_kind) "
                "VALUES (:label, 'openai_compatible', 'https://x.example', :kind)"
            ),
            {"label": label, "kind": auth_kind},
        )


def _kinds(engine: Engine) -> list[str]:
    """Each connection's `auth_kind`, by label."""
    with engine.connect() as connection:
        return [
            row[0]
            for row in connection.execute(
                text("SELECT auth_kind FROM provider_connections ORDER BY label")
            )
        ]


@pytest.fixture
def at_0034(tmp_path: Path) -> Engine:
    """A database one revision short."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "0034")
    return engine


def test_upgrading_takes_elevenlabs_and_keeps_what_was_chosen(at_0034: Engine) -> None:
    """Rebuilding the table cascades through selections unless they are kept aside."""
    engine = at_0034
    _insert(engine, "server", "api_key")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO selected_models"
                "(model_type, provider, connection_id, name) "
                "VALUES ('audio_gen', 'openai_compatible', 1, 'tts-1')"
            )
        )
    with pytest.raises(IntegrityError):
        _insert(engine, "too early", "elevenlabs")

    command.upgrade(_config(engine), "0035")

    _insert(engine, "voices", "elevenlabs")
    assert _kinds(engine) == ["api_key", "elevenlabs"]
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT connection_id, name FROM selected_models")
        ).one() == (1, "tts-1")


def test_downgrading_takes_elevenlabs_connections_with_it(at_0034: Engine) -> None:
    """The old check cannot hold one, and the rest stay."""
    engine = at_0034
    command.upgrade(_config(engine), "0035")
    _insert(engine, "server", "api_key")
    _insert(engine, "voices", "elevenlabs")

    command.downgrade(_config(engine), "0034")

    assert _kinds(engine) == ["api_key"]
