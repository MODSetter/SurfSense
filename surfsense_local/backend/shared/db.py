import enum
from pathlib import Path
from typing import Any

import sqlite_vec
from sqlalchemy import Connection, Engine, Enum, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def import_models() -> None:
    """Import every model, before anything asks SQLAlchemy to map them.

    A relationship names its target as a string, so an unimported model is a
    name that cannot resolve.
    """
    import modules.artifacts.models
    import modules.chat.models
    import modules.chunks.models
    import modules.documents.models
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
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.close()


def _begin(connection: Connection) -> None:
    connection.exec_driver_sql("BEGIN")


def create_db_engine(path: Path) -> Engine:
    """Build an engine for one SQLite file, creating its directory if new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite+pysqlite:///{path}")
    event.listen(engine, "connect", _apply_pragmas)
    event.listen(engine, "begin", _begin)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
