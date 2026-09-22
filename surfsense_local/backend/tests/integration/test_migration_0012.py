"""Revision 0012: the one migration in this phase that touches user data.

Two things happen here and both are irreversible, so both are pinned:
a generation selection pointing at Ollama is cleared, and an `ollama_pull`
egress grant becomes `model_download` and nothing else.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from shared.db import create_db_engine

pytestmark = pytest.mark.integration


def upgraded(tmp_path: Path, seed: str) -> object:
    """A database seeded at 0011 and then upgraded to head."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    command.upgrade(config, "0011")
    with engine.begin() as connection:
        for statement in seed.strip().split(";"):
            if statement.strip():
                connection.execute(text(statement))
    command.upgrade(config, "head")
    return engine


def test_an_ollama_selection_is_cleared_rather_than_remapped(tmp_path: Path) -> None:
    """The weights are in a blob format the app no longer manages, so there is
    no honest way to point the selection at an equivalent file. Leaving it would
    make `resolve_generation()` raise and chat would simply die.
    """
    engine = upgraded(
        tmp_path,
        "INSERT INTO selected_models(role, provider, name) "
        "VALUES ('generation', 'ollama', 'qwen3:4b')",
    )

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT * FROM selected_models")).all()

    assert rows == []


def test_an_image_selection_is_untouched(tmp_path: Path) -> None:
    """sd-server is not part of this swap and its weights still exist."""
    engine = upgraded(
        tmp_path,
        "INSERT INTO selected_models(role, provider, name) "
        "VALUES ('image_generation', 'sdcpp', 'sd15')",
    )

    with engine.connect() as connection:
        selected = connection.execute(
            text("SELECT provider, name FROM selected_models")
        ).one()

    assert tuple(selected) == ("sdcpp", "sd15")


def test_the_provider_check_now_names_llamacpp(tmp_path: Path) -> None:
    """A selection the app can actually resolve must be insertable, and the
    provider this runtime registers under is the one the column allows."""
    engine = upgraded(tmp_path, "")

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO selected_models(role, provider, name) "
                "VALUES ('generation', 'llamacpp', 'Qwen3-8B-Q4_K_M')"
            )
        )
        selected = connection.execute(
            text("SELECT provider FROM selected_models")
        ).scalar_one()

    assert selected == "llamacpp"


def test_ollama_is_no_longer_an_allowed_provider(tmp_path: Path) -> None:
    """Nothing can resolve it, so the column should not accept it either."""
    from sqlalchemy.exc import IntegrityError

    engine = upgraded(tmp_path, "")

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO selected_models(role, provider, name) "
                "VALUES ('generation', 'ollama', 'qwen3:4b')"
            )
        )


def test_a_download_grant_carries_over_and_a_search_grant_is_not_invented(
    tmp_path: Path,
) -> None:
    """One host, two consents. Someone who allowed model downloads allowed
    fetching a file they named; search sends text they are typing to the same
    host for a different reason. Carrying the grant to both would manufacture
    a consent nobody gave.
    """
    engine = upgraded(
        tmp_path,
        "INSERT INTO egress_destinations(destination, enabled) "
        "VALUES ('ollama_pull', 1)",
    )

    with engine.connect() as connection:
        rows = dict(
            connection.execute(
                text("SELECT destination, enabled FROM egress_destinations")
            ).all()
        )

    assert rows.get("model_download") == 1
    assert "model_search" not in rows
    assert "ollama_pull" not in rows


def test_a_refused_download_stays_refused(tmp_path: Path) -> None:
    """Renaming a destination must not quietly grant what was declined."""
    engine = upgraded(
        tmp_path,
        "INSERT INTO egress_destinations(destination, enabled) "
        "VALUES ('ollama_pull', 0)",
    )

    with engine.connect() as connection:
        allowed = connection.execute(
            text(
                "SELECT enabled FROM egress_destinations "
                "WHERE destination = 'model_download'"
            )
        ).scalar_one()

    assert allowed == 0
