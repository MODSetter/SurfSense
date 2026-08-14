"""Canonical user-visible streaming data contracts."""

from typing import Literal, NotRequired, TypedDict

ActivityCategory = Literal["file", "research", "artifact", "connector", "action"]
ActivityStatus = Literal[
    "running",
    "awaiting_approval",
    "completed",
    "error",
    "cancelled",
    "interrupted",
]
ActivityTimingStatus = Literal["running", "paused", "completed"]


class ActivityIntegration(TypedDict):
    source: Literal["native", "connector", "mcp"]
    key: NotRequired[str]
    name: NotRequired[str]


class ActivityTimingData(TypedDict):
    status: ActivityTimingStatus
    activeDurationMs: int
    sampledAt: NotRequired[str]


class ActivityData(TypedDict):
    """Full snapshot used identically on the wire and in persistence."""

    id: str
    sequence: int
    kind: str
    status: ActivityStatus
    title: str
    category: ActivityCategory
    iconKey: str
    details: NotRequired[list[str]]
    startedAt: str
    completedAt: NotRequired[str]
    integration: NotRequired[ActivityIntegration]
