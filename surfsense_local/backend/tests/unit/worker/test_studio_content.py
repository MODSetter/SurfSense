"""Content kinds: the model writes markdown or JSON, the worker renders it as-is."""

import json

import pytest

from modules.llm.profile import Tier
from worker.studio.content.flashcards import pipeline as flashcards
from worker.studio.content.mindmap import pipeline as mindmap
from worker.studio.content.quiz import pipeline as quiz
from worker.studio.content.summary import pipeline as summary
from worker.studio.shared.text import parse_json

pytestmark = pytest.mark.unit


def test_a_quiz_is_asked_for_differently_depending_on_the_model() -> None:
    """A 3B model scores best on the shortest prompt, a frontier one on the fullest."""
    compact = quiz.prompt(Tier.COMPACT, None)
    capable = quiz.prompt(Tier.CAPABLE, None)
    frontier = quiz.prompt(Tier.FRONTIER, None)

    assert len({compact, capable, frontier}) == 3
    assert len(compact) < len(capable)


def test_a_quiz_carries_the_users_focus_and_its_own_numbers_at_every_tier() -> None:
    """A steer the user typed, or a count the builder enforces, must reach the model."""
    for tier in Tier:
        filled = quiz.prompt(tier, "  the 2031 rainfall figures  ")

        assert "Focus on: the 2031 rainfall figures" in filled
        assert f"exactly {quiz.OPTIONS}" in filled
        assert "$" not in filled


def test_a_quiz_is_capped_where_its_prompt_says_it_is() -> None:
    """Open counts are a prompt's request; the ceiling is the builder's contract."""
    question = {
        "question": "Q?",
        "options": ["a", "b", "c", "d"],
        "answer": "a",
        "explanation": "Because.",
    }
    raw = json.dumps({"title": "Long", "questions": [question] * 40})

    built = quiz.build(raw, [])

    assert len(json.loads(built.primary)["questions"]) == quiz.QUESTIONS


def test_every_content_kind_is_asked_for_in_its_own_words_at_every_tier() -> None:
    """One prompt per kind and tier: a wording that suits a quiz never reaches a deck."""
    asked = {
        module.prompt(tier, "the 2031 rainfall figures")
        for module in (quiz, flashcards, mindmap, summary)
        for tier in Tier
    }

    assert len(asked) == 12
    assert all("Focus on: the 2031 rainfall figures" in text for text in asked)
    assert not any("$" in text for text in asked)


def test_a_deck_and_a_map_are_capped_where_their_prompts_say_they_are() -> None:
    """Open counts are a prompt's request; the ceiling is the builder's contract."""
    card = {"front": "Q?", "back": "A."}
    deck = flashcards.build(json.dumps({"cards": [card] * 40}), [])

    branch = {"label": "Branch", "children": [{"label": "Leaf"}]}
    map_body = mindmap.build(json.dumps({"nodes": [branch] * 40}), []).markdown

    assert len(json.loads(deck.primary)["cards"]) == flashcards.CARDS
    assert map_body.count("\n- ") == mindmap.BRANCHES


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
    assert cards.primary_mime == "application/json"
    assert "Q?" in cards.markdown and "A." in cards.markdown

    test = quiz.build(
        '{"title": "Test", "questions": [{"question": "Q?", '
        '"options": ["a", "b", "c", "d"], "answer": "a"}]}',
        [],
    )
    assert "Q?" in test.markdown and "Answer: a" in test.markdown
