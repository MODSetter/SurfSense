"""Live case 7: from a report holding a photo and a chart, place the chart, then replace it with one the agent draws.

The chart's numbers are only its bar labels, so the redraw needs the agent to read the figure.
"""

import hashlib
import io
import random
import re

import pytest
from PIL import Image, ImageDraw, ImageFilter
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image as Picture
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from modules.documents.source_figures import figure_file, list_figures
from shared.db import create_session_factory
from tests.live.live_agent import LiveAgent
from tests.live.turn_renders import (
    assert_next_version,
    assert_pages_checked,
    last_version,
)
from tests.live.word_file import WordFile

pytestmark = pytest.mark.live

CASE = "figure-swap"
TURNS = (
    "Write a one-page Word summary of the site visit report and include the "
    "chart from the report.",
    "Replace it with your own chart of the same numbers.",
)
# Parcels handled per month, thousands: written only as the chart's bar labels.
PARCELS = {"Apr": 182, "May": 196, "Jun": 214, "Jul": 171, "Aug": 188, "Sep": 225}
PHOTO_CAPTION = "Photo 1: The loading bay at the Drammen depot, 12 September 2026."
CHART_CAPTION = (
    "Figure 2: Parcels handled per month, April to September 2026 (thousands)."
)


async def test_the_agent_places_the_chart_then_redraws_it(live: LiveAgent) -> None:
    """v1 holds the source chart, not the photo in its place; v2 holds a chart of its own with the same numbers."""
    report = await live.upload("Drammen depot site visit.pdf", _site_visit())
    await live.wait_ready(report)
    chart, photo = _chart_and_photo(live, report)
    thread = await live.thread()

    first = await live.turn(thread, TURNS[0])
    draft = await last_version(live, first, "turn 1")
    assert draft.format == "docx", f"turn 1 made {draft}, not a Word file"
    await assert_pages_checked(live, first, "turn 1")
    before = WordFile(await live.file(draft.id))
    assert chart in before.pictures, (
        f"v{draft.number} does not place the report's chart"
        + (" (it placed the photo)" if photo in before.pictures else "")
    )

    second = await live.turn(thread, TURNS[1])
    edit = await last_version(live, second, "turn 2")
    assert_next_version(draft, edit, "turn 2")
    await assert_pages_checked(live, second, "turn 2")
    after = WordFile(await live.file(edit.id))
    assert chart not in after.pictures, (
        f"v{edit.number} still places the report's chart"
    )
    assert after.pictures - before.pictures, f"v{edit.number} draws no chart of its own"
    written = {int(n) for n in re.findall(r"\d+", live.spec(edit.id).get("text", ""))}
    assert set(PARCELS.values()) <= written, (
        f"v{edit.number}'s chart does not use the report's numbers {PARCELS}"
    )


def _chart_and_photo(live: LiveAgent, report: int) -> tuple[str, str]:
    """The hashes of the report's chart and photo as ingest kept them; checked before any paid call."""
    with create_session_factory(live.engine)() as session:
        figures = list_figures(session, live.workspace_id, report)
        assert len(figures) == 2, f"ingest kept {figures}, not the photo and the chart"
        by_caption = {
            ("chart" if "parcel" in (f.caption or "").lower() else "photo"): f
            for f in figures
        }
        if set(by_caption) != {"chart", "photo"}:
            # No caption read: the photo comes first on the page.
            by_caption = {"photo": figures[0], "chart": figures[1]}
        return tuple(  # type: ignore[return-value]
            hashlib.sha256(
                figure_file(
                    session, live.workspace_id, by_caption[kind].name
                ).read_bytes()
            ).hexdigest()
            for kind in ("chart", "photo")
        )


def _site_visit() -> bytes:
    """A one-page visit report: findings, a photo of the loading bay, and a labelled bar chart."""
    styles = getSampleStyleSheet()
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 50, 30, 330, 150
    chart.data = [tuple(PARCELS.values())]
    chart.categoryAxis.categoryNames = list(PARCELS)
    chart.valueAxis.valueMin, chart.valueAxis.valueMax = 0, 250
    chart.barLabelFormat = "%d"
    chart.barLabels.nudge = 7
    drawing = Drawing(420, 200)
    drawing.add(chart)
    story = [
        Paragraph("Drammen depot: site visit report", styles["Title"]),
        Paragraph("Visited 12 September 2026 by Priya Nair", styles["Italic"]),
        Paragraph("Findings", styles["Heading1"]),
        Paragraph(
            "The depot runs two shifts with 46 staff and 19 vans. The loading bay "
            "has six doors, but two have been out of use since July while the "
            "dock levellers wait for parts, so vans queue at peak. Volumes grew "
            "through the summer apart from the July holiday dip, and September "
            "was the busiest month so far.",
            styles["BodyText"],
        ),
        Picture(io.BytesIO(_loading_bay_photo()), width=12 * cm, height=7 * cm),
        Paragraph(PHOTO_CAPTION, styles["Italic"]),
        Spacer(1, 8),
        drawing,
        Paragraph(CHART_CAPTION, styles["Italic"]),
        Paragraph("Next steps", styles["Heading1"]),
        Paragraph(
            "Repair the two dock levellers before the Christmas peak, add a third "
            "shift on Saturdays from November, and review van routes for the "
            "southern postcodes.",
            styles["BodyText"],
        ),
    ]
    out = io.BytesIO()
    SimpleDocTemplate(out, pagesize=A4, title="Drammen depot site visit").build(story)
    return out.getvalue()


def _loading_bay_photo() -> bytes:
    """A photograph-like JPEG: sky, a depot wall with doors, a van, and sensor noise."""
    width, height = 960, 560
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height // 2):
        shade = 150 + y * 80 // (height // 2)
        draw.line([(0, y), (width, y)], fill=(110, 150, shade))
    draw.rectangle([0, height // 2, width, height], fill=(92, 92, 96))
    draw.rectangle([60, 120, 900, 380], fill=(170, 160, 140))
    for door in range(6):
        left = 90 + door * 135
        draw.rectangle([left, 220, left + 100, 380], fill=(70, 80, 95))
    draw.rectangle([300, 300, 560, 440], fill=(235, 235, 235))
    draw.rectangle([560, 340, 640, 440], fill=(220, 220, 225))
    for wheel in (340, 600):
        draw.ellipse([wheel - 28, 420, wheel + 28, 476], fill=(25, 25, 25))
    noise = random.Random(7)
    pixels = image.load()
    for _ in range(60_000):
        x, y = noise.randrange(width), noise.randrange(height)
        d = noise.randint(-18, 18)
        pixels[x, y] = tuple(max(0, min(255, c + d)) for c in pixels[x, y])
    image = image.filter(ImageFilter.GaussianBlur(1.2))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=88)
    return out.getvalue()
