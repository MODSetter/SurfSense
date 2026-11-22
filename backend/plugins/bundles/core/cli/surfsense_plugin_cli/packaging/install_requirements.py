"""Installs a plugin's pinned dependencies for one platform.

The one way both packaging and invoke install them, so what works on an
author's machine is installed the same way by a release.
"""

import subprocess
import sys
from pathlib import Path

from uv import find_uv_bin

from surfsense_plugin_cli.build_targets import build_targets


class DependenciesNotInstalled(Exception):
    """uv refused: its own words name the package, and this says for which system."""

    def __init__(self, platform: str, reason: str) -> None:
        super().__init__(
            f"the dependencies cannot be installed for {platform}, from prebuilt"
            f" wheels only:\n{reason}"
        )


def install_requirements(requirements: Path, platform: str, into: Path) -> None:
    """Prebuilt wheels only, every file's hash checked, for the app's Python."""
    targets = build_targets()
    finished = subprocess.run(
        [
            find_uv_bin(),
            "pip",
            "install",
            "--quiet",
            "--python",
            sys.executable,
            "--python-version",
            targets.python,
            "--python-platform",
            targets.platforms[platform],
            "--only-binary",
            ":all:",
            "--require-hashes",
            "--requirement",
            str(requirements),
            "--target",
            str(into),
        ],
        capture_output=True,
        text=True,
    )
    if finished.returncode != 0:
        raise DependenciesNotInstalled(platform, finished.stderr.strip())
