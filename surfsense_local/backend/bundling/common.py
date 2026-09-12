"""Shared PyInstaller inputs for the API and worker specs.

it assembles the inputs both specs feed to PyInstaller
(the sqlite-vec extension and Alembic revisions), so a dependency bump cannot fix
one binary and quietly miss the other.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# bundling/ -> backend/. __file__ is defined here (unlike inside a .spec).
BACKEND = Path(__file__).resolve().parent.parent


def database_inputs() -> tuple[list, list, list]:
    """(datas, binaries, hiddenimports) to open the database in a frozen binary.

    Both pieces are reached by a path, not an import the analyser can follow:
    vec0 via load_extension from C, the revisions via Alembic reading the dir.
    """
    datas, binaries, hiddenimports = collect_all("sqlite_vec")
    datas.append((str(BACKEND / "alembic"), "alembic"))
    hiddenimports += [
        "alembic.context",
        "alembic.runtime.migration",
        "alembic.runtime.environment",
    ]
    return datas, binaries, hiddenimports
