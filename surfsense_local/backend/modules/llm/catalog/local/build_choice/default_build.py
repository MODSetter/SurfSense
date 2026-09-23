"""The build a model should run as, before anything is known about the machine."""

from collections.abc import Sequence
from typing import Protocol

from modules.llm.catalog.local.build_choice.preference import PREFERENCE


class Labelled(Protocol):
    @property
    def quantization(self) -> str: ...


def default_build[B: Labelled](
    builds: Sequence[B], preference: Sequence[str] = PREFERENCE
) -> B | None:
    """The first build whose quantization the order names, or None."""
    by_label = {build.quantization.upper(): build for build in builds}
    return next((by_label[q] for q in preference if q in by_label), None)
