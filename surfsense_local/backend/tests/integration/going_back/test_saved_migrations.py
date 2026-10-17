"""A release leaves its migrations where an older release can find them."""

from pathlib import Path

import pytest

from shared.going_back.saved_migrations import save_migrations
from tests.integration.going_back.newer_app import ALEMBIC

pytestmark = pytest.mark.integration


def test_every_migration_is_saved_beside_the_database(tmp_path: Path) -> None:
    """An older release reads them from the data folder."""
    migrations = tmp_path / "migrations"

    save_migrations(migrations)

    shipped = {
        path.name: path.read_bytes() for path in (ALEMBIC / "versions").glob("*.py")
    }
    saved = {path.name: path.read_bytes() for path in migrations.iterdir()}
    assert saved == shipped


def test_scripts_a_later_release_saved_are_kept(tmp_path: Path) -> None:
    """Going back further, later, still needs them."""
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    later = migrations / "9999_later.py"
    later.write_text("revision = '9999'\n", encoding="utf-8")

    save_migrations(migrations)

    assert later.read_text(encoding="utf-8") == "revision = '9999'\n"


async def test_the_api_saves_them_when_it_starts(data_dir: Path, base_url: str) -> None:
    """Every start, so a release that was never upgraded through still leaves them."""
    shipped = {path.name for path in (ALEMBIC / "versions").glob("*.py")}

    assert {path.name for path in (data_dir / "migrations").iterdir()} == shipped
