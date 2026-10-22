"""The frozen backend packaging tests run: the release build's, or one frozen here.

SURFSENSE_TEST_FROZEN_BACKEND names a binary already frozen, as the release
workflow's; without it the spec is frozen into the given folder.
"""

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def frozen_backend(build: Path) -> Path:
    """The frozen executable, without its .exe suffix."""
    if shipped := os.environ.get("SURFSENSE_TEST_FROZEN_BACKEND"):
        return Path(shipped).resolve()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(BACKEND / "bundling" / "backend.spec"),
            "--noconfirm",
            "--distpath",
            str(build / "dist"),
            "--workpath",
            str(build / "build"),
        ],
        cwd=BACKEND,
        check=True,
        capture_output=True,
        text=True,
        # A freeze takes 10 to 20 minutes; past an hour it is stuck.
        timeout=3600,
    )
    return build / "dist" / "backend" / "surfsense-backend"
