"""Tests for connector pointer field selection."""

from __future__ import annotations

import pytest

from app.agents.chat.runtime.references.connectors import connector_pointer_fields

pytestmark = pytest.mark.unit


def test_prefers_chip_account_and_type() -> None:
    label, provider = connector_pointer_fields(
        account_name="work@acme.com",
        connector_type="Gmail",
        fallback_name="My Gmail",
    )

    assert (label, provider) == ("work@acme.com", "Gmail")


def test_falls_back_to_stored_name_when_account_missing() -> None:
    label, provider = connector_pointer_fields(
        account_name=None,
        connector_type="Slack",
        fallback_name="Acme Slack",
    )

    assert label == "Acme Slack"
    assert provider == "Slack"


def test_provider_is_none_when_unknown() -> None:
    label, provider = connector_pointer_fields(
        account_name="a@b.com",
        connector_type=None,
        fallback_name=None,
    )

    assert label == "a@b.com"
    assert provider is None
