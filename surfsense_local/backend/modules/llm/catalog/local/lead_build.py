"""Which build a row leads with, and why.

Decided on the server so the screen computes nothing, and so "why is this the
build I see" always has an answer in the data. The row's Download fetches the
lead: step two's pick when there is one, else the largest four bit or better
build that installs, and only when nothing installs the default, to say how big
the model is and that it will not fit.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from modules.llm.catalog.local.build_choice.preference import RECOMMENDABLE


class LeadReason(StrEnum):
    IN_USE = "in_use"
    INSTALLED = "installed"
    RECOMMENDED = "recommended"
    FITS_SLOWER = "fits_slower"
    NOTHING_FITS = "nothing_fits"


@dataclass(frozen=True)
class Lead:
    quantization: str
    why: LeadReason


class _Fit(Protocol):
    @property
    def can_install(self) -> bool: ...


class _Build(Protocol):
    @property
    def quantization(self) -> str: ...

    @property
    def footprint_bytes(self) -> int: ...


class _Row(Protocol):
    @property
    def build(self) -> _Build: ...

    @property
    def fit(self) -> _Fit: ...

    @property
    def installed_as(self) -> str | None: ...

    @property
    def recommended(self) -> bool: ...


def lead_build(
    builds: Sequence[_Row], default_quantization: str | None, *, selected: str | None
) -> Lead | None:
    if not builds:
        return None

    def lead(row: _Row, why: LeadReason) -> Lead:
        return Lead(row.build.quantization, why)

    for row in builds:
        if selected is not None and row.installed_as == selected:
            return lead(row, LeadReason.IN_USE)
    installed = [row for row in builds if row.installed_as]
    if installed:
        return lead(_largest(installed), LeadReason.INSTALLED)
    for row in builds:
        if row.recommended:
            return lead(row, LeadReason.RECOMMENDED)
    installable = [
        row
        for row in builds
        if row.fit.can_install and row.build.quantization.upper() in RECOMMENDABLE
    ]
    if installable:
        return lead(_largest(installable), LeadReason.FITS_SLOWER)
    default = next(
        (row for row in builds if row.build.quantization == default_quantization),
        builds[0],
    )
    return lead(default, LeadReason.NOTHING_FITS)


def _largest(rows: Sequence[_Row]) -> _Row:
    return max(rows, key=lambda row: row.build.footprint_bytes)
