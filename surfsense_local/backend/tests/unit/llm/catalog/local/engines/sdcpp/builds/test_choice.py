"""Which build of an image model the manifest pins and a row downloads."""

import pytest

from modules.llm.catalog.local.engines.sdcpp.builds.choice import default_build
from modules.llm.catalog.local.engines.sdcpp.builds.in_repo import builds_in
from tests.unit.llm.catalog.local.engines.sdcpp.builds.test_in_repo import SD15_LISTING

pytestmark = pytest.mark.unit


def test_the_default_is_q4_0_even_where_a_larger_or_smaller_file_exists() -> None:
    """Q4_0 is the build sd.cpp was measured on here; with no fit estimate for
    image models, nothing picks a different one for a machine."""
    build = default_build(builds_in(SD15_LISTING))

    assert build is not None and build.quantization == "Q4_0"


def test_a_repo_without_a_build_in_the_order_has_no_default() -> None:
    """Nothing unmeasured is offered as the one to download."""
    only_bf16 = [f for f in SD15_LISTING if "bf16" in f.path]

    assert default_build(builds_in(only_bf16)) is None
