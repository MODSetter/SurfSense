"""Trusted, version-controlled policy for queued deliverable kinds."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


@dataclass(frozen=True, slots=True)
class DeliverableKindSpec:
    max_duration_seconds: int
    max_scenes: int
    repair_cycles: int
    soft_time_limit_seconds: int
    hard_time_limit_seconds: int

    def __post_init__(self) -> None:
        if (
            self.max_duration_seconds <= 0
            or self.max_scenes <= 0
            or self.repair_cycles < 0
            or self.soft_time_limit_seconds <= 0
            or self.hard_time_limit_seconds <= self.soft_time_limit_seconds
        ):
            raise ValueError("deliverable kind policy must be positive and bounded")

    @property
    def max_repair_cycles(self) -> int:
        return self.repair_cycles

    @property
    def soft_time_limit(self) -> int:
        return self.soft_time_limit_seconds

    @property
    def hard_time_limit(self) -> int:
        return self.hard_time_limit_seconds


VIDEO_KIND: Final = "video"
VIDEO_SPEC: Final = DeliverableKindSpec(
    max_duration_seconds=180,
    max_scenes=12,
    repair_cycles=2,
    soft_time_limit_seconds=3600,
    hard_time_limit_seconds=3900,
)

DELIVERABLE_KIND_SPECS = MappingProxyType({VIDEO_KIND: VIDEO_SPEC})


def get_deliverable_kind_spec(kind: str) -> DeliverableKindSpec:
    try:
        return DELIVERABLE_KIND_SPECS[kind]
    except KeyError as exc:
        raise ValueError(f"unsupported deliverable kind: {kind!r}") from exc
