"""Tests for the CRAG 3-class deterministic grader.

The LLM-judge fallback is excluded here (network call); these tests
exercise the deterministic shortcut + the special-case routing for
``false_premise`` questions and refusal detection (``I don't know``).
"""

from __future__ import annotations

from surfsense_evals.suites.research.crag.grader import (
    CragGradeResult,
    _flags_false_premise,
    _is_refusal,
    _maybe_number,
    _normalise,
    _whole_word_substring,
    grade_deterministic,
)


class TestNormalisation:
    def test_lowercase_and_punct_stripped(self) -> None:
        assert _normalise("Apple Inc.") == "apple inc"

    def test_articles_removed(self) -> None:
        assert _normalise("The Apple Watch") == "apple watch"

    def test_empty_returns_empty(self) -> None:
        assert _normalise("") == ""


class TestNumericExtraction:
    def test_simple_int(self) -> None:
        assert _maybe_number("42") == 42.0

    def test_int_with_commas(self) -> None:
        assert _maybe_number("$1,234") == 1234.0

    def test_year_in_sentence(self) -> None:
        assert _maybe_number("released in 2008") == 2008.0

    def test_word_number(self) -> None:
        assert _maybe_number("seven") == 7.0


class TestWholeWordSubstring:
    def test_phrase_match(self) -> None:
        assert _whole_word_substring("the new york yankees", "new york")

    def test_word_boundary_required(self) -> None:
        assert not _whole_word_substring("yorkshire", "york")


class TestRefusalDetection:
    def test_explicit_idk(self) -> None:
        assert _is_refusal("Answer: I don't know")

    def test_idk_no_apostrophe(self) -> None:
        assert _is_refusal("I dont know")

    def test_no_information(self) -> None:
        assert _is_refusal("There is no information available about this.")

    def test_unable_to_answer(self) -> None:
        assert _is_refusal("I am unable to answer this question.")

    def test_empty_is_refusal(self) -> None:
        assert _is_refusal("")
        assert _is_refusal("   ")

    def test_real_answer_is_not_refusal(self) -> None:
        assert not _is_refusal("Answer: Apple Inc")
        assert not _is_refusal("The CEO is Tim Cook.")


class TestFalsePremiseDetection:
    def test_explicit_false_premise(self) -> None:
        assert _flags_false_premise(
            "The question contains a false premise; the company never had that product."
        )

    def test_no_such(self) -> None:
        assert _flags_false_premise("There is no such album.")

    def test_did_not_happen(self) -> None:
        assert _flags_false_premise("That event did not happen.")

    def test_does_not_exist(self) -> None:
        assert _flags_false_premise("That movie does not exist.")

    def test_normal_answer_is_not_premise_flag(self) -> None:
        assert not _flags_false_premise("Apple, headquartered in Cupertino.")


class TestGradeDeterministicHappyPath:
    def test_exact_match_correct(self) -> None:
        result = grade_deterministic(pred="Tim Cook", gold="Tim Cook", question_type="simple")
        assert result.grade == "correct"
        assert result.score == 1
        assert result.method == "exact"

    def test_substring_match(self) -> None:
        result = grade_deterministic(
            pred="The answer is Tim Cook, CEO of Apple.",
            gold="Tim Cook",
            question_type="simple",
        )
        assert result.grade == "correct"
        assert result.method == "substring"

    def test_alt_answer_match(self) -> None:
        result = grade_deterministic(
            pred="2,008",
            gold="two thousand eight",
            alt_answers=["2008"],
            question_type="simple",
        )
        assert result.grade == "correct"
        assert result.score == 1

    def test_numeric_within_tolerance(self) -> None:
        result = grade_deterministic(
            pred="The revenue was $1,234,000 USD",
            gold="$1,234,123",
            question_type="aggregation",
        )
        assert result.grade == "correct"
        assert result.method == "numeric"

    def test_numeric_outside_tolerance(self) -> None:
        result = grade_deterministic(
            pred="100",
            gold="500",
            question_type="aggregation",
        )
        assert result.grade == "incorrect"
        assert result.score == -1

    def test_numeric_strict_small_currency(self) -> None:
        # CRAG (unlike FRAMES) does not apply a 0.5 absolute floor —
        # ``$2.05`` should NOT match ``$2.17`` (≈5.5% off, well over 1%).
        result = grade_deterministic(
            pred="$2.05",
            gold="$2.17",
            question_type="simple",
        )
        # Falls through to lexical_miss (no substring overlap either).
        assert result.grade == "incorrect"
        assert result.method == "lexical_miss"


class TestGradeDeterministicRefusal:
    def test_idk_maps_to_missing(self) -> None:
        result = grade_deterministic(
            pred="I don't know.", gold="Tim Cook", question_type="simple",
        )
        assert result.grade == "missing"
        assert result.score == 0
        assert result.method == "refusal"

    def test_empty_pred_maps_to_missing(self) -> None:
        result = grade_deterministic(pred="", gold="Tim Cook", question_type="simple")
        assert result.grade == "missing"

    def test_no_information_maps_to_missing(self) -> None:
        result = grade_deterministic(
            pred="There is not enough information to answer.",
            gold="42",
            question_type="simple",
        )
        assert result.grade == "missing"


class TestGradeDeterministicFalsePremise:
    def test_flagging_premise_is_correct(self) -> None:
        result = grade_deterministic(
            pred="The question contains a false premise; that movie does not exist.",
            gold="invalid question",
            question_type="false_premise",
        )
        assert result.grade == "correct"
        assert result.method == "false_premise_flagged"

    def test_committing_to_false_answer_is_unclear(self) -> None:
        # Should land in false_premise_unclear → judge fallback territory.
        result = grade_deterministic(
            pred="The album was released in 2010.",
            gold="invalid question",
            question_type="false_premise",
        )
        assert result.grade == "incorrect"
        assert result.method == "false_premise_unclear"

    def test_idk_on_false_premise_is_missing(self) -> None:
        # Refusal precedes false-premise routing.
        result = grade_deterministic(
            pred="I don't know.",
            gold="invalid question",
            question_type="false_premise",
        )
        assert result.grade == "missing"


class TestGradeDeterministicLexicalMiss:
    def test_unknown_paraphrase_routes_to_judge(self) -> None:
        result = grade_deterministic(
            pred="It is the technology giant in Cupertino.",
            gold="Apple Inc",
            question_type="simple",
        )
        # Without a judge, we fall through to lexical_miss → incorrect.
        assert result.grade == "incorrect"
        assert result.method == "lexical_miss"

    def test_short_pred_no_substring_credit(self) -> None:
        # Reverse-substring path requires len >= 3 to credit.
        result = grade_deterministic(
            pred="JK",
            gold="JK Rowling",
            question_type="simple",
        )
        assert result.grade == "incorrect"


class TestGradeResultShape:
    def test_to_dict_round_trip(self) -> None:
        result = CragGradeResult(
            grade="correct", score=1, method="exact",
            normalised_pred="x", normalised_gold="x",
        )
        d = result.to_dict()
        assert d["grade"] == "correct"
        assert d["score"] == 1
        assert d["method"] == "exact"

    def test_score_matches_grade(self) -> None:
        # Construct via grader so the score field is populated correctly.
        for gold, pred, want_grade in (
            ("hi", "hi", "correct"),
            ("hi", "I don't know", "missing"),
            ("hi", "bye", "incorrect"),
        ):
            result = grade_deterministic(pred=pred, gold=gold, question_type="simple")
            assert result.grade == want_grade
            expected_score = {"correct": 1, "missing": 0, "incorrect": -1}[want_grade]
            assert result.score == expected_score
