"""What Studio and the agent say about a review: its counts, each point's verdict and the playbook
position it rests on, and what was left to a person."""

from __future__ import annotations

from typing import Any

from modules.jobs.word_clauses.contract import Contract
from modules.jobs.word_clauses.decide import PointResult
from modules.jobs.word_clauses.review import ReviewResult

RUNNER = "word-clauses/1"


def report_of(
    review: ReviewResult, model: str, checker: str | None = None
) -> dict[str, Any]:
    return {
        "runner": RUNNER,
        "model": model,
        "checker": checker,
        "settings": review.settings,
        "seconds": review.seconds,
        "whole_sources": review.whole_sources,
        "whole_contract": review.whole_contract,
        "points": len(review.results),
        "clauses": len(review.contract.clauses),
        "counts": review.counts,
        "answers": [_answer(r, review.contract) for r in review.results],
        "exceptions": review.exceptions,
    }


def _answer(result: PointResult, contract: Contract) -> dict[str, Any]:
    change = result.change
    changed = None
    if change is not None:
        clause = contract.clauses[change.clause]
        changed = {
            "kind": change.kind,
            "paragraph": clause.id,
            "label": clause.label,
            "old": clause.text[change.start : change.end],
            "new": change.new_text,
        }
    labels = []
    for clause_id in result.paragraphs:
        index = contract.find(clause_id)
        labels.append(contract.clauses[index].label if index is not None else "")
    return {
        "key": result.point.key,
        "title": result.point.title,
        "verdict": result.verdict,
        "said": result.said,
        "paragraphs": result.paragraphs,
        "labels": labels,
        "change": changed,
        "source": result.source,
        "section": result.section,
        "quote": result.quote,
        "comment": result.external,
        "note": result.internal,
        "codes": result.codes,
        "why": result.why,
    }
