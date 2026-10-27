"""Web kind: the model's JSON becomes a self-contained, escaped HTML page."""

import pytest

from modules.llm.profile import Tier
from worker.studio.web.html import pipeline as html

pytestmark = pytest.mark.unit


def test_html_escapes_model_text_so_it_cannot_carry_a_script() -> None:
    """The model supplies text only; markup it sends is neutralised, not run."""
    raw = '{"title": "T", "sections": [{"heading": "H", "paragraphs": ["<script>x</script>"]}]}'
    built = html.build(raw, [])

    assert built.primary_mime == "text/html"
    body = built.primary.decode()
    assert "<script>" not in body
    assert "&lt;script&gt;" in body


def test_a_simple_page_is_styled_as_the_agents_pages_are() -> None:
    """The skill's examples' paper palette and type, light only, in a readable column."""
    raw = '{"title": "T", "sections": [{"heading": "H", "paragraphs": ["P"]}]}'
    page = html.build(raw, []).primary.decode()

    assert "<style>" in page
    assert "color-scheme: light" in page
    for colour in ("--bg: #f4f1ea", "--text: #1d1c19", "--accent: #0f6874"):
        assert colour in page
    assert "prefers-color-scheme: dark" not in page
    # The model's text sits in the column the stylesheet sets.
    assert page.index("<main>") < page.index("<h1>T</h1>") < page.index("</main>")


@pytest.mark.parametrize("tier", list(Tier))
def test_the_model_is_told_a_simple_page_holds_text_only(tier: Tier) -> None:
    """Else it describes a diagram or an interaction the template cannot show."""
    prompt = html.prompt(tier, None)

    assert "The page holds text only" in prompt


def test_a_summary_leads_and_points_become_a_list_still_escaped() -> None:
    """The stronger tiers' extra fields: one sentence under the title, a section as a list."""
    raw = (
        '{"title": "T", "summary": "Gist <b>", "sections": ['
        '{"heading": "Steps", "points": ["First <i>", "Second"]},'
        '{"heading": "Prose", "paragraphs": ["P"]}]}'
    )
    built = html.build(raw, [])
    page = built.primary.decode()

    assert '<p class="summary">Gist &lt;b&gt;</p>' in page
    assert "<ul>\n<li>First &lt;i&gt;</li>\n<li>Second</li>\n</ul>" in page
    assert "<p>P</p>" in page
    assert "Gist <b>" in built.markdown
    assert "- First <i>" in built.markdown


@pytest.mark.parametrize(
    ("tier", "asked"),
    [(Tier.FRONTIER, True), (Tier.CAPABLE, True), (Tier.COMPACT, False)],
)
def test_only_the_stronger_tiers_are_asked_for_a_summary_and_points(
    tier: Tier, asked: bool
) -> None:
    """Each field more is a chance for a small model's JSON to break."""
    prompt = html.prompt(tier, None)

    assert ('"summary"' in prompt and '"points"' in prompt) is asked
