"""Revision 0029: a plugin's last check can say why the license was refused."""

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


def _plugin_at_0028(tmp_path: Path) -> tuple[Engine, Config]:
    """A database at 0028 holding one plugin whose server could not be reached."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0028")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO installed_plugins"
                "(id, kind, source, url, publisher, entry, enabled, check_failure) "
                "VALUES ('notes', 'remote', 'custom', 'https://notes.example/mcp', "
                "'custom', '{}', 1, 'unreachable')"
            )
        )
    return engine, config


def _set_failure(engine: Engine, failure: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE installed_plugins SET check_failure = :failure"),
            {"failure": failure},
        )


def _failure(engine: Engine) -> str:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT check_failure FROM installed_plugins")
        ).scalar_one()


def test_a_connected_plugin_keeps_its_check_and_takes_a_license_reason(
    tmp_path: Path,
) -> None:
    """The table is rebuilt to widen its check, and no row is lost on the way."""
    engine, config = _plugin_at_0028(tmp_path)

    command.upgrade(config, "0029")

    assert _failure(engine) == "unreachable"
    _set_failure(engine, "license_expired")
    assert _failure(engine) == "license_expired"


def test_an_unknown_reason_is_still_refused(tmp_path: Path) -> None:
    """The column stays a closed set after the rebuild."""
    engine, config = _plugin_at_0028(tmp_path)
    command.upgrade(config, "0029")

    with pytest.raises(IntegrityError):
        _set_failure(engine, "license_lost")


def test_going_back_reads_a_license_reason_as_a_sign_in(tmp_path: Path) -> None:
    """0028 knows no license reasons; asking to sign in again is the nearest it has."""
    engine, config = _plugin_at_0028(tmp_path)
    command.upgrade(config, "0029")
    _set_failure(engine, "needs_license")

    command.downgrade(config, "0028")

    assert _failure(engine) == "sign_in"
