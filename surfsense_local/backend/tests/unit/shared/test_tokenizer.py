import pytest

from shared.tokenizer import terms

pytestmark = pytest.mark.unit


def test_a_devanagari_word_keeps_its_marks() -> None:
    """Cut at its virama, `स्कैनर` (scanner) is `स` + `नर`.

    Those are letters, not words, and nearly every Hindi document holds nearly
    every Devanagari letter, so coverage stops telling the answering chunk from
    the rest.
    """
    assert set(terms("स्कैनर की बैटरी")) == {"स्कैनर", "की", "बैटरी"}


def test_an_accent_folds_so_a_plain_spelling_still_matches() -> None:
    """unicode61 folds Latin diacritics, which a regex could not follow without
    carrying SQLite's own table of them."""
    assert terms("café") == terms("cafe") == ["cafe"]


def test_an_underscore_separates() -> None:
    """The index splits there, so a question has to split there too."""
    assert terms("snake_case_name") == ["case", "name", "snake"]


def test_a_word_used_twice_is_one_term() -> None:
    """Coverage asks what fraction of a question a chunk matched, so a word
    repeated in the question must not count twice."""
    assert terms("the cat and the hat") == ["and", "cat", "hat", "the"]
