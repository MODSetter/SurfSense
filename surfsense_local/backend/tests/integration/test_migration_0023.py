"""Revision 0023: a connection says how it signs in, and can hold OAuth tokens.

Columns are added in place, never by rebuilding the table: a rebuild drops
`provider_connections`, which cascades into every remote selection.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from shared.db import create_db_engine

pytestmark = pytest.mark.integration

ADDED = {"auth_kind", "oauth_ciphertext", "token_version"}


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    return config


def _seed(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections(id, label, provider, base_url) "
                "VALUES (1, 'Work', 'openai_compatible', 'https://gw.example/v1')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO selected_models(model_type, provider, connection_id, name) "
                "VALUES ('text_gen', 'openai_compatible', 1, 'gpt-5')"
            )
        )


def test_an_existing_connection_signs_in_with_its_key_and_keeps_its_selection(
    tmp_path: Path,
) -> None:
    """Columns are added in place, so no selection cascades away."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0022")
    _seed(engine)

    command.upgrade(config, "head")

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT label, auth_kind, oauth_ciphertext, token_version "
                "FROM provider_connections"
            )
        ).one()
        names = (
            connection.execute(text("SELECT name FROM selected_models")).scalars().all()
        )
    assert tuple(row) == ("Work", "api_key", None, 0)
    assert names == ["gpt-5"]


def test_an_unknown_way_of_signing_in_is_refused(tmp_path: Path) -> None:
    """The CHECK holds auth_kind to the two ways the app knows."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "head")

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections(label, provider, base_url, auth_kind) "
                "VALUES ('Odd', 'openai_compatible', 'https://gw.example/v1', 'cookie')"
            )
        )


def test_downgrading_drops_the_columns_and_keeps_the_selection(tmp_path: Path) -> None:
    """Dropped in place too, so key connections keep their selections."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "head")
    _seed(engine)

    command.downgrade(config, "0022")

    columns = {
        column["name"] for column in inspect(engine).get_columns("provider_connections")
    }
    with engine.connect() as connection:
        names = (
            connection.execute(text("SELECT name FROM selected_models")).scalars().all()
        )
    assert not columns & ADDED
    assert names == ["gpt-5"]
