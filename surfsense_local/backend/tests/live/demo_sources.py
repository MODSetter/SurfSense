"""The three sources the demo flow starts from: a client report, our logo and kickoff notes.

Made fresh for each run, so the agent can only know them through SurfSense.
"""

import io

import docx
from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

CLIENT = "Halvorsen Freight"
US = "Kestrel Data Works"
YEARLY_COSTS = {"2026": 84, "2027": 61, "2028": 58}  # thousand EUR
CHART_CAPTION = "Figure 1: Projected yearly costs of the telematics programme, 2026-2028 (EUR thousand)."


def assessment_report() -> bytes:
    """A two-page PDF report whose costs are a vector bar chart with a caption."""
    styles = getSampleStyleSheet()
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 50, 30, 330, 160
    chart.data = [tuple(YEARLY_COSTS.values())]
    chart.categoryAxis.categoryNames = list(YEARLY_COSTS)
    chart.valueAxis.valueMin, chart.valueAxis.valueMax = 0, 100
    drawing = Drawing(420, 210)
    drawing.add(chart)
    story = [
        Paragraph(f"{CLIENT}: fleet telematics assessment", styles["Title"]),
        Paragraph(f"Prepared by {US}, September 2026", styles["Italic"]),
        Paragraph("Findings", styles["Heading1"]),
        Paragraph(
            f"{CLIENT} runs 310 trucks from four depots in Norway and Sweden. Fuel "
            "is 34% of operating cost, and idle time averages 2.1 hours per truck "
            "per day. Dispatch plans routes by hand each morning, and maintenance "
            "is scheduled by mileage alone, which caused 41 roadside breakdowns in "
            "the last twelve months.",
            styles["BodyText"],
        ),
        Paragraph("Recommendation", styles["Heading1"]),
        Paragraph(
            "Fit every truck with a telematics unit, feed its data into a route "
            "optimiser and a predictive maintenance model, and train dispatchers in "
            "two waves. We expect fuel use to fall 9-12% and breakdowns to halve "
            "within a year of the full rollout.",
            styles["BodyText"],
        ),
        Paragraph("Costs", styles["Heading1"]),
        Paragraph(
            "The first year carries the hardware and the rollout; later years are "
            "licences and support.",
            styles["BodyText"],
        ),
        drawing,
        Paragraph(CHART_CAPTION, styles["Italic"]),
        Spacer(1, 12),
        Paragraph(
            "Risks: driver acceptance, patchy mobile coverage on two northern "
            "routes, and the depot in Umea still running an older fleet system.",
            styles["BodyText"],
        ),
    ]
    out = io.BytesIO()
    SimpleDocTemplate(out, pagesize=A4, title="Fleet telematics assessment").build(
        story
    )
    return out.getvalue()


def our_logo() -> bytes:
    """Our company's logo: a teal disc with a white K beside the name."""
    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse([20, 20, 180, 180], fill=(0, 128, 128))
    draw.text(
        (100, 100), "K", fill="white", font=ImageFont.load_default(110), anchor="mm"
    )
    draw.text(
        (205, 100), US, fill=(0, 90, 90), font=ImageFont.load_default(40), anchor="lm"
    )
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def kickoff_notes() -> bytes:
    """Our notes from the kickoff call, with the agreed prices and dates."""
    notes = docx.Document()
    notes.add_heading(f"Kickoff call: {CLIENT}, 22 September 2026", 1)
    notes.add_paragraph(
        f"Attendees: Ingrid Halvorsen (COO, {CLIENT}), Tomas Berg (IT lead, "
        f"{CLIENT}), Priya Nair (engagement lead, {US})."
    )
    notes.add_heading("What they need", 2)
    for point in (
        "Lower fuel cost before the 2027 fuel tax rise.",
        "Fewer roadside breakdowns; two key customers have complained.",
        "A pilot first: the board will not approve all 310 trucks at once.",
    ):
        notes.add_paragraph(point, style="List Bullet")
    notes.add_heading("Prices we agreed to propose", 2)
    for point in (
        "Discovery: 9,500 EUR, two weeks.",
        "Pilot on 40 trucks at the Oslo depot: 24,000 EUR, six weeks.",
        "Rollout to all 310 trucks: 52,000 EUR.",
        "Support and licences: 1,800 EUR per month from the rollout.",
    ):
        notes.add_paragraph(point, style="List Bullet")
    notes.add_heading("Dates", 2)
    notes.add_paragraph(
        "Ingrid wants the proposal by 10 October and decides by 15 October. "
        "Discovery could start on 2 November 2026, the pilot in December, and the "
        "rollout from February to April 2027."
    )
    out = io.BytesIO()
    notes.save(out)
    return out.getvalue()
