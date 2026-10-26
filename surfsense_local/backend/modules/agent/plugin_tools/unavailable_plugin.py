"""A ready plugin a turn cannot use, or uses only in part, and why, as either engine reports it."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class UnavailablePlugin:
    title: str
    reason: Literal["unreachable", "sign_in", "license"]
