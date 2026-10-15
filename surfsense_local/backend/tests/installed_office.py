"""This machine's LibreOffice as Office support, named explicitly through the test seam.

SURFSENSE_TEST_LIBREOFFICE names the install folder, else the standard install
path is used. Never Office support's own choice: a developer's install may be
on an ended branch, which Settings would refuse.
"""

import os
import sys
from pathlib import Path

import pytest

from modules.office_support import engine
from modules.office_support.libreoffice import PackedLibreOffice
from modules.runtime_packs.office.detect import vet
from modules.runtime_packs.office.runtime import OfficeRuntime


def _installed_root() -> Path:
    named = os.environ.get("SURFSENSE_TEST_LIBREOFFICE")
    if named:
        return Path(named)
    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMW6432", r"C:\Program Files")) / "LibreOffice"
    if sys.platform == "darwin":
        return Path("/Applications/LibreOffice.app")
    return Path("/usr/lib/libreoffice")


def installed_libreoffice() -> PackedLibreOffice:
    """The installed LibreOffice as an engine; skips the test when there is none."""
    found = vet(_installed_root())
    if found.refusal == "program_missing":
        pytest.skip("no LibreOffice installed; set SURFSENSE_TEST_LIBREOFFICE")
    # Run whatever its branch, so reports name it as "LibreOffice 25.2".
    return PackedLibreOffice(
        OfficeRuntime(found.program, found.branch or "test", "installed")
    )


def installed_office_on(monkeypatch: pytest.MonkeyPatch) -> PackedLibreOffice:
    """Office support on, with this machine's LibreOffice as its runtime."""
    office = installed_libreoffice()
    monkeypatch.setattr(engine, "office_engine", lambda: office)
    return office
