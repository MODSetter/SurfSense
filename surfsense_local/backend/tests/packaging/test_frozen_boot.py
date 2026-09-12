"""Freeze a minimal binary and confirm the packaged app opens its own database."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

BACKEND = Path(__file__).resolve().parents[2]

# Frozen entry: open the DB, round-trip a vector, print the verdict.
ENTRY = """\
import struct, sys, tempfile
from pathlib import Path

from shared.config import get_search_settings
from shared.db import create_db_engine
from shared.migrations import upgrade_to_head

dim = get_search_settings().embedding_dimension
path = Path(tempfile.gettempdir()) / "surfsense-frozen-check.db"
path.unlink(missing_ok=True)

engine = create_db_engine(path)
upgrade_to_head(engine)

vector = struct.pack(f"{dim}f", *([0.1] * dim))
with engine.begin() as conn:
    conn.exec_driver_sql(
        "INSERT INTO chunk_vectors(rowid, embedding) VALUES (1, ?)", (vector,)
    )
    conn.exec_driver_sql(
        "SELECT distance FROM chunk_vectors "
        "WHERE embedding MATCH ? ORDER BY distance LIMIT 1",
        (vector,),
    ).scalar_one()

sys.stdout.write(f"frozen={getattr(sys, 'frozen', False)} vec0-ok dim={dim}\\n")
"""


def test_the_frozen_binary_opens_its_database(tmp_path: Path) -> None:
    """Freeze the entry and assert the binary opened the database."""
    entry = tmp_path / "boot.py"
    entry.write_text(ENTRY)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(entry),
            "--name",
            "frozen_check",
            "--onedir",
            "--noconfirm",
            "--distpath",
            str(tmp_path / "dist"),
            "--workpath",
            str(tmp_path / "build"),
            "--specpath",
            str(tmp_path),
            # so import shared.* resolves
            "--paths",
            str(BACKEND),
            # vec0.so: loaded by path, dropped otherwise
            "--collect-all",
            "sqlite_vec",
            # version scripts: scanned by path, dropped otherwise
            "--add-data",
            f"{BACKEND / 'alembic'}{os.pathsep}alembic",
            # named only inside env.py, which is data
            "--hidden-import",
            "alembic.context",
            "--hidden-import",
            "alembic.runtime.migration",
            "--hidden-import",
            "alembic.runtime.environment",
        ],
        cwd=BACKEND,
        check=True,
        capture_output=True,
        text=True,
    )

    binary = tmp_path / "dist" / "frozen_check" / "frozen_check"
    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)

    assert "frozen=True" in result.stdout
    assert "vec0-ok" in result.stdout
