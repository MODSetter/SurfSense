"""Revision 0027: grants stored under the earlier destination names.

`host:huggingface.co` covers search as well as downloads, so only a user who
allowed both is carried across. Every old row is removed either way.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text

from alembic import command
from shared.db import create_db_engine

pytestmark = pytest.mark.integration

HUGGINGFACE = "host:huggingface.co"


def _config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    return config


def upgraded(tmp_path: Path, rows: dict[str, bool]) -> Engine:
    """A database seeded at 0026 and then upgraded to 0027."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0026")
    with engine.begin() as connection:
        for destination, enabled in rows.items():
            connection.execute(
                text(
                    "INSERT INTO egress_destinations(destination, enabled) "
                    "VALUES (:destination, :enabled)"
                ),
                {"destination": destination, "enabled": enabled},
            )
    command.upgrade(config, "0027")
    return engine


def destinations(engine: Engine) -> dict[str, int]:
    """Every egress row, as destination to enabled."""
    with engine.connect() as connection:
        return dict(
            connection.execute(
                text("SELECT destination, enabled FROM egress_destinations")
            ).all()
        )


@pytest.mark.parametrize("download", ["model_download", "image_model_pull"])
def test_a_download_grant_alone_is_removed_not_carried(
    tmp_path: Path, download: str
) -> None:
    """The host also receives what the user types in search, which a download
    grant never covered, so the user is asked once instead."""
    engine = upgraded(tmp_path, {download: True})

    assert destinations(engine) == {}


@pytest.mark.parametrize("download", ["model_download", "image_model_pull"])
def test_search_and_a_download_together_carry_across(
    tmp_path: Path, download: str
) -> None:
    """Both halves of the host's consent were given, so it is not asked again."""
    engine = upgraded(tmp_path, {"model_search": True, download: True})

    assert destinations(engine) == {HUGGINGFACE: 1}


def test_a_refused_half_carries_nothing(tmp_path: Path) -> None:
    """A refusal is a half that was not given."""
    engine = upgraded(tmp_path, {"model_search": True, "model_download": False})

    assert destinations(engine) == {}


def test_an_answer_already_given_for_the_host_wins(tmp_path: Path) -> None:
    """From v2.0.3 the host can be answered directly; an older grant must not
    overturn that answer."""
    engine = upgraded(
        tmp_path,
        {HUGGINGFACE: False, "model_search": True, "model_download": True},
    )

    assert destinations(engine) == {HUGGINGFACE: 0}


def test_other_hosts_are_untouched(tmp_path: Path) -> None:
    """Only the three old names are this revision's business."""
    engine = upgraded(tmp_path, {"host:api.provider.example": True})

    assert destinations(engine) == {"host:api.provider.example": 1}


def test_downgrade_keeps_the_host_grant(tmp_path: Path) -> None:
    """The app at 0026 reads only host names, and a merged row cannot say
    which old name it came from."""
    engine = upgraded(tmp_path, {"model_search": True, "model_download": True})

    command.downgrade(_config(engine), "0026")

    assert destinations(engine) == {HUGGINGFACE: 1}


def test_an_install_upgrading_from_v2_0_2_is_left_clean(tmp_path: Path) -> None:
    """v2.0.2 stored `ollama_pull` and `image_model_pull`; 0012 renames the
    first, and neither covered search."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0011")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO egress_destinations(destination, enabled) "
                "VALUES ('ollama_pull', 1), ('image_model_pull', 1)"
            )
        )

    command.upgrade(config, "head")

    assert destinations(engine) == {}
