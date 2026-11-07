"""The app's job runners by the name a pack gives them: each one's config and the file it works on."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from modules.jobs.packs.manifest import PackJob
from modules.jobs.settings.declared import DeclaresSettings
from modules.jobs.word_clauses.config import load_config as clause_config
from modules.jobs.workbook_rows.config import load_config as workbook_config


@dataclass(frozen=True)
class Runner:
    load_config: Callable[[Path], DeclaresSettings]
    formats: tuple[str, ...]  # the file's format, as a revised copy names it
    # Each finishes a sentence that starts with the job's name.
    takes: str
    reads: str


BY_NAME: dict[str, Runner] = {
    "workbook-rows/1": Runner(
        workbook_config,
        ("xlsx",),
        "fills in a workbook (.xlsx or .xlsm)",
        "answers from the firm's own documents: select them too.",
    ),
    "word-clauses/1": Runner(
        clause_config,
        ("docx",),
        "reviews a Word contract (.docx)",
        "checks the contract against the firm's playbook: select it too.",
    ),
}


def runner_of(job: PackJob) -> Runner:
    """Install refuses a pack naming a runner this app lacks, so every installed job has one."""
    return BY_NAME[job.runner]
