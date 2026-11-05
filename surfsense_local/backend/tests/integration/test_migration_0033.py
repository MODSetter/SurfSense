"""Revision 0033: a firm's settings for each job, kept across its runs."""

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


def test_job_settings_come_and_go_with_the_revision(tmp_path: Path) -> None:
    """The table takes a job's settings, and goes again on downgrade."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = _config(engine)
    command.upgrade(config, "0033")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO job_settings(job, settings, checker) "
                """VALUES ('security-questionnaire', '{"provider_na": true}', NULL)"""
            )
        )
        stored = connection.execute(
            text("SELECT settings, updated_at FROM job_settings")
        ).one()

    assert stored.settings == '{"provider_na": true}' and stored.updated_at

    command.downgrade(config, "0032")
    assert "job_settings" not in inspect(engine).get_table_names()
