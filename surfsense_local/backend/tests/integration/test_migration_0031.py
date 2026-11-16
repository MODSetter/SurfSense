"""Revision 0031: a connection can be a Claude plan, run through the user's own Claude Code.

The only schema change is the auth_kind check; a Claude plan holds no credential
and nothing Claude Code reports, which is read live.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from shared.db import create_db_engine

pytestmark = pytest.mark.integration


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    return config


def _at(tmp_path: Path, revision: str) -> Engine:
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), revision)
    return engine


def _signed_in_chatgpt_with_a_selection(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections(id, label, provider, base_url, "
                "catalog_provider, auth_kind, oauth_ciphertext, token_version) "
                "VALUES (1, 'ChatGPT', 'openai_compatible', "
                "'https://api.openai.com/v1', 'openai', 'chatgpt', x'00ff', 3)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO selected_models(model_type, provider, connection_id, "
                "name, settings, updated_at) VALUES ('text_gen', "
                "'openai_compatible', 1, 'gpt-5', '{\"chat_modes\": {}}', "
                "'2026-10-01 09:00:00')"
            )
        )


def _connections(engine: Engine) -> list[tuple]:
    with engine.connect() as connection:
        return [
            tuple(row)
            for row in connection.execute(
                text(
                    "SELECT id, label, provider, base_url, catalog_provider, "
                    "api_key_ciphertext, auth_kind, oauth_ciphertext, "
                    "token_version, created_at, updated_at "
                    "FROM provider_connections ORDER BY id"
                )
            )
        ]


def _selections(engine: Engine) -> list[tuple]:
    with engine.connect() as connection:
        return [
            tuple(row)
            for row in connection.execute(
                text("SELECT * FROM selected_models ORDER BY model_type")
            )
        ]


def _add_claude_plan(engine: Engine, connection_id: int = 2) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections(id, label, provider, base_url, "
                "catalog_provider, auth_kind) VALUES (:id, 'Claude', "
                "'openai_compatible', 'https://api.anthropic.com', 'anthropic', "
                "'claude_plan')"
            ),
            {"id": connection_id},
        )


def test_a_connection_can_be_a_claude_plan(tmp_path: Path) -> None:
    """It holds no credential: Claude Code keeps the sign-in."""
    engine = _at(tmp_path, "head")

    _add_claude_plan(engine)

    assert _connections(engine)[0][6] == "claude_plan"


def test_no_other_kind_is_let_in(tmp_path: Path) -> None:
    """Widened by one kind, not opened."""
    engine = _at(tmp_path, "head")

    with (
        pytest.raises(IntegrityError),
        engine.begin() as connection,
    ):
        connection.execute(
            text(
                "INSERT INTO provider_connections(label, provider, base_url, "
                "auth_kind) VALUES ('x', 'openai_compatible', 'https://x', 'bogus')"
            )
        )


def test_the_rebuild_keeps_every_connection_and_its_selections(tmp_path: Path) -> None:
    """Dropping the old table cascades to selected_models, so the rebuild must
    put back every remote selection it took away."""
    engine = _at(tmp_path, "0030")
    _signed_in_chatgpt_with_a_selection(engine)
    connections, selections = _connections(engine), _selections(engine)

    command.upgrade(_config(engine), "head")

    assert _connections(engine) == connections
    assert _selections(engine) == selections
    assert len(selections) == 1


def test_deleting_a_connection_still_clears_its_selections(tmp_path: Path) -> None:
    """The rebuilt table keeps the cascade."""
    engine = _at(tmp_path, "0030")
    _signed_in_chatgpt_with_a_selection(engine)
    command.upgrade(_config(engine), "head")

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM provider_connections WHERE id = 1"))

    assert _selections(engine) == []


def test_downgrading_drops_only_the_claude_plan(tmp_path: Path) -> None:
    """The old check cannot hold it; every other connection and selection stays."""
    engine = _at(tmp_path, "0030")
    _signed_in_chatgpt_with_a_selection(engine)
    command.upgrade(_config(engine), "head")
    _add_claude_plan(engine)
    keep_connections = _connections(engine)[:1]
    keep_selections = _selections(engine)

    command.downgrade(_config(engine), "0030")

    assert _connections(engine) == keep_connections
    assert _selections(engine) == keep_selections
