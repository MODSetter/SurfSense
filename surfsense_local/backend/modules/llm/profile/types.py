from dataclasses import dataclass
from enum import StrEnum


class Tier(StrEnum):
    """How much prompt structure a model wants. The value names its prompt file."""

    COMPACT = "compact"
    CAPABLE = "capable"
    FRONTIER = "frontier"


class Line(StrEnum):
    """Where a model sits in its own vendor's line-up, when it states no count."""

    FLAGSHIP = "flagship"
    SMALL = "small"


@dataclass(frozen=True)
class Fingerprint:
    """What is known about the selected model. Unknown stays None."""

    provider: str
    name: str
    params_b: float | None = None
    vendor: str | None = None
    line: Line | None = None
