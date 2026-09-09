"""Model [n] labels resolve to [citation:<chunk_id>] for the renderer."""

import pytest

from modules.chat.prompt import Citation, resolve_citations

pytestmark = pytest.mark.unit

SOURCES = [
    Citation(1, 101, 11, 1, 5),
    Citation(2, 102, 12, None, None),
    Citation(3, 103, 13, 6, 9),
]


def test_rewrites_ordinals_to_chunk_markers() -> None:
    """Unknown tokens are dropped while valid ordinals become chunk ids."""
    text, used = resolve_citations("First [3]. Second [1]. Bogus [9].", SOURCES)

    assert text == "First [citation:103]. Second [citation:101]. Bogus ."
    assert [(c.source_id, c.chunk_id) for c in used] == [(3, 103), (1, 101)]


def test_old_citation_wrapper_is_the_same_ordinal() -> None:
    """A model that still writes [citation:n] is rewritten to the chunk id."""
    text, used = resolve_citations(
        "First [citation:3]. Second [citation:1]. Bogus [citation:9].", SOURCES
    )

    assert text == "First [citation:103]. Second [citation:101]. Bogus ."
    assert [(c.source_id, c.chunk_id) for c in used] == [(3, 103), (1, 101)]


def test_a_repeated_source_maps_to_one_number() -> None:
    """Citing the same source twice yields one catalog entry."""
    text, used = resolve_citations("A [1] and again [1].", SOURCES)

    assert text == "A [citation:101] and again [citation:101]."
    assert [c.source_id for c in used] == [1]


def test_tokens_inside_code_are_left_alone() -> None:
    """Inline and fenced code pass through without becoming citations."""
    text, used = resolve_citations(
        "Use `[1]` here [2].\n```\n[3]\n```\n",
        SOURCES,
    )

    assert "`[1]`" in text
    assert "[3]" in text
    assert "[citation:102]" in text
    assert [c.source_id for c in used] == [2]


def test_no_valid_citation_leaves_no_sources() -> None:
    """When nothing resolves, the marker is dropped and the source list is empty."""
    text, used = resolve_citations("Just text [9].", SOURCES)

    assert text == "Just text ."
    assert used == []


def test_empty_answer() -> None:
    """An empty answer resolves to itself with no sources."""
    assert resolve_citations("", SOURCES) == ("", [])
