"""The job skills installed packs bring, for the agent's configuration to list and allow by name."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from modules.jobs.packs.installed import installed_packs


@dataclass(frozen=True)
class JobSkill:
    name: str  # the skill's folder name, which opencode allows it by
    folder: Path  # the folder holding it, which opencode scans for skills


def job_skills() -> tuple[JobSkill, ...]:
    found = []
    for pack in installed_packs():
        for job in pack.manifest.jobs:
            if job.skill is None:
                continue
            relative = PurePosixPath(job.skill)
            found.append(
                JobSkill(relative.name, pack.path(str(relative.parent)).resolve())
            )
    return tuple(sorted(found, key=lambda skill: skill.name))
