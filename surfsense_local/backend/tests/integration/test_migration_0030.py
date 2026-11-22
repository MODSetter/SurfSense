"""Revision 0030: audio.cpp fills the speech recognition slot too."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from shared.db import create_db_engine

pytestmark = pytest.mark.integration

NEMOTRON = "nemotron-3.5-asr-streaming-0.6b-q8_0"
SETTINGS = '{"voices": ["alloy"], "chat_modes": {"a/1/b": "agent"}}'


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    return config


def _choose(engine: Engine, model_type: str, provider: str = "audiocpp") -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO selected_models(model_type, provider, name) "
                "VALUES (:type, :provider, :name)"
            ),
            {"type": model_type, "provider": provider, "name": NEMOTRON},
        )


def _rows(engine: Engine) -> list[tuple]:
    with engine.connect() as connection:
        return [
            tuple(row)
            for row in connection.execute(
                text(
                    "SELECT model_type, provider, connection_id, name, params_b, "
                    "vendor, line, settings, updated_at FROM selected_models "
                    "ORDER BY model_type"
                )
            )
        ]


def _remote_voice_with_settings(engine: Engine) -> None:
    """A server's audio model with the voices the user added and a chat mode."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections(id, label, provider, base_url) "
                "VALUES (1, 'Gateway', 'openai_compatible', 'https://x.example/v1')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO selected_models(model_type, provider, connection_id, "
                "name, params_b, vendor, line, settings, updated_at) VALUES "
                "('audio_gen', 'openai_compatible', 1, 'tts-1', 1.5, 'openai', "
                "'small', :settings, '2026-10-01 09:00:00')"
            ),
            {"settings": SETTINGS},
        )


def test_audio_cpp_can_fill_the_speech_recognition_slot(tmp_path: Path) -> None:
    """Nemotron runs on the bundled audio.cpp server, with no connection."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "head")

    _choose(engine, "speech_to_text")


def test_it_could_not_before(tmp_path: Path) -> None:
    """The check this revision widens."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "0029")

    with pytest.raises(IntegrityError):
        _choose(engine, "speech_to_text")


@pytest.mark.parametrize("provider", ["llamacpp", "sdcpp"])
def test_no_other_local_runtime_can_fill_it(tmp_path: Path, provider: str) -> None:
    """Only audio.cpp hears."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "head")

    with pytest.raises(IntegrityError):
        _choose(engine, "speech_to_text", provider)


def test_audio_cpp_still_cannot_fill_the_chat_slot(tmp_path: Path) -> None:
    """Widened by one type, not opened."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "head")

    with pytest.raises(IntegrityError):
        _choose(engine, "text_gen")


def test_the_rebuild_keeps_every_column_of_every_selection(tmp_path: Path) -> None:
    """0018's rebuild predates the settings column: copying it would drop the
    voices a user added."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0029")
    _remote_voice_with_settings(engine)
    before = _rows(engine)

    command.upgrade(config, "head")

    assert _rows(engine) == before
    assert before[0][7] == SETTINGS


def test_deleting_the_connection_still_clears_its_selections(tmp_path: Path) -> None:
    """The rebuilt table keeps the cascade."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "0029")
    _remote_voice_with_settings(engine)
    command.upgrade(_config(engine), "head")

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM provider_connections WHERE id = 1"))

    assert _rows(engine) == []


def test_downgrading_drops_only_the_speech_recognition_choice(tmp_path: Path) -> None:
    """The old checks cannot hold it; the rest keeps every column."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "head")
    _remote_voice_with_settings(engine)
    _choose(engine, "speech_to_text")
    kept = [row for row in _rows(engine) if row[0] != "speech_to_text"]

    command.downgrade(config, "0029")

    assert _rows(engine) == kept
