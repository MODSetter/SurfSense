"""The contract eval scores each gold point once, unread ones included, and finds what is wrong
with a redlined copy as a file."""

import docx
import pytest
from job_eval.contract_cases import ContractCase, GoldPoint
from job_eval.contract_integrity import contract_problems
from job_eval.contract_score import score_review

from modules.artifacts.revised_copies.engines import word
from modules.jobs.word_clauses.config import ReviewPoint
from modules.jobs.word_clauses.decide import PointResult

pytestmark = pytest.mark.unit


def _case(tmp_path, *gold: GoldPoint) -> ContractCase:
    return ContractCase(
        "nda",
        "NDA",
        "contract-redline",
        tmp_path / "c.docx",
        (),
        gold,
        "draft",
        tmp_path,
    )


def _result(key: str, said: str, verdict: str, *paragraphs: str) -> PointResult:
    return PointResult(
        ReviewPoint(key, key, ""), verdict, said=said, paragraphs=list(paragraphs)
    )


def test_each_gold_point_is_scored_once_and_an_unread_one_counts_against_the_run(
    tmp_path,
):
    """Verdicts, changes and found clauses are counted per gold point; a point the run never
    reviewed is a miss, not a gap in the denominator."""
    case = _case(
        tmp_path,
        GoldPoint("notice", "deviates", ("P4",), "requires + Contradiction"),
        GoldPoint("oral", "meets", ("P2",), "requires + Entailment"),
        GoldPoint("copies", "not_covered", (), "silent"),
        GoldPoint("survival", "missing", (), "requires + NotMentioned"),
    )
    results = [
        _result("notice", "deviates", "changed", "P4"),
        _result("oral", "deviates", "changed", "P3"),
        _result("copies", "not_covered", "not_covered"),
    ]

    scored = score_review(case, results)

    assert (scored.correct, scored.outcome_correct) == (2, 2)
    assert scored.changes == {"right": 1, "unneeded": 1, "missed": 1}
    assert scored.located == (1, 2)
    assert scored.confusion() == {"meets>deviates": 1, "missing>unread": 1}


def _nda(path):
    document = docx.Document()
    document.add_paragraph("The Receiving Party may disclose it when required by law.")
    document.save(path)
    return path


def test_a_copy_with_surfsense_changes_alone_that_rejects_to_the_original_passes(
    tmp_path,
):
    """A redlined copy that opens, holds only SurfSense's changes and gives back the original
    once they are rejected has no problems."""
    original = _nda(tmp_path / "nda.docx")
    revised = tmp_path / "revised.docx"
    word.apply(
        original,
        [
            {
                "op": "replace_text",
                "quote": "required by law",
                "text": "a court orders it",
            }
        ],
        revised,
    )

    assert contract_problems(original, revised) == []


def test_a_change_by_another_author_is_a_problem(tmp_path):
    """Only SurfSense's changes may be in the copy."""
    original = _nda(tmp_path / "nda.docx")
    revised = tmp_path / "revised.docx"
    word.apply(
        original,
        [{"op": "replace_text", "quote": "required by law", "text": "ordered"}],
        revised,
        author="Someone else",
    )

    assert contract_problems(original, revised) == [
        "changes by others: ['Someone else']"
    ]
