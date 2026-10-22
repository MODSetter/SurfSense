"""The frozen worker's Docling reads a page exactly as the source tree does.

The bundle ships torch as bytecode and only the transformers models the
layout engine loads; neither may change what Docling reads. Layout, TableFormer and OCR all run here, which no import
check reaches. Needs the parser pack: SURFSENSE_LOCAL_MODELS_DIR, else
backend/models.
"""

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image as Picture
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from tests.packaging.frozen_backend import frozen_backend

pytestmark = pytest.mark.packaging

BACKEND = Path(__file__).resolve().parents[2]
MODELS = Path(os.environ.get("SURFSENSE_LOCAL_MODELS_DIR", BACKEND / "models"))

SCANNED_LINE = "Quarterly revenue grew in every region"


def _scanned_paragraph() -> Picture:
    """Text only as pixels, so the page needs OCR."""
    image = Image.new("L", (1600, 160), 255)
    try:
        font = ImageFont.truetype("arial.ttf", 56)
    except OSError:
        font = ImageFont.load_default(size=56)
    ImageDraw.Draw(image).text((30, 40), SCANNED_LINE, fill=0, font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return Picture(buffer, width=440, height=44)


def _page_with_a_table_and_a_scan(path: Path) -> Path:
    styles = getSampleStyleSheet()
    regions = ["North", "South", "East", "West", "Central", "Islands"]
    rows = [["Region", "Q1 sales", "Q2 sales", "Q3 sales", "Q4 sales"]] + [
        [name, *[str(100 + 7 * i + 3 * q) for q in range(4)]]
        for i, name in enumerate(regions)
    ]
    # Ruled and roomy: a small, sparse grid reads to the layout model as a picture.
    table = Table(rows, colWidths=[110, 80, 80, 80, 80], rowHeights=22)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    SimpleDocTemplate(str(path), pagesize=A4).build(
        [
            Paragraph("Sales by region", styles["Heading1"]),
            Paragraph(
                "The table below lists sales per quarter for every region we serve.",
                styles["BodyText"],
            ),
            Spacer(1, 12),
            table,
            Spacer(1, 24),
            _scanned_paragraph(),
        ]
    )
    return path


def _reading(command: list[str], source: Path, out: Path) -> str:
    env = {**os.environ, "SURFSENSE_LOCAL_MODELS_DIR": str(MODELS)}
    subprocess.run(
        [*command, "--check-docling-reading", str(source), str(out)],
        cwd=BACKEND,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        # Loading the layout, table and OCR models and reading one page.
        timeout=900,
    )
    return out.read_text(encoding="utf-8")


@pytest.mark.skipif(not (MODELS / "docling").is_dir(), reason="no parser pack")
def test_frozen_docling_reads_a_table_and_a_scan_as_source_does(
    tmp_path_factory: pytest.TempPathFactory, tmp_path: Path
) -> None:
    """Same Markdown from both: the table's cells and the OCR'd line."""
    binary = frozen_backend(tmp_path_factory.mktemp("frozen-backend"))
    source = _page_with_a_table_and_a_scan(tmp_path / "page.pdf")

    from_source = _reading(
        [
            sys.executable,
            "-c",
            "import sys; from worker.command_line import run; run(sys.argv[1:])",
        ],
        source,
        tmp_path / "source.md",
    )
    frozen = _reading([str(binary)], source, tmp_path / "frozen.md")

    # The reading itself is real: a table with its cells, and the scanned line.
    assert "| North" in from_source and "| Islands" in from_source
    assert "144" in from_source
    assert "revenue" in from_source.lower()
    assert frozen == from_source
