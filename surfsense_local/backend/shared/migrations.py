import re
from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, text

from alembic import command
from shared.config import get_search_settings

DECLARED_WIDTH = re.compile(r"float\[(\d+)\]")


def upgrade_to_head(engine: Engine) -> None:
    """Apply pending migrations. The only thing in the app allowed to emit DDL."""
    revisions = Path(__file__).resolve().parent.parent / "alembic"

    config = Config()
    config.set_main_option("script_location", str(revisions))
    config.attributes["engine"] = engine
    command.upgrade(config, "head")

    _check_embedding_width(engine)


def _check_embedding_width(engine: Engine) -> None:
    """Refuse a database whose vectors were written by a different model.

    Nothing here can be migrated: embeddings of another width are not merely the
    wrong shape, they are unrelated numbers. Search would return whatever
    survived, so the app stops and asks to be reindexed instead.
    """
    expected = get_search_settings().embedding_dimension
    with engine.connect() as connection:
        schema = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE name = 'chunk_vectors'")
        ).scalar_one()

    found = int(DECLARED_WIDTH.search(schema).group(1))
    if found != expected:
        raise RuntimeError(
            f"chunk_vectors holds {found}-dimension vectors but the configured "
            f"embedding model produces {expected}. Reindex before starting."
        )
