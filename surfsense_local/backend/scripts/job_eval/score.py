"""What a run earns on its case: each gold cell's answer, and the two numbers the job gate holds,
accuracy and "Yes" without support.

A "Yes" counts as unsupported when it has no quote found in a source, and as false when the
gold answer is not "Yes": the quote exists but does not settle the question.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from job_eval.cases import Case

from modules.jobs.workbook_rows.cell_answers import cell_value
from modules.jobs.workbook_rows.config import JobConfig
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
    cited: list[dict]  # every quote found in a source: source, section, line, quote
    evidence: str
    missing: str  # what the second check found the quote leaves out
    comment: str = ""
    looked_again: bool = False
    trace: list[dict] = field(default_factory=list)
    # The passages the question saw, by number; [] when it saw every passage.
    shown: list[int] = field(default_factory=list)


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


def score_case(
    case: Case, results: list[RowResult], config: JobConfig | None = None
) -> CaseScore:
    fallback = config.fallback.answer if config else "Needs review"
    by_cell = {(r.row.sheet.casefold(), r.row.answer_cell): r for r in results}
    scored = CaseScore(case.id)
    for gold in case.gold:
        result = by_cell.get((gold.sheet.casefold(), gold.cell))
        answer = result.answer if result else ""
        said = result.said if result else None
        if result and "NOT_ON_DROPDOWN" in result.codes:
            # The cell could not hold the answer and was left blank: the requester's workbook
            # says nothing, as for any row left to a person.
            answer, said = fallback, result.answer
        expected = gold.answer
        choice = config.choice(gold.answer) if config else None
        if result and choice and cell_value(choice, result.row.allowed) is None:
            # A gold answer the cell cannot hold is one no job can write: the right outcome
            # is the blank a person fills, as for an answer the job could not write.
            expected = fallback
        scored.rows.append(
            RowScore(
                sheet=gold.sheet,
                cell=gold.cell,
                question=gold.question,
                gold=gold.answer,
                answer=answer,
                said=said,
                correct=answer == expected,
                quote=result.quote if result else "",
                source=result.source if result else "",
                codes=list(result.codes) if result else ["UNREACHED"],
                cited=[c.__dict__ for c in result.cited] if result else [],
                evidence=gold.evidence,
                missing=result.missing if result else "",
                comment=result.comment if result else "",
                looked_again=result.looked_again if result else False,
                trace=result.trace if result else [],
                shown=result.shown if result else [],
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
