"""Which build of an image model a row downloads."""

import pytest

from modules.llm.catalog.local.engines.sdcpp.builds.choice import default_build
from modules.llm.catalog.local.engines.sdcpp.builds.in_repo import builds_in
from tests.unit.llm.catalog.local.engines.sdcpp.builds.test_in_repo import SD15_LISTING

pytestmark = pytest.mark.unit


def test_the_default_is_the_first_build_the_entry_pins() -> None:
    """The refresh writes builds in the entry's reviewed order, so a small video
    model can lead with Q8_0 while a large image model leads with Q4_0."""
    largest_first = sorted(builds_in(SD15_LISTING), key=lambda b: -b.footprint_bytes)

    assert default_build(largest_first) is largest_first[0]


def test_a_model_with_no_build_has_no_default() -> None:
    """Nothing unpinned is offered as the one to download."""
    assert default_build([]) is None
