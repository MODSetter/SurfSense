"""Revision 0014: a connection names the manifest provider it reaches.

Existing connections become `custom`: their provider was never recorded, and
reading it back from the URL is the guess the design refuses, so they keep
today's behaviour until the user picks one.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

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


def test_an_existing_connection_becomes_custom_and_keeps_the_rest(
    tmp_path: Path,
) -> None:
    """Nothing about it changes except the new, honest default."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0013")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections(id, label, provider, base_url) "
                "VALUES (1, 'Work', 'openai_compatible', 'https://api.openai.com/v1')"
            )
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT label, base_url, catalog_provider FROM provider_connections")
        ).one()
    assert tuple(row) == ("Work", "https://api.openai.com/v1", "custom")


def test_downgrading_removes_the_column(tmp_path: Path) -> None:
    """The old schema has nowhere to keep it."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "head")

    command.downgrade(config, "0013")

    columns = {column["name"] for column in inspect(engine).get_columns("provider_connections")}
    assert "catalog_provider" not in columns


@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_a_selection_on_a_connection_survives_either_direction(
    tmp_path: Path, direction: str
) -> None:
    """Rebuilding the connections table must not cascade into the selections."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0013" if direction == "upgrade" else "head")
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

    if direction == "upgrade":
        command.upgrade(config, "head")
    else:
        command.downgrade(config, "0013")

    with engine.connect() as connection:
        names = connection.execute(text("SELECT name FROM selected_models")).scalars().all()
    assert names == ["gpt-5"]
