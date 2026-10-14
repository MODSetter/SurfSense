import sys
from pathlib import Path


def program_in(root: Path) -> Path:
    """The executable that waits for its conversion, inside a LibreOffice install.

    On Windows soffice.com, not soffice.exe, which detaches and returns 0 at once.
    On macOS `root` is LibreOffice.app.
    """
    if sys.platform == "win32":
        return root / "program" / "soffice.com"
    if sys.platform == "darwin":
        return root / "Contents" / "MacOS" / "soffice"
    return root / "program" / "soffice"


def bootstrap_file(root: Path) -> Path:
    """Where an install names its branch, as ProductKey=LibreOffice 26.8."""
    if sys.platform == "win32":
        return root / "program" / "bootstrap.ini"
    if sys.platform == "darwin":
        return root / "Contents" / "Resources" / "bootstraprc"
    return root / "program" / "bootstraprc"


def share_dir(root: Path) -> Path:
    if sys.platform == "darwin":
        return root / "Contents" / "Resources"
    return root / "share"
