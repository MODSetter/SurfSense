"""What a run earns on its case: each gold cell's answer, and the two numbers the job gate holds,
accuracy and "Yes" without support.

A "Yes" counts as unsupported when it has no quote found in a source, and as false when the
gold answer is not "Yes": the quote exists but does not settle the question.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from job_eval.cases import Case

from modules.jobs.workbook_rows.decide import RowResult

YES = "Yes"


@dataclass
class RowScore:
    sheet: str
    cell: str
    question: str
    gold: str
    answer: str  # "" when the job never reached the cell
    said: str | None
    correct: bool
    quote: str
    source: str
    codes: list[str]
    evidence: str
    missing: str  # what the second check found the quote leaves out


@dataclass
class CaseScore:
    case: str
    rows: list[RowScore] = field(default_factory=list)
    dropdown_violations: int = 0
    integrity: list[str] = field(default_factory=list)

    @property
    def correct(self) -> int:
        return sum(1 for r in self.rows if r.correct)

    @property
    def accuracy(self) -> float:
        return self.correct / len(self.rows) if self.rows else 0.0

    @property
    def yes_without_quote(self) -> int:
        return sum(1 for r in self.rows if r.answer == YES and not r.quote)

    @property
    def false_yes(self) -> int:
        return sum(1 for r in self.rows if r.answer == YES and r.gold != YES)

    @property
    def unreached(self) -> int:
        return sum(1 for r in self.rows if not r.answer)

    def confusion(self) -> dict[str, int]:
        """Gold to answer, as "Yes>Needs review" counts, misses only."""
        return dict(
            Counter(
                f"{r.gold}>{r.answer or 'unreached'}"
                for r in self.rows
                if not r.correct
            )
        )


def score_case(case: Case, results: list[RowResult]) -> CaseScore:
    by_cell = {(r.row.sheet.casefold(), r.row.answer_cell): r for r in results}
    scored = CaseScore(case.id)
    for gold in case.gold:
        result = by_cell.get((gold.sheet.casefold(), gold.cell))
        answer = result.answer if result else ""
        scored.rows.append(
            RowScore(
                sheet=gold.sheet,
                cell=gold.cell,
                question=gold.question,
                gold=gold.answer,
                answer=answer,
                said=result.said if result else None,
                correct=answer == gold.answer,
                quote=result.quote if result else "",
                source=result.source if result else "",
                codes=list(result.codes) if result else ["UNREACHED"],
                evidence=gold.evidence,
                missing=result.missing if result else "",
            )
        )
    scored.dropdown_violations = sum(
        1
        for r in results
        if r.written is not None
        and r.row.allowed is not None
        and r.written not in r.row.allowed
    )
    return scored
