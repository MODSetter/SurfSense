from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine

from alembic import command


def upgrade_to_head(engine: Engine) -> None:
    """Apply pending migrations. The only thing in the app allowed to emit DDL."""
    revisions = Path(__file__).resolve().parent.parent / "alembic"

    config = Config()
    config.set_main_option("script_location", str(revisions))
    config.attributes["engine"] = engine
    command.upgrade(config, "head")
