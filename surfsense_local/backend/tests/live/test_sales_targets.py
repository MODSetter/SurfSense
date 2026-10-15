"""Live case 10: which regions missed their target last quarter, from a sales CSV and a targets workbook, then a Word report charting it.

Six months of orders are too many rows to add up from the text: the figures
must come from the analysis tool, and the report's chart from its run.
"""

import csv
import hashlib
import io
import random
import re
from datetime import date

import openpyxl
import pytest

from shared.config import get_storage_settings
from tests.live.live_agent import LiveAgent, answer, steps
from tests.live.turn_renders import assert_pages_checked, last_version
from tests.live.word_file import WordFile

pytestmark = pytest.mark.live

CASE = "sales-targets"
TURNS = (
    "Which regions missed their sales target last quarter, and by how much?",
    "Put that in a short Word report with a bar chart of each region's shortfall.",
)
ANALYSE = "surfsense_analyze_data"
REGIONS = ("North", "South", "East", "West", "Central")
PRODUCTS = ("Heat pump", "Solar kit", "Battery pack", "Smart meter")
# Each region's target as a share of what it sold, so who misses is fixed.
TARGET_SHARE = {
    "North": 0.94,
    "South": 1.09,
    "East": 1.03,
    "West": 0.88,
    "Central": 1.14,
}
QUARTERS = {"Q2": (4, 5, 6), "Q3": (7, 8, 9)}
_CHART = re.compile(r"analysis-([0-9a-f]{8})-(.+)")
_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*(k\b|K\b|thousand)?")


def _orders() -> list[dict[str, object]]:
    """April to September 2026, a few hundred orders, the same every run."""
    pick = random.Random(2026)
    rows: list[dict[str, object]] = []
    for month in (*QUARTERS["Q2"], *QUARTERS["Q3"]):
        for region in REGIONS:
            for _ in range(pick.randint(9, 14)):
                rows.append(
                    {
                        "order_id": f"SO-{len(rows) + 10_001}",
                        "order_date": date(
                            2026, month, pick.randint(1, 28)
                        ).isoformat(),
                        "region": region,
                        "product": pick.choice(PRODUCTS),
                        "net_amount_eur": pick.randrange(1_200, 9_800, 10),
                    }
                )
    return rows


ORDERS = _orders()


def _sold(quarter: str) -> dict[str, int]:
    months = QUARTERS[quarter]
    return {
        region: sum(
            int(o["net_amount_eur"])
            for o in ORDERS
            if o["region"] == region
            and date.fromisoformat(str(o["order_date"])).month in months
        )
        for region in REGIONS
    }


TARGETS = {
    quarter: {
        r: round(sold * TARGET_SHARE[r], -3) for r, sold in _sold(quarter).items()
    }
    for quarter in QUARTERS
}
SHORTFALL = {
    region: int(TARGETS["Q3"][region] - sold)
    for region, sold in _sold("Q3").items()
    if sold < TARGETS["Q3"][region]
}


async def test_the_agent_finds_the_shortfalls_then_charts_them_in_word(
    live: LiveAgent,
) -> None:
    """Turn 1 states each missed region's true shortfall from an analysis; turn 2's Word file holds that analysis's chart."""
    sales = await live.upload("Sales orders Apr-Sep 2026.csv", _sales_csv())
    targets = await live.upload("Regional targets 2026.xlsx", _targets_workbook())
    await live.wait_ready(sales, targets)
    thread = await live.thread()

    first = await live.turn(thread, TURNS[0])
    ran = [s for s in steps(first, ANALYSE) if s["status"] == "completed"]
    assert ran, "turn 1 answered without running an analysis"
    said = answer(first)
    for region, short in SHORTFALL.items():
        assert region in said, f"turn 1 does not name {region}, which missed: {said}"
        assert _states(said, short), (
            f"turn 1 does not give {region}'s shortfall of {short:,} EUR: {said}"
        )

    second = await live.turn(thread, TURNS[1])
    report = await last_version(live, second, "turn 2")
    assert report.format == "docx", f"turn 2 made {report}, not a Word file"
    await assert_pages_checked(live, second, "turn 2")
    placed = [
        n for n in live.spec(report.id).get("images") or [] if _CHART.fullmatch(n)
    ]
    assert placed, f"v{report.number} places no analysis chart"
    pictures = WordFile(await live.file(report.id)).pictures
    charts = {name: _chart_hash(live, name) for name in placed}
    assert any(h in pictures for h in charts.values()), (
        f"v{report.number} holds none of the analysis charts it named: {list(charts)}"
    )


def _states(said: str, amount: int) -> bool:
    """The amount is written, to within 1%: 12,345, 12 345, 12.3k or 12.3 thousand."""
    # \s takes the no-break and thin spaces some locales group thousands with.
    flat = re.sub(r"(?<=\d)[,\s](?=\d{3}(?!\d))", "", said)
    for match in _NUMBER.finditer(flat):
        value = float(match[1]) * (1000 if match[2] else 1)
        if abs(value - amount) <= amount * 0.01:
            return True
    return False


def _chart_hash(live: LiveAgent, name: str) -> str | None:
    """The PNG an analysis chart name stands for, hashed; None when no run kept it."""
    match = _CHART.fullmatch(name)
    assert match is not None
    threads = get_storage_settings().agent_threads_dir(live.workspace_id)
    found = list(threads.glob(f"*/outputs/analysis/{match[1]}/{match[2]}.png"))
    return hashlib.sha256(found[0].read_bytes()).hexdigest() if found else None


def _sales_csv() -> bytes:
    """Every order, one row each, as the shop exports it."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(ORDERS[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(ORDERS)
    return out.getvalue().encode()


def _targets_workbook() -> bytes:
    """The year's targets, a column per quarter, as finance keeps them."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Targets 2026"
    sheet.append(["Region", "Q1", "Q2", "Q3", "Q4"])
    for region in REGIONS:
        q2, q3 = TARGETS["Q2"][region], TARGETS["Q3"][region]
        sheet.append([region, round(q2 * 0.9, -3), q2, q3, round(q3 * 1.1, -3)])
    notes = book.create_sheet("Notes")
    notes.append(["Targets are net sales in EUR, excluding VAT."])
    notes.append(["Set by finance in January 2026; Q3 was revised in June."])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
