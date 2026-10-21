"""A ready plugin a turn cannot use, or uses only in part, and why, as either engine reports it."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class UnavailablePlugin:
    title: str
    # `left_out`: some of its tools were not offered, for want of room in the window.
    reason: Literal["unreachable", "sign_in", "license", "left_out"]
