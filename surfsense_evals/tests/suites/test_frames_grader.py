"""Tests for the FRAMES grader's deterministic shortcut.

The LLM-judge fallback is excluded here (network call); we just
confirm the rule-based path picks up obvious correct/incorrect
cases and routes the ambiguous ones to ``lexical_miss`` so the
runner knows to consult the judge.
"""

from __future__ import annotations

from surfsense_evals.suites.research.frames.grader import (
    _maybe_number,
    _normalise,
    _whole_word_substring,
    grade_deterministic,
)


class TestNormalisation:
    def test_lowercase_and_punct_stripped(self) -> None:
        assert _normalise("Jane Ballou.") == "jane ballou"

    def test_articles_removed(self) -> None:
        assert _normalise("The Eiffel Tower") == "eiffel tower"

    def test_whitespace_squashed(self) -> None:
        assert _normalise("  multi   space\tinput  ") == "multi space input"

    def test_empty_returns_empty(self) -> None:
        assert _normalise("") == ""
        assert _normalise(None) == ""  # type: ignore[arg-type]


class TestNumericExtraction:
    def test_simple_int(self) -> None:
        assert _maybe_number("42") == 42.0

    def test_int_with_commas(self) -> None:
        assert _maybe_number("1,234") == 1234.0

    def test_year_in_sentence(self) -> None:
        assert _maybe_number("It was published in 1847.") == 1847.0

    def test_word_number(self) -> None:
        assert _maybe_number("five") == 5.0
        assert _maybe_number("Twenty") == 20.0

    def test_no_number_returns_none(self) -> None:
        assert _maybe_number("Jane Ballou") is None
        assert _maybe_number("") is None


class TestWholeWordSubstring:
    def test_phrase_match(self) -> None:
        assert _whole_word_substring("president of the united states", "united states")

    def test_word_boundary_required(self) -> None:
        # "states" should NOT match inside "statesman"
        assert not _whole_word_substring("the renowned statesman", "states")

    def test_empty_needle(self) -> None:
        assert not _whole_word_substring("anything", "")


class TestExactMatch:
    def test_identical(self) -> None:
        r = grade_deterministic(pred="Jane Ballou", gold="Jane Ballou")
        assert r.correct is True
        assert r.method == "exact"

    def test_case_insensitive(self) -> None:
        r = grade_deterministic(pred="paris", gold="Paris")
        assert r.correct is True
        assert r.method == "exact"

    def test_punctuation_ignored(self) -> None:
        r = grade_deterministic(pred="Jane Ballou.", gold="Jane Ballou")
        assert r.correct is True


class TestNumericPath:
    def test_int_match(self) -> None:
        r = grade_deterministic(pred="The answer is 87", gold="87")
        assert r.correct is True
        assert r.method == "numeric"

    def test_word_number_matches_digit(self) -> None:
        r = grade_deterministic(pred="five", gold="5")
        assert r.correct is True
        assert r.method == "numeric"

    def test_off_by_more_than_tolerance_fails(self) -> None:
        r = grade_deterministic(pred="86", gold="87")
        # 86 vs 87, abs diff = 1, tol = max(0.01*87, 0.5) = 0.87 → fails
        assert r.correct is False
        assert r.method == "numeric_miss"

    def test_within_one_percent_passes(self) -> None:
        r = grade_deterministic(pred="100", gold="101")
        # 1.0 abs diff, tol = max(0.01*101, 0.5) = 1.01 → passes
        assert r.correct is True


class TestSubstringPath:
    def test_pred_contains_gold(self) -> None:
        r = grade_deterministic(
            pred="The answer is Jane Ballou according to records",
            gold="Jane Ballou",
        )
        assert r.correct is True
        assert r.method == "substring"

    def test_gold_contains_pred_with_minimum_length(self) -> None:
        # Gold = "John F Kennedy", pred = "Kennedy" → reverse substring,
        # ≥3 chars, but the FRAMES style usually accepts this.
        r = grade_deterministic(pred="Kennedy", gold="John F. Kennedy")
        assert r.correct is True
        assert r.method == "substring_reverse"

    def test_too_short_pred_no_reverse_credit(self) -> None:
        r = grade_deterministic(pred="of", gold="World of Warcraft")
        # "of" passes length but is a stopword; the article-stripping
        # normaliser removes it from gold, so substring fails. Either
        # way, the grader should NOT credit this.
        assert r.correct is False


class TestLexicalMiss:
    def test_completely_different_pred_falls_through(self) -> None:
        r = grade_deterministic(pred="London", gold="Paris")
        assert r.correct is False
        assert r.method == "lexical_miss"

    def test_empty_pred(self) -> None:
        r = grade_deterministic(pred="", gold="Paris")
        assert r.correct is False
        assert r.method == "empty_pred"

    def test_empty_gold_defensive(self) -> None:
        r = grade_deterministic(pred="something", gold="")
        # Defensive guard — gold should never be empty in practice.
        assert r.correct is False
        assert r.method == "empty_gold"


class TestGradeResultShape:
    def test_dict_has_all_expected_keys(self) -> None:
        r = grade_deterministic(pred="Paris", gold="Paris")
        d = r.to_dict()
        assert set(d) >= {
            "correct",
            "f1",
            "method",
            "normalised_pred",
            "normalised_gold",
            "judge_rationale",
        }
