"""normalize_citations resolves inline [n] against the sources the model was given."""

import pytest

from modules.chat.prompt import Citation, normalize_citations

pytestmark = pytest.mark.unit

SOURCES = [
    Citation(1, 101, 11, 1, 5),
    Citation(2, 102, 12, None, None),
    Citation(3, 103, 13, 6, 9),
]


def test_drops_invented_ordinals_and_renumbers_survivors() -> None:
    """An [n] with no source is dropped; the rest renumber by first appearance."""
    text, used = normalize_citations("First [3]. Second [1]. Bogus [9].", SOURCES)

    assert text == "First [1]. Second [2]. Bogus ."
    assert [(c.id, c.chunk_id) for c in used] == [(1, 103), (2, 101)]


def test_a_repeated_source_maps_to_one_number() -> None:
    """Citing the same source twice yields one entry, both markers the same number."""
    text, used = normalize_citations("A [1] and again [1].", SOURCES)

    assert text == "A [1] and again [1]."
    assert [c.id for c in used] == [1]


def test_ordinals_inside_code_are_left_alone() -> None:
    """Inline and fenced code pass through, so `arr[1]` is never read as a citation."""
    text, used = normalize_citations(
        "Use `arr[1]` here [2].\n```\nx[1] = 3\n```\n", SOURCES
    )

    assert "`arr[1]`" in text
    assert "x[1] = 3" in text
    assert [c.id for c in used] == [1]  # only the [2] outside code, renumbered to [1]


def test_no_valid_citation_leaves_no_sources() -> None:
    """When nothing resolves, the marker is dropped and the source list is empty."""
    text, used = normalize_citations("Just text [9].", SOURCES)

    assert text == "Just text ."
    assert used == []


def test_empty_answer() -> None:
    """An empty answer resolves to itself with no sources."""
    assert normalize_citations("", SOURCES) == ("", [])
