"""Freeze the API and worker into onedir binaries for the installer.

Run with `uv run scripts/build_binaries.py`. Emits dist/api/ and dist/worker/,
which electron-builder copies into the app's resources/. PyInstaller cannot
cross-compile, so this runs once per OS, on that OS.
"""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
BUNDLING = BACKEND / "bundling"
SPECS = ("api.spec", "worker.spec")


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
    for spec in SPECS:
        build(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
