from sqlalchemy import Engine

from alembic import context
from shared.config import get_storage_settings
from shared.db import create_db_engine

config = context.config


def _engine() -> Engine:
    """Reuse the app's engine when called in-process, so pragmas always match."""
    passed_in = config.attributes.get("engine")
    return passed_in or create_db_engine(get_storage_settings().database_path)


def run_migrations_offline() -> None:
    context.configure(
        url=str(_engine().url),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with _engine().connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
