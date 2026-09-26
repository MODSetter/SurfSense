"""What a ranking earns against a query's answer, by the eval's rules."""

import pytest
from retrieval_eval.cases import Query
from retrieval_eval.score import Ranking, score

pytestmark = pytest.mark.unit

WARRANTY = Query(
    id="warranty",
    slice="english",
    text="How long is the warranty on the Kestrel X200?",
    expect=["covered for 27 months"],
)


def _hits(*passages: str) -> list[str]:
    return list(passages)


def test_the_answer_at_the_top_scores_full_marks() -> None:
    """Rank 1 is what chat reads first, so it is the best a ranking can do."""
    result = score(
        WARRANTY,
        _hits("The X200 is covered for 27 months.", "Returns run 30 days."),
    )

    assert result == Ranking(found=True, rank=1, in_top_5=True)


def test_the_answer_further_down_is_still_found_but_ranked_lower() -> None:
    """chat sends five passages, so rank 4 still reaches the model."""
    result = score(
        WARRANTY,
        _hits(
            "Returns run 30 days.",
            "Rinse the jar.",
            "Shelf B.",
            "Covered for 27 months.",
        ),
    )

    assert result == Ranking(found=True, rank=4, in_top_5=True)


def test_an_answer_below_the_fifth_passage_never_reaches_the_model() -> None:
    """Found by retrieval, but outside what chat puts in the prompt."""
    result = score(
        WARRANTY,
        _hits("a", "b", "c", "d", "e", "The X200 is covered for 27 months."),
    )

    assert result == Ranking(found=True, rank=6, in_top_5=False)


def test_a_ranking_without_the_answer_is_a_miss() -> None:
    """Nothing retrieved answers the query, so there is no rank to report."""
    result = score(WARRANTY, _hits("Returns run 30 days.", "Rinse the jar."))

    assert result == Ranking(found=False, rank=None, in_top_5=False)
