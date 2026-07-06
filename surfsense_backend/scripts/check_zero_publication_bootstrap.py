"""Self-check for ensure_publication on a create_all-bootstrapped scratch DB."""

import asyncio

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

SCRATCH_DB = "surfsense_zero_pub_check"
ADMIN_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"
SCRATCH_URL = f"postgresql+asyncpg://postgres:postgres@localhost:5432/{SCRATCH_DB}"


async def main() -> None:
    admin = await asyncpg.connect(ADMIN_DSN)
    await admin.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
    await admin.execute(f'CREATE DATABASE "{SCRATCH_DB}"')
    await admin.close()

    from app.db import Base
    from app.zero_publication import ensure_publication, verify_publication

    engine = create_async_engine(SCRATCH_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(ensure_publication)
            mismatches = await conn.run_sync(verify_publication)
            assert not mismatches, f"shape wrong after ensure: {mismatches}"

            # Second call must be a no-op that leaves a verified shape.
            await conn.run_sync(ensure_publication)
            mismatches = await conn.run_sync(verify_publication)
            assert not mismatches, f"shape wrong after re-ensure: {mismatches}"
    finally:
        await engine.dispose()
        admin = await asyncpg.connect(ADMIN_DSN)
        await admin.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
        await admin.close()

    print("OK: ensure_publication creates and verifies on a create_all DB, idempotently.")


asyncio.run(main())
