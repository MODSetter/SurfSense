"""What is wrong with a redlined copy as a file, apart from the review's judgement: it must open,
hold only SurfSense's changes, read as the original once they are rejected, and pass the engine's
own checks."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from modules.artifacts.revised_copies.engines import word
from modules.artifacts.revised_copies.engines.package import (
    PackageRefusedError,
    open_package,
    package_problems,
)
from modules.artifacts.revised_copies.engines.word_check import word_problems
from modules.artifacts.revised_copies.engines.word_xml import DEL, INS, w
from modules.jobs.word_clauses.contract import read_contract


def contract_problems(original: Path, revised: Path) -> list[str]:
    try:
        package = open_package(revised)
        main = word.main_part(package)
    except PackageRefusedError as refused:
        return [f"the copy does not open: {refused.message}"]
    problems = [*package_problems(package), *word_problems(package, main)]
    body = package.xml(main).find(w("body"))
    authors = {e.get(w("author")) for e in body.iter(INS, DEL)}
    if authors - {"SurfSense"}:
        problems.append(f"changes by others: {sorted(authors - {'SurfSense'})}")
    with TemporaryDirectory() as folder:
        rejected = Path(folder) / "rejected.docx"
        word.reject_all(revised, rejected)
        before = [c.text.strip() for c in read_contract(original).clauses]
        after = [c.text.strip() for c in read_contract(rejected).clauses]
    if before != after:
        first = next(
            (i for i, (a, b) in enumerate(zip(before, after, strict=False)) if a != b),
            min(len(before), len(after)),
        )
        problems.append(
            f"rejecting every change does not give back paragraph {first + 1}"
        )
    return problems
