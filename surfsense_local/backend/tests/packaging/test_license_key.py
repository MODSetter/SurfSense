"""The shipped verifier must not accept files signed with the public test seed."""

from pathlib import Path

import pytest

from modules.license.verify import KEYGEN_PUBLIC_KEY_HEX

pytestmark = pytest.mark.packaging

FIXTURE_KEY = (
    Path(__file__).resolve().parents[4]
    / "plans/community-local/contracts/license-sample/public-key.hex"
)


def test_the_shipped_key_is_not_the_fixture_key() -> None:
    """Anyone with the repo could sign a license otherwise; blocks a release build."""
    assert FIXTURE_KEY.read_text().strip() != KEYGEN_PUBLIC_KEY_HEX
