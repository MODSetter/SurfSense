"""Prove a LibreOffice runs before SurfSense relies on it: one small DOCX to PDF."""

import tempfile
import time
from pathlib import Path

from modules.runtime_packs.office.runtime import OfficeRuntime
from modules.runtime_packs.office.soffice.convert import convert

# A first run seeds a profile, which took 4.9 s for three files (measured).
SMOKE_SECONDS = 120


def smoke_test(runtime: OfficeRuntime) -> None:
    """Raises an OfficeError when the conversion does not produce a PDF."""
    import docx

    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "smoke.docx"
        document = docx.Document()
        document.add_paragraph("SurfSense Office support check")
        document.save(source)
        convert(
            source,
            "pdf",
            Path(folder) / "out",
            deadline=time.monotonic() + SMOKE_SECONDS,
            runtime=runtime,
        )
