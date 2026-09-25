"""The licence rule: a curated model allows commercial use with no revenue cap,
registration, membership or excluded territory.
"""

from collections.abc import Iterable
from typing import Protocol

# Hugging Face licence tags a person has read and found to pass. An OpenRAIL or
# Gemma licence's use restrictions pass on to the user; they do not limit
# commercial use. A custom licence joins only with its clause cited in review.
COMMERCIAL = frozenset(
    {
        "apache-2.0",
        "mit",
        "gemma",
        "openrail",
        "openrail++",
        "creativeml-openrail-m",
    }
)


class Licensed(Protocol):
    id: str
    license: str


def refused(models: Iterable[Licensed]) -> list[str]:
    """Why each model fails the rule. Empty means every one passes."""
    return [
        f"{m.id}: {m.license} does not allow commercial use without a cap"
        for m in models
        if m.license not in COMMERCIAL
    ]
