"""Celery tasks package."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import config

_celery_engine = None
_celery_session_maker = None


def get_celery_session_maker() -> async_sessionmaker:
    """Return a shared async session maker for Celery tasks.

    A single NullPool engine is created per worker process and reused
    across all task invocations to avoid leaking engine objects.
    """
    global _celery_engine, _celery_session_maker
    if _celery_session_maker is None:
        _celery_engine = create_async_engine(
            config.DATABASE_URL,
            poolclass=NullPool,
            echo=False,
        )
        _celery_session_maker = async_sessionmaker(
            _celery_engine, expire_on_commit=False
        )
    return _celery_session_maker
