"""The build to recommend on this machine: the default, or the nearest below it.

Never above the default, however much memory is spare: the default is chosen for
quality per byte, and a larger build that also fits costs several times the
download for little gain. The gate is the speed tier the badge reads, so a
recommended build never carries a badge saying it will be slow.
"""

from collections.abc import Callable, Sequence
from typing import Protocol

from modules.llm.fit import RECOMMENDABLE_TIERS, SpeedTier


class Sized(Protocol):
    @property
    def footprint_bytes(self) -> int: ...


def recommended_build[B: Sized](
    builds: Sequence[B], default: B | None, tier_of: Callable[[B], SpeedTier]
) -> B | None:
    """The default when it runs well here, else the largest smaller build that
    does, else None: every build physics allows stays installable, unstarred."""
    if default is None:
        return None
    if tier_of(default) in RECOMMENDABLE_TIERS:
        return default
    smaller = sorted(
        (b for b in builds if b.footprint_bytes < default.footprint_bytes),
        key=lambda b: b.footprint_bytes,
        reverse=True,
    )
    return next((b for b in smaller if tier_of(b) in RECOMMENDABLE_TIERS), None)
