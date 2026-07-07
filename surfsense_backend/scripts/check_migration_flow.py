"""Self-check for the alembic fast-forward/adoption flow in alembic/env.py.

Verifies ``alembic upgrade head`` succeeds on the three DB states it must
handle without replaying pre-workspace-rename history against a
workspace-shape schema:

  1. fresh   -- empty database (fast-forward: create_all + stamp head)
  2. bootstrap -- create_all-created schema + zero_publication, no alembic
     history (adoption: stamp head)
  3. midcrash -- bootstrap schema whose alembic_version is stuck at a
     pre-rename revision from a failed replay (adoption: stamp head)

Run:  python scripts/check_migration_flow.py
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

ADMIN_URL = os.getenv(
    "ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
SCRATCH_DB = "surfsense_check_migration_flow"
SCRATCH_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{SCRATCH_DB}"
SCRATCH_URL_ASYNC = SCRATCH_URL.replace("postgresql://", "postgresql+asyncpg://")


async def recreate_scratch_db() -> None:
    import asyncpg

    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
    await admin.execute(f'CREATE DATABASE "{SCRATCH_DB}"')
    await admin.close()


async def drop_scratch_db() -> None:
    import asyncpg

    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
    await admin.close()


def run_alembic_upgrade() -> None:
    env = dict(os.environ, DATABASE_URL=SCRATCH_URL_ASYNC)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
    )


async def bootstrap_schema() -> None:
    """Mimic app startup bootstrap: create_all + ensure_publication, no stamp."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.db import Base
    from app.zero_publication import ensure_publication

    engine = create_async_engine(SCRATCH_URL_ASYNC)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_publication)
    await engine.dispose()


async def set_version(version: str | None) -> None:
    import asyncpg

    conn = await asyncpg.connect(SCRATCH_URL)
    if version is None:
        await conn.execute("DROP TABLE IF EXISTS alembic_version")
    else:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS alembic_version ("
            "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
        await conn.execute("DELETE FROM alembic_version")
        await conn.execute(
            "INSERT INTO alembic_version (version_num) VALUES ($1)", version
        )
    await conn.close()


async def assert_at_head() -> None:
    import asyncpg

    from alembic.script import ScriptDirectory

    head = ScriptDirectory(str(BACKEND_DIR / "alembic")).get_current_head()
    conn = await asyncpg.connect(SCRATCH_URL)
    version = await conn.fetchval("SELECT version_num FROM alembic_version")
    workspaces = await conn.fetchval("SELECT to_regclass('workspaces')")
    publication = await conn.fetchval(
        "SELECT 1 FROM pg_publication WHERE pubname = 'zero_publication'"
    )
    await conn.close()
    assert version == head, f"expected version {head}, got {version}"
    assert workspaces, "workspaces table missing"
    assert publication, "zero_publication missing"


async def main() -> None:
    try:
        # 1. Fresh empty DB -> fast-forward.
        await recreate_scratch_db()
        run_alembic_upgrade()
        await assert_at_head()
        print("OK: fresh DB fast-forwards to head")

        # 2. Bootstrap-created schema, no alembic history -> adoption.
        await recreate_scratch_db()
        await bootstrap_schema()
        await set_version(None)
        run_alembic_upgrade()
        await assert_at_head()
        print("OK: bootstrap-created schema adopted (stamped head)")

        # 3. Bootstrap schema stuck at a pre-rename revision -> adoption.
        await set_version("4")
        run_alembic_upgrade()
        await assert_at_head()
        print("OK: pre-rename stuck revision adopted (stamped head)")

        # Re-run must be a clean no-op.
        run_alembic_upgrade()
        await assert_at_head()
        print("OK: repeat upgrade is a no-op")
    finally:
        await drop_scratch_db()


asyncio.run(main())
