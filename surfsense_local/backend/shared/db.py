import enum
import importlib
import pkgutil
from pathlib import Path
from typing import Any

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
    """Register every slice's models before the first mapper is configured.

    Relationships name their target as a string, so a slice nobody imported is
    a name SQLAlchemy cannot resolve, and every query against a table that
    points at it fails at runtime.
    """
    import modules

    for found in pkgutil.walk_packages(modules.__path__, f"{modules.__name__}."):
        if found.name.endswith(".models"):
            importlib.import_module(found.name)


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
