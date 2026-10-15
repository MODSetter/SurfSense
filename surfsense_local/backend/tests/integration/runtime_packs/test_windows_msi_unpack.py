"""TDF's pinned Windows MSI unpacks without installing anything, and the result converts.

Opt-in: SURFSENSE_TEST_OFFICE_MSI names a downloaded copy of the pinned MSI
(358 MB); the unpacked tree takes about 1.2 GB for the test's duration.
"""

import hashlib
import os
import sys
import time
from pathlib import Path

import docx
import pytest

from modules.runtime_packs.office.pin import FILES
from modules.runtime_packs.office.program import program_in
from modules.runtime_packs.office.runtime import OfficeRuntime
from modules.runtime_packs.office.soffice.convert import convert
from modules.runtime_packs.office.soffice.version import report_version
from modules.runtime_packs.office.unpack.windows_msi import unpack_msi

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows MSI"),
]


@pytest.fixture
def pinned_msi() -> Path:
    """The pinned MSI the seam names, after checking it is the pinned file."""
    named = os.environ.get("SURFSENSE_TEST_OFFICE_MSI")
    if not named:
        pytest.skip("set SURFSENSE_TEST_OFFICE_MSI to the downloaded pinned MSI")
    msi = Path(named)
    digest = hashlib.sha256(msi.read_bytes()).hexdigest()
    assert digest == FILES["windows-x64"].sha256
    return msi


def test_the_pinned_msi_unpacks_into_a_folder_that_converts(
    pinned_msi: Path, tmp_path: Path
) -> None:
    """No copy of the package is left beside the files, and the version is the pinned one."""
    root = unpack_msi(pinned_msi, tmp_path / "staging")
    assert program_in(root).is_file()
    assert not (root / pinned_msi.name).exists()

    office = OfficeRuntime(program_in(root), FILES["windows-x64"].version, "pack")
    deadline = time.monotonic() + 180
    assert report_version(office, deadline=deadline) == FILES["windows-x64"].version
    source = tmp_path / "a.docx"
    document = docx.Document()
    document.add_paragraph("Pinned build check")
    document.save(source)
    pdf = convert(source, "pdf", tmp_path / "out", deadline=deadline, runtime=office)
    assert pdf.read_bytes().startswith(b"%PDF-")
