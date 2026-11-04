"""The pack key SurfSense signs its job packs with is the one a shipped app trusts."""

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from modules.jobs.packs.signature import PACK_PUBLIC_KEYS_HEX, signed_payload
from tests.job_pack_samples import TEST_PACK_PUBLIC_KEY_HEX

pytestmark = pytest.mark.unit


def test_the_production_pack_key_is_compiled_in() -> None:
    """The key the maintainer holds, newest first, so a shipped app installs the packs it signs.
    Imported as shipped, before the tests' own key joins it while each test runs."""
    assert PACK_PUBLIC_KEYS_HEX[0] == (
        "1545536e7caeffd794d26d01cfc22e5ef01d07ddf10894dfe517c2d6afdb9230"
    )


def test_the_shipped_keys_exclude_the_test_key() -> None:
    """The test key's private half is in this repository: an app that trusted it would install
    any pack anyone signed with it."""
    assert TEST_PACK_PUBLIC_KEY_HEX not in PACK_PUBLIC_KEYS_HEX


def test_every_shipped_key_is_an_ed25519_public_key() -> None:
    """A key that does not load is skipped when a pack is checked, so it would trust no pack."""
    for key_hex in PACK_PUBLIC_KEYS_HEX:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex))


def test_the_signed_form_is_pinned() -> None:
    """The bytes signed are the one contract with the signing script outside this repository:
    a change here refuses every pack it signed."""
    assert signed_payload({"b": 1, "a": "é", "files": {"z": "0", "y": "1"}}) == (
        'surfsense-job-pack/1\n{"a":"é","b":1,"files":{"y":"1","z":"0"}}'.encode()
    )
