"""What contacting one server found: problems fail the pull request, warnings only inform it."""

from dataclasses import dataclass, field


@dataclass
class Findings:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, other: "Findings") -> None:
        self.problems += other.problems
        self.warnings += other.warnings
