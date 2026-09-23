"""Revision 0013: a selection is keyed by what the model is for, not by a role.

`generation` and `image_generation` were a second word for `text_gen` and
`image_gen`, one to one, so the rows are renamed in place and nothing else about
them changes.
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


def migrated(tmp_path: Path, seed: str, target: str = "head") -> Engine:
    """A database seeded at 0012 and then moved to `target`."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0012")
    with engine.begin() as connection:
        for statement in seed.strip().split(";"):
            if statement.strip():
                connection.execute(text(statement))
    command.upgrade(config, target)
    return engine


def test_a_chat_selection_becomes_the_text_gen_selection(tmp_path: Path) -> None:
    """The row is renamed in place: its model and its fingerprint are unchanged."""
    engine = migrated(
        tmp_path,
        "INSERT INTO selected_models(role, provider, name, params_b) "
        "VALUES ('generation', 'llamacpp', 'Qwen3-8B-Q4_K_M', 8.2)",
    )

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT model_type, provider, name, params_b FROM selected_models")
        ).one()

    assert tuple(row) == ("text_gen", "llamacpp", "Qwen3-8B-Q4_K_M", 8.2)


def test_an_image_selection_becomes_the_image_gen_selection(tmp_path: Path) -> None:
    """sd-server's selection keeps its model under the new key."""
    engine = migrated(
        tmp_path,
        "INSERT INTO selected_models(role, provider, name) "
        "VALUES ('image_generation', 'sdcpp', 'sdxl-base-1.0')",
    )

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT model_type, provider, name FROM selected_models")
        ).one()

    assert tuple(row) == ("image_gen", "sdcpp", "sdxl-base-1.0")


def test_downgrading_keeps_the_two_old_slots_and_drops_the_new_ones(
    tmp_path: Path,
) -> None:
    """The old schema has no key for a video selection, so it cannot survive."""
    engine = migrated(tmp_path, "")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections(id, label, provider, base_url) "
                "VALUES (1, 'Gateway', 'openai_compatible', 'https://gw.example/v1')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO selected_models(model_type, provider, connection_id, name) "
                "VALUES ('text_gen', 'openai_compatible', 1, 'gpt-5'), "
                "('video_gen', 'openai_compatible', 1, 'veo-3')"
            )
        )

    command.downgrade(_config(engine), "0012")

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT role, name FROM selected_models")).all()

    assert [tuple(row) for row in rows] == [("generation", "gpt-5")]


@pytest.mark.parametrize(
    ("provider", "model_type"),
    [("llamacpp", "image_gen"), ("sdcpp", "text_gen"), ("llamacpp", "video_gen")],
)
def test_a_local_runtime_holds_only_the_type_it_serves(
    tmp_path: Path, provider: str, model_type: str
) -> None:
    """The database refuses what selection refuses, so no other path can write it."""
    engine = migrated(tmp_path, "")

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO selected_models(model_type, provider, name) "
                f"VALUES ('{model_type}', '{provider}', 'some-model')"
            )
        )
