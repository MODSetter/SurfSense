"""Freeze the backend into one onedir binary for the installer.

Run with `uv run scripts/build_binaries.py`. Emits dist/backend/, which
electron-builder copies into the app's resources/. PyInstaller cannot
cross-compile, so this runs once per OS, on that OS.
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

from linux_symbol_tables import strip_symbol_tables
from macos_local_symbols import strip_local_symbols

BACKEND = Path(__file__).resolve().parent.parent
BUNDLING = BACKEND / "bundling"
SPECS = ("backend.spec",)


def _require_sqlite_load_extension() -> None:
    """Refuse to freeze a Python that cannot load sqlite-vec.

    PyInstaller copies this interpreter's _sqlite3. python.org macOS builds
    omit enable_load_extension, and the packaged app then dies on migrate.
    """
    if not hasattr(sqlite3.connect(":memory:"), "enable_load_extension"):
        raise SystemExit(
            "This Python cannot load sqlite-vec "
            f"(no sqlite3.enable_load_extension; {sys.executable}). "
            "On macOS freeze with uv's Python, not python.org: "
            "UV_PYTHON_PREFERENCE=only-managed uv python install 3.12"
        )


def build(spec: str) -> None:
    name = spec.removesuffix(".spec")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(BUNDLING / spec),
            "--noconfirm",
            "--distpath",
            str(BACKEND / "dist"),
            "--workpath",
            str(BACKEND / "build" / name),
        ],
        cwd=BACKEND,
        check=True,
    )


def main() -> int:
    _require_sqlite_load_extension()
    for spec in SPECS:
        build(spec)
        internal = BACKEND / "dist" / spec.removesuffix(".spec") / "_internal"
        if sys.platform == "darwin":
            print(
                f"stripped local symbols from {strip_local_symbols(internal)} Mach-O files"
            )
        elif sys.platform == "linux":
            stripped, kept = strip_symbol_tables(internal)
            print(f"stripped symbol tables from {stripped} ELF files")
            for path in kept:
                print(f"kept unstripped, strip would misalign it: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
