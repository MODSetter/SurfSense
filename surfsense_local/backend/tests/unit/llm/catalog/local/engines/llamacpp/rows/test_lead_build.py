"""Which build a row leads with, and why: decided once, on the server."""

from dataclasses import dataclass

import pytest

from modules.llm.catalog.local.engines.llamacpp.rows.lead_build import lead_build
from modules.llm.catalog.local.rows import LeadReason
from modules.llm.fit import FitState

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class Fit:
    state: FitState

    @property
    def can_install(self) -> bool:
        return self.state is not FitState.TOO_BIG


@dataclass(frozen=True)
class B:
    quantization: str
    footprint: int
    state: FitState = FitState.FITS
    installed_as: str | None = None
    recommended: bool = False

    @property
    def fit(self) -> Fit:
        return Fit(self.state)

    @property
    def build(self):
        return self

    @property
    def footprint_bytes(self) -> int:
        return self.footprint


TOO_BIG = FitState.TOO_BIG
PARTIAL = FitState.PARTIAL


def test_the_build_in_use_leads() -> None:
    """In use leads, whatever else is true."""
    builds = [B("Q4_K_M", 4, installed_as="m-q4"), B("UD-Q4_K_XL", 5, recommended=True)]

    lead = lead_build(builds, "UD-Q4_K_XL", selected="m-q4")

    assert (lead.quantization, lead.why) == ("Q4_K_M", LeadReason.IN_USE)


def test_an_installed_build_leads_over_a_recommendation() -> None:
    """What is on disk is what Use acts on."""
    builds = [B("Q4_K_M", 4, installed_as="m-q4"), B("UD-Q4_K_XL", 5, recommended=True)]

    lead = lead_build(builds, "UD-Q4_K_XL", selected=None)

    assert (lead.quantization, lead.why) == ("Q4_K_M", LeadReason.INSTALLED)


def test_the_recommended_build_leads_when_nothing_is_on_disk() -> None:
    """Step two's pick is what Download fetches."""
    builds = [B("Q4_K_M", 4), B("UD-Q4_K_XL", 5, recommended=True)]

    lead = lead_build(builds, "UD-Q4_K_XL", selected=None)

    assert (lead.quantization, lead.why) == ("UD-Q4_K_XL", LeadReason.RECOMMENDED)


def test_without_a_recommendation_the_largest_build_that_installs_leads() -> None:
    """Never a disabled Download on a model a smaller build of which installs."""
    builds = [
        B("Q3_K_M", 3, PARTIAL),
        B("Q4_K_S", 4, PARTIAL),
        B("Q4_K_M", 5, TOO_BIG),
        B("UD-Q4_K_XL", 6, TOO_BIG),
    ]

    lead = lead_build(builds, "UD-Q4_K_XL", selected=None)

    assert (lead.quantization, lead.why) == ("Q4_K_S", LeadReason.FITS_SLOWER)


def test_a_three_bit_build_does_not_lead_even_if_it_installs() -> None:
    """The same four bit floor the recommendation keeps."""
    builds = [B("Q3_K_M", 3, PARTIAL), B("UD-Q4_K_XL", 6, TOO_BIG)]

    lead = lead_build(builds, "UD-Q4_K_XL", selected=None)

    assert (lead.quantization, lead.why) == ("UD-Q4_K_XL", LeadReason.NOTHING_FITS)


def test_when_nothing_installs_the_default_leads_to_say_so() -> None:
    """It names the model's size and that it will not fit."""
    builds = [B("Q4_K_M", 5, TOO_BIG), B("UD-Q4_K_XL", 6, TOO_BIG)]

    lead = lead_build(builds, "UD-Q4_K_XL", selected=None)

    assert (lead.quantization, lead.why) == ("UD-Q4_K_XL", LeadReason.NOTHING_FITS)


def test_no_builds_means_no_lead() -> None:
    """A row with nothing to offer leads with nothing."""
    assert lead_build([], None, selected=None) is None
