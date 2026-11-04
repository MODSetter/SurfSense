"""The pack key SurfSense signs its job packs with is the one a shipped app trusts."""

import pytest

from modules.jobs.packs.signature import PACK_PUBLIC_KEYS_HEX

pytestmark = pytest.mark.unit


def test_the_production_pack_key_is_compiled_in() -> None:
    """The key the maintainer holds, newest first, so a shipped app installs the packs it signs.
    Imported before the tests' own key replaces it while each test runs."""
    assert PACK_PUBLIC_KEYS_HEX[0] == (
        "1545536e7caeffd794d26d01cfc22e5ef01d07ddf10894dfe517c2d6afdb9230"
    )
