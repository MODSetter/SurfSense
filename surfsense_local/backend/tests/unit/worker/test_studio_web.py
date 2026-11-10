"""Web kind: the model's JSON becomes a self-contained, escaped HTML page."""

from types import SimpleNamespace

import pytest

from modules.llm.profile import Tier
from worker.studio.shared import generate
from worker.studio.web.html import pipeline as html
from worker.studio.web.html import schema as page_schema

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


def test_a_small_model_is_told_to_write_the_page_in_its_own_words() -> None:
    """Without it, Qwen3 1.7B and 4B copied 92% and 94% of their pages from the
    source word for word; with it, 1% and 2%."""
    prompt = html.prompt(Tier.COMPACT, None)

    assert "in your own words" in prompt


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


@pytest.mark.parametrize("tier", list(Tier))
def test_a_simple_page_asks_the_model_for_its_schema(
    tier: Tier, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unconstrained, Qwen3 0.6B broke 4 pages in 9 and Qwen3 4B 3 in 9: a quote
    left unescaped, a bracket too many, a section repeated until the window ran out."""
    sent: list[dict | None] = []

    def fake_run_model(*_a: object, json_schema: dict | None = None, **_kw: object):
        sent.append(json_schema)
        return '{"title": "T", "sections": [{"heading": "H", "paragraphs": ["P"]}]}'

    monkeypatch.setattr(generate, "run_model", fake_run_model)
    monkeypatch.setattr(html, "writes_script", lambda _selection: False)

    html.render(SimpleNamespace(tier=tier, selection=None), [], None)

    assert sent == [page_schema.reply(tier)]


def test_the_small_page_schema_asks_only_what_its_prompt_does() -> None:
    """The compact prompt asks for neither a summary nor points."""
    reply = page_schema.reply(Tier.COMPACT)
    section = reply["properties"]["sections"]["items"]

    assert set(reply["properties"]) == {"title", "sections"}
    assert set(section["properties"]) == {"heading", "paragraphs"}
    assert section["required"] == ["heading", "paragraphs"]


@pytest.mark.parametrize("tier", [Tier.CAPABLE, Tier.FRONTIER])
def test_a_stronger_page_schema_takes_a_summary_and_points(tier: Tier) -> None:
    """A section holds paragraphs or points, so only its heading is required."""
    reply = page_schema.reply(tier)
    section = reply["properties"]["sections"]["items"]

    assert "summary" in reply["properties"]
    assert set(section["properties"]) == {"heading", "paragraphs", "points"}
    assert section["required"] == ["heading"]


@pytest.mark.parametrize("tier", list(Tier))
def test_every_list_in_a_page_schema_is_bounded(tier: Tier) -> None:
    """A model that repeats stops at a ceiling instead of filling the window."""
    sections = page_schema.reply(tier)["properties"]["sections"]
    lists = [
        prop
        for prop in sections["items"]["properties"].values()
        if prop["type"] == "array"
    ]

    assert sections["maxItems"] == html.SECTIONS
    assert lists and all("maxItems" in prop for prop in lists)


def test_a_page_with_no_section_fails_rather_than_opening_empty() -> None:
    """A title alone opened as a ready page; failing says why and lets the job retry."""
    with pytest.raises(ValueError, match="no usable sections"):
        html.build(
            '{"title": "T", "sections": [{"heading": "", "paragraphs": []}]}', []
        )
