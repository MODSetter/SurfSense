from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from alembic import command
from modules.embedding.active import active_index
from modules.embedding.vector_table import declared_width

_REVISIONS = Path(__file__).resolve().parent.parent / "alembic"


def upgrade_to_head(engine: Engine) -> None:
    """Apply pending migrations. The API runs this; besides locking the embedder,
    nothing else in the app emits DDL."""
    config = _config()
    config.attributes["engine"] = engine
    command.upgrade(config, "head")

    _check_embedding_width(engine)


def is_migrated(engine: Engine) -> bool:
    """Whether the database is at this code's latest revision."""
    head = ScriptDirectory.from_config(_config()).get_current_head()
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision() == head


def _config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(_REVISIONS))
    return config


def _check_embedding_width(engine: Engine) -> None:
    """Refuse an index whose table cannot hold the vectors its model makes.

    Embeddings of another width are not merely the wrong shape, they are
    unrelated numbers, so the app stops rather than search what survived.
    """
    with Session(engine) as session:
        index = active_index(session)
        if index is None:
            return  # Onboarding has not chosen yet.
        found = declared_width(session.connection(), index.vector_table)

    if found != index.spec.dimension:
        raise RuntimeError(
            f"{index.vector_table} holds {found}-dimension vectors but "
            f"{index.spec.id} makes {index.spec.dimension}."
        )
