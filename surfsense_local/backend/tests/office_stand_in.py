"""LibreOffice played by a stand-in, so a feature's Office path runs where no Office pack is installed."""

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from modules.office_support import OfficeRunError, WorkbookValues, engine

NAME = "LibreOffice 26.8.1"


@dataclass
class StandInOffice:
    """Answers each call as told, and keeps what it was handed to read."""

    name: str = NAME
    pages: int = 5
    values: WorkbookValues = field(default_factory=dict)
    failure: str | None = None
    read: list[tuple[str, bytes]] = field(default_factory=list)
    deadlines: list[float] = field(default_factory=list)

    def pdf_of(self, file: Path, *, deadline: float) -> bytes:
        self.read.append((file.suffix, file.read_bytes()))
        self.deadlines.append(deadline)
        if self.failure is not None:
            raise OfficeRunError(self.failure)
        return pdf_of_pages(self.pages, "LibreOffice page")

    def values_of(self, workbook: Path, *, deadline: float) -> WorkbookValues:
        self.read.append((workbook.suffix, workbook.read_bytes()))
        self.deadlines.append(deadline)
        if self.failure is not None:
            raise OfficeRunError(self.failure)
        return self.values


def pdf_of_pages(pages: int, label: str) -> bytes:
    """An A4 PDF whose page k says "<label> k"."""
    out = BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    for number in range(1, pages + 1):
        drawing.drawString(72, 760, f"{label} {number}")
        drawing.showPage()
    drawing.save()
    return out.getvalue()


def office_on(monkeypatch: pytest.MonkeyPatch, **told: object) -> StandInOffice:
    """Office support on, with the stand-in as its LibreOffice."""
    office = StandInOffice(**told)  # type: ignore[arg-type]
    monkeypatch.setattr(engine, "office_engine", lambda: office)
    return office


def office_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Office support off, whatever this machine has installed."""
    monkeypatch.setattr(engine, "office_engine", lambda: None)
