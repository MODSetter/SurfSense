"""Content kinds: the model writes markdown or JSON, the worker renders it as-is."""

import pytest

from worker.studio.content.flashcards import pipeline as flashcards
from worker.studio.content.mindmap import pipeline as mindmap
from worker.studio.content.quiz import pipeline as quiz
from worker.studio.content.summary import pipeline as summary
from worker.studio.shared.text import parse_json

pytestmark = pytest.mark.unit


def test_a_summary_takes_its_title_from_the_first_h1() -> None:
    """The document title comes from the model's H1, so the list reads well."""
    built = summary.build("# Saturn's rings\n\nThey are mostly ice.", [])

    assert built.title == "Saturn's rings"
    assert built.markdown.startswith("# Saturn's rings")
    assert built.primary is None  # the markdown is the body, not a file


def test_a_summary_without_a_heading_still_has_a_title() -> None:
    """A model that skips the H1 still yields a named, openable artifact."""
    assert summary.build("Just prose, no heading.", []).title == "Summary"


def test_parse_json_survives_fences_and_surrounding_prose() -> None:
    """Local models wrap JSON in prose and fences; the object is still recovered."""
    raw = 'Sure!\n```json\n{"title": "T", "sections": []}\n```\nHope that helps.'
    assert parse_json(raw) == {"title": "T", "sections": []}


def test_parse_json_rejects_a_non_object() -> None:
    """A builder must fail loudly, not render half a spec, on bad output."""
    with pytest.raises(ValueError, match="JSON"):
        parse_json("not json at all")


def test_mindmap_renders_a_nested_outline_and_no_file() -> None:
    """A mind map is a markdown body Markmap reads; there is nothing to download."""
    raw = '{"title": "Saturn", "nodes": [{"label": "Rings", "children": [{"label": "Ice"}]}]}'
    built = mindmap.build(raw, [])

    assert built.primary is None
    assert "# Saturn" in built.markdown
    assert "- Rings" in built.markdown
    assert "  - Ice" in built.markdown


def test_flashcards_and_quiz_project_to_readable_markdown() -> None:
    """The searchable body carries the content, so both index and read plainly."""
    cards = flashcards.build(
        '{"title": "Deck", "cards": [{"front": "Q?", "back": "A."}]}', []
    )
    assert cards.primary is None
    assert "Q?" in cards.markdown and "A." in cards.markdown

    test = quiz.build(
        '{"title": "Test", "questions": [{"question": "Q?", '
        '"options": ["a", "b"], "answer": "a"}]}',
        [],
    )
    assert "Q?" in test.markdown and "Answer: a" in test.markdown
