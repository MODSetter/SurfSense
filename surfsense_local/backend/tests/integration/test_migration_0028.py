"""Revision 0028: a plugin's last check can say why it failed, a refused license among them."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from shared.db import create_db_engine

pytestmark = pytest.mark.integration


def _at_0028(tmp_path: Path) -> Engine:
    """A database upgraded to 0028."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    command.upgrade(config, "0028")
    return engine


def _connect_plugin(engine: Engine, failure: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO installed_plugins"
                "(id, kind, source, url, entry, enabled, check_failure) "
                "VALUES ('reddit', 'remote', 'first_party', "
                "'https://plugins.surfsense.com/reddit/mcp', '{}', 1, :failure)"
            ),
            {"failure": failure},
        )


@pytest.mark.parametrize(
    "failure",
    ["needs_license", "license_expired", "license_revoked", "license_invalid"],
)
def test_a_check_can_say_the_license_was_refused(tmp_path: Path, failure: str) -> None:
    """Contract 2's reasons, as SurfSense's plugin host refuses a license."""
    engine = _at_0028(tmp_path)

    _connect_plugin(engine, failure)

    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT check_failure FROM installed_plugins")
            ).scalar_one()
            == failure
        )


def test_an_unknown_failure_is_refused(tmp_path: Path) -> None:
    """The column stays a closed set."""
    engine = _at_0028(tmp_path)

    with pytest.raises(IntegrityError):
        _connect_plugin(engine, "license_lost")
