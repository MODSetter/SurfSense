"""The vec0 table an index's vectors live in.

Its name comes from a database row and is spliced into SQL, so it is checked
against a fixed shape first.
"""

import re

from sqlalchemy import Connection, text

_NAME = re.compile(r"^chunk_vectors(_[0-9]+)?$")
_DECLARED_WIDTH = re.compile(r"float\[(\d+)\]")


def checked(name: str) -> str:
    if not _NAME.fullmatch(name):
        raise ValueError(f"not a vector table name: {name!r}")
    return name


def declared_width(connection: Connection, name: str) -> int | None:
    """The width the table was created with, or None if it does not exist."""
    schema = connection.execute(
        text("SELECT sql FROM sqlite_master WHERE name = :name"),
        {"name": checked(name)},
    ).scalar_one_or_none()
    return None if schema is None else int(_DECLARED_WIDTH.search(schema).group(1))
