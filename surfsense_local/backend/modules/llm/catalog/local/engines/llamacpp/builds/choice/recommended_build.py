"""The build to recommend on this machine: the default, or the nearest below it.

Never above the default, however much memory is spare: the default is chosen for
quality per byte, and a larger build that also fits costs several times the
download for little gain. Never below four bits either: past that floor the star
belongs on a smaller model. The gate is the speed tier the badge reads, so a
recommended build never carries a badge saying it will be slow.
"""

from collections.abc import Callable, Sequence
from typing import Protocol

from modules.llm.catalog.local.engines.llamacpp.builds.choice.preference import RECOMMENDABLE
from modules.llm.fit import RECOMMENDABLE_TIERS, SpeedTier


class Sized(Protocol):
    @property
    def quantization(self) -> str: ...

    @property
    def footprint_bytes(self) -> int: ...


def recommended_build[B: Sized](
    builds: Sequence[B], default: B | None, tier_of: Callable[[B], SpeedTier]
) -> B | None:
    """The default when it runs well here, else the largest smaller build at or
    above four bits that does, else None: every build physics allows stays
    installable, unstarred."""
    if default is None:
        return None
    candidates = sorted(
        (
            b
            for b in builds
            if b.footprint_bytes <= default.footprint_bytes
            and b.quantization.upper() in RECOMMENDABLE
        ),
        key=lambda b: (b is not default, -b.footprint_bytes),
    )
    return next((b for b in candidates if tier_of(b) in RECOMMENDABLE_TIERS), None)
