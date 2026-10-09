"""Find a LibreOffice the user already has, and say whether SurfSense may run it.

Fixed install locations only: PATH and HKCU are writable by any process the
user runs. Snap and Flatpak installs are not looked at; their confinement hides
the data folder. Reads files only; the smoke runs when the user confirms.
"""

import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from modules.runtime_packs.office.pin import SUPPORTED_BRANCHES
from modules.runtime_packs.office.program import bootstrap_file, program_in, share_dir

# What TDF's installers put in share/extensions; anything else loads into every
# profile, SurfSense's included.
_BUNDLED_EXTENSION = re.compile(r"dict-[A-Za-z0-9-]+|nlpsolver|wiki-publisher")
_PRODUCT_KEY = re.compile(r"^ProductKey\s*=\s*LibreOffice\s+(\d+\.\d+)\s*$", re.M)


@dataclass(frozen=True)
class FoundOffice:
    """An install, and why it may not be used (None when it may)."""

    root: Path
    branch: str | None
    refusal: str | None

    @property
    def program(self) -> Path:
        return program_in(self.root)


def find_installed(
    candidates: Iterable[Path] | None = None, *, today: date | None = None
) -> FoundOffice | None:
    """The first install at a fixed location, vetted; None when there is none."""
    for root in candidates if candidates is not None else _fixed_locations():
        if program_in(root).is_file():
            return vet(root, today=today)
    return None


def vet(root: Path, *, today: date | None = None) -> FoundOffice:
    if not program_in(root).is_file():
        return FoundOffice(root, None, "program_missing")
    branch = _branch(root)
    if branch is None:
        return FoundOffice(root, None, "branch_unknown")
    ends = SUPPORTED_BRANCHES.get(branch)
    if ends is None:
        return FoundOffice(root, branch, "branch_unsupported")
    if (today or date.today()) > ends:
        return FoundOffice(root, branch, "branch_ended")
    if _has_shared_extensions(root):
        return FoundOffice(root, branch, "shared_extensions")
    return FoundOffice(root, branch, None)


def _branch(root: Path) -> str | None:
    try:
        text = bootstrap_file(root).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _PRODUCT_KEY.search(text)
    return match.group(1) if match else None


def _has_shared_extensions(root: Path) -> bool:
    share = share_dir(root)
    installed = share / "uno_packages" / "cache" / "uno_packages"
    if installed.is_dir() and any(installed.iterdir()):
        return True
    bundled = share / "extensions"
    return bundled.is_dir() and any(
        not _BUNDLED_EXTENSION.fullmatch(entry.name) for entry in bundled.iterdir()
    )


def _fixed_locations() -> list[Path]:
    if sys.platform == "win32":
        return [*_registered_windows_install(), _program_files() / "LibreOffice"]
    if sys.platform == "darwin":
        return [
            Path("/Applications/LibreOffice.app"),
            Path.home() / "Applications" / "LibreOffice.app",
        ]
    return [
        Path("/usr/lib/libreoffice"),
        Path("/usr/lib64/libreoffice"),
        *sorted(Path("/opt").glob("libreoffice*"), reverse=True),
    ]


def _program_files() -> Path:
    folder = os.environ.get("PROGRAMW6432") or os.environ.get("PROGRAMFILES")
    return Path(folder or r"C:\Program Files")


def _registered_windows_install() -> list[Path]:
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\LibreOffice\UNO\InstallPath"
        ) as key:
            program, _ = winreg.QueryValueEx(key, "")
    except OSError:
        return []
    # The value names the program folder.
    return [Path(program).parent]
