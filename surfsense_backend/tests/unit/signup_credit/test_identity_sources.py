"""One person is one identity, whatever spelling their login rows carry."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import config
from app.signup_credit.identity.registry import identities_of

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _pepper(monkeypatch):
    """Fingerprinting refuses to run unkeyed; the value itself is irrelevant."""
    monkeypatch.setattr(config, "SECRET_KEY", "test-pepper")


def google_user(*account_ids: str) -> SimpleNamespace:
    return SimpleNamespace(
        oauth_accounts=[
            SimpleNamespace(oauth_name="google", account_id=account_id)
            for account_id in account_ids
        ]
    )


def test_a_legacy_prefixed_google_row_is_the_same_identity_as_the_bare_one():
    """Rows predating the `sub` switch read `people/<sub>`; same person either way."""
    legacy = google_user("people/108231")
    canonical = google_user("108231")

    assert identities_of(legacy) == identities_of(canonical)
