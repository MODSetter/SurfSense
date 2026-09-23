"""Revision 0015: a local image selection names its build, not the old list."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text

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


def _selected(tmp_path: Path, provider: str, name: str) -> tuple[Engine, Config]:
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0014")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO selected_models(model_type, provider, name) "
                "VALUES ('image_gen', :provider, :name)"
            ),
            {"provider": provider, "name": name},
        )
    return engine, config


def _name(engine: Engine) -> str:
    with engine.connect() as connection:
        return connection.execute(text("SELECT name FROM selected_models")).scalar_one()


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("stable-diffusion-1.5", "v1-5-pruned_Q4_0"),
        ("sdxl-base-1.0", "sd_xl_base_1.0_0_Q4_0"),
        ("sdxl-turbo", "stable-diffusion-xl-1.0-turbo-Q4_0"),
    ],
)
def test_an_old_image_selection_names_its_build(
    tmp_path: Path, old: str, new: str
) -> None:
    """The same weights, by the name the catalog and sd-server now use."""
    engine, config = _selected(tmp_path, "sdcpp", old)

    command.upgrade(config, "head")

    assert _name(engine) == new


def test_a_remote_image_selection_is_left_alone(tmp_path: Path) -> None:
    """Only sd-server's names changed; a connection's model id is its own."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0014")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections(id, label, provider, base_url) "
                "VALUES (1, 'Cloud', 'openai_compatible', 'https://x.test/v1')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO selected_models(model_type, provider, connection_id, name) "
                "VALUES ('image_gen', 'openai_compatible', 1, 'sdxl-turbo')"
            )
        )

    command.upgrade(config, "head")

    assert _name(engine) == "sdxl-turbo"


def test_downgrading_restores_the_old_name(tmp_path: Path) -> None:
    """The previous release looks the old name up in its hard-coded list."""
    engine, config = _selected(tmp_path, "sdcpp", "sdxl-base-1.0")
    command.upgrade(config, "head")

    command.downgrade(config, "0014")

    assert _name(engine) == "sdxl-base-1.0"
