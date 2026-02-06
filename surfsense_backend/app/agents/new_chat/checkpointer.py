"""
PostgreSQL-based checkpointer for LangGraph agents.

This module provides a persistent checkpointer using AsyncPostgresSaver
that stores conversation state in the PostgreSQL database.

Uses a connection pool (psycopg_pool.AsyncConnectionPool) to handle
connection lifecycle, health checks, and automatic reconnection,
preventing 'the connection is closed' errors in long-running deployments.
"""

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import config

logger = logging.getLogger(__name__)

# Global checkpointer instance (initialized lazily)
_checkpointer: AsyncPostgresSaver | None = None
_connection_pool: AsyncConnectionPool | None = None
_checkpointer_initialized: bool = False


def get_postgres_connection_string() -> str:
    """
    Convert the async DATABASE_URL to a sync postgres connection string for psycopg3.

    The DATABASE_URL is typically in format:
    postgresql+asyncpg://user:pass@host:port/dbname

    We need to convert it to:
    postgresql://user:pass@host:port/dbname
    """
    db_url = config.DATABASE_URL

    # Handle asyncpg driver prefix
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql://")

    # Handle other async prefixes
    if "+asyncpg" in db_url:
        return db_url.replace("+asyncpg", "")

    return db_url


async def _create_checkpointer() -> AsyncPostgresSaver:
    """
    Create a new AsyncPostgresSaver backed by a connection pool.

    The connection pool automatically handles:
    - Connection health checks before use
    - Reconnection when connections die (idle timeout, DB restart, etc.)
    - Connection lifecycle management (max_lifetime, max_idle)
    """
    global _connection_pool

    conn_string = get_postgres_connection_string()

    _connection_pool = AsyncConnectionPool(
        conninfo=conn_string,
        min_size=2,
        max_size=10,
        # Connections are recycled after 30 minutes to avoid stale connections
        max_lifetime=1800,
        # Idle connections are closed after 5 minutes
        max_idle=300,
        open=False,
        # Connection kwargs required by AsyncPostgresSaver:
        # - autocommit: required for .setup() to commit checkpoint tables
        # - prepare_threshold: disable prepared statements for compatibility
        # - row_factory: checkpointer accesses rows as dicts (row["column"])
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    await _connection_pool.open(wait=True)

    checkpointer = AsyncPostgresSaver(conn=_connection_pool)
    logger.info("[Checkpointer] Created AsyncPostgresSaver with connection pool")
    return checkpointer


async def get_checkpointer() -> AsyncPostgresSaver:
    """
    Get or create the global AsyncPostgresSaver instance.

    This function:
    1. Creates the checkpointer with a connection pool if it doesn't exist
    2. Sets up the required database tables on first call
    3. Returns the cached instance on subsequent calls

    The underlying connection pool handles reconnection automatically,
    so a stale/closed connection will not cause OperationalError.

    Returns:
        AsyncPostgresSaver: The configured checkpointer instance
    """
    global _checkpointer, _checkpointer_initialized

    if _checkpointer is None:
        _checkpointer = await _create_checkpointer()
        _checkpointer_initialized = False

    # Setup tables on first call (idempotent)
    if not _checkpointer_initialized:
        await _checkpointer.setup()
        _checkpointer_initialized = True

    return _checkpointer


async def setup_checkpointer_tables() -> None:
    """
    Explicitly setup the checkpointer tables.

    This can be called during application startup to ensure
    tables exist before any agent calls.
    """
    await get_checkpointer()
    logger.info("[Checkpointer] PostgreSQL checkpoint tables ready")


async def close_checkpointer() -> None:
    """
    Close the checkpointer connection pool.

    This should be called during application shutdown.
    """
    global _checkpointer, _connection_pool, _checkpointer_initialized

    if _connection_pool is not None:
        await _connection_pool.close()
        logger.info("[Checkpointer] PostgreSQL connection pool closed")

    _checkpointer = None
    _connection_pool = None
    _checkpointer_initialized = False
