"""Builders render deterministically, and the registry matches the API catalog."""

import pytest

from modules.artifacts.formats import FORMATS
from worker.studio.builders import BUILDERS
from worker.studio.builders.summary import build
from worker.studio.media import MEDIA
from worker.studio.office import OFFICE
from worker.studio.text import parse_json

pytestmark = pytest.mark.unit


def test_every_format_routes_to_exactly_one_family() -> None:
    """The catalog partitions across the three families the pipeline can route.

    Every catalog key is a deterministic builder, a model-written office document,
    or a media deliverable — with no key in two families and none left unrouted —
    so the pipeline never meets a format it cannot produce.
    """
    families = (set(BUILDERS), set(OFFICE), set(MEDIA))
    assert set().union(*families) == {fmt.key for fmt in FORMATS}
    for first in families:
        for second in families:
            if first is not second:
                assert first.isdisjoint(second)


def test_a_summary_takes_its_title_from_the_first_h1() -> None:
    """The document title comes from the model's H1, so the list reads well."""
    built = build("# Saturn's rings\n\nThey are mostly ice.", [])

    assert built.title == "Saturn's rings"
    assert built.markdown.startswith("# Saturn's rings")
    assert built.primary is None  # the markdown is the body, not a file


def test_a_summary_without_a_heading_still_has_a_title() -> None:
    """A model that skips the H1 still yields a named, openable artifact."""
    assert build("Just prose, no heading.", []).title == "Summary"


def test_parse_json_survives_fences_and_surrounding_prose() -> None:
    """Local models wrap JSON in prose and fences; the object is still recovered."""
    raw = 'Sure!\n```json\n{"title": "T", "sections": []}\n```\nHope that helps.'
    assert parse_json(raw) == {"title": "T", "sections": []}


def test_parse_json_rejects_a_non_object() -> None:
    """A builder must fail loudly, not render half a spec, on bad output."""
    with pytest.raises(ValueError, match="JSON"):
        parse_json("not json at all")


def test_html_escapes_model_text_so_it_cannot_carry_a_script() -> None:
    """The model supplies text only; markup it sends is neutralised, not run."""
    raw = '{"title": "T", "sections": [{"heading": "H", "paragraphs": ["<script>x</script>"]}]}'
    built = BUILDERS["html"].build(raw, [])

    assert built.primary_mime == "text/html"
    body = built.primary.decode()
    assert "<script>" not in body
    assert "&lt;script&gt;" in body


def test_mindmap_renders_a_nested_outline_and_no_file() -> None:
    """A mind map is a markdown body Markmap reads; there is nothing to download."""
    raw = '{"title": "Saturn", "nodes": [{"label": "Rings", "children": [{"label": "Ice"}]}]}'
    built = BUILDERS["mindmap"].build(raw, [])

    assert built.primary is None
    assert "# Saturn" in built.markdown
    assert "- Rings" in built.markdown
    assert "  - Ice" in built.markdown


def test_flashcards_and_quiz_project_to_readable_markdown() -> None:
    """The searchable body carries the content, so both index and read plainly."""
    cards = BUILDERS["flashcards"].build(
        '{"title": "Deck", "cards": [{"front": "Q?", "back": "A."}]}', []
    )
    assert cards.primary is None
    assert "Q?" in cards.markdown and "A." in cards.markdown

    quiz = BUILDERS["quiz"].build(
        '{"title": "Test", "questions": [{"question": "Q?", '
        '"options": ["a", "b"], "answer": "a"}]}',
        [],
    )
    assert "Q?" in quiz.markdown and "Answer: a" in quiz.markdown
