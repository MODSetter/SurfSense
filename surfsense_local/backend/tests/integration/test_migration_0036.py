"""Revision 0036: saved OpenCode connections move to the Console's documented URLs."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, text

from alembic import command
from shared.db import create_db_engine

pytestmark = pytest.mark.integration
KEY = b"sealed key"


def _config(engine: Engine) -> Config:
    """Alembic pointed at this engine."""
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parents[2] / "alembic")
    )
    config.attributes["engine"] = engine
    return config


def _insert(engine: Engine, label: str, catalog_provider: str, base_url: str) -> None:
    """One connection row, straight into the table."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO provider_connections"
                "(label, provider, base_url, api_key_ciphertext, catalog_provider) "
                "VALUES (:label, 'openai_compatible', :url, :key, :provider)"
            ),
            {"label": label, "url": base_url, "key": KEY, "provider": catalog_provider},
        )


def _saved(engine: Engine) -> dict[str, tuple[str, bytes]]:
    """Each connection's URL and key, by label."""
    with engine.connect() as connection:
        return {
            row[0]: (row[1], row[2])
            for row in connection.execute(
                text(
                    "SELECT label, base_url, api_key_ciphertext "
                    "FROM provider_connections"
                )
            )
        }


@pytest.fixture
def at_0035(tmp_path: Path) -> Engine:
    """A database one revision short."""
    engine = create_db_engine(tmp_path / "surfsense.db")
    command.upgrade(_config(engine), "0035")
    return engine


def test_a_saved_default_moves_and_keeps_its_key(at_0035: Engine) -> None:
    """The old URLs are gone from OpenCode's docs, so they may stop answering."""
    _insert(at_0035, "zen", "opencode", "https://opencode.ai/zen/v1")
    _insert(at_0035, "go", "opencode-go", "https://opencode.ai/zen/go/v1")

    command.upgrade(_config(at_0035), "0036")

    assert _saved(at_0035) == {
        "zen": ("https://opencode.ai/inference/openai/v1", KEY),
        "go": ("https://opencode.ai/inference/go/openai/v1", KEY),
    }


def test_a_url_the_user_chose_stays(at_0035: Engine) -> None:
    """A proxy, or the same address under another provider, is the user's own."""
    _insert(at_0035, "proxy", "opencode", "https://proxy.example/zen/v1")
    _insert(at_0035, "custom", "custom", "https://opencode.ai/zen/v1")

    command.upgrade(_config(at_0035), "0036")

    assert _saved(at_0035) == {
        "proxy": ("https://proxy.example/zen/v1", KEY),
        "custom": ("https://opencode.ai/zen/v1", KEY),
    }
