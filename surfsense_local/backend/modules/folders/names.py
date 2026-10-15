import unicodedata
from typing import Annotated

from pydantic import StringConstraints

FolderName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


def name_key(name: str, *, case_sensitive: bool = False) -> str:
    """The key sibling names are unique by.

    Folded in Python because SQLite's NOCASE folds ASCII only: 'É' and 'é'
    would be two folders. The Library is always case-insensitive.
    """
    normalized = unicodedata.normalize("NFC", name)
    return normalized if case_sensitive else normalized.casefold()
