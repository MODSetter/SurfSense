"""Copy LibreOffice.app out of TDF's disk image, unchanged, so its seal stays valid."""

import subprocess
import tempfile
from pathlib import Path

HDIUTIL_SECONDS = 10 * 60


def unpack_dmg(dmg: Path, into: Path) -> Path:
    """Copy the app into `into` and return the path of LibreOffice.app."""
    into.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as mount:
        subprocess.run(
            [
                "hdiutil",
                "attach",
                "-nobrowse",
                "-readonly",
                "-noautoopen",
                "-mountpoint",
                mount,
                str(dmg),
            ],
            check=True,
            timeout=HDIUTIL_SECONDS,
            stdout=subprocess.DEVNULL,
        )
        try:
            # ditto keeps extended attributes and the code signature as they are.
            subprocess.run(
                [
                    "ditto",
                    str(Path(mount) / "LibreOffice.app"),
                    str(into / "LibreOffice.app"),
                ],
                check=True,
                timeout=HDIUTIL_SECONDS,
            )
        finally:
            subprocess.run(
                ["hdiutil", "detach", "-force", mount],
                check=False,
                timeout=HDIUTIL_SECONDS,
                stdout=subprocess.DEVNULL,
            )
    return into / "LibreOffice.app"
