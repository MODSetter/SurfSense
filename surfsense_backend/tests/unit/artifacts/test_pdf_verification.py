from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfWriter

from app.artifacts.verification.formats import pdf


class FakePage:
    def __init__(
        self,
        *,
        text: str = "A sufficiently long line of document text.",
        x: float = 100,
        y: float = 100,
        embedded: bool = True,
    ) -> None:
        self.text = text
        self.x = x
        self.y = y
        self.mediabox = SimpleNamespace(left=0, right=612, bottom=0, top=792)
        self.font = {
            "/BaseFont": "/Helvetica",
            "/FontDescriptor": {"/FontFile2": object()} if embedded else {},
        }

    def extract_text(self, visitor_text=None):
        if visitor_text:
            visitor_text(
                self.text,
                [1, 0, 0, 1, 0, 0],
                [1, 0, 0, 1, self.x, self.y],
                self.font,
                12,
            )
        return self.text


def _one_page_pdf() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


def test_pdf_checks_detect_unembedded_font(monkeypatch):
    monkeypatch.setattr(
        pdf,
        "PdfReader",
        lambda _stream: SimpleNamespace(pages=[FakePage(x=10, embedded=False)]),
    )

    result = pdf.check_pdf(b"%PDF")

    assert result.page_count == 1
    assert not result.clean
    assert any("unembedded fonts: /Helvetica" in finding for finding in result.findings)


def test_font_that_draws_no_text_is_not_flagged(monkeypatch):
    monkeypatch.setattr(
        pdf,
        "PdfReader",
        lambda _stream: SimpleNamespace(pages=[FakePage(text="   ", embedded=False)]),
    )

    result = pdf.check_pdf(b"%PDF")

    assert not any("unembedded" in finding for finding in result.findings)


def test_running_header_in_margin_is_not_a_structural_failure(monkeypatch):
    monkeypatch.setattr(
        pdf,
        "PdfReader",
        lambda _stream: SimpleNamespace(pages=[FakePage(x=10, y=780)]),
    )

    assert pdf.check_pdf(b"%PDF").clean


def test_pdf_check_reports_near_blank_page():
    result = pdf.check_pdf(_one_page_pdf())

    assert result.page_count == 1
    assert result.findings == (
        "page 1 is blank or near-blank (0 non-whitespace characters)",
    )


def test_pdf_check_reports_expected_page_mismatch():
    result = pdf.check_pdf(_one_page_pdf(), expected_pages=2, min_chars=0)

    assert result.findings == ("expected 2 page(s), found 1",)


def test_pdf_check_reports_empty_bytes():
    assert pdf.check_pdf(b"").findings == ("PDF is empty",)


def test_pdf_check_reports_malformed_bytes():
    result = pdf.check_pdf(b"not a PDF")

    assert "could not be parsed" in result.findings[0]
