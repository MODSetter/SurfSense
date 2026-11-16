"""The contract as a call shows it: every clause by its id and list number, or, when the whole
contract would crowd the model's window, the clauses nearest the point."""

from __future__ import annotations

from modules.jobs.evidence.passages import Passage
from modules.jobs.evidence.retrieval import Embed, Retriever
from modules.jobs.word_clauses.config import ReviewPoint
from modules.jobs.word_clauses.contract import Clause, Contract


def clause_line(clause: Clause) -> str:
    """`[P12 | 4.2] text`: the number beside the id, so it is never taken for quotable text."""
    tag = f"{clause.id} | {clause.label}" if clause.label else clause.id
    return f"[{tag}] {clause.text.strip()}"


class Outline:
    def __init__(
        self,
        contract: Contract,
        budget_chars: int,
        per_point: int,
        embed: Embed | None = None,
    ) -> None:
        self._contract = contract
        self._lines = [clause_line(c) for c in contract.clauses]
        self.full = "\n".join(self._lines)
        self.whole = len(self.full) <= budget_chars
        self._retriever = None
        if not self.whole:
            # A budget of nothing ranks every clause rather than showing them all.
            self._retriever = Retriever(
                [
                    Passage(0, "", c.label, n, n, c.text)
                    for n, c in enumerate(contract.clauses, start=1)
                ],
                0,
                per_point,
                embed=embed,
            )

    def for_point(self, point: ReviewPoint) -> str:
        if self._retriever is None:
            return self.full
        shown = self._retriever.for_question(point_query(point))
        lines, previous = [], -1
        for index in shown:
            if previous >= 0 and index > previous + 1:
                lines.append("[...]")
            lines.append(self._lines[index])
            previous = index
        return "\n".join(lines)


def point_query(point: ReviewPoint) -> str:
    """What a point is searched by, in the contract and in the playbook."""
    return " ".join([point.title, point.covers, *point.queries])
