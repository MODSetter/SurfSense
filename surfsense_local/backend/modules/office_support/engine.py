"""The one door from SurfSense's features to LibreOffice, open only while Office support is on.

Every caller keeps its old path when `office_engine()` is None, and treats
an OfficeRunError as that path too, with the sentence added to its report.
"""

from pathlib import Path
from typing import Protocol

# A recalculated cell as openpyxl reads it back: dates are serial numbers.
CellValue = float | int | str | bool
# Sheet name, then the cell's coordinate such as "B7".
WorkbookValues = dict[str, dict[str, CellValue]]


class OfficeRunError(Exception):
    """LibreOffice was busy, ran out of time or failed, said in a sentence a report can carry."""


class OfficeEngine(Protocol):
    """LibreOffice as the features call it: each call reads a copy and never writes the file given."""

    # What a report names, such as "LibreOffice 26.8.1".
    name: str

    def pdf_of(self, file: Path, *, deadline: float) -> bytes:
        """The whole file as LibreOffice lays it out, by the monotonic `deadline`."""
        ...

    def values_of(self, workbook: Path, *, deadline: float) -> WorkbookValues:
        """Every formula's value once LibreOffice has recalculated the workbook."""
        ...


def office_engine() -> OfficeEngine | None:
    """LibreOffice when Office support is on and its runtime is in place; None otherwise."""
    from modules.office_support.libreoffice import packed_libreoffice

    return packed_libreoffice()
