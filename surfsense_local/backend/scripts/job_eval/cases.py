"""A job's eval cases: real files in, a gold answer per scored cell, and where each file came from.

Cases live with the job's own content (its pack's private repository), never in this tree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GoldRow:
    sheet: str
    cell: str
    question: str
    answer: str
    evidence: str  # where the deciding passage is, for a person checking a miss


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    job: str
    workbook: Path
    sources: tuple[Path, ...]
    gold: tuple[GoldRow, ...]
    gold_status: str  # "draft", "model-checked" or "hand-checked"
    folder: Path

    def gold_at(self, sheet: str, cell: str) -> GoldRow | None:
        return next(
            (
                g
                for g in self.gold
                if g.sheet.casefold() == sheet.casefold() and g.cell == cell
            ),
            None,
        )


def load_cases(eval_dir: Path, only: list[str] | None = None) -> list[Case]:
    cases = []
    for case_file in sorted((eval_dir / "cases").glob("*/case.json")):
        raw = json.loads(case_file.read_text(encoding="utf-8"))
        if only and raw["id"] not in only:
            continue
        folder = case_file.parent
        gold = json.loads((folder / raw["gold"]).read_text(encoding="utf-8"))
        cases.append(
            Case(
                id=raw["id"],
                title=raw["title"],
                job=raw["job"],
                workbook=folder / raw["workbook"],
                sources=tuple(folder / s for s in raw["sources"]),
                gold=tuple(
                    GoldRow(
                        sheet=row["sheet"],
                        cell=row["cell"],
                        question=row["question"],
                        answer=row["answer"],
                        evidence=row.get("evidence", ""),
                    )
                    for row in gold["rows"]
                ),
                gold_status=gold.get("status", "draft"),
                folder=folder,
            )
        )
    return cases
