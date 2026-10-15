"""What a live case reads from a PDF the agent made, checked on PDFs made here."""

import io

import pytest
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from tests.live.pdf_file import PdfFile

pytestmark = pytest.mark.unit


def _pdf(*story) -> bytes:
    out = io.BytesIO()
    SimpleDocTemplate(out).build(list(story))
    return out.getvalue()


def test_it_counts_pages_and_reads_their_text() -> None:
    """A case asking for one page counts what the PDF holds."""
    styles = getSampleStyleSheet()
    data = _pdf(
        Paragraph("Client brief", styles["Title"]),
        PageBreak(),
        Paragraph("Costs", styles["Heading1"]),
    )

    pdf = PdfFile(data)

    assert pdf.pages == 2
    assert "Client brief" in pdf.text and "Costs" in pdf.text


def test_bold_text_is_each_run_set_in_a_bold_font() -> None:
    """ReportLab has no bold flag: a run is bold when its font is a bold face."""
    styles = getSampleStyleSheet()
    table = Table([["Item", "Cost"], ["Total", "47,300 EUR"]])
    table.setStyle(TableStyle([("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold")]))
    data = _pdf(Paragraph("A <b>firm</b> price", styles["BodyText"]), table)

    pdf = PdfFile(data)

    assert pdf.bold_text == ["firm", "Total 47,300 EUR"]


def test_headings_are_the_lines_set_larger_than_the_body() -> None:
    """ReportLab tags nothing as a heading; its heading styles are larger than body text."""
    styles = getSampleStyleSheet()
    table = Table([["Owner", "Action"], ["CEO", "Approve the band"]])
    data = _pdf(
        Paragraph("Board update", styles["Title"]),
        Paragraph("Results", styles["Heading1"]),
        Paragraph("Revenue rose 18% on a year ago, ahead of plan.", styles["BodyText"]),
        Paragraph("<b>Margin</b> fell two points.", styles["BodyText"]),
        PageBreak(),
        Paragraph("Decisions needed", styles["Heading2"]),
        table,
    )

    pdf = PdfFile(data)

    assert pdf.headings == ["Board update", "Results", "Decisions needed"]
