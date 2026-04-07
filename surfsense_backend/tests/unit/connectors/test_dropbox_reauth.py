"""Test that Dropbox re-auth preserves folder_cursors in connector config."""

import pytest

pytestmark = pytest.mark.unit


def test_reauth_preserves_folder_cursors():
    """G1: re-authentication preserves folder_cursors alongside cursor."""
    old_config = {
        "access_token": "old-token-enc",
        "refresh_token": "old-refresh-enc",
        "cursor": "old-cursor-abc",
        "folder_cursors": {"/docs": "cursor-docs-123", "/photos": "cursor-photos-456"},
        "_token_encrypted": True,
        "auth_expired": True,
    }

    new_connector_config = {
        "access_token": "new-token-enc",
        "refresh_token": "new-refresh-enc",
        "token_type": "bearer",
        "expires_in": 14400,
        "expires_at": "2026-04-06T16:00:00+00:00",
        "_token_encrypted": True,
    }

    existing_cursor = old_config.get("cursor")
    existing_folder_cursors = old_config.get("folder_cursors")
    merged_config = {
        **new_connector_config,
        "cursor": existing_cursor,
        "folder_cursors": existing_folder_cursors,
        "auth_expired": False,
    }

    assert merged_config["access_token"] == "new-token-enc"
    assert merged_config["cursor"] == "old-cursor-abc"
    assert merged_config["folder_cursors"] == {
        "/docs": "cursor-docs-123",
        "/photos": "cursor-photos-456",
    }
    assert merged_config["auth_expired"] is False
