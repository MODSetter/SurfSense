"""The documents skill as the agent reads it: its examples run in the script runner."""

import re
from io import BytesIO

import docx
import pypdfium2
import pytest

from modules.agent.opencode_config import DOCUMENTS_SKILL, skills_folder
from worker.document_script.run import run_document_script

pytestmark = pytest.mark.integration

_EXAMPLE = re.compile(r"^## Example: (\w+)\n\n```python\n(.*?)^```", re.M | re.S)


def _examples() -> dict[str, str]:
    """Each example script in the skill, by the heading it is under."""
    text = (skills_folder() / DOCUMENTS_SKILL / "SKILL.md").read_text(encoding="utf-8")
    return dict(_EXAMPLE.findall(text))


def test_the_skill_names_itself_as_opencode_finds_it() -> None:
    """opencode lists a skill by its frontmatter name, and the config allows only that one."""
    text = (skills_folder() / DOCUMENTS_SKILL / "SKILL.md").read_text(encoding="utf-8")

    frontmatter = text.split("---")[1]
    assert f"name: {DOCUMENTS_SKILL}\n" in frontmatter
    assert "description: " in frontmatter


def test_the_skill_says_what_the_agent_can_look_at_and_what_previews_leave_out() -> (
    None
):
    """A source's figures can be opened, and a Word preview hides headers and footers."""
    text = (skills_folder() / DOCUMENTS_SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "sources/figures/" in text
    assert "headers and footers" in text
    # Most local models read no images: opencode answers their `read` with an error.
    assert (
        "If `read` cannot show you the image, place that figure with its caption "
        "and tell the user" in text
    )
    assert "When `read` cannot show you the previews" in text


def test_the_word_example_renders_a_document_with_its_table_and_chart() -> None:
    """A model copies the example's habits, so the example itself must run."""
    result = run_document_script(
        _examples()["Word"], output_name="document.docx", images={}
    )

    assert result.ok, f"{result.error}\n{result.traceback_tail}"
    document = docx.Document(BytesIO(result.output))
    assert document.paragraphs[0].style.name == "Title"
    assert [
        p.style.name for p in document.paragraphs if p.text.startswith("A pilot")
    ] == ["List Bullet"]
    assert document.tables[0].rows[0].cells[0].text == "Phase"
    assert len(document.inline_shapes) == 1
    assert round(document.sections[0].page_width.cm, 1) == 21.0


def test_the_pdf_example_renders_an_a4_page_with_its_table() -> None:
    """The PDF example's text, table and list all reach the page."""
    result = run_document_script(
        _examples()["PDF"], output_name="document.pdf", images={}
    )

    assert result.ok, f"{result.error}\n{result.traceback_tail}"
    pdf = pypdfium2.PdfDocument(result.output)
    try:
        page = pdf[0]
        text = page.get_textpage().get_text_range()
        assert (round(page.get_width()), round(page.get_height())) == (595, 842)
    finally:
        pdf.close()
    for words in ("Client proposal", "Costs & timeline", "Rollout", "48,000 EUR"):
        assert words in text
