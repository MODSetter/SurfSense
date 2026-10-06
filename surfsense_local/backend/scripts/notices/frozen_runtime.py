"""What freezing adds to both binaries beyond the app's own dependencies."""

import platform
import sysconfig
from pathlib import Path

# A dev dependency, so `uv export --no-dev` never names it, yet its bootloader ships.
PYINSTALLER = "pyinstaller"
PYINSTALLER_NOTE = (
    "Its bootloader runs inside the frozen API and worker binaries, under the GPL "
    "with PyInstaller's bootloader exception."
)


def interpreter_notice() -> dict[str, str]:
    """CPython, whose LICENSE.txt also covers the libraries its build bundles."""
    licence = Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt"
    return {
        "name": "CPython",
        "version": platform.python_version(),
        "tree": "python",
        "license": "PSF-2.0",
        "text": licence.read_text(encoding="utf-8").strip()
        if licence.is_file()
        else "",
        "note": "The interpreter and standard library frozen into the API and worker.",
    }
