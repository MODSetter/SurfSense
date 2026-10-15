"""Unpack TDF's MSI as an administrative image: its files in a folder, nothing installed.

`msiexec /a` registers no product, writes no system folder and needs no
elevation (measured on 26.8.0: 36 s, unelevated).
"""

import subprocess
from pathlib import Path

# Generous: an administrative image of 26.8.0 took 36 s on the development machine.
MSIEXEC_SECONDS = 15 * 60
# ERROR_INSTALL_ALREADY_RUNNING: Windows runs one installation at a time.
_ANOTHER_INSTALL = 1618


class MsiFailedError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def unpack_msi(msi: Path, into: Path) -> Path:
    """Unpack into `into` and return the install root, which holds program/."""
    into.mkdir(parents=True, exist_ok=True)
    log = into.parent / f"{into.name}.msiexec.log"
    # One string: msiexec reads PROPERTY="value", which list quoting would wrap whole.
    command = f'msiexec.exe /a "{msi}" /qn TARGETDIR="{into}" /L*v "{log}"'
    try:
        done = subprocess.run(command, timeout=MSIEXEC_SECONDS, check=False)
    except subprocess.TimeoutExpired as timeout:
        raise MsiFailedError("unpack_timeout", "msiexec took too long") from timeout
    if done.returncode == _ANOTHER_INSTALL:
        raise MsiFailedError("another_install", "another installation is running")
    if done.returncode != 0:
        raise MsiFailedError("unpack_failed", f"msiexec exited with {done.returncode}")
    log.unlink(missing_ok=True)
    # An administrative image keeps a copy of the package beside the files.
    (into / msi.name).unlink(missing_ok=True)
    return into
