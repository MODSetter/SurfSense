"""Source citation tokens resolve against the catalog given to the model."""

import pytest

from modules.chat.prompt import Citation, resolve_citations

pytestmark = pytest.mark.unit

SOURCES = [
    Citation(1, 101, 11, 1, 5),
    Citation(2, 102, 12, None, None),
    Citation(3, 103, 13, 6, 9),
]


def test_drops_invented_tokens_and_preserves_source_ids() -> None:
    """Unknown tokens are dropped while valid source identities remain stable."""
    text, used = resolve_citations(
        "First [citation:3]. Second [citation:1]. Bogus [citation:9].", SOURCES
    )

    assert text == "First [citation:3]. Second [citation:1]. Bogus ."
    assert [(c.source_id, c.chunk_id) for c in used] == [(3, 103), (1, 101)]


def test_a_repeated_source_maps_to_one_number() -> None:
    """Citing the same source twice yields one catalog entry."""
    text, used = resolve_citations("A [citation:1] and again [citation:1].", SOURCES)

    assert text == "A [citation:1] and again [citation:1]."
    assert [c.source_id for c in used] == [1]


def test_tokens_inside_code_are_left_alone() -> None:
    """Inline and fenced code pass through without becoming citations."""
    text, used = resolve_citations(
        "Use `[citation:1]` here [citation:2].\n```\n[citation:3]\n```\n",
        SOURCES,
    )

    assert "`[citation:1]`" in text
    assert "[citation:3]" in text
    assert [c.source_id for c in used] == [2]


def test_no_valid_citation_leaves_no_sources() -> None:
    """When nothing resolves, the marker is dropped and the source list is empty."""
    text, used = resolve_citations("Just text [citation:9].", SOURCES)

    assert text == "Just text ."
    assert used == []


def test_empty_answer() -> None:
    """An empty answer resolves to itself with no sources."""
    assert resolve_citations("", SOURCES) == ("", [])


def test_legacy_ordinals_are_plain_text() -> None:
    """The pre-release [n] syntax is not a compatibility citation format."""
    assert resolve_citations("Legacy [1].", SOURCES) == ("Legacy [1].", [])
