"""A review scored against its gold: whether each point's verdict is right, whether the points that
needed a change got one and no other did, and whether the clause the experts cite was found."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from job_eval.contract_cases import ContractCase

from modules.jobs.word_clauses.decide import PointResult

_NEEDS_CHANGE = ("deviates", "missing")


@dataclass
class ScoredPoint:
    point: str
    gold: str
    said: str  # the model's verdict; "" when none could be read
    outcome: str  # the run's: changed, meets, not_covered or for_person
    right: bool  # the verdict said matches the gold
    changed_right: bool  # changed exactly when the gold needs a change
    # A cited paragraph holds expert evidence; None when the gold has none.
    located: bool | None
    codes: list[str] = field(default_factory=list)


@dataclass
class ContractScore:
    points: list[ScoredPoint]

    @property
    def correct(self) -> int:
        return sum(p.right for p in self.points)

    @property
    def outcome_correct(self) -> int:
        return sum(p.changed_right and p.outcome != "for_person" for p in self.points)

    @property
    def changes(self) -> dict[str, int]:
        """Changes made where the gold needs one, made where it needs none, and missed."""
        made = [p.outcome == "changed" for p in self.points]
        needed = [p.gold in _NEEDS_CHANGE for p in self.points]
        return {
            "right": sum(m and n for m, n in zip(made, needed, strict=True)),
            "unneeded": sum(m and not n for m, n in zip(made, needed, strict=True)),
            "missed": sum(n and not m for m, n in zip(made, needed, strict=True)),
        }

    @property
    def located(self) -> tuple[int, int]:
        """Points whose expert evidence a cited paragraph holds, of those with evidence."""
        known = [p.located for p in self.points if p.located is not None]
        return sum(known), len(known)

    def confusion(self) -> dict[str, int]:
        """Each wrong verdict as gold>said."""
        return dict(
            Counter(
                f"{p.gold}>{p.said or 'unread'}" for p in self.points if not p.right
            )
        )


def score_review(case: ContractCase, results: list[PointResult]) -> ContractScore:
    """Gold points the run did not review are scored as unread, never left out."""
    by_key = {r.point.key: r for r in results}
    scored = []
    for gold in case.gold:
        result = by_key.get(gold.point)
        said = result.said if result else ""
        outcome = result.verdict if result else "for_person"
        cited = set(result.paragraphs) if result else set()
        scored.append(
            ScoredPoint(
                point=gold.point,
                gold=gold.verdict,
                said=said,
                outcome=outcome,
                right=said == gold.verdict,
                changed_right=(outcome == "changed") == (gold.verdict in _NEEDS_CHANGE),
                located=bool(cited & set(gold.evidence)) if gold.evidence else None,
                codes=list(result.codes) if result else ["UNREACHED"],
            )
        )
    return ContractScore(scored)
