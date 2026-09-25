"""Revision 0017: sd-server fills the image editing and video slots too."""

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


def _choose(engine: Engine, model_type: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO selected_models(model_type, provider, name) "
                "VALUES (:type, 'sdcpp', 'flux-2-klein-4b-Q4_0')"
            ),
            {"type": model_type},
        )


@pytest.mark.parametrize("model_type", ["image_edit", "video_gen"])
def test_sd_server_can_fill_the_editing_and_video_slots(
    tmp_path: Path, model_type: str
) -> None:
    """FLUX.2 klein edits with the files it generates with."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "head")

    _choose(engine, model_type)


def test_it_could_not_before(tmp_path: Path) -> None:
    """The check this revision widens."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "0016")

    with pytest.raises(IntegrityError):
        _choose(engine, "image_edit")


def test_sd_server_still_cannot_fill_the_chat_or_audio_slots(tmp_path: Path) -> None:
    """Chat stays llama.cpp's and audio audio.cpp's."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "head")

    with pytest.raises(IntegrityError):
        _choose(engine, "text_gen")


def test_downgrading_drops_what_the_old_checks_cannot_hold(tmp_path: Path) -> None:
    """An editing choice goes; the image choice stays."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "head")
    _choose(engine, "image_gen")
    _choose(engine, "image_edit")

    command.downgrade(config, "0016")

    with engine.connect() as connection:
        kept = connection.execute(
            text("SELECT model_type FROM selected_models")
        ).scalars()
        assert list(kept) == ["image_gen"]
