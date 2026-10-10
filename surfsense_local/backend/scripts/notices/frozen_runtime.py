"""What freezing adds to both binaries beyond the app's own dependencies."""

import platform
import sys
import sysconfig
from collections.abc import Sequence
from pathlib import Path

# A dev dependency, so `uv export --no-dev` never names it, yet its bootloader ships.
PYINSTALLER = "pyinstaller"
PYINSTALLER_NOTE = (
    "Its bootloader runs inside the frozen API and worker binaries, under the GPL "
    "with PyInstaller's bootloader exception."
)


def _licence_places() -> list[Path]:
    # python-build-standalone on Windows, as uv installs it, keeps LICENSE.txt in
    # the installation root rather than in Lib.
    return [Path(sysconfig.get_paths()["stdlib"]), Path(sys.base_prefix)]


def interpreter_notice(places: Sequence[Path] | None = None) -> dict[str, str]:
    """CPython, whose LICENSE.txt also covers the libraries its build bundles."""
    licences = [p / "LICENSE.txt" for p in places or _licence_places()]
    licence = next((p for p in licences if p.is_file()), None)
    return {
        "name": "CPython",
        "version": platform.python_version(),
        "tree": "python",
        "license": "PSF-2.0",
        "text": licence.read_text(encoding="utf-8").strip() if licence else "",
        "note": "The interpreter and standard library frozen into the API and worker.",
    }
