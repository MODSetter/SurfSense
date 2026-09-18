import asyncio
import enum
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import sqlite_vec
from sqlalchemy import (
    Connection,
    DateTime,
    Engine,
    Enum,
    MetaData,
    TypeDecorator,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from shared.sqlite import enable_wal

# SQLite is the only backend that lets constraints stay unnamed, and Alembic's
# batch mode cannot drop what it cannot name. Retrofitting this later would not
# match the names already on disk, so it has to hold from the first migration.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UtcDateTime(TypeDecorator[datetime]):
    """SQLite keeps no offset: rows hold UTC wall time (func.now() is UTC), so a
    value read back is stamped UTC. Serialised with its offset, the client stops
    reading it as local time. Aware values written are converted to UTC first."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, _dialect: Any
    ) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(
        self, value: datetime | None, _dialect: Any
    ) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar = {datetime: UtcDateTime}


def import_models() -> None:
    """Import every model, before anything asks SQLAlchemy to map them.

    A relationship names its target as a string, so an unimported model is a
    name that cannot resolve.
    """
    import modules.artifacts.models
    import modules.chat.models
    import modules.chunks.models
    import modules.documents.models
    import modules.egress.models
    import modules.license.models
    import modules.llm.models
    import modules.workspaces.models


def text_enum(members: type[enum.Enum]) -> Enum:
    """SQLite has no enum type, so store the values behind a CHECK constraint."""
    return Enum(
        members,
        native_enum=False,
        # Off by default since SQLAlchemy 1.4, which would leave the column a
        # bare VARCHAR that accepts anything.
        create_constraint=True,
        values_callable=lambda column: [member.value for member in column],
    )


def _apply_pragmas(dbapi_connection: Any, _record: Any) -> None:
    # pysqlite otherwise autocommits DDL, stranding a migration that dies midway.
    dbapi_connection.isolation_level = None

    # Not built into SQLite: without it vec0 does not exist.
    dbapi_connection.enable_load_extension(True)
    sqlite_vec.load(dbapi_connection)
    dbapi_connection.enable_load_extension(False)

    cursor = dbapi_connection.cursor()
    # First, so what follows waits for a concurrent writer instead of failing.
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()
    enable_wal(dbapi_connection)


# The API sets this for the span of one request. Waiting for the write lock on
# the event loop would stall every request, including the one about to release
# it, so a transaction opened there is a programming error, not a slow path.
serving_request: ContextVar[bool] = ContextVar("serving_request", default=False)


def _on_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _begin(connection: Connection) -> None:
    if serving_request.get() and _on_event_loop():
        raise RuntimeError(
            "SQLite transaction opened on the event loop; "
            "run session work through api.dependencies.transact"
        )
    # Take the write lock up front: a read-then-write transaction then waits on
    # busy_timeout instead of failing at once with SQLITE_BUSY_SNAPSHOT. The
    # price is that no transaction may stay open across a slow call (a model,
    # a probe, a stream), which is what the guard above and transact() enforce.
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def create_db_engine(path: Path) -> Engine:
    """Build an engine for one SQLite file, creating its directory if new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite+pysqlite:///{path}")
    event.listen(engine, "connect", _apply_pragmas)
    event.listen(engine, "begin", _begin)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
