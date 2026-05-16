"""Tests for the MMLongBench-Doc format-aware grader.

The grader is the critical correctness piece for the open-ended
benchmark (no MCQ shortcut), so we cover all five formats with
representative happy-path + edge-case rows.
"""

from __future__ import annotations

import pytest

from surfsense_evals.suites.multimodal_doc.mmlongbench.grader import grade


class TestStrFormat:
    def test_exact_match(self) -> None:
        r = grade(pred="Apollo 11", gold="Apollo 11", answer_format="Str")
        assert r.correct is True
        assert r.f1 == 1.0
        assert r.method == "str_norm"

    def test_lowercase_normalised(self) -> None:
        r = grade(pred="paris", gold="Paris", answer_format="Str")
        assert r.correct is True

    def test_punctuation_difference_drops_to_substring(self) -> None:
        # "N.A.S.A." normalises to "n a s a" (whitespace tokens) which
        # doesn't equal "nasa" — but the F1 token overlap is still 0
        # because none of the single letters appear standalone in "nasa".
        # We assert the grader fails closed rather than over-claiming.
        r = grade(pred="N.A.S.A.", gold="NASA", answer_format="Str")
        assert r.correct is False  # explicit: this is a failure mode we accept

    def test_substring_credit(self) -> None:
        r = grade(pred="The answer is Paris.", gold="Paris", answer_format="Str")
        assert r.correct is True

    def test_completely_wrong(self) -> None:
        r = grade(pred="London", gold="Paris", answer_format="Str")
        assert r.correct is False
        assert r.f1 < 0.5

    def test_empty_pred(self) -> None:
        r = grade(pred="", gold="Paris", answer_format="Str")
        assert r.correct is False
        assert r.f1 == 0.0


class TestIntFormat:
    def test_exact_int(self) -> None:
        assert grade(pred="42", gold="42", answer_format="Int").correct is True

    def test_int_in_sentence(self) -> None:
        assert grade(pred="The answer is 42 years.", gold="42", answer_format="Int").correct is True

    def test_int_with_commas(self) -> None:
        assert grade(pred="1,500", gold="1500", answer_format="Int").correct is True

    def test_wrong_int(self) -> None:
        assert grade(pred="41", gold="42", answer_format="Int").correct is False

    def test_no_int_in_pred(self) -> None:
        assert grade(pred="not answerable", gold="42", answer_format="Int").correct is False


class TestFloatFormat:
    def test_exact_float(self) -> None:
        assert grade(pred="3.14", gold="3.14", answer_format="Float").correct is True

    def test_within_tolerance(self) -> None:
        # 1% tolerance — 3.14 vs 3.13 is well within.
        assert grade(pred="3.13", gold="3.14", answer_format="Float").correct is True

    def test_outside_tolerance(self) -> None:
        assert grade(pred="3.5", gold="3.14", answer_format="Float").correct is False

    def test_european_decimal_comma(self) -> None:
        # ``3,14`` should parse as 3.14
        assert grade(pred="3,14", gold="3.14", answer_format="Float").correct is True

    def test_zero_gold_with_small_abs_diff(self) -> None:
        # Absolute tolerance of 0.01 should kick in for near-zero golds.
        assert grade(pred="0.005", gold="0", answer_format="Float").correct is True


class TestListFormat:
    def test_exact_set_match(self) -> None:
        r = grade(pred="apple, banana, cherry", gold="apple, banana, cherry", answer_format="List")
        assert r.correct is True
        assert r.f1 == pytest.approx(1.0)

    def test_set_match_different_order(self) -> None:
        r = grade(pred="cherry, apple, banana", gold="apple, banana, cherry", answer_format="List")
        assert r.correct is True

    def test_partial_overlap_gives_f1(self) -> None:
        r = grade(pred="apple, banana", gold="apple, banana, cherry", answer_format="List")
        assert r.correct is False
        assert 0.0 < r.f1 < 1.0

    def test_extra_items_lower_precision(self) -> None:
        r = grade(pred="apple, banana, cherry, date", gold="apple, banana, cherry", answer_format="List")
        assert 0.0 < r.f1 < 1.0
        # Recall=1, precision=3/4 → F1 ~= 0.857
        assert r.f1 == pytest.approx(2 * (3 / 4) * 1 / (3 / 4 + 1), rel=1e-3)


class TestNoneFormat:
    def test_unknown_phrase_credited(self) -> None:
        for phrase in ("Not answerable", "I cannot answer this.", "No answer", "N/A"):
            r = grade(pred=phrase, gold="Not answerable", answer_format="None")
            assert r.correct is True, phrase

    def test_actual_answer_marked_wrong(self) -> None:
        # The arm hallucinated an answer when it should have said "I don't know".
        r = grade(pred="The answer is 42.", gold="Not answerable", answer_format="None")
        assert r.correct is False


class TestUnknownFormatFallsBackToStr:
    def test_blank_format_uses_str_grader(self) -> None:
        r = grade(pred="Paris", gold="Paris", answer_format="")
        assert r.correct is True
        assert r.method == "str_norm"

    def test_garbage_format_uses_str_grader(self) -> None:
        r = grade(pred="Paris", gold="Paris", answer_format="quux")
        assert r.correct is True
        assert r.method == "str_norm"
