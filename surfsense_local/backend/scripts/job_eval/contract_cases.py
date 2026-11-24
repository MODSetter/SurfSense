"""A contract job's eval cases: a real contract, the firm's real playbook, and the gold verdict on
each review point, with the expert evidence it rests on.

Cases live with the job's own content (its pack's private repository), never in this tree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

VERDICTS = ("meets", "deviates", "missing", "not_covered")


@dataclass(frozen=True)
class GoldPoint:
    point: str  # the review point's key
    verdict: str  # one of VERDICTS
    evidence: tuple[str, ...]  # the paragraphs the experts' evidence sits in, as "P<n>"
    basis: str  # what the verdict follows from, for a person checking a miss


@dataclass(frozen=True)
class ContractCase:
    id: str
    title: str
    job: str
    contract: Path
    sources: tuple[Path, ...]
    gold: tuple[GoldPoint, ...]
    gold_status: str  # "draft", "model-checked" or "hand-checked"
    folder: Path


def load_contract_cases(
    eval_dir: Path, only: list[str] | None = None
) -> list[ContractCase]:
    cases = []
    for case_file in sorted((eval_dir / "cases").glob("*/case.json")):
        raw = json.loads(case_file.read_text(encoding="utf-8"))
        if only and raw["id"] not in only:
            continue
        folder = case_file.parent
        gold = json.loads((folder / raw["gold"]).read_text(encoding="utf-8"))
        points = tuple(
            GoldPoint(
                point=row["point"],
                verdict=row["verdict"],
                evidence=tuple(row.get("evidence", ())),
                basis=row.get("basis", ""),
            )
            for row in gold["points"]
        )
        wrong = [p.verdict for p in points if p.verdict not in VERDICTS]
        if wrong:
            raise ValueError(f"{raw['id']}: no verdict named {wrong[0]!r}")
        cases.append(
            ContractCase(
                id=raw["id"],
                title=raw["title"],
                job=raw["job"],
                contract=folder / raw["contract"],
                sources=tuple(folder / s for s in raw["sources"]),
                gold=points,
                gold_status=gold.get("status", "draft"),
                folder=folder,
            )
        )
    return cases
