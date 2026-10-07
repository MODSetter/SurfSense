"""The data skill as the agent reads it: its examples run in the script runner over real files."""

import re
from pathlib import Path

import openpyxl
import pytest

from modules.agent.opencode_config import DATA_SKILL, skills_folder
from worker.document_script.analysis_run import AnalysisInput, run_analysis_script

pytestmark = pytest.mark.integration

_EXAMPLE = re.compile(r"^## Example: ([\w ]+)\n\n```python\n(.*?)^```", re.M | re.S)


def _skill() -> str:
    return (skills_folder() / DATA_SKILL / "SKILL.md").read_text(encoding="utf-8")


def _examples() -> dict[str, str]:
    """Each example script in the skill, by the heading it is under."""
    return dict(_EXAMPLE.findall(_skill()))


def test_the_skill_names_itself_as_opencode_finds_it() -> None:
    """opencode lists a skill by its frontmatter name, and the config allows only that one."""
    frontmatter = _skill().split("---")[1]

    assert f"name: {DATA_SKILL}\n" in frontmatter
    assert "description: " in frontmatter


def test_the_skill_says_when_to_read_instead_and_how_a_chart_reaches_a_document() -> (
    None
):
    """The tool's limits and the chart's name are what a model gets wrong without it."""
    text = _skill()

    assert "surfsense_analyze_data" in text
    assert "manifest.json" in text
    assert "sources/" in text
    assert "surfsense_render_document" in text
    assert "IMAGES_DIR/<name>.png" in text
    assert "third failed run" in text


def test_the_totals_example_saves_a_table_and_a_chart(tmp_path: Path) -> None:
    """A CSV with a messy header and numbers stored as text still adds up."""
    sales = tmp_path / "Sales.csv"
    sales.write_text(
        " region ,revenue\nNorth,120\nSouth,80\nNorth,150\nSouth,n/a\n",
        encoding="utf-8",
    )
    source = AnalysisInput(sales, "Sales.csv", 4, "Sales 2026")

    run = run_analysis_script(
        _examples()["Totals by group with a chart"], [source], tmp_path / "kept"
    )

    assert run.ok, run.traceback_tail
    assert "Source: Sales 2026" in run.stdout
    assert re.search(r"North\s+270", run.stdout)
    assert run.kept == ("revenue_by_region.csv", "revenue_by_region.png")


def test_the_workbook_example_shows_every_sheet(tmp_path: Path) -> None:
    """A workbook's sheets are looked at before any of them is computed on."""
    book = openpyxl.Workbook()
    book.active.title = "2025"
    book.active.append(["product", "units"])
    book.active.append(["Crate", 12])
    later = book.create_sheet("2026")
    later.append(["product", "units"])
    later.append(["Pallet", 30])
    book.save(tmp_path / "Stock.xlsx")
    source = AnalysisInput(tmp_path / "Stock.xlsx", "Stock.xlsx", 5, "Stock")

    run = run_analysis_script(
        _examples()["Every sheet of a workbook"], [source], tmp_path / "kept"
    )

    assert run.ok, run.traceback_tail
    assert "Stock / 2025: 1 rows" in run.stdout
    assert "Stock / 2026: 1 rows" in run.stdout
    assert "Pallet" in run.stdout
