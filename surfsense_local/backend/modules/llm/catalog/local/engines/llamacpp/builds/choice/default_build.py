"""The build a model should run as, before anything is known about the machine."""

from collections.abc import Sequence
from typing import Protocol

from modules.llm.catalog.local.engines.llamacpp.builds.choice.preference import (
    PREFERENCE,
)


class Labelled(Protocol):
    @property
    def quantization(self) -> str: ...


def default_build[B: Labelled](
    builds: Sequence[B],
    preference: Sequence[str] = PREFERENCE,
    *,
    first: str | None = None,
) -> B | None:
    """The build the entry names as its default, else the first build whose
    quantization the order names, else None.

    `first` is a model's own measured default, where the order's convention is
    worse for it: Spark-X2.6-4B at `Q8_0` passed every agent case its `Q4_K_M`
    missed half of."""
    by_label = {build.quantization.upper(): build for build in builds}
    if first is not None and first.upper() in by_label:
        return by_label[first.upper()]
    return next((by_label[q] for q in preference if q in by_label), None)
