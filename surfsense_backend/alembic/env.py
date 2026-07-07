import asyncio
import logging
import os
import sys
from logging.config import fileConfig

import sqlalchemy as sa
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from alembic.script import ScriptDirectory

# Ensure the app directory is in the Python path
# This allows Alembic to find your models
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

# Import your models base
from app.db import Base  # Assuming your Base is defined in app.db

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override SQLAlchemy URL from environment variables when available
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

MIGRATION_ADVISORY_LOCK_NAMESPACE = "surfsense"
MIGRATION_ADVISORY_LOCK_NAME = "alembic_migrations"

# Migration 170 renamed searchspaces -> workspaces, so a ``workspaces`` table
# can only exist once the schema is at revision >= 170. If it exists while the
# recorded revision is missing or still pre-170, the schema did not come from
# this migration history at all -- it was created by the startup bootstrap
# (``Base.metadata.create_all`` in ``app.db.create_db_and_tables``), which
# always builds the *current* model shape. Replaying history against such a
# schema fails (e.g. migration 5's ``ALTER COLUMN ... TYPE`` is rejected
# because the column already sits in zero_publication's column list), so the
# schema is adopted by stamping head instead.
BOOTSTRAP_MARKER_TABLE = "workspaces"
RENAME_REVISION = "170"


def _stamp_head(connection: Connection, script: ScriptDirectory) -> None:
    context.get_context().stamp(script, script.get_current_head())
    if connection.in_transaction():
        # The outer begin_transaction() is a no-op under
        # transaction_per_migration, so commit explicitly.
        connection.commit()


def _fast_forward_fresh_db(connection: Connection) -> bool:
    """Build a fresh (empty) DB at head via create_all instead of replaying.

    Historical migrations were written against the pre-workspace-rename
    schema (``searchspaces``, ``search_space_id``), while migration 0's
    ``create_all`` builds the *current* models -- so replaying the chain on a
    fresh DB crashes as soon as a migration touches a renamed object (first
    at migration 18). A fresh DB needs no history: create the head-shape
    schema directly, mirror migration 0's indexes, create the Zero
    publication, and stamp head. Replay remains only for legacy DBs that
    genuinely contain the old objects.

    ponytail: seed-data migrations (114/128 default prompts) are skipped on
    this path, same as always for create_all-bootstrapped DBs; the app copes
    with missing seeds. If seeds ever become mandatory, add a runtime seeding
    step rather than resurrecting the replay.
    """
    for table in ("documents", "searchspaces", BOOTSTRAP_MARKER_TABLE):
        if connection.execute(sa.text("SELECT to_regclass(:t)"), {"t": table}).scalar():
            return False
    if connection.execute(sa.text("SELECT to_regclass('alembic_version')")).scalar():
        current = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar()
        if current:
            return False

    logging.getLogger("alembic.env").info(
        "Fresh database detected: creating head-shape schema via create_all "
        "and stamping head instead of replaying migration history."
    )
    connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(bind=connection)
    # Same core indexes migration 0 created (runtime setup_indexes() adds the
    # rest concurrently on app boot).
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS document_vector_index ON documents "
            "USING hnsw (embedding public.vector_cosine_ops)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS document_search_index ON documents "
            "USING gin (to_tsvector('english', content))"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS chucks_vector_index ON chunks "
            "USING hnsw (embedding public.vector_cosine_ops)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS chucks_search_index ON chunks "
            "USING gin (to_tsvector('english', content))"
        )
    )

    from app.zero_publication import ensure_publication

    ensure_publication(connection)

    _stamp_head(connection, ScriptDirectory.from_config(config))
    return True


def _adopt_bootstrapped_schema(connection: Connection) -> bool:
    """Stamp head instead of replaying history on a create_all-created DB.

    Returns True when the schema was adopted (migrations must then be
    skipped for this run).

    ponytail: assumes the bootstrapped schema matches the checked-out models
    (true whenever the backend booted on this checkout, since create_all runs
    on every startup). If the checkout moved ahead without a backend boot,
    column-level drift from the skipped migrations is possible; the upgrade
    path is re-bootstrapping (boot the backend once) before stamping.
    """
    marker = connection.execute(
        sa.text("SELECT to_regclass(:t)"), {"t": BOOTSTRAP_MARKER_TABLE}
    ).scalar()
    if marker is None:
        return False

    # Guard against a legacy-shape DB that merely had missing tables filled in
    # by a later create_all: adoption requires the core tables to be in the
    # current (post-rename) shape too, not just the marker table to exist.
    documents_renamed = connection.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'documents' AND column_name = 'workspace_id'"
        )
    ).scalar()
    if not documents_renamed:
        return False

    current = None
    if connection.execute(sa.text("SELECT to_regclass('alembic_version')")).scalar():
        current = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar()

    script = ScriptDirectory.from_config(config)
    pre_rename_revisions = {
        rev.revision for rev in script.iterate_revisions(RENAME_REVISION, "base")
    } - {RENAME_REVISION}
    if current is not None and current not in pre_rename_revisions:
        # Genuinely migration-managed at >= 170; run migrations normally.
        return False

    logging.getLogger("alembic.env").info(
        "Adopting bootstrap-created schema (%r exists, recorded revision %r "
        "predates the workspace rename): stamping %s instead of replaying "
        "migration history.",
        BOOTSTRAP_MARKER_TABLE,
        current,
        script.get_current_head(),
    )
    _stamp_head(connection, script)
    return True


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        transaction_per_migration=True,
    )

    lock_params = {
        "namespace": MIGRATION_ADVISORY_LOCK_NAMESPACE,
        "name": MIGRATION_ADVISORY_LOCK_NAME,
    }
    connection.execute(
        sa.text("SELECT pg_advisory_lock(hashtext(:namespace), hashtext(:name))"),
        lock_params,
    )
    try:
        if not _fast_forward_fresh_db(connection) and not _adopt_bootstrapped_schema(
            connection
        ):
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connection.execute(
            sa.text("SELECT pg_advisory_unlock(hashtext(:namespace), hashtext(:name))"),
            lock_params,
        )


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
