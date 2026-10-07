"""LibreOffice from the Office pack, or the install the user confirmed, as an OfficeEngine."""

import datetime
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from modules.office_support.engine import CellValue, OfficeRunError, WorkbookValues
from modules.runtime_packs.office.runtime import (
    OfficeRuntime,
    OfficeUnavailable,
    office_runtime,
)
from modules.runtime_packs.office.soffice import errors
from modules.runtime_packs.office.soffice.convert import convert
from modules.runtime_packs.office.soffice.recalc import recalc


class PackedLibreOffice:
    """The runner converts a neutralized copy, so the file a caller names is only read."""

    def __init__(self, runtime: OfficeRuntime) -> None:
        self._runtime = runtime
        self.name = f"LibreOffice {runtime.version}"

    def pdf_of(self, file: Path, *, deadline: float) -> bytes:
        with tempfile.TemporaryDirectory(prefix="surfsense-office-") as out:
            with _as_sentences():
                pdf = convert(
                    file, "pdf", Path(out), deadline=deadline, runtime=self._runtime
                )
            return pdf.read_bytes()

    def values_of(self, workbook: Path, *, deadline: float) -> WorkbookValues:
        with _as_sentences():
            recalculated = recalc(workbook, deadline=deadline, runtime=self._runtime)
        # A cell LibreOffice computed to an error is left out, so it stays blank.
        return {
            sheet: {
                cell: plain
                for cell, value in cells.items()
                if (plain := _plain(value)) is not None
            }
            for sheet, cells in recalculated.values.items()
        }


def packed_libreoffice() -> PackedLibreOffice | None:
    """The LibreOffice Settings turned on, or None while Office support is off."""
    runtime = office_runtime()
    if isinstance(runtime, OfficeUnavailable):
        return None
    return PackedLibreOffice(runtime)


@contextmanager
def _as_sentences() -> Iterator[None]:
    """The runner's errors as the sentence a feature's report carries."""
    try:
        yield
    except errors.OfficeBusy as error:
        raise OfficeRunError("LibreOffice was busy with another file.") from error
    except errors.OfficeTimeout as error:
        raise OfficeRunError("LibreOffice did not finish in time.") from error
    except errors.OfficeMissing as error:
        raise OfficeRunError("Office support was turned off.") from error
    except errors.OfficeError as error:
        raise OfficeRunError(f"LibreOffice could not convert it: {error}") from error


def _plain(value: object) -> CellValue | None:
    """A value a cell can cache; a date is its serial number, as Excel stores it."""
    # Only the worker recalculates; the API binary carries no openpyxl.
    from openpyxl.utils.datetime import to_excel

    if isinstance(value, datetime.datetime | datetime.date | datetime.time):
        return to_excel(value)
    if isinstance(value, bool | int | float | str):
        return value
    return None
