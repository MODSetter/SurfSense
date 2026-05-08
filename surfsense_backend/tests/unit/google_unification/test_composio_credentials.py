"""Unit tests: Composio credential helpers + ``get_access_token`` masking guard.

Covers two seams between Surfsense and Composio:

1. ``build_composio_credentials`` returns a ``google.oauth2.credentials.Credentials``
   object with a working refresh handler (mocks the whole ``ComposioService``).
2. ``ComposioService.get_access_token`` rejects masked / missing tokens with
   actionable error messages (mocks only the Composio SDK boundary so the
   real guard logic is exercised).

The masking guard is the boundary handler that production tripped over when
Composio's "Mask Connected Account Secrets" project setting was enabled.
The corresponding fix landed in ``cea8618``; these tests lock that contract
in place so any future weakening of the guard surfaces immediately.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# build_composio_credentials — high-level wrapper tests
# ---------------------------------------------------------------------------


@patch("app.services.composio_service.ComposioService")
def test_returns_credentials_with_token_and_expiry(mock_composio_service):
    """build_composio_credentials returns a Credentials object with the Composio access token."""
    mock_service = MagicMock()
    mock_service.get_access_token.return_value = "fake-access-token"
    mock_composio_service.return_value = mock_service

    from app.utils.google_credentials import build_composio_credentials

    creds = build_composio_credentials("test-account-id")

    assert isinstance(creds, Credentials)
    assert creds.token == "fake-access-token"
    assert creds.expiry is not None
    assert creds.expiry > datetime.now(UTC).replace(tzinfo=None)


@patch("app.services.composio_service.ComposioService")
def test_refresh_handler_fetches_fresh_token(mock_composio_service):
    """The refresh_handler on the returned Credentials fetches a new token from Composio."""
    mock_service = MagicMock()
    mock_service.get_access_token.side_effect = [
        "initial-token",
        "refreshed-token",
    ]
    mock_composio_service.return_value = mock_service

    from app.utils.google_credentials import build_composio_credentials

    creds = build_composio_credentials("test-account-id")
    assert creds.token == "initial-token"

    refresh_handler = creds._refresh_handler
    assert callable(refresh_handler)

    new_token, new_expiry = refresh_handler(request=None, scopes=None)

    assert new_token == "refreshed-token"
    assert new_expiry > datetime.now(UTC).replace(tzinfo=None)
    assert mock_service.get_access_token.call_count == 2


# ---------------------------------------------------------------------------
# ComposioService.get_access_token — boundary masking guard tests
# ---------------------------------------------------------------------------


def _service_with_account(account: object):
    """Build a real ``ComposioService`` whose underlying Composio SDK is faked.

    Only the SDK boundary is patched — the real ``get_access_token`` method
    runs, so changes to the masking / missing-token guards surface here.
    """
    from app.services import composio_service as composio_service_module

    with patch.object(composio_service_module, "Composio") as mock_composio_cls:
        mock_client = MagicMock()
        mock_client.connected_accounts.get.return_value = account
        mock_composio_cls.return_value = mock_client

        service = composio_service_module.ComposioService(api_key="unit-test-api-key")

    # ``service.client`` already references ``mock_client`` even after the
    # patch context exits because the constructor captured it during init.
    return service


@pytest.mark.parametrize("masked_token", ["x", "xxxxxxxx", "x" * 19])
def test_get_access_token_raises_on_masked_token(masked_token):
    """Tokens shorter than the 20-char unmask threshold must raise with the dashboard hint.

    Composio masks ``state.val.access_token`` by default (project setting
    "Mask Connected Account Secrets"). A masked token will always silently
    fail downstream OAuth calls, so the guard surfaces it with the exact
    text needed to fix the dashboard config.
    """
    fake_account = MagicMock()
    fake_account.state.val.access_token = masked_token
    service = _service_with_account(fake_account)

    with pytest.raises(ValueError, match="Mask Connected Account Secrets"):
        service.get_access_token("any-account-id")


def test_get_access_token_raises_when_state_val_missing():
    """No ``state.val`` on the connected account is a hard failure with an account-id hint."""
    fake_account = MagicMock()
    fake_account.state = None
    service = _service_with_account(fake_account)

    with pytest.raises(ValueError, match=r"No state\.val.*missing-state-account"):
        service.get_access_token("missing-state-account")


def test_get_access_token_raises_when_access_token_empty():
    """``state.val`` present but ``access_token`` empty must fail before the masking check."""
    fake_account = MagicMock()
    fake_account.state.val.access_token = ""
    service = _service_with_account(fake_account)

    with pytest.raises(ValueError, match=r"No access_token.*missing-token-account"):
        service.get_access_token("missing-token-account")


def test_get_access_token_raises_when_access_token_none():
    """``state.val.access_token = None`` must fail before the masking check."""
    fake_account = MagicMock()
    fake_account.state.val.access_token = None
    service = _service_with_account(fake_account)

    with pytest.raises(ValueError, match=r"No access_token.*none-token-account"):
        service.get_access_token("none-token-account")


def test_get_access_token_returns_unmasked_token():
    """Happy path: a >=20-char access token is returned verbatim."""
    fake_account = MagicMock()
    unmasked = "u" * 32
    fake_account.state.val.access_token = unmasked
    service = _service_with_account(fake_account)

    assert service.get_access_token("happy-account") == unmasked
